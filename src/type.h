#ifndef KCC_TYPE_H
#define KCC_TYPE_H

#include "arena.h"

#include <stdbool.h>

enum type_kind {
	type_kind_int,
	type_kind_function,
};

struct type {
	enum type_kind kind;
};

struct function_parameter_type {
	const struct type *type;
	struct function_parameter_type *next;
};

struct function_type {
	struct type type;
	const struct type *return_type;
	struct function_parameter_type *parameters;
	size_t parameter_count;
};

extern const struct type type_int;
/* Current syntax supports int returns and int parameters only. */
struct function_type *type_new_int_function(struct arena *arena, size_t parameter_count);
bool type_compatible(const struct type *left, const struct type *right);

#endif
