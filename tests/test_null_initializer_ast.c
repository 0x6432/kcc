/* M15i2 canonical null tag, ownership, immutable source captures and rollback.
 * Build with compiler sources excluding main.c, like integer initializer AST.
 */
#include "parse.h"
#include "sema.h"
#include "consteval.h"
#include "type.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

struct fixture {
	struct source source;
	struct arena arena;
	FILE *stream;
	struct diagnostics diagnostics;
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
};

static void open_fixture(struct fixture *f, const char *text)
{
	memset(f, 0, sizeof *f);
	f->stream = tmpfile();
	assert(f->stream);
	f->diagnostics.stream = f->stream;
	assert(source_from_bytes(&f->source, "null-initializer-ast.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&f->source));
	preprocess_init(&f->preprocessor, &f->source, &f->diagnostics);
	f->unit = parse_translation_unit(&f->preprocessor, &f->arena, &f->diagnostics);
	assert(f->unit && f->diagnostics.errors == 0);
}

static void close_fixture(struct fixture *f)
{
	arena_destroy(&f->arena);
	preprocess_destroy(&f->preprocessor);
	source_destroy(&f->source);
	assert(fclose(f->stream) == 0);
}

static struct ast_external_declaration *declaration(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = f->unit->declarations;

	while (index--) {
		assert(d);
		d = d->next;
	}
	assert(d);
	return d;
}

static struct ast_external_object_declaration *object(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = declaration(f, index);

	assert(d->kind == external_object_declaration);
	return (struct ast_external_object_declaration *)d;
}

static struct ast_external_type_declaration *queried(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = declaration(f, index);

	assert(d->kind == external_type_declaration);
	return (struct ast_external_type_declaration *)d;
}

static uint64_t referent_count(const struct type *type)
{
	const struct type *referent;

	assert(type && type->kind == type_kind_pointer);
	referent = ((const struct pointer_type *)type)->referent;
	assert(referent->kind == type_kind_array);
	return ((const struct array_type *)referent)->count;
}

static void assert_null(struct external_object_symbol *symbol,
	struct ast_external_declaration *definition)
{
	assert(symbol && symbol->definition == definition);
	assert(symbol->initializer_value.kind == static_data_null_pointer);
	assert(symbol->type->kind == type_kind_pointer);
	assert(type_object_size(symbol->type) == 8);
	assert(type_object_alignment(symbol->type) == 8);
}

static void check_ownership(void)
{
	struct fixture f;
	struct ast_external_object_declaration *first, *definition, *last, *absent, *integer;

	open_fixture(&f, "static int *cell; extern int *cell=sizeof cell-8;"
		"static int *cell; extern int *absent; int integer=0;");
	first = object(&f, 0);
	definition = object(&f, 1);
	last = object(&f, 2);
	absent = object(&f, 3);
	assert(!first->initializer && definition->initializer && !last->initializer);
	assert(!first->symbol && !definition->symbol && !last->symbol);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	assert(first->symbol == definition->symbol && first->symbol == last->symbol);
	assert_null(first->symbol, &definition->external);
	assert(first->symbol->is_internal && definition->is_extern);
	assert(first->symbol->tentative_definition == &first->external);
	assert(absent->symbol && absent->symbol->definition == NULL);
	assert(absent->symbol->tentative_definition == NULL);
	integer = object(&f, 4);
	assert(integer->symbol->definition == &integer->external);
	assert(integer->symbol->initializer_value.kind == static_data_integer);
	assert(integer->symbol->initializer_value.integer_bits == 0);
	/* An explicit integer zero and an explicit null are distinct canonical tags. */
	assert(integer->symbol->initializer_value.kind != first->symbol->initializer_value.kind);
	close_fixture(&f);

	open_fixture(&f, "int *cell=0; int *cell; extern int *cell;");
	definition = object(&f, 0);
	first = object(&f, 1);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	assert_null(definition->symbol, &definition->external);
	assert(first->symbol == definition->symbol);
	assert(first->symbol->tentative_definition == &first->external);
	close_fixture(&f);
}

static void check_captures(void)
{
	struct fixture f;
	struct ast_external_object_declaration *first, *later;
	struct ast_external_type_declaration *alias;
	const struct type *initializer_type;
	struct external_object_symbol saved;
	struct null_initializer_result result;

	open_fixture(&f, "int (*cell)[]=0; extern int (*cell)[3];"
		"typedef int (*P)[]; static P other=nullptr; extern int (*other)[4];");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	first = object(&f, 0);
	later = object(&f, 1);
	assert(first->symbol == later->symbol);
	assert_null(first->symbol, &first->external);
	assert(referent_count(first->type) == 0);
	assert(referent_count(first->initializer->type) == 0);
	assert(referent_count(later->type) == 3);
	assert(referent_count(first->symbol->type) == 3);
	assert(first->type != first->symbol->type);
	alias = queried(&f, 3);
	assert_null(alias->object_symbol, &alias->external);
	assert(alias->object_symbol == object(&f, 4)->symbol);
	assert(alias->object_symbol->is_internal && !alias->symbol);
	assert(referent_count(alias->type) == 0);
	assert(referent_count(alias->initializer->type) == 0);
	assert(referent_count(alias->object_symbol->type) == 4);
	/* The pure query must not publish/change data or retarget a captured AST. */
	memcpy(&saved, first->symbol, sizeof saved);
	initializer_type = first->initializer->type;
	result = evaluate_null_initializer(first->initializer);
	assert(result.status == constant_value && result.message == NULL);
	result = evaluate_null_initializer(first->initializer);
	assert(result.status == constant_value);
	assert(memcmp(&saved, first->symbol, sizeof saved) == 0);
	assert(first->initializer->type == initializer_type);
	close_fixture(&f);
}

static void check_alias_and_const(void)
{
	struct fixture f;
	struct ast_external_type_declaration *definition;
	struct ast_external_object_declaration *direct;

	open_fixture(&f, "typedef int *const P; static P cell=(typeof(nullptr))0;"
		"static typeof(cell) cell; const int *const qualified=nullptr;"
		"int (*function)(void)=(void *)0; int (*incomplete)[]=0;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	definition = queried(&f, 1);
	assert_null(definition->object_symbol, &definition->external);
	assert(definition->type->qualifiers == type_qualifier_const);
	assert(definition->initializer->type->qualifiers == 0);
	assert(queried(&f, 2)->object_symbol == definition->object_symbol);
	assert(definition->object_symbol->tentative_definition == &queried(&f, 2)->external);
	direct = object(&f, 3);
	assert_null(direct->symbol, &direct->external);
	assert(direct->type->qualifiers == type_qualifier_const);
	assert(((const struct pointer_type *)direct->type)->referent->qualifiers == type_qualifier_const);
	direct = object(&f, 4);
	assert_null(direct->symbol, &direct->external);
	assert(((const struct pointer_type *)direct->type)->referent->kind == type_kind_function);
	direct = object(&f, 5);
	assert_null(direct->symbol, &direct->external);
	assert(referent_count(direct->type) == 0);
	close_fixture(&f);
}

static void check_failed_existing(const char *text, bool defined, bool tentative,
	bool internal, bool unknown_array)
{
	struct fixture f;
	struct ast_external_object_declaration *first, *failed;

	open_fixture(&f, text);
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	first = object(&f, 0);
	failed = object(&f, 1);
	assert(first->symbol && failed->initializer);
	assert(failed->symbol == NULL && failed->type == NULL);
	assert(first->symbol->definition == (defined ? &first->external : NULL));
	assert(first->symbol->tentative_definition == (tentative ? &first->external : NULL));
	assert(first->symbol->type == first->type);
	assert(first->symbol->is_internal == internal);
	assert(first->symbol->next == NULL);
	if (defined)
		assert(first->symbol->initializer_value.kind == static_data_null_pointer);
	if (unknown_array)
		assert(referent_count(first->symbol->type) == 0);
	close_fixture(&f);
}

static void check_failed_new(const char *text, bool query)
{
	struct fixture f;

	open_fixture(&f, text);
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	if (query) {
		struct ast_external_type_declaration *failed = queried(&f, 0);

		assert(failed->initializer && !failed->object_symbol && !failed->symbol && !failed->type);
	} else {
		struct ast_external_object_declaration *failed = object(&f, 0);

		assert(failed->initializer && !failed->symbol && !failed->type);
	}
	close_fixture(&f);
}

static void check_failed_pure_query(const char *text, enum constant_status status,
	const char *message)
{
	struct fixture f;
	struct ast_external_object_declaration *failed;
	struct null_initializer_result result;
	const struct type *captured;

	open_fixture(&f, text);
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	failed = object(&f, 0);
	assert(!failed->symbol && !failed->type && failed->initializer->type);
	captured = failed->initializer->type;
	result = evaluate_null_initializer(failed->initializer);
	assert(result.status == status && result.message && strcmp(result.message, message) == 0);
	result = evaluate_null_initializer(failed->initializer);
	assert(result.status == status && failed->initializer->type == captured);
	assert(!failed->symbol && !failed->type && f.diagnostics.errors == 1);
	close_fixture(&f);
}

int main(void)
{
	check_failed_pure_query("int *cell=0*(1/0);", constant_invalid,
		"division by zero in integer constant expression");
	check_failed_pure_query("int *cell=(2147483647+1)*0;", constant_invalid,
		"signed overflow in integer constant expression");
	check_failed_pure_query("int *cell=1?(int *)0:(int *)0;", constant_not_constant,
		"file-scope pointer initializer requires a supported null constant expression");
	check_ownership();
	check_captures();
	check_alias_and_const();
	check_failed_existing("int *cell; int *cell=cell;", false, true, false, false);
	check_failed_existing("extern int *cell; int *cell=(int *)(0*(1/0));", false, false, false, false);
	check_failed_existing("static int *cell; extern int *cell=(const void *)0;", false, true, true, false);
	check_failed_existing("int *cell=0; int *cell=0;", true, false, false, false);
	check_failed_existing("static int *cell=0; extern int *cell=(int *)0;", true, false, true, false);
	check_failed_existing("int (*cell)[]; int (*cell)[3]=cell;", false, true, false, true);
	check_failed_existing("int *cell; long *cell=0;", false, true, false, false);
	check_failed_new("int *cell=cell;", false);
	check_failed_new("typeof((int *)0) cell=cell;", true);
	check_failed_new("int *cell=(int *)(0*(2147483647+1));", false);
	check_failed_new("typeof((int *)0) cell=(int *)0+0;", true);
	puts("Null initializer AST tags, ownership, captures, pure queries and rollback passed");
	return 0;
}
