#include "type.h"

#include <assert.h>

const struct type type_bool = { type_kind_bool };
const struct type type_char = { type_kind_char };
const struct type type_schar = { type_kind_schar };
const struct type type_uchar = { type_kind_uchar };
const struct type type_short = { type_kind_short };
const struct type type_ushort = { type_kind_ushort };
const struct type type_int = { type_kind_int };
const struct type type_uint = { type_kind_uint };
const struct type type_long = { type_kind_long };
const struct type type_ulong = { type_kind_ulong };
const struct type type_long_long = { type_kind_long_long };
const struct type type_ulong_long = { type_kind_ulong_long };

struct integer_properties {
	enum type_kind kind;
	unsigned width;
	unsigned rank;
	bool unsigned_type;
	const struct type *unsigned_counterpart;
};

/* Target LP64 properties, independent of the compiler host's long width. */
static const struct integer_properties integer_properties[] = {
	/* Bool has eight storage bits but only the values 0 and 1. */
	{ type_kind_bool, 8, 0, true, &type_bool },
	{ type_kind_char, 8, 1, false, &type_uchar },
	{ type_kind_schar, 8, 1, false, &type_uchar },
	{ type_kind_uchar, 8, 1, true, &type_uchar },
	{ type_kind_short, 16, 2, false, &type_ushort },
	{ type_kind_ushort, 16, 2, true, &type_ushort },
	{ type_kind_int, 32, 3, false, &type_uint },
	{ type_kind_uint, 32, 3, true, &type_uint },
	{ type_kind_long, 64, 4, false, &type_ulong },
	{ type_kind_ulong, 64, 4, true, &type_ulong },
	{ type_kind_long_long, 64, 5, false, &type_ulong_long },
	{ type_kind_ulong_long, 64, 5, true, &type_ulong_long },
};

bool type_is_integer(const struct type *type)
{
	for (size_t i = 0; i < sizeof(integer_properties) / sizeof(integer_properties[0]); i++)
		if (integer_properties[i].kind == type->kind)
			return true;
	return false;
}

static const struct integer_properties *integer_properties_for(const struct type *type)
{
	for (size_t i = 0; i < sizeof(integer_properties) / sizeof(integer_properties[0]); i++)
		if (integer_properties[i].kind == type->kind)
			return &integer_properties[i];
	assert(0 && "integer properties requested for noninteger type");
	return NULL;
}

bool type_is_unsigned(const struct type *type)
{
	return integer_properties_for(type)->unsigned_type;
}

unsigned type_integer_width(const struct type *type)
{
	return integer_properties_for(type)->width;
}

/* All implemented types below int fit in int, including unsigned char/short. */
const struct type *type_integer_promotion(const struct type *type)
{
	if (type_integer_width(type) < 32)
		return &type_int;
	return type;
}

const struct type *type_usual_arithmetic(const struct type *left, const struct type *right)
{
	const struct integer_properties *a;
	const struct integer_properties *b;
	const struct type *unsigned_type;
	const struct type *signed_type;
	const struct integer_properties *unsigned_properties;
	const struct integer_properties *signed_properties;

	left = type_integer_promotion(left);
	right = type_integer_promotion(right);
	a = integer_properties_for(left);
	b = integer_properties_for(right);
	if (a->unsigned_type == b->unsigned_type)
		return a->rank >= b->rank ? left : right;
	unsigned_type = a->unsigned_type ? left : right;
	signed_type = a->unsigned_type ? right : left;
	unsigned_properties = integer_properties_for(unsigned_type);
	signed_properties = integer_properties_for(signed_type);
	if (unsigned_properties->rank >= signed_properties->rank)
		return unsigned_type;
	if (signed_properties->width > unsigned_properties->width)
		return signed_type;
	return signed_properties->unsigned_counterpart;
}

static bool integer_literal_fits(uint64_t value, const struct type *type)
{
	unsigned width = type_integer_width(type);

	if (type_is_unsigned(type))
		return width == 64 || value <= UINT32_MAX;
	return value <= (width == 64 ? (uint64_t)INT64_MAX : (uint64_t)INT32_MAX);
}

/* Candidates are in standard rank order, not chosen by truncation/sign bits. */
const struct type *type_integer_literal(uint64_t value, unsigned base,
	bool unsigned_suffix, unsigned long_suffix)
{
	const struct type *candidates[6];
	size_t count = 0;

	if (long_suffix > 2)
		return NULL;
	if (!long_suffix) {
		if (!unsigned_suffix)
			candidates[count++] = &type_int;
		if (unsigned_suffix || base != 10)
			candidates[count++] = &type_uint;
	}
	if (long_suffix < 2) {
		if (!unsigned_suffix)
			candidates[count++] = &type_long;
		if (unsigned_suffix || base != 10)
			candidates[count++] = &type_ulong;
	}
	if (!unsigned_suffix)
		candidates[count++] = &type_long_long;
	if (unsigned_suffix || base != 10)
		candidates[count++] = &type_ulong_long;
	for (size_t i = 0; i < count; i++)
		if (integer_literal_fits(value, candidates[i]))
			return candidates[i];
	return NULL;
}

struct function_type *type_new_function(struct arena *arena, const struct type *return_type,
	const struct type *const *parameters, size_t parameter_count)
{
	struct function_type *type = arena_alloc(arena, sizeof(*type));
	struct function_parameter_type **tail;

	if (!type)
		return NULL;
	*type = (struct function_type) {
		.type = { type_kind_function },
		.return_type = return_type,
		.parameter_count = parameter_count,
	};
	tail = &type->parameters;
	for (size_t i = 0; i < parameter_count; i++) {
		struct function_parameter_type *parameter = arena_alloc(arena, sizeof(*parameter));

		if (!parameter)
			return NULL;
		*parameter = (struct function_parameter_type) { .type = parameters[i] };
		*tail = parameter;
		tail = &parameter->next;
	}
	return type;
}

bool type_compatible(const struct type *left, const struct type *right)
{
	const struct function_type *left_function;
	const struct function_type *right_function;
	const struct function_parameter_type *left_parameter;
	const struct function_parameter_type *right_parameter;

	if (left->kind != right->kind)
		return false;
	if (type_is_integer(left))
		return true;
	left_function = (const struct function_type *)left;
	right_function = (const struct function_type *)right;
	if (!type_compatible(left_function->return_type, right_function->return_type) ||
		left_function->parameter_count != right_function->parameter_count)
		return false;
	left_parameter = left_function->parameters;
	right_parameter = right_function->parameters;
	while (left_parameter && right_parameter) {
		if (!type_compatible(left_parameter->type, right_parameter->type))
			return false;
		left_parameter = left_parameter->next;
		right_parameter = right_parameter->next;
	}
	return !left_parameter && !right_parameter;
}
