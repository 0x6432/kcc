#include "arena.h"
#include "type.h"

#include <assert.h>
#include <stdio.h>

static const struct type *const integer_types[] = {
	&type_bool, &type_char, &type_schar, &type_uchar, &type_short,
	&type_ushort, &type_int, &type_uint, &type_long, &type_ulong,
	&type_long_long, &type_ulong_long,
};

static void test_leaf_qualification(struct arena *arena)
{
	const struct type *qualified_void;

	for (size_t i = 0; i < sizeof(integer_types) / sizeof(integer_types[0]); i++) {
		const struct type *plain = integer_types[i];
		const struct type *qualified = type_qualified(arena, plain, type_qualifier_const);
		const struct type *unqualified;

		assert(qualified && qualified != plain);
		assert(!plain->qualifiers && qualified->qualifiers == type_qualifier_const);
		assert(qualified->kind == plain->kind);
		assert(type_qualified(arena, qualified, type_qualifier_const) == qualified);
		assert(type_qualified(arena, qualified, 0) == qualified);
		assert(type_unqualified(arena, plain) == plain);
		assert(type_is_integer(qualified) && type_is_scalar(qualified));
		assert(type_is_object(qualified) && type_is_complete_object(qualified));
		assert(type_object_size(qualified) == type_object_size(plain));
		assert(type_object_alignment(qualified) == type_object_alignment(plain));
		assert(type_value_width(qualified) == type_value_width(plain));
		assert(type_integer_width(qualified) == type_integer_width(plain));
		assert(type_is_unsigned(qualified) == type_is_unsigned(plain));
		assert(!type_compatible(qualified, plain) && !type_compatible(plain, qualified));
		assert(type_unqualified_compatible(qualified, plain));
		assert(type_unqualified_compatible(plain, qualified));
		assert(type_composite(arena, qualified, qualified) == qualified);
		unqualified = type_unqualified(arena, qualified);
		assert(unqualified && !unqualified->qualifiers);
		assert(type_compatible(unqualified, plain));
		assert(qualified->qualifiers == type_qualifier_const && !plain->qualifiers);
		for (size_t j = 0; j < sizeof(integer_types) / sizeof(integer_types[0]); j++) {
			assert(type_compatible(unqualified, integer_types[j]) == (i == j));
			assert(type_unqualified_compatible(qualified, integer_types[j]) == (i == j));
		}
	}
	qualified_void = type_qualified(arena, &type_void, type_qualifier_const);

	assert(qualified_void && type_is_object(qualified_void));
	assert(!type_is_complete_object(qualified_void) && !type_is_scalar(qualified_void));
	assert(!type_compatible(qualified_void, &type_void));
	assert(type_unqualified_compatible(qualified_void, &type_void));
	assert(type_compatible(type_unqualified(arena, qualified_void), &type_void));
	assert(!type_void.qualifiers);
}

static void test_pointer_levels(struct arena *arena)
{
	const struct type *qualified_int = type_qualified(arena, &type_int, type_qualifier_const);
	struct pointer_type *plain = type_new_pointer(arena, &type_int);
	struct pointer_type *to_const = type_new_pointer(arena, qualified_int);
	const struct type *const_pointer = type_qualified(arena, &plain->type, type_qualifier_const);
	const struct type *both = type_qualified(arena, &to_const->type, type_qualifier_const);
	const struct type *unqualified = type_unqualified(arena, both);
	struct pointer_type *nested_plain = type_new_pointer(arena, &plain->type);
	struct pointer_type *nested_qualified = type_new_pointer(arena, const_pointer);
	struct pointer_type *nested_pointee_const = type_new_pointer(arena, &to_const->type);

	assert(qualified_int && plain && to_const && const_pointer && both && unqualified);
	assert(nested_plain && nested_qualified && nested_pointee_const);
	assert(!plain->type.qualifiers && plain->referent == &type_int);
	assert(((const struct pointer_type *)const_pointer)->referent == &type_int);
	assert(type_object_size(const_pointer) == 8 && type_value_width(const_pointer) == 64);
	assert(!type_compatible(const_pointer, &plain->type));
	assert(type_unqualified_compatible(const_pointer, &plain->type));
	assert(!type_unqualified_compatible(&to_const->type, &plain->type));
	assert(!type_unqualified_compatible(both, const_pointer));
	assert(type_compatible(unqualified, &to_const->type));
	assert(((const struct pointer_type *)unqualified)->referent == qualified_int);
	assert(!type_unqualified_compatible(&nested_plain->type, &nested_qualified->type));
	assert(!type_unqualified_compatible(&nested_plain->type, &nested_pointee_const->type));
	assert(both->qualifiers == type_qualifier_const && !to_const->type.qualifiers);
}

