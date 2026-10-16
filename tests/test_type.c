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

int main(void)
{
	struct arena arena = {0};

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
