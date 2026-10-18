/* Independent M16 member/copy AST oracle. Build with compiler sources excluding main.c.
 * No Makefile changes required. Query snapshots cover reachable cyclic nominal
 * types, member identities, captured paths, local slots, and copy temporaries.
 * Run against a frozen production checkout before making release PASS claims. */
#include "parse.h"
#include "sema.h"
#include "consteval.h"
#include "type.h"

#include <assert.h>
#include <limits.h>
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
	assert(source_from_bytes(&f->source, "offset-ast.c", (const unsigned char *)text, strlen(text)));
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

/* Copy object representations, not hashes: even shared captures, pointer links,
 * padding and ownership fields must remain byte-for-byte unchanged by queries.
 * Deduplication makes this a bounded DAG walk rather than expanding sharing. */
struct saved_bytes { const void *address; size_t size; unsigned char bytes[512]; };
struct snapshot { size_t count; struct saved_bytes entries[2048]; };

static bool save(struct snapshot *s, const void *address, size_t size)
{
	for (size_t i = 0; i < s->count; ++i)
		if (s->entries[i].address == address)
			return false;
	assert(address && s->count < 2048 && size <= sizeof s->entries[0].bytes);
	s->entries[s->count].address = address;
	s->entries[s->count].size = size;
	memcpy(s->entries[s->count++].bytes, address, size);
	return true;
}

static void save_type(struct snapshot *s, const struct type *t)
{
	if (!t) return;
	if (type_is_record(t)) {
		const struct record_type *r = (const struct record_type *)t;
		if (!save(s, r, sizeof *r)) return;
		const struct record_definition *d = r->definition;
		if (!save(s, d, sizeof *d)) return;
		for (const struct record_member *m = d->members; m; m = m->next) {
			if (!save(s, m, sizeof *m)) break;
			save_type(s, m->type);
		}
	} else if (t->kind == type_kind_pointer) {
		if (save(s, t, sizeof(struct pointer_type)))
			save_type(s, ((const struct pointer_type *)t)->referent);
	} else if (t->kind == type_kind_array) {
		if (save(s, t, sizeof(struct array_type)))
			save_type(s, ((const struct array_type *)t)->element);
	} else if (t->kind == type_kind_function) {
		if (!save(s, t, sizeof(struct function_type))) return;
		const struct function_type *fn = (const struct function_type *)t;
		save_type(s, fn->return_type);
		for (const struct function_parameter_type *p = fn->parameters; p; p = p->next) {
			if (!save(s, p, sizeof *p)) break;
			save_type(s, p->type);
		}
	} else {
		(void)save(s, t, sizeof *t);
	}
}

#define SAVE_NODE(T) const struct T *n = (const struct T *)e; \
	if (!save(s, n, sizeof *n)) return

static void save_expression(struct snapshot *s, const struct ast_expression *e)
{
	assert(e);
	/* Unevaluated ICE arms can intentionally retain untyped parsed nodes. */
	if (e->type) save_type(s, e->type);
	switch (e->kind) {
	case expression_member: {
		SAVE_NODE(ast_member_expression);
		save_expression(s, n->operand);
		if (n->member) {
			(void)save(s, n->member, sizeof *n->member);
			save_type(s, n->member->type);
		}
		break;
	}
	case expression_assignment: {
		SAVE_NODE(ast_assignment_expression);
		save_expression(s, n->left); save_expression(s, n->right); break;
	}
	case expression_comma: {
		SAVE_NODE(ast_comma_expression);
		save_expression(s, n->left); save_expression(s, n->right); break;
	}
	case expression_pointer_offset: {
		SAVE_NODE(ast_pointer_offset_expression);
		save_expression(s, n->base); save_expression(s, n->index); break;
	}
	case expression_address: {
		SAVE_NODE(ast_address_expression); save_expression(s, n->operand); break;
	}
	case expression_subscript: {
		SAVE_NODE(ast_subscript_expression);
		save_expression(s, n->left); save_expression(s, n->right); break;
	}
	case expression_indirection: {
		SAVE_NODE(ast_indirection_expression); save_expression(s, n->operand); break;
	}
	case expression_load: {
		SAVE_NODE(ast_load_expression); save_expression(s, n->operand); break;
	}
	case expression_array_decay: {
		SAVE_NODE(ast_array_decay_expression); save_expression(s, n->operand); break;
	}
	case expression_function_decay: {
		SAVE_NODE(ast_function_decay_expression); save_expression(s, n->operand); break;
	}
	case expression_cast: {
		SAVE_NODE(ast_cast_expression); save_expression(s, n->operand); break;
	}
	case expression_conversion: {
		SAVE_NODE(ast_conversion_expression); save_expression(s, n->operand); break;
	}
	case expression_unary: {
		SAVE_NODE(ast_unary_expression); save_expression(s, n->operand); break;
	}
	case expression_binary: {
		SAVE_NODE(ast_binary_expression);
		save_expression(s, n->left); save_expression(s, n->right); break;
	}
	case expression_conditional: {
		SAVE_NODE(ast_conditional_expression);
		save_expression(s, n->condition); save_expression(s, n->then_value);
		save_expression(s, n->else_value); break;
	}
	case expression_external_object: {
		SAVE_NODE(ast_external_object_expression);
		(void)save(s, n->object, sizeof *n->object); save_type(s, n->object->type); break;
	}
	case expression_function_designator: {
		SAVE_NODE(ast_function_designator_expression);
		(void)save(s, n->function, sizeof *n->function); break;
	}
	case expression_string: {
		SAVE_NODE(ast_string_expression);
		(void)save(s, n->bytes, n->length+1); break;
	}
	case expression_name: {
		SAVE_NODE(ast_name_expression);
		if (n->declaration) {
			(void)save(s, n->declaration, sizeof *n->declaration);
			save_type(s, n->declaration->type);
		}
		break;
	}
	case expression_integer: (void)save(s, e, sizeof(struct ast_integer_expression)); break;
	case expression_nullptr: (void)save(s, e, sizeof(struct ast_nullptr_expression)); break;
	case expression_sizeof_type: (void)save(s, e, sizeof(struct ast_sizeof_type_expression)); break;
	default: fprintf(stderr, "purity walker missing expression kind %d\n", (int)e->kind);
		assert(!"extend the explicit purity walker for this AST kind");
	}
}

