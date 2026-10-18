/* Genuine TLS duration, canonical ownership, lexical captures and refusal.
 * Build against the chosen source tree, compiler C files excluding main.c, -Isrc.
 * This is a fresh parse+sema oracle, never a second sema pass on a lowered AST.
 */
#include "parse.h"
#include "sema.h"
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
	assert(source_from_bytes(&f->source, "thread-storage-ast.c",
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
	assert(!fclose(f->stream));
}

static struct ast_external_declaration *declaration(struct fixture *f, unsigned n)
{
	struct ast_external_declaration *d = f->unit->declarations;
	while (n--) {
		assert(d);
		d = d->next;
	}
	assert(d);
	return d;
}

static struct ast_external_object_declaration *object(struct fixture *f, unsigned n)
{
	struct ast_external_declaration *d = declaration(f, n);
	assert(d->kind == external_object_declaration);
	return (struct ast_external_object_declaration *)d;
}

static struct ast_function *function(struct fixture *f, unsigned n)
{
	struct ast_external_declaration *d = declaration(f, n);
	assert(d->kind == external_function_definition);
	return (struct ast_function *)d;
}

static struct ast_block_item *item(struct ast_compound_statement *body, unsigned n)
{
	struct ast_block_item *i = body->items;
	while (n--) {
		assert(i);
		i = i->next;
	}
	assert(i);
	return i;
}

static struct ast_local_declaration *local(struct ast_compound_statement *body, unsigned n)
{
	struct ast_block_item *i = item(body, n);
	assert(i->kind == block_item_declaration);
	return (struct ast_local_declaration *)i;
}

static struct ast_compound_statement *block(struct ast_compound_statement *body, unsigned n)
{
	struct ast_block_item *i = item(body, n);
	struct ast_statement *s;
	assert(i->kind == block_item_statement);
	s = ((struct ast_statement_item *)i)->statement;
	assert(s->kind == statement_compound);
	return (struct ast_compound_statement *)s;
}

static struct ast_expression *address_operand(struct ast_local_declaration *d)
{
	assert(d->initializer && d->initializer->kind == expression_address);
	return ((struct ast_address_expression *)d->initializer)->operand;
}

static void assert_reference(struct ast_local_declaration *d, struct external_object_symbol *s)
{
	struct ast_expression *e = address_operand(d);
	assert(e->kind == expression_external_object);
	assert(((struct ast_external_object_expression *)e)->object == s);
	assert(e->is_lvalue);
}

static void check_canonical_duration(void)
{
	struct fixture f;
	struct ast_external_object_declaration *a, *b, *c, *d;
	open_fixture(&f, "extern _Thread_local int cell; extern thread_local int cell; "
		"_Thread_local int cell=42; extern thread_local int cell;");
	a = object(&f, 0); b = object(&f, 1); c = object(&f, 2); d = object(&f, 3);
	assert(a->is_thread_local && b->is_thread_local && c->is_thread_local && d->is_thread_local);
	assert(a->is_extern && b->is_extern && d->is_extern && !c->is_extern);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors);
	assert(a->symbol == b->symbol && a->symbol == c->symbol && a->symbol == d->symbol);
	assert(a->symbol->is_thread_local && !a->symbol->is_internal);
	assert(a->symbol->definition == &c->external);
	assert(!a->symbol->tentative_definition);
	assert(a->symbol->initializer_value.kind == static_data_integer);
	assert(a->symbol->initializer_value.integer_bits == 42);
	assert(a->symbol->file_type == a->type && a->type == a->symbol->type);
	assert(!f.unit->static_declarations);
	close_fixture(&f);

	open_fixture(&f, "static thread_local int cell=7; extern _Thread_local int cell; "
		"extern _Thread_local int cell; _Thread_local extern int cell;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	a = object(&f, 0); b = object(&f, 1); c = object(&f, 2); d = object(&f, 3);
	assert(a->symbol == b->symbol && a->symbol == c->symbol && a->symbol == d->symbol);
	assert(a->symbol->is_internal && a->symbol->is_thread_local);
	assert(a->symbol->definition == &a->external && a->symbol->initializer_value.integer_bits == 7);
	close_fixture(&f);
}

static void check_zero_definition(void)
{
	struct fixture f;
	struct ast_external_object_declaration *a, *b, *c;
	open_fixture(&f, "extern _Thread_local int cell; thread_local int cell; "
		"extern _Thread_local int cell;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	a = object(&f, 0); b = object(&f, 1); c = object(&f, 2);
	assert(a->symbol == b->symbol && a->symbol == c->symbol);
	assert(a->symbol->definition == &b->external && !a->symbol->tentative_definition);
	assert(a->symbol->initializer_value.kind == static_data_zero);
	assert(!b->initializer && b->symbol->is_thread_local);
	close_fixture(&f);

	open_fixture(&f, "thread_local int cell; _Thread_local int cell=1;");
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	a = object(&f, 0); b = object(&f, 1);
	assert(a->symbol && a->symbol->definition == &a->external);
	assert(a->symbol->initializer_value.kind == static_data_zero);
	assert(!a->symbol->tentative_definition && !b->symbol && !b->type);
	close_fixture(&f);
}

static void check_lexical_bindings(void)
{
	struct fixture f;
	struct ast_function *fn;
	struct ast_compound_statement *nested, *alias, *automatic;
	struct ast_local_declaration *private, *external, *auto_cell;
	struct ast_external_object_declaration *synthetic;
	struct external_object_symbol *file;
	open_fixture(&f, "_Thread_local int cell=40; int *pick(void) { int *before=&cell; "
		"{ static thread_local int cell=41; int *inside=&cell; } "
		"{ extern _Thread_local int cell; int *again=&cell; } "
		"{ int cell=2; int *ordinary=&cell; } int *after=&cell; return after; }");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors);
	file = object(&f, 0)->symbol;
	fn = function(&f, 1);
	nested = block(fn->body, 1); alias = block(fn->body, 2); automatic = block(fn->body, 3);
	private = local(nested, 0); external = local(alias, 0); auto_cell = local(automatic, 0);
	assert(private->is_static && private->is_thread_local && !private->is_extern);
	assert(private->object_symbol && private->object_symbol != file);
	assert(private->object_symbol->is_thread_local && private->object_symbol->is_internal);
	assert(private->object_symbol->is_block_static && !file->is_block_static);
	assert(external->is_extern && external->is_thread_local && !external->is_static);
	assert(external->object_symbol == file);
	assert(!auto_cell->is_thread_local && !auto_cell->object_symbol);
	assert_reference(local(fn->body, 0), file);
	assert_reference(local(nested, 1), private->object_symbol);
	assert_reference(local(alias, 1), file);
	assert_reference(local(fn->body, 4), file);
	assert(address_operand(local(automatic, 1))->kind == expression_name);
	assert(((struct ast_name_expression *)address_operand(local(automatic, 1)))->declaration == auto_cell);
	assert(f.unit->static_declarations && !f.unit->static_declarations->next);
	assert(f.unit->static_declarations->kind == external_object_declaration);
	synthetic = (struct ast_external_object_declaration *)f.unit->static_declarations;
	assert(synthetic->symbol == private->object_symbol && synthetic->is_thread_local);
	assert(private->object_symbol->definition == &synthetic->external);
	assert(synthetic->initializer == private->initializer);
	assert(private->object_symbol->initializer_value.integer_bits == 41);
	/* Runtime TLS addresses cannot leak into a static address proof. */
	struct external_object_symbol saved = *file;
	assert(evaluate_address_initializer(local(fn->body, 0)->initializer).status == constant_not_constant);
	assert(evaluate_address_initializer(local(nested, 1)->initializer).status == constant_not_constant);
	assert(!memcmp(&saved, file, sizeof saved));
	close_fixture(&f);
}

static void check_distinct_block_storage(void)
{
	struct fixture f;
	struct ast_external_declaration *d;
	struct external_object_symbol *symbols[3];
	unsigned n = 0;
	open_fixture(&f, "int *a(void) { static _Thread_local int cell; return &cell; } "
		"int *b(void) { static thread_local int cell=2; "
		"{ static _Thread_local int cell=3; } return &cell; }");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	for (d = f.unit->static_declarations; d; d = d->next) {
		struct ast_external_object_declaration *o = (struct ast_external_object_declaration *)d;
		assert(d->kind == external_object_declaration && n < 3);
		assert(o->is_thread_local && o->symbol->is_thread_local && o->symbol->is_internal);
		for (unsigned i = 0; i < n; i++) assert(o->symbol != symbols[i]);
		symbols[n++] = o->symbol;
	}
	assert(n == 3);
	assert(local(function(&f, 0)->body, 0)->object_symbol == symbols[0]);
	assert(local(function(&f, 1)->body, 0)->object_symbol == symbols[1]);
	assert(local(block(function(&f, 1)->body, 1), 0)->object_symbol == symbols[2]);
	assert(!symbols[0]->tentative_definition && symbols[0]->definition);
	assert(symbols[0]->initializer_value.kind == static_data_zero);
	assert(symbols[1]->definition && symbols[1]->initializer_value.integer_bits == 2);
	assert(symbols[2]->definition && symbols[2]->initializer_value.integer_bits == 3);
	close_fixture(&f);
}

static void check_alias_and_file_capture(void)
{
	struct fixture f;
	struct ast_external_type_declaration *alias;
	struct ast_local_declaration *first, *later;
	struct external_object_symbol *symbol;
	open_fixture(&f, "typedef const int I; thread_local I frozen=42; "
		"int *a(void) { extern _Thread_local int cell; return &cell; } "
		"_Thread_local int cell=7;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(declaration(&f, 1)->kind == external_type_declaration);
	alias = (struct ast_external_type_declaration *)declaration(&f, 1);
	assert(alias->is_thread_local && alias->object_symbol && !alias->symbol);
	assert(alias->object_symbol->is_thread_local && alias->type->qualifiers == type_qualifier_const);
	first = local(function(&f, 2)->body, 0);
	assert(first->object_symbol == object(&f, 3)->symbol && first->is_thread_local);
	close_fixture(&f);

	open_fixture(&f, "extern _Thread_local int rows[]; int f(void) { "
		"extern thread_local int rows[3]; int (*inside)[3]=&rows; return sizeof rows; } "
		"_Thread_local int rows[3];");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	symbol = object(&f, 0)->symbol;
	first = local(function(&f, 1)->body, 0); later = local(function(&f, 1)->body, 1);
	assert(first->object_symbol == symbol && object(&f, 2)->symbol == symbol);
	assert(((const struct array_type *)object(&f, 0)->type)->count == 0);
	assert(((const struct array_type *)first->type)->count == 3);
	assert(((const struct array_type *)symbol->type)->count == 3);
	assert_reference(later, symbol);
	assert(((const struct array_type *)address_operand(later)->type)->count == 3);
	close_fixture(&f);
}

static void check_failed_duration(const char *text, bool tls)
{
	struct fixture f;
	struct ast_external_object_declaration *first, *failed;
	open_fixture(&f, text);
	first = object(&f, 0); failed = object(&f, 1);
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	assert(first->symbol && first->symbol->is_thread_local == tls);
	assert(first->symbol->tentative_definition == (tls ? NULL : &first->external));
	assert(first->symbol->definition == (tls ? &first->external : NULL));
	assert(!failed->symbol && !failed->type);
	close_fixture(&f);
}

static void check_tls_widths(void)
{
	struct fixture f;
	const enum type_kind kinds[] = { type_kind_char, type_kind_short, type_kind_long,
		type_kind_ulong_long, type_kind_bool, type_kind_bool, type_kind_nullptr };
	const unsigned sizes[] = { 1, 2, 8, 8, 1, 1, 8 };
	const uint64_t bits[] = { 249, 53191, UINT64_C(4294967297), UINT64_MAX, 1, 1, 0 };
	open_fixture(&f, "_Thread_local char byte=-7; thread_local short half=-12345; "
		"_Thread_local long wide=4294967297L; thread_local unsigned long long full=18446744073709551615ULL; "
		"_Thread_local _Bool flag=1; thread_local bool other=true; "
		"thread_local typeof(nullptr) empty=nullptr;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors);
	for (unsigned i = 0; i < 7; i++) {
		struct ast_external_declaration *d = declaration(&f, i);
		struct external_object_symbol *symbol;
		const struct type *type;
		if (d->kind == external_type_declaration) {
			struct ast_external_type_declaration *o = (struct ast_external_type_declaration *)d;
			assert(o->is_thread_local);
			symbol = o->object_symbol;
			type = o->type;
		} else {
			assert(d->kind == external_object_declaration);
			symbol = ((struct ast_external_object_declaration *)d)->symbol;
			type = ((struct ast_external_object_declaration *)d)->type;
		}
		assert(symbol && symbol->is_thread_local && symbol->definition == d);
		assert(!symbol->tentative_definition && type->kind == kinds[i]);
		assert(type_object_size(type) == sizes[i] && type_object_alignment(type) == sizes[i]);
		assert(symbol->initializer_value.kind == (i == 6 ? static_data_null_pointer : static_data_integer));
		if (i != 6) assert(symbol->initializer_value.integer_bits == bits[i]);
	}
	close_fixture(&f);
}

static void check_legal_tls_pointer_initializers(void)
{
	struct fixture f;
	struct external_object_symbol *global, *private;
	struct function_symbol *target;
	open_fixture(&f, "int ordinary; static int hidden=42; static int target(void) { return 42; } "
		"thread_local int *pub=&ordinary; _Thread_local int *priv=&hidden; "
		"thread_local int (*fp)(void)=target; _Thread_local char *text=\"tls\";");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors);
	global = object(&f, 0)->symbol; private = object(&f, 1)->symbol;
	target = function(&f, 2)->declaration->symbol;
	assert(!global->is_thread_local && !private->is_thread_local);
	for (unsigned i = 3; i < 7; i++) {
		struct ast_external_object_declaration *o = object(&f, i);
		struct address_initializer_result result;
		assert(o->symbol->is_thread_local && o->symbol->definition == &o->external);
		assert(o->symbol->initializer_value.kind == static_data_address);
		result = evaluate_address_initializer(o->initializer);
		assert(result.status == constant_value);
		assert(result.address.kind == o->symbol->initializer_value.address.kind);
		if (i < 5) {
			assert(result.address.kind == static_address_object);
			assert(result.address.base.object == (i == 3 ? global : private));
		} else if (i == 5) {
			assert(result.address.kind == static_address_function && result.address.base.function == target);
		} else {
			assert(result.address.kind == static_address_string);
			assert(result.address.base.string == f.unit->strings);
			assert(result.address.base.string->length == 3);
		}
	}
	close_fixture(&f);
}

static void check_failed_address(void)
{
	struct fixture f;
	struct ast_external_object_declaration *base, *failed;
	open_fixture(&f, "_Thread_local int cell; int *pointer=&cell;");
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	base = object(&f, 0); failed = object(&f, 1);
	assert(base->symbol && base->symbol->is_thread_local);
	assert(!failed->symbol && !failed->type && failed->initializer);
	assert(evaluate_address_initializer(failed->initializer).status == constant_not_constant);
	assert(!base->symbol->tentative_definition && base->symbol->definition == &base->external);
	close_fixture(&f);
}

int main(void)
{
	check_canonical_duration();
	check_zero_definition();
	check_lexical_bindings();
	check_distinct_block_storage();
	check_alias_and_file_capture();
	check_failed_duration("int cell; extern _Thread_local int cell;", false);
	check_failed_duration("thread_local int cell; extern int cell;", true);
	check_tls_widths();
	check_legal_tls_pointer_initializers();
	check_failed_address();
	puts("TLS AST duration, ownership, lexical bindings, captures and refusal passed");
	return 0;
}
