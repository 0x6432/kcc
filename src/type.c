#include "type.h"

#include <assert.h>

const struct type type_int = { type_kind_int };
const struct type type_uint = { type_kind_uint };
const struct type type_long = { type_kind_long };
const struct type type_ulong = { type_kind_ulong };

struct integer_properties {
	enum type_kind kind;
	unsigned width;
	unsigned rank;
	bool unsigned_type;
	const struct type *unsigned_counterpart;
};

/* Target LP64 properties, independent of the compiler host's long width. */
static const struct integer_properties integer_properties[] = {
	{ type_kind_int, 32, 1, false, &type_uint },
	{ type_kind_uint, 32, 1, true, &type_uint },
	{ type_kind_long, 64, 2, false, &type_ulong },
	{ type_kind_ulong, 64, 2, true, &type_ulong },
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

const struct type *type_usual_arithmetic(const struct type *left, const struct type *right)
{
	const struct integer_properties *a = integer_properties_for(left);
	const struct integer_properties *b = integer_properties_for(right);
	const struct type *unsigned_type;
	const struct type *signed_type;
	const struct integer_properties *unsigned_properties;
	const struct integer_properties *signed_properties;

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
	const struct type *candidates[4];
	size_t count = 0;

	if (long_suffix > 1)
		return NULL;
	if (!long_suffix) {
		if (!unsigned_suffix)
			candidates[count++] = &type_int;
		if (unsigned_suffix || base != 10)
			candidates[count++] = &type_uint;
	}
	if (!unsigned_suffix)
		candidates[count++] = &type_long;
	if (unsigned_suffix || base != 10)
		candidates[count++] = &type_ulong;
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