static struct address_initializer_result pure_query(struct fixture *f, struct ast_expression *e)
{
	struct snapshot s = {0};
	struct address_initializer_result first;
	assert(e && e->type && e->depth <= ast_max_expression_depth);
	long position = ftell(f->stream);
	assert(position >= 0);
	(void)save(&s, f->unit, sizeof *f->unit);
	(void)save(&s, &f->arena, sizeof f->arena);
	(void)save(&s, &f->diagnostics, sizeof f->diagnostics);
	save_expression(&s, e);
	/* Queries must not append function autoslots or record snapshots, even if
	 * the expression itself is already a nonconstant record value/load. */
	for (const struct ast_external_declaration *d = f->unit->declarations; d; d = d->next) {
		if (d->kind != external_function_definition) continue;
		const struct ast_function *fn = (const struct ast_function *)d;
		(void)save(&s, fn, sizeof *fn);
		for (const struct ast_local_declaration *l = fn->locals; l; l = l->next_local) {
			(void)save(&s, l, sizeof *l); save_type(&s, l->type);
		}
		for (const struct ast_load_expression *l = fn->record_temporaries; l; l = l->next_record_temporary)
			save_expression(&s, &l->expression);
	}
	first = evaluate_address_initializer(e);
	for (unsigned iteration = 0; iteration < 3; ++iteration) {
		struct address_initializer_result result = evaluate_address_initializer(e);
		assert(result.status == first.status && result.message == first.message);
		assert(result.location.source == first.location.source && result.location.offset == first.location.offset);
		assert(result.origin_type == first.origin_type);
		if (result.status == constant_value) {
			assert(result.address.kind == first.address.kind);
			assert(result.address.byte_addend == first.address.byte_addend);
			if (result.address.kind == static_address_object)
				assert(result.address.base.object == first.address.base.object);
			else if (result.address.kind == static_address_string)
				assert(result.address.base.string == first.address.base.string);
			else
				assert(result.address.base.function == first.address.base.function);
		}
		for (size_t i = 0; i < s.count; ++i)
			assert(memcmp(s.entries[i].address, s.entries[i].bytes, s.entries[i].size) == 0);
		assert(ftell(f->stream) == position);
	}
	return first;
}

static struct ast_function *function(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = declaration(f, index);
	assert(d->kind == external_function_definition);
	return (struct ast_function *)d;
}

static struct ast_block_item *item(struct ast_function *fn, unsigned index)
{
	struct ast_block_item *i = fn->body->items;
	while (index--) { assert(i); i = i->next; }
	assert(i);
	return i;
}

static struct ast_local_declaration *local(struct ast_function *fn, unsigned index)
{
	struct ast_block_item *i = item(fn, index);
	assert(i->kind == block_item_declaration);
	return (struct ast_local_declaration *)i;
}

