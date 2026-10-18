/* M15 initialized external integer ownership, binding and failed-publication API.
 * Build against compiler sources (excluding main.c), exactly like static-array AST tests.
 */
#include "parse.h"
#include "sema.h"
#include "type.h"

#include <assert.h>
#include <stdint.h>
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
	assert(source_from_bytes(&f->source, "integer-initializer-ast.c",
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

static void check_anchor_and_self_binding(void)
{
	struct fixture f;
	struct ast_external_object_declaration *first, *definition, *last;

	open_fixture(&f, "int cell; extern int cell=sizeof cell+38; int cell;");
	first = object(&f, 0);
	definition = object(&f, 1);
	last = object(&f, 2);
	assert(!first->initializer && definition->initializer && !last->initializer);
	assert(!first->symbol && !definition->symbol && !last->symbol);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	assert(first->symbol == definition->symbol && first->symbol == last->symbol);
	assert(first->symbol->tentative_definition == &first->external);
	assert(first->symbol->definition == &definition->external);
	assert(first->symbol->initializer_value.kind == static_data_integer);
	assert(first->symbol->initializer_value.integer_bits == 42);
	assert(!first->symbol->is_internal && definition->is_extern);
	assert(type_is_integer(definition->initializer->type));
	assert(type_object_size(first->symbol->type) == 4);
	close_fixture(&f);
}

static void check_explicit_zero_and_private_linkage(void)
{
	struct fixture f;
	struct ast_external_object_declaration *zero, *pure, *first, *definition;

	open_fixture(&f, "extern int zero=0; extern int zero;"
		"static unsigned char cell; extern unsigned char cell=257;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	zero = object(&f, 0);
	pure = object(&f, 1);
	first = object(&f, 2);
	definition = object(&f, 3);
	assert(zero->initializer && zero->symbol == pure->symbol);
	assert(zero->symbol->definition == &zero->external);
	assert(zero->symbol->tentative_definition == NULL);
	assert(zero->symbol->initializer_value.kind == static_data_integer);
	assert(zero->symbol->initializer_value.integer_bits == 0);
	assert(first->symbol == definition->symbol && first->symbol->is_internal);
	assert(first->symbol->tentative_definition == &first->external);
	assert(first->symbol->definition == &definition->external);
	assert(first->symbol->initializer_value.kind == static_data_integer);
	assert(first->symbol->initializer_value.integer_bits == 1);
	assert(type_object_size(first->symbol->type) == 1);
	close_fixture(&f);
}

static void check_alias_query_anchors(void)
{
	struct fixture f;
	struct ast_external_type_declaration *first, *definition, *last, *truth;

	open_fixture(&f, "typedef const long T; static T cell;"
		"extern T cell=sizeof cell+34; static typeof(cell) cell;"
		"typeof(_Bool) truth=1ULL<<63;");
	first = queried(&f, 1);
	definition = queried(&f, 2);
	last = queried(&f, 3);
	truth = queried(&f, 4);
	assert(!first->initializer && definition->initializer && truth->initializer);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	assert(!first->symbol && !definition->symbol && !last->symbol);
	assert(first->object_symbol == definition->object_symbol);
	assert(last->object_symbol == first->object_symbol);
	assert(first->object_symbol->is_internal);
	assert(first->object_symbol->tentative_definition == &first->external);
	assert(first->object_symbol->definition == &definition->external);
	assert(first->object_symbol->initializer_value.kind == static_data_integer);
	assert(first->object_symbol->initializer_value.integer_bits == 42);
	assert(type_object_size(first->object_symbol->type) == 8);
	assert(truth->object_symbol->definition == &truth->external);
	assert(truth->object_symbol->tentative_definition == NULL);
	assert(truth->object_symbol->initializer_value.kind == static_data_integer);
	assert(truth->object_symbol->initializer_value.integer_bits == 1);
	assert(type_object_size(truth->object_symbol->type) == 1);
	close_fixture(&f);
}

static void check_target_bits(void)
{
	struct fixture f;
	const uint64_t bits[] = { UINT64_C(255), UINT64_C(65535), UINT64_C(4294967295), UINT64_MAX };
	unsigned i;

	open_fixture(&f, "signed char a=-1; short b=-1; int c=-1; long long d=-1;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	for (i = 0; i < sizeof bits / sizeof bits[0]; ++i) {
		struct ast_external_object_declaration *d = object(&f, i);

		assert(d->symbol->definition == &d->external);
		assert(d->symbol->tentative_definition == NULL);
		assert(d->symbol->initializer_value.kind == static_data_integer);
		assert(d->symbol->initializer_value.integer_bits == bits[i]);
	}
	close_fixture(&f);
}

static void check_failed_publication(const char *text, bool had_definition, bool had_tentative)
{
	struct fixture f;
	struct ast_external_object_declaration *first, *failed;

	open_fixture(&f, text);
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	first = object(&f, 0);
	failed = object(&f, 1);
	assert(first->symbol);
	assert(failed->initializer && failed->symbol == NULL && failed->type == NULL);
	assert(first->symbol->definition == (had_definition ? &first->external : NULL));
	assert(first->symbol->tentative_definition == (had_tentative ? &first->external : NULL));
	assert(first->symbol->initializer_value.kind == static_data_integer);
	assert(first->symbol->initializer_value.integer_bits == (had_definition ? 42 : 0));
	assert(first->symbol->type == first->type);
	assert(!first->symbol->is_internal);
	close_fixture(&f);
}

static void check_new_failure(const char *text, bool query)
{
	struct fixture f;

	open_fixture(&f, text);
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	if (query) {
		struct ast_external_type_declaration *failed = queried(&f, 0);

		assert(failed->initializer && failed->object_symbol == NULL && failed->symbol == NULL);
		assert(failed->type == NULL);
	} else {
		struct ast_external_object_declaration *failed = object(&f, 0);

		assert(failed->initializer && failed->symbol == NULL && failed->type == NULL);
	}
	close_fixture(&f);
}

int main(void)
{
	check_anchor_and_self_binding();
	check_explicit_zero_and_private_linkage();
	check_alias_query_anchors();
	check_target_bits();
	check_failed_publication("int cell; int cell=2147483647+1;", false, true);
	check_failed_publication("extern int cell; int cell=1/0;", false, false);
	check_failed_publication("int cell=42; int cell=9;", true, false);
	check_failed_publication("int cell; const int cell=42;", false, true);
	check_new_failure("_Bool cell=2147483647+1;", false);
	check_new_failure("typeof(_Bool) cell=2147483647+1;", true);
	check_new_failure("int cell=cell;", false);
	check_new_failure("typeof(int) cell=cell;", true);
	puts("Integer initializer AST ownership, target bits, self binding and failed publication passed");
	return 0;
}
