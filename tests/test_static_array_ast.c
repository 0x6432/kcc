#include "parse.h"
#include "sema.h"
#include "type.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint64_t array_count(const struct type *type)
{
	assert(type && type->kind == type_kind_array);
	return ((const struct array_type *)type)->count;
}

static void check_captures(void)
{
	const char *text =
		"typedef int Unknown[];"
		"static int items[3];"
		"extern int items[];"
		"static Unknown items;"
		"static int (*pointer)[];"
		"static int rows[2][3];"
		"static typeof(rows) copy;"
		"int inspect(void) { return sizeof(items)+sizeof(pointer); }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_external_typedef_declaration *alias;
	struct ast_external_object_declaration *first, *later, *pointer, *rows;
	struct ast_external_type_declaration *queried, *copy;
	struct ast_function *function;
	const struct type *referent;

	assert(stream);
	assert(source_from_bytes(&source, "static-arrays.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);

	alias = (struct ast_external_typedef_declaration *)unit->declarations;
	assert(alias->external.kind == external_typedef_declaration);
	first = (struct ast_external_object_declaration *)alias->external.next;
	later = (struct ast_external_object_declaration *)first->external.next;
	queried = (struct ast_external_type_declaration *)later->external.next;
	pointer = (struct ast_external_object_declaration *)queried->external.next;
	rows = (struct ast_external_object_declaration *)pointer->external.next;
	copy = (struct ast_external_type_declaration *)rows->external.next;
	function = (struct ast_function *)copy->external.next;
	assert(first->external.kind == external_object_declaration && first->is_static);
	assert(later->external.kind == external_object_declaration && later->is_extern);
	assert(queried->external.kind == external_type_declaration && queried->is_static);
	assert(first->symbol == later->symbol && first->symbol == queried->object_symbol);
	assert(first->symbol->is_internal);
	assert(first->symbol->tentative_definition == &first->external);
	assert(array_count(first->symbol->type) == 3);
	assert(array_count(first->type) == 3);
	assert(array_count(later->type) == 0);
	assert(array_count(alias->declaration->type) == 0);
	assert(queried->type == alias->declaration->type);
	assert(array_count(queried->type) == 0);
	assert(first->symbol->type != queried->type);
	assert(type_object_size(first->symbol->type) == 12);
	assert(type_object_alignment(first->symbol->type) == 4);

	assert(pointer->is_static && pointer->symbol->is_internal);
	assert(pointer->symbol->tentative_definition == &pointer->external);
	assert(pointer->type->kind == type_kind_pointer);
	referent = ((const struct pointer_type *)pointer->type)->referent;
	assert(array_count(referent) == 0); /* No recursive pointee completion. */
	assert(rows->is_static && rows->symbol->is_internal);
	assert(array_count(rows->type) == 2);
	assert(array_count(((const struct array_type *)rows->type)->element) == 3);
	assert(type_object_size(rows->type) == 24);
	assert(copy->object_symbol != rows->symbol && copy->object_symbol->is_internal);
	assert(copy->object_symbol->tentative_definition == &copy->external);
	assert(copy->type == rows->type);
	assert(copy->object_symbol->type == rows->type);
	assert(function->external.kind == external_function_definition);
	assert(function->locals == NULL && function->external.next == NULL);

	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void check_rejection(const char *text, bool first_valid)
{
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_external_object_declaration *first;

	assert(stream);
	assert(source_from_bytes(&source, "static-array-reject.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	assert(!sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 1);
	first = (struct ast_external_object_declaration *)unit->declarations;
	assert(first->external.kind == external_object_declaration);
	if (first_valid) {
		struct ast_external_object_declaration *second =
			(struct ast_external_object_declaration *)first->external.next;

		assert(first->symbol && first->symbol->is_internal);
		assert(first->symbol->tentative_definition == &first->external);
		assert(array_count(first->symbol->type) == 3);
		assert(second->symbol == NULL); /* Failed registration publishes nothing. */
	} else {
		assert(first->symbol == NULL);
		assert(array_count(first->type_syntax->type) == 0);
	}
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static uint64_t pointer_array_count(const struct type *type)
{
	assert(type && type->kind == type_kind_pointer);
	return array_count(((const struct pointer_type *)type)->referent);
}

static void check_expression_captures(void)
{
	const char *text =
		"static int (*views[2])[];"
		"typeof(views[0]) early(void) { return views[0]; }"
		"extern int (*views[2])[3];"
		"typeof(views[0]) late(void) { return views[0]; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_external_object_declaration *first, *later;
	struct ast_function *early, *late;
	struct ast_return_statement *early_return, *late_return;
	struct ast_statement_item *item;
	const struct array_type *canonical;

	assert(stream);
	assert(source_from_bytes(&source, "static-array-captures.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	first = (struct ast_external_object_declaration *)unit->declarations;
	early = (struct ast_function *)first->external.next;
	later = (struct ast_external_object_declaration *)early->external.next;
	late = (struct ast_function *)later->external.next;
	assert(first->external.kind == external_object_declaration);
	assert(early->external.kind == external_function_definition);
	assert(later->external.kind == external_object_declaration);
	assert(late->external.kind == external_function_definition);
	assert(first->symbol == later->symbol && first->symbol->is_internal);
	assert(first->symbol->tentative_definition == &first->external);
	canonical = (const struct array_type *)first->symbol->type;
	assert(array_count(&canonical->type) == 2);
	assert(pointer_array_count(canonical->element) == 3);
	assert(pointer_array_count(((const struct array_type *)first->type)->element) == 0);
	assert(pointer_array_count(early->return_type) == 0);
	assert(pointer_array_count(late->return_type) == 3);
	item = (struct ast_statement_item *)early->body->items;
	assert(item->item.kind == block_item_statement && item->statement->kind == statement_return);
	early_return = (struct ast_return_statement *)item->statement;
	item = (struct ast_statement_item *)late->body->items;
	assert(item->item.kind == block_item_statement && item->statement->kind == statement_return);
	late_return = (struct ast_return_statement *)item->statement;
	assert(early_return->value->kind == expression_load);
	assert(late_return->value->kind == expression_load);
	assert(pointer_array_count(early_return->value->type) == 0);
	assert(pointer_array_count(late_return->value->type) == 3);
	assert(early->locals == NULL && late->locals == NULL);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

int main(void)
{
	check_captures();
	check_expression_captures();
	check_rejection("static int items[]; static int items[3];", false);
	check_rejection("static int items[3]; static int items[4];", true);
	check_rejection("static int items[3]; int items[3];", true);
	puts("Static-array AST captures, source-point constraints and no-mutation failures passed");
	return 0;
}