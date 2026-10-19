/* Independent M15 lexical captures, stable entities, static ownership and
 * failed publication. Link compiler sources except main.c; assertions required.
 */
#include "parse.h"
#include "sema.h"
#include "type.h"
#include "codegen.h"

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
	assert(source_from_bytes(&f->source, "block-storage-ast.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&f->source));
	preprocess_init(&f->preprocessor, &f->source, &f->diagnostics);
	f->unit = parse_translation_unit(&f->preprocessor, &f->arena, &f->diagnostics);
	assert(f->unit && !f->diagnostics.errors);
}

static void close_fixture(struct fixture *f)
{
	arena_destroy(&f->arena);
	preprocess_destroy(&f->preprocessor);
	source_destroy(&f->source);
	assert(fclose(f->stream) == 0);
}

static struct ast_external_declaration *external(struct fixture *f, unsigned n)
{
	struct ast_external_declaration *d = f->unit->declarations;
	while (n--) { assert(d); d = d->next; }
	assert(d);
	return d;
}

static struct ast_function *function(struct fixture *f, unsigned n)
{
	struct ast_external_declaration *d = external(f, n);
	assert(d->kind == external_function_definition);
	return (struct ast_function *)d;
}

static struct ast_block_item *item(struct ast_compound_statement *block, unsigned n)
{
	struct ast_block_item *i = block->items;
	while (n--) { assert(i); i = i->next; }
	assert(i);
	return i;
}

static struct ast_local_declaration *local(struct ast_compound_statement *block, unsigned n)
{
	struct ast_block_item *i = item(block, n);
	assert(i->kind == block_item_declaration);
	return (struct ast_local_declaration *)i;
}

static struct ast_compound_statement *nested(struct ast_compound_statement *block, unsigned n)
{
	struct ast_block_item *i = item(block, n);
	struct ast_statement *s;
	assert(i->kind == block_item_statement);
	s = ((struct ast_statement_item *)i)->statement;
	assert(s->kind == statement_compound);
	return (struct ast_compound_statement *)s;
}

static uint64_t count(const struct type *t)
{
	assert(t && t->kind == type_kind_array);
	return ((const struct array_type *)t)->count;
}

static const struct type *referent(const struct type *t)
{
	assert(t && t->kind == type_kind_pointer);
	return ((const struct pointer_type *)t)->referent;
}

static struct ast_external_object_expression *array_source(struct ast_expression *e)
{
	assert(e && e->kind == expression_array_decay);
	e = ((struct ast_array_decay_expression *)e)->operand;
	assert(e->kind == expression_external_object);
	return (struct ast_external_object_expression *)e;
}

static void assert_auto_locals(struct ast_function *f, unsigned expected)
{
	unsigned n = 0;
	for (struct ast_local_declaration *l = f->locals; l; l = l->next_local) {
		assert(!l->is_extern && !l->is_static);
		assert(!l->object_symbol && !l->function_symbol);
		n++;
	}
	assert(n == expected);
}

static void check_object_captures(void)
{
	struct fixture f;
	struct ast_external_object_declaration *first, *last;
	struct ast_function *fn;
	struct ast_compound_statement *inner;
	struct ast_local_declaration *outer, *complete, *early, *middle, *late;
	struct ast_external_object_expression *a, *b, *c;
	struct external_object_symbol saved;

	open_fixture(&f, "extern int cells[]; int inspect(void) { extern int cells[];"
		"int *early=cells; { extern int cells[3]; int (*middle)[3]=&cells; }"
		"int *late=cells; return 42; } extern int cells[3];");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors && !f.unit->static_declarations);
	first = (struct ast_external_object_declaration *)external(&f, 0);
	last = (struct ast_external_object_declaration *)external(&f, 2);
	fn = function(&f, 1);
	outer = local(fn->body, 0); early = local(fn->body, 1);
	inner = nested(fn->body, 2);
	complete = local(inner, 0); middle = local(inner, 1); late = local(fn->body, 3);
	assert(outer->is_extern && complete->is_extern);
	assert(!outer->is_static && !complete->is_static);
	assert(outer->object_symbol == first->symbol && complete->object_symbol == first->symbol);
	assert(first->symbol == last->symbol);
	assert(count(first->type) == 0 && count(last->type) == 3);
	assert(count(outer->type) == 0 && count(complete->type) == 3);
	assert(count(first->symbol->type) == 3 && count(first->symbol->file_type) == 3);
	assert(!first->symbol->definition && !first->symbol->tentative_definition);
	a = array_source(early->initializer); c = array_source(late->initializer);
	assert(middle->initializer->kind == expression_address);
	b = (struct ast_external_object_expression *)((struct ast_address_expression *)middle->initializer)->operand;
	assert(b->expression.kind == expression_external_object);
	assert(a->object == first->symbol && b->object == a->object && c->object == a->object);
	assert(count(a->expression.type) == 0 && count(b->expression.type) == 3 && count(c->expression.type) == 0);
	assert(count(referent(middle->initializer->type)) == 3);
	assert_auto_locals(fn, 3);
	/* Repeated consteval is pure: no canonical type/owner mutation. */
	saved = *first->symbol;
	assert(evaluate_address_initializer(middle->initializer).status == constant_value);
	assert(evaluate_address_initializer(middle->initializer).address.base.object == first->symbol);
	assert(memcmp(&saved, first->symbol, sizeof saved) == 0);
	close_fixture(&f);
}