static void test_array_qualification(struct arena *arena)
{
	struct array_type *row = type_new_array(arena, &type_int, 3);
	struct array_type *matrix = type_new_array(arena, &row->type, 2);
	const struct type *qualified = type_qualified(arena, &matrix->type, type_qualifier_const);
	const struct array_type *outer = (const struct array_type *)qualified;
	const struct array_type *inner = (const struct array_type *)outer->element;
	const struct type *unqualified = type_unqualified(arena, qualified);
	struct array_type *unknown = type_new_incomplete_array(arena, &type_int);
	const struct type *qualified_unknown = type_qualified(arena, &unknown->type, type_qualifier_const);
	struct pointer_type *pointer = type_new_pointer(arena, &type_int);
	struct array_type *pointers = type_new_array(arena, &pointer->type, 2);
	const struct type *qualified_pointers = type_qualified(arena, &pointers->type, type_qualifier_const);
	const struct type *pointer_element = ((const struct array_type *)qualified_pointers)->element;
	struct pointer_type *to_const = type_new_pointer(arena, inner->element);
	struct array_type *const_pointees = type_new_array(arena, &to_const->type, 2);

	assert(row && matrix && qualified && unqualified && unknown && qualified_unknown);
	assert(pointer && pointers && qualified_pointers && to_const && const_pointees);
	assert(outer->count == 2 && inner->count == 3);
	assert(qualified->qualifiers == type_qualifier_const);
	assert(inner->type.qualifiers == type_qualifier_const);
	assert(inner->element->qualifiers == type_qualifier_const);
	assert(!matrix->type.qualifiers && !row->type.qualifiers && !type_int.qualifiers);
	assert(type_object_size(qualified) == 24 && type_object_alignment(qualified) == 4);
	assert(type_compatible(unqualified, &matrix->type));
	assert(!type_compatible(qualified, &matrix->type));
	assert(type_unqualified_compatible(qualified, &matrix->type));
	assert(type_unqualified_compatible(&matrix->type, qualified));
	assert(((const struct array_type *)qualified_unknown)->count == 0);
	assert(!type_is_complete_object(qualified_unknown));
	assert(type_compatible(qualified_unknown, &inner->type));
	assert(!type_compatible(qualified_unknown, &row->type));
	assert(pointer_element->qualifiers == type_qualifier_const);
	assert(((const struct pointer_type *)pointer_element)->referent == &type_int);
	assert(type_unqualified_compatible(qualified_pointers, &pointers->type));
	assert(!const_pointees->type.qualifiers);
	assert(!type_unqualified_compatible(qualified_pointers, &const_pointees->type));
}

