/* Checked address offsets: query purity, immutable captures, invalid status and
 * publication rollback. Link against compiler sources excluding main.c.
 * Synthetic large domains exercise int64 relocation limits unavailable through
 * the source language's independent 1 MiB array storage cap. */
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
struct snapshot { size_t count; struct saved_bytes entries[256]; };

static bool save(struct snapshot *s, const void *address, size_t size)
{
	for (size_t i = 0; i < s->count; ++i)
		if (s->entries[i].address == address)
			return false;
	assert(address && s->count < 256 && size <= sizeof s->entries[0].bytes);
	s->entries[s->count].address = address;
	s->entries[s->count].size = size;
	memcpy(s->entries[s->count++].bytes, address, size);
	return true;
}

static void save_type(struct snapshot *s, const struct type *t)
{
	if (t->kind == type_kind_pointer) {
		if (save(s, t, sizeof(struct pointer_type)))
			save_type(s, ((const struct pointer_type *)t)->referent);
	} else if (t->kind == type_kind_array) {
		if (save(s, t, sizeof(struct array_type)))
			save_type(s, ((const struct array_type *)t)->element);
	} else if (t->kind == type_kind_function) {
		(void)save(s, t, sizeof(struct function_type));
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
	case expression_name: (void)save(s, e, sizeof(struct ast_name_expression)); break;
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

static void check_value(const char *source, unsigned index, int64_t addend)
{
	struct fixture f;
	struct ast_external_object_declaration *d;
	struct address_initializer_result result;
	open_fixture(&f, source);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors && !f.diagnostics.warnings);
	d = object(&f, index);
	assert(d->symbol && d->symbol->definition == &d->external);
	assert(d->symbol->initializer_value.kind == static_data_address);
	assert(d->symbol->initializer_value.address.byte_addend == addend);
	result = pure_query(&f, d->initializer);
	assert(result.status == constant_value && !result.message && result.origin_type);
	assert(result.address.byte_addend == addend);
	assert(evaluate_null_initializer(d->initializer).status == constant_not_constant);
	if (result.address.kind == static_address_object) {
		assert(result.address.base.object == object(&f, 0)->symbol);
		assert(d->symbol->initializer_value.address.base.object == result.address.base.object);
	} else {
		assert(result.address.kind == static_address_string);
		assert(result.address.base.string == f.unit->strings);
		assert(d->symbol->initializer_value.address.base.string == f.unit->strings);
	}
	close_fixture(&f);
}

static void check_failure(const char *source, unsigned index, enum constant_status status, const char *message)
{
	struct fixture f;
	struct ast_external_object_declaration *d;
	struct address_initializer_result result;
	open_fixture(&f, source);
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	d = object(&f, index);
	assert(!d->symbol && !d->type && d->initializer && d->initializer->type);
	result = pure_query(&f, d->initializer);
	assert(result.status == status && result.message);
	if (message)
		assert(strcmp(result.message, message) == 0);
	if (status == constant_invalid && d->initializer->kind == expression_pointer_offset) {
		const struct ast_pointer_offset_expression *n = (const struct ast_pointer_offset_expression *)d->initializer;
		struct constant_result integer = evaluate_integer_constant(n->index);
		if (integer.status == constant_invalid) {
			assert(result.message == integer.message);
			assert(result.location.source == integer.location.source && result.location.offset == integer.location.offset);
		}
	}
	close_fixture(&f);
}

static void check_capture_and_origin(void)
{
	struct fixture f;
	struct ast_external_object_declaration *early, *late, *known, *restored;
	struct ast_pointer_offset_expression *offset;
	struct address_initializer_result result;
	const struct ast_array_decay_expression *decay;
	open_fixture(&f, "extern int target[]; int *early=target; extern int target[3];"
		"int *known=target+3; const void *restored=(const void *)((int *)(void *)(target+1)+1); int zero=0; int four=4;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	early = object(&f, 1); late = object(&f, 2); known = object(&f, 3); restored = object(&f, 4);
	assert(early->initializer->kind == expression_array_decay);
	decay = (const struct ast_array_decay_expression *)early->initializer;
	assert(((const struct array_type *)decay->operand->type)->count == 0);
	assert(((const struct array_type *)object(&f, 0)->type)->count == 0);
	assert(((const struct array_type *)late->symbol->type)->count == 3);
	assert(object(&f, 0)->symbol == late->symbol);
	assert(pure_query(&f, early->initializer).address.byte_addend == 0);
	/* Equivalent checked +0 built after canonical completion: source capture
	 * still has no upper extent. The query must not read the canonical bound. */
	offset = ast_new_pointer_offset(&f.arena, early->initializer->location,
		early->initializer, object(&f, 5)->initializer, 4, false);
	assert(offset); offset->expression.type = early->initializer->type;
	assert(pure_query(&f, &offset->expression).status == constant_value);
	assert(pure_query(&f, &offset->expression).address.byte_addend == 0);
	offset->index = object(&f, 6)->initializer;
	/* Position four exceeds the later bound three, but the source-point
	 * declaration had no upper bound. Do not learn one from its symbol. */
	assert(pure_query(&f, &offset->expression).status == constant_value);
	assert(pure_query(&f, &offset->expression).address.byte_addend == 16);
	assert(pure_query(&f, known->initializer).address.byte_addend == 12);
	result = pure_query(&f, restored->initializer);
	assert(result.status == constant_value && result.address.byte_addend == 8);
	assert(((const struct pointer_type *)result.origin_type)->referent->kind == type_kind_int);
	assert(((const struct pointer_type *)restored->initializer->type)->referent->kind == type_kind_void);
	close_fixture(&f);
}

static void check_rollback(void)
{
	struct fixture f;
	struct ast_external_object_declaration *prior, *failed;
	open_fixture(&f, "extern int target[3]; static int *cell; extern int *cell=(target+4)-1;");
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	prior = object(&f, 1); failed = object(&f, 2);
	assert(prior->symbol && prior->symbol->is_internal);
	assert(prior->symbol->type == prior->type);
	assert(prior->symbol->tentative_definition == &prior->external && !prior->symbol->definition);
	assert(!failed->symbol && !failed->type);
	assert(pure_query(&f, failed->initializer).status == constant_invalid);
	close_fixture(&f);

	open_fixture(&f, "extern int target[3]; int *cell=target+1; int *cell=target+2;");
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	prior = object(&f, 1); failed = object(&f, 2);
	assert(prior->symbol->definition == &prior->external);
	assert(prior->symbol->initializer_value.kind == static_data_address);
	assert(prior->symbol->initializer_value.address.byte_addend == 4);
	assert(prior->symbol->initializer_value.address.base.object == object(&f, 0)->symbol);
	assert(!failed->symbol && !failed->type);
	assert(pure_query(&f, prior->initializer).address.byte_addend == 4);
	close_fixture(&f);

	open_fixture(&f, "extern int target[3]; typeof(target+1) cell=(target-1)+1;");
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	assert(declaration(&f, 1)->kind == external_type_declaration);
	{
		struct ast_external_type_declaration *query = (struct ast_external_type_declaration *)declaration(&f, 1);
		assert(!query->type && !query->symbol && !query->object_symbol && query->initializer);
		assert(pure_query(&f, query->initializer).status == constant_invalid);
	}
	close_fixture(&f);
}

static void check_synthetic_limit(void)
{
	struct fixture f;
	struct ast_external_object_expression base = {0};
	struct ast_array_decay_expression decay = {0};
	struct ast_pointer_offset_expression offset = {0};
	struct ast_integer_expression index = {0};
	struct array_type array = { .type = { .kind = type_kind_array }, .element = &type_long, .count = UINT64_MAX/8 };
	struct pointer_type pointer = { .type = { .kind = type_kind_pointer }, .referent = &type_long };
	struct address_initializer_result result;
	open_fixture(&f, "extern long target[3];");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	base.expression = (struct ast_expression){ .kind=expression_external_object, .type=&array.type, .depth=1 };
	base.object = object(&f, 0)->symbol;
	decay.expression = (struct ast_expression){ .kind=expression_array_decay, .type=&pointer.type, .depth=2 };
	decay.operand = &base.expression;
	index.expression = (struct ast_expression){ .kind=expression_integer, .type=&type_ulong_long, .depth=1 };
	index.value = (uint64_t)INT64_MAX/8;
	offset.expression = (struct ast_expression){ .kind=expression_pointer_offset, .type=&pointer.type, .depth=3 };
	offset.base = &decay.expression; offset.index = &index.expression; offset.element_size = 8;
	result = pure_query(&f, &offset.expression);
	assert(result.status == constant_value && result.address.byte_addend == INT64_MAX-7);
	index.value += 1;
	result = pure_query(&f, &offset.expression);
	assert(result.status == constant_invalid);
	assert(strcmp(result.message, "static pointer offset exceeds the relocation addend limit") == 0);
	/* Full unsigned magnitude must not be reinterpreted as signed -1. */
	index.value = UINT64_MAX;
	result = pure_query(&f, &offset.expression);
	assert(result.status == constant_invalid);
	assert(strcmp(result.message, "static pointer offset is outside its captured object bounds") == 0);
	/* Exact signed relocation maximum is representable; the next byte is not.
	 * This is a query-only synthetic domain, never executable source UB. */
	array.element = &type_char; array.count = UINT64_MAX;
	pointer.referent = &type_char; offset.element_size = 1;
	index.value = (uint64_t)INT64_MAX;
	result = pure_query(&f, &offset.expression);
	assert(result.status == constant_value && result.address.byte_addend == INT64_MAX);
	index.value += 1;
	result = pure_query(&f, &offset.expression);
	assert(result.status == constant_invalid);
	assert(strcmp(result.message, "static pointer offset exceeds the relocation addend limit") == 0);
	/* Unknown upper extent is not a licence for unsigned64 wraparound. */
	array.count = 0; index.value = UINT64_MAX;
	result = pure_query(&f, &offset.expression);
	assert(result.status == constant_invalid);
	assert(strcmp(result.message, "static pointer offset exceeds the relocation addend limit") == 0);
	close_fixture(&f);
}

static void check_function_cast_identity(void)
{
	struct fixture f;
	struct ast_function_declaration *prototype;
	struct ast_external_object_declaration *cell;
	struct address_initializer_result result;
	const struct function_type *origin;
	open_fixture(&f, "int target(int); long (*cell)(long)=(long (*)(long))target;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(declaration(&f, 0)->kind == external_function_declaration);
	prototype = (struct ast_function_declaration *)declaration(&f, 0);
	cell = object(&f, 1);
	result = pure_query(&f, cell->initializer);
	assert(result.status == constant_value && result.address.kind == static_address_function);
	assert(result.address.byte_addend == 0 && result.address.base.function == prototype->symbol);
	assert(cell->symbol->initializer_value.kind == static_data_address);
	assert(cell->symbol->initializer_value.address.base.function == prototype->symbol);
	origin = (const struct function_type *)((const struct pointer_type *)result.origin_type)->referent;
	assert(origin->return_type->kind == type_kind_int);
	assert(((const struct function_type *)((const struct pointer_type *)cell->initializer->type)->referent)->return_type->kind == type_kind_long);
	/* Identity proof only: never call through an incompatible signature. */
	close_fixture(&f);
}

int main(void)
{
	static const char bounds[] = "static pointer offset is outside its captured object bounds";
	check_value("extern int target[3]; int *cell=(target+3)-1;", 1, 8);
	check_value("extern int target[3]; int *cell=(target+3)+(-3);", 1, 0);
	check_value("extern int target; int *cell=(&target+1)-1;", 1, 0);
	check_value("extern short target[3]; short *cell=2+target;", 1, 4);
	check_value("extern int target[3]; int *cell=target+(unsigned char)258;", 1, 8);
	check_value("extern int target[3]; int *cell=target+(1?2:1/0);", 1, 8);
	check_value("const char *cell=(\"ab\\0c\" \"d\"+6)-3;", 0, 3);
	check_value("const char *cell=\"\"+1;", 0, 1);
	check_value("extern int target[3]; int *cell=&target[3];", 1, 12);
	check_value("extern int target[3]; int *cell=&*(target+3);", 1, 12);
	check_value("extern int target[3]; int (*cell)[3]=&target+1;", 1, 12);
	check_value("extern int target[2][3]; int (*cell)[3]=target+2;", 1, 24);
	check_value("extern int target[2][3]; int *cell=&target[1][2];", 1, 20);
	check_value("extern int target[2][3]; int *cell=(target[1]+3)-2;", 1, 16);
	check_value("extern int target[2][2][3]; int *cell=&target[1][1][2];", 1, 44);
	check_value("char (*cell)[4]=&\"abc\"+1;", 0, 4);
	check_failure("extern int target[3]; int *cell=(target+4)-1;", 1, constant_invalid, bounds);
	check_failure("extern int target[3]; int *cell=(target-1)+1;", 1, constant_invalid, bounds);
	check_failure("extern int target[3]; int *cell=target+(1/0);", 1, constant_invalid, NULL);
	check_failure("extern int target[3]; int *cell=target+(2147483647+1);", 1, constant_invalid, NULL);
	check_failure("extern int target[3]; int *cell=target+18446744073709551615ULL;", 1, constant_invalid, bounds);
	check_failure("extern int target[3]; int *cell=target-(-9223372036854775807LL-1LL);", 1, constant_invalid, bounds);
	check_failure("extern int target[2][3]; int *cell=target[0]+4;", 1, constant_invalid, bounds);
	check_failure("extern int target[2][3]; int *cell=target[1]-1;", 1, constant_invalid, bounds);
	check_value("extern int target[]; int *cell=target+0;", 1, 0);
	check_failure("extern int target[]; int *cell=(target-1)+1;", 1, constant_invalid, bounds);
	check_failure("extern int target[]; int (*cell)[3]=(int (*)[3])&target+0;", 1, constant_not_constant, NULL);
	check_failure("extern char target[3]; int *cell=(int *)(void *)target+0;", 1, constant_not_constant, NULL);
	check_failure("int *cell=(int *)0+0;", 0, constant_not_constant, NULL);
	check_failure("extern int target[3]; const int n=1; int *cell=target+n;", 2, constant_not_constant, NULL);
	check_failure("extern int target[2][3]; int *cell=target[2];", 1, constant_invalid,
		"static pointer decay requires an existing array subobject");
	check_value("int *cell; int *cell=(int *)&cell;", 1, 0);
	check_value("extern int target[3]; char *cell=(char *)target+1;", 1, 1);
	check_value("extern int target; unsigned char *cell=(unsigned char *)&target+1;", 1, 1);
	check_value("extern int target[3]; char *cell=(char *)(target+1)+3;", 1, 7);
	check_value("extern int target[3]; char *cell=(char *)&target+12;", 1, 12);
	check_value("const int target; int *cell=(int *)(const void *)&target;", 1, 0);
	check_failure("extern int target[3]; char *cell=(char *)target+5;", 1, constant_invalid, bounds);
	check_failure("extern int target[3]; char *cell=(char *)(target+1)-1;", 1, constant_invalid, bounds);
	check_failure("extern long target; int *cell=(int *)&target+1;", 1, constant_not_constant, NULL);
	check_failure("extern int target; int *cell=(int *)((char *)&target+1);", 1, constant_not_constant, NULL);
	check_value("extern int target[3]; int *cell=(int *)(short *)target+2;", 1, 8);
	check_value("extern int target[3]; int *cell=(int *)((char *)target+4)+1;", 1, 8);
	check_failure("extern int target[3]; signed char *cell=(signed char *)((unsigned char *)target+3)+2;",
		1, constant_invalid, bounds);
	check_function_cast_identity();
	check_capture_and_origin();
	check_rollback();
	check_synthetic_limit();
	puts("Address offset AST purity, captures, strict ICE, bounds, int64 limits and rollback passed");
	return 0;
}
