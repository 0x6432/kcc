#ifndef KCC_TYPE_H
#define KCC_TYPE_H

#include "arena.h"
#include "lex.h"

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
	type_kind_float,
	type_kind_double,
	type_kind_nullptr,
	type_kind_pointer,
	type_kind_array,
	type_kind_function,
	type_kind_struct,
	type_kind_union,
	type_kind_enum,
};

struct enum_member_info {
	struct token name;
	uint64_t bits;
};

struct enum_definition {
	bool complete;
	bool defined;
	bool defining;
	bool fixed;
	bool is_nodiscard;
	const struct type *underlying; /* NULL denotes ordinary enum int. */
	struct token tag;
	struct enum_member_info *members; /* Sorted by name after definition. */
	size_t member_count;
};

enum type_qualifier {
	type_qualifier_const = 1u << 0,
	type_qualifier_atomic = 1u << 1,
	/* Syntax-only marker: _Atomic(type-name) rejects a qualified operand. */
	type_qualifier_atomic_specifier = 1u << 2,
	type_qualifier_restrict = 1u << 3,
	type_qualifier_volatile = 1u << 4,
};

struct type {
	enum type_kind kind;
	unsigned qualifiers;
};

struct enum_type {
	struct type type;
	struct enum_definition *definition;
};

/* Stable nominal identity shared by every qualified wrapper. */
struct record_member {
	struct token name;
	const struct type *type;
	uint64_t offset;
	unsigned alignment; /* Explicit member alignment; zero means natural. */
	bool anonymous;
	bool is_flexible;
	struct record_member *next;
};

struct record_definition {
	bool is_union;
	bool complete;
	bool has_flexible_array;
	struct record_member *members;
	size_t member_count;
	uint64_t size;
	unsigned alignment;
};

struct record_type {
	struct type type;
	struct record_definition *definition;
};

enum { type_max_record_size = 1024 * 1024, type_max_alignment = 256 };
/* QBE alloc16 returns a 16-aligned address; the worst adjustment needed
 * to reach a larger power-of-two alignment is alignment - 16. */
static inline unsigned type_stack_alignment_padding(unsigned alignment)
{
	return alignment > 16 ? alignment - 16 : 0;
}
bool type_is_record(const struct type *type);
struct record_definition *type_record_definition(const struct type *type);
struct record_type *type_new_record(struct arena *arena, bool is_union);
/* No allocation/diagnostics; failure leaves layout and completeness unchanged. */
bool type_record_layout(struct record_definition *definition);
const struct record_member *type_record_find_member(const struct type *type,
	const struct token *name, uint64_t *offset);

struct pointer_type {
	struct type type;
	const struct type *referent;
};

struct array_type {
	struct type type;
	const struct type *element;
	uint64_t count; /* Zero means unknown or runtime bound. */
	bool runtime_bound; /* Runtime object only; never a fixed-size surrogate. */
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
	bool variadic;
};

extern const struct type type_nullptr;
extern const struct type type_void;
extern const struct type type_bool;
extern const struct type type_float;
extern const struct type type_double;
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
/* Includes a fixed enum compatible with bool. */
bool type_is_boolean(const struct type *type);
bool type_is_floating(const struct type *type);
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