static void test_qualified_composite(struct arena *arena)
{
	const struct type *qualified_int = type_qualified(arena, &type_int, type_qualifier_const);
	struct array_type *unknown = type_new_incomplete_array(arena, qualified_int);
	struct array_type *known = type_new_array(arena, qualified_int, 3);
	struct pointer_type *left = type_new_pointer(arena, &unknown->type);
	struct pointer_type *right = type_new_pointer(arena, &known->type);
	const struct type *a = type_qualified(arena, &left->type, type_qualifier_const);
	const struct type *b = type_qualified(arena, &right->type, type_qualifier_const);
	const struct type *composite = type_composite(arena, a, b);
	const struct pointer_type *pointer = (const struct pointer_type *)composite;
	const struct array_type *array = (const struct array_type *)pointer->referent;
	struct array_type *a_outer = type_new_array(arena, a, 2);
	struct array_type *b_outer = type_new_array(arena, b, 2);
	const struct type *outer = type_composite(arena, &a_outer->type, &b_outer->type);

	assert(qualified_int && unknown && known && left && right && a && b && composite);
	assert(a_outer && b_outer && outer);
	assert(composite != a && composite->qualifiers == type_qualifier_const);
	assert(array->count == 3 && array->type.qualifiers == type_qualifier_const);
	assert(type_compatible(array->element, qualified_int));
	assert(type_compatible(composite, b));
	assert(type_composite(arena, b, a) == b);
	assert(unknown->count == 0 && !left->type.qualifiers && !right->type.qualifiers);
	assert(outer->qualifiers == type_qualifier_const);
	assert(type_compatible(((const struct array_type *)outer)->element, b));
}

static void test_function_referents(struct arena *arena)
{
	const struct type *qualified_int = type_qualified(arena, &type_int, type_qualifier_const);
	struct pointer_type *plain = type_new_pointer(arena, &type_int);
	struct pointer_type *to_const = type_new_pointer(arena, qualified_int);
	const struct type *a_parameters[] = { &plain->type };
	const struct type *b_parameters[] = { &to_const->type };
	struct function_type *a = type_new_function(arena, &type_int, a_parameters, 1);
	struct function_type *b = type_new_function(arena, &type_int, b_parameters, 1);
	struct pointer_type *pointer = type_new_pointer(arena, &a->type);
	const struct type *qualified_pointer = type_qualified(arena, &pointer->type, type_qualifier_const);

	assert(qualified_int && plain && to_const && a && b && pointer && qualified_pointer);
	assert(type_unqualified(arena, &a->type) == &a->type);
	assert(type_qualified(arena, &a->type, 0) == &a->type);
	assert(!type_compatible(&a->type, &b->type));
	assert(!type_unqualified_compatible(&a->type, &b->type));
	assert(((const struct pointer_type *)qualified_pointer)->referent == &a->type);
	assert(type_unqualified_compatible(qualified_pointer, &pointer->type));
	assert(!a->type.qualifiers && a->parameters->type == &plain->type);
	{
		struct function_type *v = type_new_function(arena, &type_int, a_parameters, 1);
		const struct type *composite;

		assert(v);
		v->variadic = true;
		assert(!type_compatible(&a->type, &v->type));
		composite = type_composite(arena, &v->type, &v->type);
		assert(composite && ((const struct function_type *)composite)->variadic);
	}

}

static void test_bounded_layers(struct arena *arena)
{
	const struct type *pointer = &type_int;
	const struct type *array = &type_int;
	const struct type *qualified_pointer;
	const struct type *qualified_array;

	for (size_t i = 0; i < 64; i++) {
		struct pointer_type *next_pointer = type_new_pointer(arena, pointer);
		struct array_type *next_array = type_new_array(arena, array, 1);

		assert(next_pointer && next_array);
		pointer = &next_pointer->type;
		array = &next_array->type;
	}
	qualified_pointer = type_qualified(arena, pointer, type_qualifier_const);
	qualified_array = type_qualified(arena, array, type_qualifier_const);

	assert(qualified_pointer && qualified_array);
	assert(type_unqualified_compatible(pointer, qualified_pointer));
	assert(type_unqualified_compatible(array, qualified_array));
	assert(type_compatible(pointer, type_unqualified(arena, qualified_pointer)));
	assert(type_compatible(array, type_unqualified(arena, qualified_array)));
	assert(!pointer->qualifiers && !array->qualifiers);
}

