#include "codegen.h"
#include "parse.h"
#include "sema.h"
#include "type.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

struct fuzz_include_context {
	const unsigned char *data;
	size_t length;
};

/* All fuzz header loading is memory-only, regardless of the requested path. */
static bool load_fuzz_include(void *context, struct source *source, const char *path)
{
	struct fuzz_include_context *input = context;

	if (strstr(path, "missing") && strncmp(path, "fallback/", 9) != 0)
		return false;
	return source_from_bytes(source, path, input->data, input->length);
}

/* Static literal objects are separate from scalar value loads and local slots. */
static void check_string_objects(const struct ast_translation_unit *unit)
{
	size_t count = 0;
	size_t bytes = 0;

	for (const struct ast_string_expression *string = unit->strings; string;
		string = string->next_string) {
		const struct array_type *array;

		assert(count < ast_max_string_literals && string->object_id == count);
		assert(string->expression.kind == expression_string && string->expression.is_lvalue);
		assert(string->expression.depth == 1 && string->expression.type->kind == type_kind_array);
		assert(string->length <= ast_max_string_length && string->bytes[string->length] == 0);
		array = (const struct array_type *)string->expression.type;
		assert(array->element == &type_char && array->count == string->length + 1);
		assert(type_object_alignment(&array->type) == 1);
		assert(type_object_size(&array->type) == string->length + 1);
		assert(string->length < ast_max_string_storage - bytes);
		bytes += string->length + 1;
		count++;
	}
}

/* Fuzz compiler stages, never execute generated programs. */
int LLVMFuzzerTestOneInput(const unsigned char *data, size_t size)
{
	struct source source;
	struct arena arena = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	FILE *stream;
	struct diagnostics diagnostics;
	struct fuzz_include_context includes;
	const char *directories[] = { "missing", "fallback" };

	if (size > 65536)
		return 0;
	stream = fopen("/dev/null", "w");
	assert(stream);
	diagnostics = (struct diagnostics) { .stream = stream };
	assert(source_from_bytes(&source, "fuzz.c", data, size));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	includes = (struct fuzz_include_context) { .data = data, .length = size };
	for (size_t i = 0; i < size; i++)
		if (data[i] == '\n') {
			includes.data = data + i + 1;
			includes.length = size - i - 1;
			break;
		}
	preprocess_set_include_loader(&preprocessor, load_fuzz_include, &includes);
	assert(preprocess_set_include_directories(&preprocessor, directories, 2));
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	if (unit && sema_translation_unit(unit, &arena, &diagnostics)) {
		assert(diagnostics.errors == 0);
		check_string_objects(unit);
		assert(codegen_translation_unit(stream, unit));
	}
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
	return 0;
}
