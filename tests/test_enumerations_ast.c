/* Independent M18 enum AST/type/ICE/rollback invariants.
 * Build with compiler sources excluding main.c, -Isrc; run under both host sanitizers.
 * Names remain checked expression_enumerator leaves, never object slots/loads.
 */
#include "parse.h"
#include "sema.h"
#include "consteval.h"
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
	assert(source_from_bytes(&f->source, "enumerations-ast.c",
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

static struct ast_enum_type_syntax *enumeration(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = declaration(f, index);
	assert(d->kind == external_declaration_tag);
	struct ast_tag_declaration *tag = ((struct ast_external_tag_declaration *)d)->declaration;
	assert(tag->type_syntax->kind == type_syntax_enum);
	return (struct ast_enum_type_syntax *)tag->type_syntax;
}

static struct ast_external_object_declaration *object(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = declaration(f, index);
	assert(d->kind == external_object_declaration);
	return (struct ast_external_object_declaration *)d;
}

static struct ast_expression *unconverted(struct ast_expression *e)
{
	while (e->kind == expression_conversion)
		e = ((struct ast_conversion_expression *)e)->operand;
	return e;
}

static void check_enum_shape_and_compatible_types(void)
{
	struct fixture f;
	open_fixture(&f, "enum U { ZERO, ANSWER=42 }; enum U value=ANSWER;"
		"const enum U frozen=ANSWER; enum S { NEG=-1 }; enum S negative=NEG;");
	struct ast_enum_type_syntax *u = enumeration(&f, 0), *s = enumeration(&f, 3);
	assert(!u->syntax.type && !s->syntax.type);
	assert(u->has_definition && u->enumerator_count == 2);
	assert(!u->enumerators->value && u->enumerators->next->value);
	assert(!u->enumerators->type && !u->enumerators->next->type);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors);
	const struct type *ut = u->syntax.type, *st = s->syntax.type;
	assert(ut->kind == type_kind_enum && st->kind == type_kind_enum);
	assert(type_enum_definition(ut)->complete && type_enum_definition(st)->complete);
	assert(type_enum_definition(ut)->compatible_type == &type_uint);
	assert(type_enum_definition(st)->compatible_type == &type_int);
	assert(type_is_integer(ut) && type_is_scalar(ut) && type_is_complete_object(ut));
	assert(type_object_size(ut) == 4 && type_object_alignment(ut) == 4);
	assert(type_integer_width(ut) == 32 && type_is_unsigned(ut));
	assert(!type_is_unsigned(st));
	assert(type_integer_promotion(ut) == &type_uint);
	assert(type_integer_promotion(st) == &type_int);
	assert(type_compatible(ut, &type_uint) && !type_same(ut, &type_uint));
	assert(!type_compatible(ut, &type_int));
	assert(type_compatible(st, &type_int) && !type_same(st, &type_int));
	assert(!type_same(ut, st) && !type_compatible(ut, st));
	struct ast_external_object_declaration *value = object(&f, 1), *frozen = object(&f, 2);
	assert(value->type == ut && type_enum_definition(frozen->type) == type_enum_definition(ut));
	assert(frozen->type->qualifiers & type_qualifier_const);
	assert(!(ut->qualifiers & type_qualifier_const));
	assert(value->symbol && frozen->symbol && object(&f, 4)->symbol);
	assert(value->symbol->initializer_value.integer_bits == 42);
	assert(object(&f, 4)->symbol->initializer_value.integer_bits == UINT32_MAX);
	assert(!f.unit->static_declarations && !f.unit->strings);
	close_fixture(&f);
}

static void check_exact_enumerator_leaf_and_query_purity(void)
{
	struct fixture f;
	open_fixture(&f, "enum E { BASE=40, ANSWER=BASE+2 }; int cell=ANSWER;");
	struct ast_enum_type_syntax *syntax = enumeration(&f, 0);
	struct ast_enumerator *base = syntax->enumerators, *answer = base->next;
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(base->type == &type_int && base->bits == 40);
	assert(answer->type == &type_int && answer->bits == 42);
	struct ast_expression *e = unconverted(object(&f, 1)->initializer);
	assert(e->kind == expression_enumerator && e->type == &type_int);
	assert(e->depth == 1 && !e->is_lvalue);
	struct ast_enumerator_expression *leaf = (struct ast_enumerator_expression *)e;
	assert(leaf->enumerator == answer && leaf->bits == 42);
	struct ast_enumerator_expression saved_leaf;
	struct ast_enumerator saved_answer, saved_base;
	struct enum_definition saved_definition;
	struct ast_enum_type_syntax saved_syntax;
	memcpy(&saved_leaf, leaf, sizeof saved_leaf);
	memcpy(&saved_answer, answer, sizeof saved_answer);
	memcpy(&saved_base, base, sizeof saved_base);
	memcpy(&saved_definition, type_enum_definition(syntax->syntax.type), sizeof saved_definition);
	memcpy(&saved_syntax, syntax, sizeof saved_syntax);
	for (unsigned i = 0; i < 32; ++i) {
		struct constant_result r = evaluate_integer_constant(e);
		assert(r.status == constant_value && r.type == &type_int && r.bits == 42);
		assert(r.location.source == e->location.source && r.location.offset == e->location.offset);
		struct constant_result expression = evaluate_integer_constant(answer->value);
		assert(expression.status == constant_value && expression.bits == 42);
		assert(memcmp(&saved_leaf, leaf, sizeof saved_leaf) == 0);
		assert(memcmp(&saved_answer, answer, sizeof saved_answer) == 0);
		assert(memcmp(&saved_base, base, sizeof saved_base) == 0);
		assert(memcmp(&saved_definition, type_enum_definition(syntax->syntax.type), sizeof saved_definition) == 0);
		assert(memcmp(&saved_syntax, syntax, sizeof saved_syntax) == 0);
		assert(!f.diagnostics.errors);
	}
	close_fixture(&f);
}

static void check_signed_bits_and_no_storage(void)
{
	struct fixture f;
	open_fixture(&f, "enum E { LOW=-2147483647-1, NEXT, NEG=-1, ZERO, HIGH=2147483647 };");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	struct ast_enum_type_syntax *syntax = enumeration(&f, 0);
	const uint64_t bits[] = { UINT64_C(2147483648), UINT64_C(2147483649), UINT32_MAX, 0, INT32_MAX };
	struct ast_enumerator *item = syntax->enumerators;
	for (unsigned i = 0; i < sizeof bits / sizeof bits[0]; ++i) {
		assert(item && item->bits == bits[i] && item->type == &type_int);
		item = item->next;
	}
	assert(!item && !f.unit->static_declarations && !f.unit->strings);
	assert(f.unit->declarations && !f.unit->declarations->next);
	close_fixture(&f);
}

static void check_same_representation_distinct_nominal_types(void)
{
	struct fixture f;
	open_fixture(&f, "enum E { A=0 }; enum F { B=0 }; enum E first; enum E second;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	const struct type *e = enumeration(&f, 0)->syntax.type, *other = enumeration(&f, 1)->syntax.type;
	assert(type_is_unsigned(e) && type_is_unsigned(other));
	assert(!type_same(e, other) && !type_compatible(e, other));
	assert(type_same(object(&f, 2)->type, object(&f, 3)->type));
	assert(type_same(e, object(&f, 2)->type));
	const struct type *qualified = type_qualified(&f.arena, e, type_qualifier_const);
	assert(qualified && qualified != e && type_enum_definition(qualified) == type_enum_definition(e));
	assert(type_unqualified(&f.arena, qualified) && !(e->qualifiers & type_qualifier_const));
	struct enum_definition before;
	memcpy(&before, type_enum_definition(e), sizeof before);
	const struct type *composite = type_composite(&f.arena, e, &type_uint);
	assert(composite && type_compatible(composite, e));
	assert(memcmp(&before, type_enum_definition(e), sizeof before) == 0);
	close_fixture(&f);
}

static void check_shared_syntax_not_resolved_twice(void)
{
	struct fixture f;
	open_fixture(&f, "enum E { A=42 } first=A, second=A;");
	struct ast_external_object_declaration *first = object(&f, 0), *second = object(&f, 1);
	assert(first->type_syntax == second->type_syntax);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(first->type && first->type == second->type);
	assert(first->symbol != second->symbol);
	assert(first->symbol->initializer_value.integer_bits == 42);
	assert(second->symbol->initializer_value.integer_bits == 42);
	close_fixture(&f);
}

static void check_promoted_shift_operand_and_result_identity(void)
{
	struct fixture f;
	open_fixture(&f, "enum U { A=1 }; enum S { NEG=-1 };"
		"unsigned ul=(enum U)1<<1; unsigned ur=(enum U)4>>1;"
		"int sl=(enum S)1<<1; int sr=(enum S)4>>1;"
		"unsigned up=+(enum U)1; unsigned ub=(enum U)1+1;"
		"int sp=+(enum S)1; int sb=(enum S)1+1;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(!f.diagnostics.errors);
	/* Assignment result/ABI coincidence cannot prove expression identity:
	 * inspect the binary node and its converted operands before assignment.
	 * In particular enum-compatible uint is NOT the canonical uint type. */
	for (unsigned i = 0; i < 4; ++i) {
		struct ast_expression *root = unconverted(object(&f, i + 2)->initializer);
		const struct type *expected = i < 2 ? &type_uint : &type_int;
		assert(root->kind == expression_binary && root->type == expected);
		struct ast_binary_expression *binary = (struct ast_binary_expression *)root;
		assert(binary->left->type == expected);
		assert(binary->right->type == &type_int);
		assert(binary->left->kind == expression_conversion);
		struct constant_result value = evaluate_integer_constant(root);
		assert(value.status == constant_value && value.type == expected && value.bits == 2);
	}
	for (unsigned i = 0; i < 4; ++i) {
		struct ast_expression *root = unconverted(object(&f, i + 6)->initializer);
		const struct type *expected = i < 2 ? &type_uint : &type_int;
		assert(root->type == expected);
		if (i % 2 == 0) {
			assert(root->kind == expression_unary);
			assert(((struct ast_unary_expression *)root)->operand->type == expected);
		} else {
			assert(root->kind == expression_binary);
			struct ast_binary_expression *binary = (struct ast_binary_expression *)root;
			assert(binary->left->type == expected && binary->right->type == expected);
		}
	}
	close_fixture(&f);
}

static void check_failed_definition_rolls_back_values_and_syntax(void)
{
	const char *sources[] = {
		"enum Good { KEPT=42 }; enum Bad { FIRST=1, FAIL=1/0 };",
		"enum Good { KEPT=42 }; enum Bad { FIRST=1, FIRST=2 };",
		"enum Good { KEPT=42 }; enum Bad { FIRST=1, HUGE=2147483648U };",
		"enum Good { KEPT=42 }; enum Bad { FIRST=1, SELF=sizeof(enum Bad *) };",
	};
	for (unsigned n = 0; n < sizeof sources / sizeof sources[0]; ++n) {
		struct fixture f;
		open_fixture(&f, sources[n]);
		struct ast_enum_type_syntax *good = enumeration(&f, 0), *bad = enumeration(&f, 1);
		assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
		assert(f.diagnostics.errors == 1);
		assert(good->syntax.type && type_enum_definition(good->syntax.type)->complete);
		assert(good->enumerators->bits == 42 && good->enumerators->type == &type_int);
		assert(!bad->syntax.type);
		for (struct ast_enumerator *e = bad->enumerators; e; e = e->next)
			assert(!e->type && !e->bits);
		assert(!f.unit->static_declarations);
		close_fixture(&f);
	}
}

static void check_failed_enclosing_initializer_publication(void)
{
	struct fixture f;
	open_fixture(&f, "int kept=42; int failed=sizeof(enum E { NEW=1 })+1/0;");
	struct ast_external_object_declaration *kept = object(&f, 0), *failed = object(&f, 1);
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1 && kept->symbol && kept->type);
	assert(kept->symbol->initializer_value.integer_bits == 42);
	assert(!failed->symbol && !failed->type);
	assert(!kept->symbol->next);
	assert(failed->initializer_syntax && !failed->initializer_plan);
	close_fixture(&f);
}

int main(void)
{
	check_enum_shape_and_compatible_types();
	check_exact_enumerator_leaf_and_query_purity();
	check_signed_bits_and_no_storage();
	check_same_representation_distinct_nominal_types();
	check_shared_syntax_not_resolved_twice();
	check_promoted_shift_operand_and_result_identity();
	check_failed_definition_rolls_back_values_and_syntax();
	check_failed_enclosing_initializer_publication();
	puts("enumeration AST/type/ICE/rollback invariants passed");
	return 0;
}