static void test_nullptr_type(struct arena *arena)
{
	const struct type *qualified = type_qualified(arena, &type_nullptr, type_qualifier_const);
	struct pointer_type *pointer = type_new_pointer(arena, &type_nullptr);
	struct array_type *array = type_new_array(arena, &type_nullptr, 2);
	struct function_type *function = type_new_function(arena, &type_nullptr, NULL, 0);

	assert(type_is_scalar(&type_nullptr) && type_is_complete_object(&type_nullptr));
	assert(type_is_object(&type_nullptr) && !type_is_integer(&type_nullptr));
	assert(type_nullptr.kind != type_kind_pointer && !type_nullptr.qualifiers);
	assert(type_value_width(&type_nullptr) == 64 && type_object_size(&type_nullptr) == 8);
	assert(type_object_alignment(&type_nullptr) == 8);
	assert(qualified && !type_compatible(qualified, &type_nullptr));
	assert(type_unqualified_compatible(qualified, &type_nullptr));
	assert(type_compatible(type_unqualified(arena, qualified), &type_nullptr));
	assert(type_composite(arena, &type_nullptr, type_unqualified(arena, qualified)) == &type_nullptr);
	assert(!type_compatible(&type_nullptr, &type_ulong) && !type_compatible(&type_nullptr, &type_void));
	assert(pointer && pointer->referent == &type_nullptr && !type_compatible(&pointer->type, &type_nullptr));
	assert(array && type_object_size(&array->type) == 16 && type_object_alignment(&array->type) == 8);
	assert(function && function->return_type == &type_nullptr);
	assert(!type_nullptr.qualifiers && qualified->qualifiers == type_qualifier_const);
}


static void test_enum_types(struct arena *arena)
{
	struct enum_definition first = { .complete = true };
	struct enum_definition second = { .complete = true };
	struct enum_type a = { .type = { .kind = type_kind_enum }, .definition = &first };
	struct enum_type b = { .type = { .kind = type_kind_enum }, .definition = &second };
	const struct type *qualified = type_qualified(arena, &a.type, type_qualifier_const);
	const struct type *unqualified = type_unqualified(arena, qualified);
	assert(qualified && unqualified);
	assert(type_is_integer(&a.type) && type_is_complete_object(&a.type));
	assert(type_object_size(&a.type) == 4 && type_object_alignment(&a.type) == 4);
	assert(type_integer_promotion(&a.type) == &type_int);
	assert(type_compatible(&a.type, &type_int) && !type_same(&a.type, &type_int));
	assert(type_composite(arena, &type_int, &a.type) == &a.type);
	assert(type_composite(arena, &a.type, &type_int) == &a.type);
	assert(!type_compatible(&a.type, &b.type));
	assert(type_same(&a.type, unqualified));
	assert(type_unqualified_compatible(qualified, &a.type));
	assert(!type_compatible(qualified, &a.type));
	first.complete = false;
	assert(!type_is_complete_object(&a.type) && !type_is_complete_object(qualified));
	{
		struct enum_definition fixed = { .complete = true, .fixed = true, .underlying = &type_ushort };
		struct enum_definition wide = { .complete = true, .fixed = true, .underlying = &type_ulong_long };
		struct enum_type small = { .type = { .kind = type_kind_enum }, .definition = &fixed };
		struct enum_type large = { .type = { .kind = type_kind_enum }, .definition = &wide };
		assert(type_is_unsigned(&small.type) && type_integer_width(&small.type) == 16);
		assert(type_object_size(&small.type) == 2 && type_integer_promotion(&small.type) == &type_int);
		assert(type_compatible(&small.type, &type_ushort) && !type_compatible(&small.type, &type_int));
		assert(type_composite(arena, &type_ushort, &small.type) == &small.type);
		assert(type_is_unsigned(&large.type) && type_integer_width(&large.type) == 64);
		assert(type_integer_promotion(&large.type) == &type_ulong_long);
		assert(type_compatible(&large.type, &type_ulong_long) && !type_compatible(&large.type, &small.type));
	}
}

static void test_runtime_array_qualification(struct arena *arena)
{
	struct array_type *runtime = type_new_incomplete_array(arena, &type_int);
	struct array_type *incomplete = type_new_incomplete_array(arena, &type_int);
	const struct type *qualified, *unqualified, *composite;
	assert(runtime && incomplete);
	runtime->runtime_bound = true;
	qualified = type_qualified(arena, &runtime->type, type_qualifier_const);
	assert(qualified && ((const struct array_type *)qualified)->runtime_bound);
	unqualified = type_unqualified(arena, qualified);
	assert(unqualified && ((const struct array_type *)unqualified)->runtime_bound);
	composite = type_composite(arena, &incomplete->type, &runtime->type);
	assert(composite && ((const struct array_type *)composite)->runtime_bound);
	assert(!incomplete->runtime_bound && runtime->runtime_bound);
}