static void check_hidden_registry(void)
{
	struct fixture f;
	struct ast_function *a, *b, *c;
	struct ast_local_declaration *x, *y, *z;
	open_fixture(&f, "int a(void) { extern int cells[]; return 1; }"
		"int b(void) { extern int cells[3]; return 2; }"
		"int c(void) { extern int cells[]; return 3; }");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	a = function(&f, 0); b = function(&f, 1); c = function(&f, 2);
	x = local(a->body, 0); y = local(b->body, 0); z = local(c->body, 0);
	assert(x->object_symbol == y->object_symbol && y->object_symbol == z->object_symbol);
	assert(count(x->type) == 0 && count(y->type) == 3 && count(z->type) == 0);
	assert(count(x->object_symbol->type) == 3 && !x->object_symbol->file_type);
	assert(!x->object_symbol->definition && !x->object_symbol->tentative_definition);
	assert_auto_locals(a, 0); assert_auto_locals(b, 0); assert_auto_locals(c, 0);
	assert(!f.unit->static_declarations);
	close_fixture(&f);
}

static const struct function_type *signature(const struct type *t)
{
	assert(t && t->kind == type_kind_function);
	return (const struct function_type *)t;
}

static uint64_t parameter_count(const struct type *t)
{
	const struct function_type *s = signature(t);
	assert(s->parameter_count == 1 && s->parameters);
	return count(referent(s->parameters->type));
}

static struct ast_function_designator_expression *function_source(struct ast_expression *e)
{
	assert(e && e->kind == expression_function_decay);
	e = ((struct ast_function_decay_expression *)e)->operand;
	assert(e->kind == expression_function_designator);
	return (struct ast_function_designator_expression *)e;
}

static void check_function_captures(void)
{
	struct fixture f;
	struct ast_function *fn;
	struct ast_local_declaration *first, *later;
	struct ast_function_designator_expression *a, *b, *c;
	open_fixture(&f, "int inspect(void) { int target(int (*)[]);"
		"int (*early)(int (*)[])=target; { extern int target(int (*)[3]);"
		"int (*middle)(int (*)[3])=target; } int (*late)(int (*)[])=target; return 42; }");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	fn = function(&f, 0); first = local(fn->body, 0); later = local(nested(fn->body, 2), 0);
	assert(!first->is_extern && !first->is_static && !first->object_symbol);
	assert(first->function_symbol == later->function_symbol && later->is_extern);
	assert(!first->function_symbol->file_type && !first->function_symbol->is_internal);
	assert(parameter_count(first->type) == 0 && parameter_count(later->type) == 3);
	assert(parameter_count(&first->function_symbol->type->type) == 3);
	a = function_source(local(fn->body, 1)->initializer);
	b = function_source(local(nested(fn->body, 2), 1)->initializer);
	c = function_source(local(fn->body, 3)->initializer);
	assert(a->function == first->function_symbol && b->function == a->function && c->function == a->function);
	assert(parameter_count(a->expression.type) == 0 && parameter_count(b->expression.type) == 3);
	assert(parameter_count(c->expression.type) == 0 && a->function->is_referenced);
	assert_auto_locals(fn, 3);
	close_fixture(&f);
}

static bool token_equals(struct token token, const char *text)
{
	return token.length == strlen(text) && memcmp(token.spelling_location.source->data +
		token.spelling_location.offset, text, token.length) == 0;
}