static struct ast_expression *statement_value(struct ast_function *fn, unsigned index)
{
	struct ast_block_item *i = item(fn, index);
	assert(i->kind == block_item_statement);
	struct ast_statement *s = ((struct ast_statement_item *)i)->statement;
	assert(s->kind == statement_expression);
	return ((struct ast_expression_statement *)s)->value;
}

static struct ast_member_expression *member(struct ast_expression *e, uint64_t offset, bool indirect)
{
	assert(e->kind == expression_member && e->is_lvalue);
	struct ast_member_expression *m = (struct ast_member_expression *)e;
	assert(m->member && m->offset == offset && m->indirect == indirect);
	assert(e->type && type_unqualified_compatible(e->type, m->member->type));
	return m;
}

static struct ast_expression *address_operand(struct ast_expression *e)
{
	assert(e->kind == expression_address);
	return ((struct ast_address_expression *)e)->operand;
}

static void check_paths_and_qualification(void)
{
	struct fixture f;
	open_fixture(&f,
		"struct Leaf { const int fixed; int a[2]; }; "
		"struct R { char lead; struct Leaf in; union { struct { short low; int high; }; long wide; }; int *p; }; "
		"struct R target; const struct R frozen; "
		"int *cell=&target.in.a[1]; const int *fixed=&target.in.fixed; "
		"const int *cq=&frozen.in.a[0]; int *promoted=&target.high;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors && !f.diagnostics.warnings);
	struct ast_external_object_declaration *target = object(&f, 2);
	struct ast_external_object_declaration *frozen = object(&f, 3);
	assert(type_record_definition(target->type) == type_record_definition(frozen->type));
	assert(target->type != frozen->type && frozen->type->qualifiers == type_qualifier_const);
	assert(type_object_size(target->type) == 32 && type_object_alignment(target->type) == 8);
	const int64_t offsets[] = {12,4,8,20};
	for (unsigned i = 0; i < 4; ++i) {
		struct ast_external_object_declaration *d = object(&f, i+4);
		assert(d->symbol && d->symbol->definition == &d->external);
		assert(d->symbol->initializer_value.kind == static_data_address);
		assert(d->symbol->initializer_value.address.byte_addend == offsets[i]);
		struct address_initializer_result r = pure_query(&f, d->initializer);
		assert(r.status == constant_value && r.address.byte_addend == offsets[i]);
		assert(r.address.kind == static_address_object);
		assert(r.address.base.object == (i == 2 ? frozen->symbol : target->symbol));
	}
	struct ast_expression *sub = address_operand(object(&f,4)->initializer);
	assert(sub->kind == expression_indirection && type_same(sub->type, &type_int));
	struct ast_expression *offset = ((struct ast_indirection_expression *)sub)->operand;
	assert(offset->kind == expression_pointer_offset);
	assert(((struct ast_pointer_offset_expression *)offset)->element_size == 4);
	struct ast_expression *decay = ((struct ast_pointer_offset_expression *)offset)->base;
	assert(decay->kind == expression_array_decay);
	struct ast_member_expression *a = member(((struct ast_array_decay_expression *)decay)->operand,4,false);
	struct ast_member_expression *in = member(a->operand,4,false);
	assert(a->member != in->member && type_is_record(in->expression.type));
	assert(in->operand->kind == expression_external_object);
	struct ast_member_expression *fixed = member(address_operand(object(&f,5)->initializer),0,false);
	assert(fixed->expression.type->qualifiers == type_qualifier_const);
	struct ast_member_expression *high = member(address_operand(object(&f,7)->initializer),20,false);
	assert(high->member->offset == 4); /* Local leaf offset != accumulated promoted path. */
	assert(type_same(high->member->type, &type_int));
	assert(!f.unit->static_declarations);
	close_fixture(&f);
}

static size_t local_count(const struct ast_function *fn)
{
	size_t count = 0;
	for (const struct ast_local_declaration *l = fn->locals; l; l = l->next_local) ++count;
	return count;
}

static void check_copy_node_identity(void)
{
	struct fixture f;
	open_fixture(&f, "struct S { int x; }; int f(void) { struct S a; struct S b=a; struct S c; c=b; return c.x; }");
	struct ast_function *fn = function(&f,1);
	struct ast_local_declaration *a = local(fn,0), *b = local(fn,1), *c = local(fn,2);
	struct ast_expression *original_source = b->initializer;
	struct ast_expression *original_assignment = statement_value(fn,3);
	assert(original_assignment->kind == expression_assignment);
	struct ast_assignment_expression *assignment = (struct ast_assignment_expression *)original_assignment;
	struct ast_expression *original_left = assignment->left, *original_right = assignment->right;
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors && !f.diagnostics.warnings);
	assert(local_count(fn) == 3 && a->slot == 0 && b->slot == 1 && c->slot == 2);
	assert(fn->record_temporary_count == 2);
	assert(b->initializer->kind == expression_load);
	struct ast_load_expression *first = (struct ast_load_expression *)b->initializer;
	assert(first->operand == original_source && first->operand->kind == expression_name);
	assert(((struct ast_name_expression *)first->operand)->declaration == a);
	assert(statement_value(fn,3) == original_assignment && assignment->left == original_left);
	assert(assignment->right->kind == expression_load);
	struct ast_load_expression *second = (struct ast_load_expression *)assignment->right;
	assert(second != first && second->operand == original_right);
	assert(((struct ast_name_expression *)second->operand)->declaration == b);
	assert(first->record_temporary_slot != second->record_temporary_slot);
	assert(first->record_temporary_slot < 2 && second->record_temporary_slot < 2);
	assert(type_is_record(first->expression.type) && !first->expression.is_lvalue);
	assert(!assignment->expression.is_lvalue && type_is_record(assignment->expression.type));
	assert(pure_query(&f, b->initializer).status == constant_not_constant);
	assert(pure_query(&f, &assignment->expression).status == constant_not_constant);
	assert(fn->record_temporary_count == 2 && local_count(fn) == 3);
	close_fixture(&f);
}