/* These semantic types are internal only: source and ABI lowering still reject
 * non-native widths. Exercise identity and C integer conversions independently. */
static void test_bitint_width_types(struct arena *arena)
{
	assert(!type_bitint(0, true) && !type_bitint(1, false));
	assert(!type_bitint(65, true) && !type_bitint(65, false));
	for (unsigned w = 1; w <= 64; w++) {
		for (unsigned u = 0; u < 2; u++) {
			const struct type *t = type_bitint(w, u != 0);
			if (w == 1 && !u) { assert(!t); continue; }
			const struct type *q = type_qualified(arena, t, type_qualifier_const);
			unsigned size = w <= 8 ? 1 : w <= 16 ? 2 : w <= 32 ? 4 : 8;
			assert(type_bitint_width_lowerable(w) == (w == 8 || w == 16 || w == 32 || w == 64));
			assert(t && q && type_is_bitint(t) && type_is_integer(t));
			assert(type_integer_width(q) == w && type_is_unsigned(q) == (u != 0));
			assert(type_object_size(q) == size && type_object_alignment(q) == size);
			assert(type_integer_promotion(t) == t);
			assert(!type_compatible(q, t) && type_unqualified_compatible(q, t));
			assert(type_compatible(type_unqualified(arena, q), t));
			for (unsigned v = 1; v <= 64; v++) {
				for (unsigned z = 0; z < 2; z++) {
					const struct type *other = type_bitint(v, z != 0);
					if (!other) continue;
					assert(type_compatible(t, other) == (w == v && u == z));
					const struct type *expected = w > v ? t : v > w ? other :
						type_bitint(w, u || z);
					assert(type_compatible(type_usual_arithmetic(t, other), expected));
				}
			}
			/* Mixed with int and unsigned int after integer promotions. */
			const struct type *si = w > 32 ? t : &type_int;
			if (w == 32 && u) si = &type_uint;
			const struct type *ui = w > 32 ? t : &type_uint;
			assert(type_compatible(type_usual_arithmetic(t, &type_int), si));
			assert(type_compatible(type_usual_arithmetic(&type_uint, t), ui));
			assert(type_compatible(type_usual_arithmetic(t, &type_long),
				w == 64 && u ? &type_ulong : &type_long));
			assert(type_compatible(type_usual_arithmetic(t, &type_ulong), &type_ulong));
			assert(type_compatible(type_usual_arithmetic(t, &type_long_long),
				w == 64 && u ? &type_ulong_long : &type_long_long));
			assert(type_compatible(type_usual_arithmetic(t, &type_ulong_long), &type_ulong_long));
		}
	}
	/* Do not expose an aggregate ABI simply because a semantic type exists. */
	struct record_member member = { .type = type_bitint(5, false) };
	struct record_definition def = { .complete = true, .members = &member, .member_count = 1,
		.size = 1, .alignment = 1 };
	struct record_type record = { .type = { .kind = type_kind_struct }, .definition = &def };
	struct aggregate_abi abi;
	assert(!type_aggregate_abi(&record.type, &abi));
	def.size = 24; /* MEMORY classification must not bypass the guard. */
	assert(!type_aggregate_abi(&record.type, &abi));
}

int main(void)
{
	struct arena arena = {0};

	test_bitint_width_types(&arena);
	test_enum_types(&arena);
	test_runtime_array_qualification(&arena);
	test_nullptr_type(&arena);
	test_leaf_qualification(&arena);
	test_pointer_levels(&arena);
	test_array_qualification(&arena);
	test_qualified_composite(&arena);
	test_function_referents(&arena);
	test_bounded_layers(&arena);
	arena_destroy(&arena);
	puts("Type qualification tests passed");
	return 0;
}
