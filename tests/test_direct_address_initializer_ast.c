/* P1 direct address base identity, immutable captures and failed publication.
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
	assert(source_from_bytes(&f->source, "direct-address-ast.c",
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

static void assert_object_address(struct external_object_symbol *symbol,
	struct ast_external_declaration *definition, const struct external_object_symbol *base)
{
	assert(symbol && symbol->definition == definition);
	assert(symbol->initializer_value.kind == static_data_address);
	assert(symbol->initializer_value.address.kind == static_address_object);
	assert(symbol->initializer_value.address.base.object == base);
	assert(type_object_size(symbol->type) == 8 && type_object_alignment(symbol->type) == 8);
}

static void check_canonical_ownership(void)
{
	struct fixture f;
	struct ast_external_object_declaration *base, *first, *definition, *last;
	struct external_object_symbol saved;
	struct address_initializer_result result;

	open_fixture(&f, "extern int target; static int *cell; extern int *cell=&target;"
		"static int *cell; int target=42;");
	base = object(&f, 0);
	first = object(&f, 1);
	definition = object(&f, 2);
	last = object(&f, 3);
	assert(!first->initializer && definition->initializer && !last->initializer);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	assert(first->symbol == definition->symbol && first->symbol == last->symbol);
	assert(first->symbol->is_internal && definition->is_extern);
	assert(first->symbol->tentative_definition == &first->external);
	assert_object_address(first->symbol, &definition->external, base->symbol);
	assert(base->symbol == object(&f, 4)->symbol);
	assert(base->symbol->definition == &object(&f, 4)->external);
	assert(base->symbol->initializer_value.kind == static_data_integer);
	assert(base->symbol->initializer_value.integer_bits == 42);
	memcpy(&saved, first->symbol, sizeof saved);
	result = evaluate_address_initializer(definition->initializer);
	assert(result.status == constant_value && !result.message);
	assert(result.address.kind == static_address_object && result.address.base.object == base->symbol);
	assert(result.origin_type && result.origin_type->kind == type_kind_pointer);
	assert(evaluate_null_initializer(definition->initializer).status == constant_not_constant);
	assert(memcmp(&saved, first->symbol, sizeof saved) == 0);
	close_fixture(&f);

	open_fixture(&f, "extern int target; int *cell=&target; int *cell;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	base = object(&f, 0);
	definition = object(&f, 1);
	assert_object_address(definition->symbol, &definition->external, base->symbol);
	assert(!base->symbol->definition && !base->symbol->tentative_definition);
	assert(definition->symbol == object(&f, 2)->symbol);
	close_fixture(&f);
}

static void check_self_and_null_distinction(void)
{
	struct fixture f;
	struct ast_external_object_declaration *self, *null, *pointer;

	open_fixture(&f, "void *self=&self; int *empty=0; int **pointer=&empty;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	self = object(&f, 0);
	null = object(&f, 1);
	pointer = object(&f, 2);
	assert_object_address(self->symbol, &self->external, self->symbol);
	assert_object_address(pointer->symbol, &pointer->external, null->symbol);
	assert(null->symbol->definition == &null->external);
	assert(null->symbol->initializer_value.kind == static_data_null_pointer);
	assert(evaluate_address_initializer(null->initializer).status == constant_not_constant);
	close_fixture(&f);
}

static void check_array_captures(void)
{
	struct fixture f;
	struct ast_external_object_declaration *base, *definition, *later;
	struct ast_expression *source;
	struct address_initializer_result result;

	open_fixture(&f, "extern int target[]; int (*cell)[]=&target;"
		"extern int target[3]; extern int (*cell)[3]; int *decay=target;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	base = object(&f, 0);
	definition = object(&f, 1);
	later = object(&f, 3);
	assert_object_address(definition->symbol, &definition->external, base->symbol);
	assert(base->symbol == object(&f, 2)->symbol);
	assert(((const struct array_type *)base->type)->count == 0);
	assert(((const struct array_type *)base->symbol->type)->count == 3);
	assert(definition->symbol == later->symbol);
	assert(referent_count(definition->type) == 0);
	assert(referent_count(definition->initializer->type) == 0);
	assert(referent_count(later->type) == 3 && referent_count(definition->symbol->type) == 3);
	source = definition->initializer;
	assert(source->kind == expression_address);
	source = ((struct ast_address_expression *)source)->operand;
	assert(source->kind == expression_external_object);
	assert(((const struct array_type *)source->type)->count == 0);
	assert(((struct ast_external_object_expression *)source)->object == base->symbol);
	result = evaluate_address_initializer(definition->initializer);
	assert(result.status == constant_value && referent_count(result.origin_type) == 0);
	assert(result.address.base.object == base->symbol);
	definition = object(&f, 4);
	assert_object_address(definition->symbol, &definition->external, base->symbol);
	assert(((const struct pointer_type *)definition->initializer->type)->referent->kind == type_kind_int);
	assert(evaluate_address_initializer(definition->initializer).origin_type->kind == type_kind_pointer);
	close_fixture(&f);
}

static void check_alias_and_origin(void)
{
	struct fixture f;
	struct ast_external_type_declaration *alias, *query;
	struct ast_external_object_declaration *base, *direct;
	struct address_initializer_result result;

	open_fixture(&f, "extern int target; typedef const int *const P; static P cell=&target;"
		"typeof(&target) other=(int *)(void *)&target; const void *generic=(const void *)&target;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	base = object(&f, 0);
	alias = queried(&f, 2);
	query = queried(&f, 3);
	assert_object_address(alias->object_symbol, &alias->external, base->symbol);
	assert(alias->object_symbol->is_internal && !alias->symbol);
	assert(alias->type->qualifiers == type_qualifier_const);
	assert(alias->initializer->type->qualifiers == 0);
	assert_object_address(query->object_symbol, &query->external, base->symbol);
	direct = object(&f, 4);
	assert_object_address(direct->symbol, &direct->external, base->symbol);
	result = evaluate_address_initializer(direct->initializer);
	assert(result.status == constant_value);
	assert(((const struct pointer_type *)result.origin_type)->referent->kind == type_kind_int);
	assert(((const struct pointer_type *)direct->initializer->type)->referent->kind == type_kind_void);
	close_fixture(&f);
}

static void check_function_reference(void)
{
	struct fixture f;
	struct ast_function_declaration *prototype;
	struct ast_function *definition;
	struct ast_external_object_declaration *pointer, *address;
	struct function_symbol saved;
	struct address_initializer_result result;

	open_fixture(&f, "static int target(int); int (*cell)(int)=target;"
		"int (*other)(int)=&target; static int target(int x) { return x; }");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	prototype = (struct ast_function_declaration *)declaration(&f, 0);
	assert(prototype->external.kind == external_function_declaration);
	definition = (struct ast_function *)declaration(&f, 3);
	assert(definition->external.kind == external_function_definition);
	assert(prototype->symbol == definition->declaration->symbol);
	assert(prototype->symbol->is_internal && prototype->symbol->is_referenced);
	assert(prototype->symbol->definition == definition);
	pointer = object(&f, 1);
	address = object(&f, 2);
	assert(pointer->symbol->initializer_value.kind == static_data_address);
	assert(address->symbol->initializer_value.kind == static_data_address);
	assert(pointer->symbol->initializer_value.address.kind == static_address_function);
	assert(pointer->symbol->initializer_value.address.base.function == prototype->symbol);
	assert(address->symbol->initializer_value.address.base.function == prototype->symbol);
	memcpy(&saved, prototype->symbol, sizeof saved);
	result = evaluate_address_initializer(pointer->initializer);
	assert(result.status == constant_value && result.address.base.function == prototype->symbol);
	assert(memcmp(&saved, prototype->symbol, sizeof saved) == 0);
	close_fixture(&f);
}

static void check_string_identity(void)
{
	struct fixture f;
	struct ast_string_expression *first, *second, *third;
	const unsigned char contents[] = { 'a', 'b', 0, 'c', 'd', 0 };
	struct address_initializer_result result;

	open_fixture(&f, "char *cell=\"ab\\0c\" \"d\"; char (*whole)[6]=&\"ab\\0cd\";"
		"const char *last=\"other\";");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	first = f.unit->strings;
	assert(first);
	second = first->next_string;
	assert(second);
	third = second->next_string;
	assert(third && !third->next_string);
	assert(first->object_id == 0 && second->object_id == 1 && third->object_id == 2);
	assert(first->length == 5 && second->length == 5 && third->length == 5);
	assert(memcmp(first->bytes, contents, sizeof contents) == 0);
	assert(memcmp(second->bytes, contents, sizeof contents) == 0);
	assert(memcmp(third->bytes, "other", 6) == 0);
	for (unsigned i = 0; i < 3; ++i) {
		struct ast_external_object_declaration *d = object(&f, i);
		struct ast_string_expression *expected = i == 0 ? first : i == 1 ? second : third;

		assert(d->symbol->definition == &d->external);
		assert(d->symbol->initializer_value.kind == static_data_address);
		assert(d->symbol->initializer_value.address.kind == static_address_string);
		assert(d->symbol->initializer_value.address.base.string == expected);
		result = evaluate_address_initializer(d->initializer);
		assert(result.status == constant_value && result.address.base.string == expected);
		assert(f.unit->strings == first && first->next_string == second);
		assert(second->next_string == third && !third->next_string);
	}
	assert(referent_count(object(&f, 1)->initializer->type) == 6);
	close_fixture(&f);
}

static void check_failed_existing(const char *text, bool defined, bool tentative, bool unknown)
{
	struct fixture f;
	struct ast_external_object_declaration *first, *failed;

	open_fixture(&f, text);
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	first = object(&f, 0);
	failed = object(&f, 1);
	assert(first->symbol && failed->initializer && !failed->symbol && !failed->type);
	assert(first->symbol->definition == (defined ? &first->external : NULL));
	assert(first->symbol->tentative_definition == (tentative ? &first->external : NULL));
	assert(first->symbol->type == first->type);
	if (defined)
		assert_object_address(first->symbol, &first->external, first->symbol);
	if (unknown)
		assert(referent_count(first->symbol->type) == 0);
	close_fixture(&f);
}

static void check_failed_query(void)
{
	struct fixture f;
	struct ast_external_type_declaration *failed;

	open_fixture(&f, "typeof((int *)0) cell=(int *)0+0;");
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	failed = queried(&f, 0);
	assert(failed->initializer && !failed->object_symbol && !failed->symbol && !failed->type);
	assert(evaluate_address_initializer(failed->initializer).status == constant_not_constant);
	close_fixture(&f);
}

static void check_assignment_origin_rollback(void)
{
	struct fixture f;
	struct ast_external_object_declaration *first, *failed;

	open_fixture(&f, "extern int (*cell)[]; char x; int (*cell)[3]=(void *)&x;");
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	first = object(&f, 0);
	failed = object(&f, 2);
	assert(first->symbol && object(&f, 1)->symbol);
	assert(!failed->symbol && !failed->type && failed->initializer);
	assert(!first->symbol->definition && !first->symbol->tentative_definition);
	assert(first->symbol->type == first->type && referent_count(first->symbol->type) == 0);
	assert(evaluate_address_initializer(failed->initializer).status == constant_not_constant);
	close_fixture(&f);
}

static void check_missing_internal_function(void)
{
	struct fixture f;
	struct ast_function_declaration *prototype;
	struct ast_external_object_declaration *pointer;

	open_fixture(&f, "static int target(int); int (*cell)(int)=target;");
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	prototype = (struct ast_function_declaration *)declaration(&f, 0);
	pointer = object(&f, 1);
	assert(prototype->symbol && prototype->symbol->is_internal);
	assert(prototype->symbol->is_referenced && !prototype->symbol->definition);
	/* Finalization is fail-fast, not global TU rollback: an earlier successful
	 * pointer initializer has published its data before this missing body error.
	 */
	assert(pointer->symbol->definition == &pointer->external);
	assert(pointer->symbol->initializer_value.address.base.function == prototype->symbol);
	close_fixture(&f);
}

int main(void)
{
	check_assignment_origin_rollback();
	check_missing_internal_function();
	check_canonical_ownership();
	check_self_and_null_distinction();
	check_array_captures();
	check_alias_and_origin();
	check_function_reference();
	check_string_identity();
	/* Aligned explicit cast original promoted to test_address_offset_ast.c. */
	check_failed_existing("extern int *cell; int *cell=(int *)0+0;", false, false, false);
	check_failed_existing("void *cell=&cell; void *cell=&cell;", true, false, false);
	check_failed_existing("int (*cell)[]; int (*cell)[3]=cell;", false, true, true);
	check_failed_query();
	puts("Direct address AST base identity, origin/captures, ownership, strings and rollback passed");
	return 0;
}
