#include "type.h"

const struct type type_int = { type_kind_int };
const struct type type_uint = { type_kind_uint };

bool type_is_integer(const struct type *type)
{
	return type->kind == type_kind_int || type->kind == type_kind_uint;
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