static void check_static_ownership(void)
{
	struct fixture f;
	struct ast_function *fn;
	struct ast_external_declaration *emission;
	struct external_object_symbol *symbols[6];
	unsigned n = 0;
	open_fixture(&f, "int inspect(int argument) { static int scalar=sizeof scalar;"
		"static int cells[3]; static int *empty=0; static int (*row)[3]=&cells;"
		"static void *self=&self; int automatic=argument; { static int scalar=42; } return automatic; }");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors);
	fn = function(&f, 0);
	assert_auto_locals(fn, 2); /* One parameter, one automatic; no static slots. */
	for (emission = f.unit->static_declarations; emission; emission = emission->next) {
		struct ast_external_object_declaration *d = (struct ast_external_object_declaration *)emission;
		struct ast_local_declaration *l = n < 5 ? local(fn->body, n) : local(nested(fn->body, 6), 0);
		char expected[64];
		assert(n < 6 && emission->kind == external_object_declaration);
		snprintf(expected, sizeof expected, ".Lkcc.static.%u", n);
		assert(token_equals(d->name, expected) && token_equals(d->symbol->name, expected));
		assert(l->is_static && !l->is_extern && !l->is_register);
		assert(l->object_symbol == d->symbol && !l->function_symbol);
		assert(d->is_static && !d->is_extern && d->type_syntax == l->type_syntax);
		assert(d->initializer == l->initializer && d->type == l->type);
		assert(d->symbol->is_internal && !d->symbol->file_type);
		assert(d->symbol->definition == emission && !d->symbol->tentative_definition);
		for (unsigned j = 0; j < n; j++) assert(symbols[j] != d->symbol);
		symbols[n++] = d->symbol;
	}
	assert(n == 6 && !fn->external.next);
	assert(symbols[0]->initializer_value.kind == static_data_integer && symbols[0]->initializer_value.integer_bits == 4);
	assert(symbols[1]->initializer_value.kind == static_data_zero && count(symbols[1]->type) == 3);
	assert(type_object_size(symbols[1]->type) == 12 && type_object_alignment(symbols[1]->type) == 4);
	assert(symbols[2]->initializer_value.kind == static_data_null_pointer);
	assert(symbols[3]->initializer_value.kind == static_data_address);
	assert(symbols[3]->initializer_value.address.kind == static_address_object);
	assert(symbols[3]->initializer_value.address.base.object == symbols[1]);
	assert(symbols[4]->initializer_value.kind == static_data_address);
	assert(symbols[4]->initializer_value.address.base.object == symbols[4]);
	assert(symbols[5]->initializer_value.kind == static_data_integer && symbols[5]->initializer_value.integer_bits == 42);
	/* Repeat codegen: immutable lowering and fresh per-invocation state. */
	{
		FILE *a = tmpfile(), *b = tmpfile();
		int x, y;
		assert(a && b && codegen_translation_unit(a, f.unit) && codegen_translation_unit(b, f.unit));
		assert(fflush(a) == 0 && fflush(b) == 0);
		assert(ftell(a) > 0 && ftell(b) > 0);
		rewind(a); rewind(b);
		do { x = fgetc(a); y = fgetc(b); assert(x == y); } while (x != EOF);
		assert(!ferror(a) && !ferror(b));
		assert(fclose(a) == 0 && fclose(b) == 0);
	}
	close_fixture(&f);
}

static void check_register_and_nullptr_storage(void)
{
	struct fixture f;
	struct ast_function *fn;
	struct ast_local_declaration *array, *pointer, *size, *empty;
	open_fixture(&f, "int probe(register void) { register int a[2];"
		"typeof(a+0) p=0; unsigned long size=sizeof(a[0]);"
		"static typeof(nullptr) empty=nullptr; return 42; }");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors);
	fn = function(&f, 0);
	assert(fn->declaration->parameters && fn->declaration->parameters->is_void_marker);
	assert(fn->declaration->parameters->is_register && !fn->declaration->parameters->local);
	assert(fn->declaration->symbol->type->parameter_count == 0);
	array = local(fn->body, 0); pointer = local(fn->body, 1);
	size = local(fn->body, 2); empty = local(fn->body, 3);
	assert(array->is_register && count(array->type) == 2);
	assert(type_same(referent(pointer->type), &type_int));
	assert(evaluate_integer_constant(size->initializer).status == constant_value);
	assert(evaluate_integer_constant(size->initializer).bits == 4);
	assert(empty->is_static && empty->type->kind == type_kind_nullptr);
	assert(empty->object_symbol && empty->object_symbol->initializer_value.kind == static_data_null_pointer);
	assert(type_object_size(empty->type) == 8 && type_object_alignment(empty->type) == 8);
	assert(empty->object_symbol->definition == f.unit->static_declarations);
	assert(!f.unit->static_declarations->next);
	assert_auto_locals(fn, 3);
	close_fixture(&f);
}

static void check_failed_publication(void)
{
	const char *texts[] = {
		"int inspect(void) { static int first=42; static int bad=1/0; return 0; }",
		"int inspect(int argument) { static int first=42; static int *bad=&argument; return 0; }",
		"int inspect(void) { static int first=42; static int bad=bad; return 0; }",
	};
	for (unsigned i = 0; i < sizeof texts / sizeof *texts; i++) {
		struct fixture f;
		struct ast_local_declaration *bad;
		struct ast_external_object_declaration *first;
		open_fixture(&f, texts[i]);
		assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
		assert(f.diagnostics.errors == 1);
		first = (struct ast_external_object_declaration *)f.unit->static_declarations;
		assert(first && first->external.kind == external_object_declaration && !first->external.next);
		assert(first->symbol->definition == &first->external);
		assert(first->symbol->initializer_value.kind == static_data_integer && first->symbol->initializer_value.integer_bits == 42);
		bad = local(function(&f, 0)->body, 1);
		assert(!bad->object_symbol && !bad->initializer_plan);
		close_fixture(&f);
	}
}

int main(void)
{
	check_object_captures();
	check_hidden_registry();
	check_function_captures();
	check_static_ownership();
	check_failed_publication();
	check_register_and_nullptr_storage();
	puts("Block storage AST: lexical snapshots, entity identity, private owners, rollback and immutable codegen passed");
	return 0;
}
