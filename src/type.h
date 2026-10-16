#ifndef KCC_TYPE_H
#define KCC_TYPE_H

#include "arena.h"

#include <stdbool.h>
#include <stdint.h>

enum type_kind {
	type_kind_void,
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
	type_kind_nullptr,
	type_kind_pointer,
	type_kind_array,
	type_kind_function,
};

enum type_qualifier {
	type_qualifier_const = 1u << 0,
};

struct type {
	enum type_kind kind;
	unsigned qualifiers;
};

struct pointer_type {
	struct type type;
	const struct type *referent;
};

struct array_type {
	struct type type;
	const struct type *element;
	uint64_t count; /* Zero means unknown bound, never a zero-length array. */
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

extern const struct type type_nullptr;
extern const struct type type_void;
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
bool type_is_scalar(const struct type *type);
bool type_is_object(const struct type *type);
bool type_is_complete_object(const struct type *type);
/* QBE scalar value width is separate from target object storage size. */
unsigned type_value_width(const struct type *type);
/* Target layout for implemented complete object types, not host sizeof. */
uint64_t type_object_size(const struct type *type);
unsigned type_object_alignment(const struct type *type);
struct array_type *type_new_incomplete_array(struct arena *arena, const struct type *element);
struct array_type *type_new_array(struct arena *arena, const struct type *element,
	uint64_t count);
struct pointer_type *type_new_pointer(struct arena *arena, const struct type *referent);
bool type_is_unsigned(const struct type *type);
unsigned type_integer_width(const struct type *type);
const struct type *type_integer_promotion(const struct type *type);
const struct type *type_usual_arithmetic(const struct type *left, const struct type *right);
const struct type *type_integer_literal(uint64_t value, unsigned base,
	bool unsigned_suffix, unsigned long_suffix);
struct function_type *type_new_function(struct arena *arena, const struct type *return_type,
	const struct type *const *parameters, size_t parameter_count);
/* Qualifier operations preserve shared inputs; NULL means allocation failure.
 * Array qualification follows C23 through elements, never pointer referents.
 * Function types cannot be qualified. Existing no-op results may be shared. */
const struct type *type_qualified(struct arena *arena, const struct type *type,
	unsigned qualifiers);
const struct type *type_unqualified(struct arena *arena, const struct type *type);
bool type_compatible(const struct type *left, const struct type *right);
bool type_same(const struct type *left, const struct type *right);
/* Ignore only root qualifiers (including equivalent array element qualifiers).
 * Below a pointer, qualification must still match exactly. */
bool type_unqualified_compatible(const struct type *left, const struct type *right);
/* Merge compatible declarations without changing either input type graph. */
const struct type *type_composite(struct arena *arena, const struct type *left,
	const struct type *right);

#endif