static void check_address_no_autoslots(void)
{
	struct fixture f;
	open_fixture(&f, "struct S { int x; int a[2]; }; int f(void) { struct S a; struct S *p=&a; int *q=&p->x; return sizeof a+sizeof *p; }");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	struct ast_function *fn = function(&f,1);
	assert(local_count(fn) == 3 && !fn->record_temporary_count && !fn->record_temporaries);
	struct ast_expression *e = local(fn,2)->initializer;
	struct ast_member_expression *m = member(address_operand(e),0,true);
	assert(m->operand->kind == expression_load); /* Pointer loaded, never whole record. */
	assert(m->operand->type->kind == type_kind_pointer);
	assert(pure_query(&f,e).status == constant_not_constant);
	assert(local_count(fn) == 3 && !fn->record_temporary_count && !fn->record_temporaries);
	close_fixture(&f);
}

static void check_failed_address_publication(void)
{
	struct fixture f;
	open_fixture(&f, "struct S { int x; int a[2]; }; struct S target; int *cell=&target.a[3];");
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	struct ast_external_object_declaration *target = object(&f,1), *cell = object(&f,2);
	assert(target->symbol && target->symbol->tentative_definition == &target->external);
	assert(!cell->symbol && !cell->type && cell->initializer && cell->initializer->type);
	struct address_initializer_result r = pure_query(&f,cell->initializer);
	assert(r.status == constant_invalid && r.message);
	assert(!f.unit->static_declarations);
	close_fixture(&f);
}

static void check_snapshot_limit_failure(void)
{
	/* The failed 257th snapshot must not publish a temporary, consume an
	 * autoslot, or rewrite the expression root to an unregistered load. */
	char source[4096];
	size_t n = (size_t)snprintf(source,sizeof source,"struct S { int x; }; int f(void) { struct S a; ");
	for (unsigned i=0; i<ast_max_record_temporaries+1; ++i) {
		assert(n+3 < sizeof source);
		memcpy(source+n,"a; ",3); n+=3;
	}
	assert(n+12 < sizeof source);
	memcpy(source+n,"return 0; }",12);
	struct fixture f;
	open_fixture(&f,source);
	assert(!sema_translation_unit(f.unit,&f.arena,&f.diagnostics));
	assert(f.diagnostics.errors == 1);
	struct ast_function *fn = function(&f,1);
	assert(fn->record_temporary_count == ast_max_record_temporaries && local_count(fn) == 1);
	bool slots[ast_max_record_temporaries] = {0};
	size_t count=0;
	for (struct ast_load_expression *l=fn->record_temporaries; l; l=l->next_record_temporary) {
		assert(l->expression.kind == expression_load && type_is_record(l->expression.type));
		assert(l->record_temporary_slot < ast_max_record_temporaries && !slots[l->record_temporary_slot]);
		slots[l->record_temporary_slot]=true; ++count;
	}
	assert(count == ast_max_record_temporaries);
	struct ast_expression *failed = statement_value(fn,ast_max_record_temporaries+1);
	assert(failed->kind == expression_name && failed->is_lvalue && type_is_record(failed->type));
	close_fixture(&f);
}

int main(void)
{
	check_paths_and_qualification();
	check_copy_node_identity();
	check_address_no_autoslots();
	check_failed_address_publication();
	check_snapshot_limit_failure();
	puts("M16 record AST: member paths/qualifiers/copy identity/query purity/no autoslots/failure snapshots");
	return 0;
}
