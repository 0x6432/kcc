#include "codegen.h"
#include "parse.h"
#include "sema.h"

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
		assert(codegen_translation_unit(stream, unit));
	}
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
	return 0;
}
