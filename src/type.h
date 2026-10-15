#ifndef KCC_TYPE_H
#define KCC_TYPE_H

#include "arena.h"

#include <stdbool.h>
#include <stdint.h>

enum type_kind {
	type_kind_char,
	type_kind_schar,
	type_kind_uchar,
	type_kind_short,
	type_kind_ushort,
	type_kind_int,
	type_kind_uint,
	type_kind_long,
	type_kind_ulong,
	type_kind_long_long,
	type_kind_ulong_long,
	type_kind_bool,
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

extern const struct type type_bool;
extern const struct type type_char;
extern const struct type type_schar;
extern const struct type type_uchar;
extern const struct type type_short;
extern const struct type type_ushort;
extern const struct type type_int;
extern const struct type type_uint;
extern const struct type type_long;
extern const struct type type_ulong;
extern const struct type type_long_long;
extern const struct type type_ulong_long;
bool type_is_integer(const struct type *type);
bool type_is_unsigned(const struct type *type);
unsigned type_integer_width(const struct type *type);
const struct type *type_integer_promotion(const struct type *type);
const struct type *type_usual_arithmetic(const struct type *left, const struct type *right);
const struct type *type_integer_literal(uint64_t value, unsigned base,
	bool unsigned_suffix, unsigned long_suffix);
struct function_type *type_new_function(struct arena *arena, const struct type *return_type,
	const struct type *const *parameters, size_t parameter_count);
bool type_compatible(const struct type *left, const struct type *right);

#endif
