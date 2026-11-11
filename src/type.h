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
	type_kind_bitint8,
	type_kind_ubitint8,
	type_kind_bitint16,
	type_kind_ubitint16,
	type_kind_bitint32,
	type_kind_ubitint32,
	type_kind_bitint64,
	type_kind_ubitint64,
	/* Width-aware non-native types; ABI uses separate safety gates. */
	type_kind_bitint_other,
	type_kind_ubitint_other,
	/* GCC-compatible extended types of partial-width bit-field expressions. */
	type_kind_field_signed,
	type_kind_field_unsigned,
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
	const char *nodiscard_message;
	bool is_deprecated;
	const char *deprecated_message;
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
	bool is_deprecated;
	const char *deprecated_message;
	bool is_flexible;
	bool is_bit_field;
	unsigned bit_width; /* 0..64; zero denotes an unnamed separator. */
	unsigned bit_offset; /* Low-bit-first offset within the addressed byte. */
	struct record_member *next;
};

struct record_definition {
	struct token tag; /* Empty for untagged, nominal-only types. */
	bool is_union;
	bool complete;
	bool is_nodiscard;
	const char *nodiscard_message;
	bool is_deprecated;
	const char *deprecated_message;
	bool has_flexible_array;
	bool has_volatile_member;
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
/* Bounded x86-64 SysV/QBE aggregate calling convention. */
enum { type_max_abi_record_size = 1024 };
enum aggregate_abi_class { aggregate_abi_none, aggregate_abi_integer, aggregate_abi_sse };
struct aggregate_abi {
	unsigned size, alignment;
	enum aggregate_abi_class classes[2]; /* Both none denotes MEMORY. */
};
/* Legacy-Clang mode skips unnamed bit-fields. GCC 12 mode separately opts
 * into modern zero-width separator classification. Modes are exclusive;
 * unrepresentable QBE shapes are rejected and the default remains unchanged. */
bool type_aggregate_abi_for_mode(const struct type *type, struct aggregate_abi *abi,
	bool legacy_clang_abi, bool gcc12_zero_width_abi);
bool type_aggregate_abi(const struct type *type, struct aggregate_abi *abi);

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
extern const struct type type_bitint8, type_ubitint8, type_bitint16, type_ubitint16;
extern const struct type type_bitint32, type_ubitint32, type_bitint64, type_ubitint64;
/* Returns a canonical semantic type, or NULL for invalid widths.
 * Non-native widths remain subject to operation and ABI safety gates. */
const struct type *type_bitint(unsigned width, bool is_unsigned);
/* Whether source values of this width currently have lowering support. */
bool type_bitint_width_lowerable(unsigned width);
/* Only native-sized BitInts use the existing aggregate and atomic paths. */
bool type_bitint_width_native(unsigned width);
bool type_is_bitint(const struct type *type);
bool type_is_integer(const struct type *type);
bool type_is_field_integer(const struct type *type);
bool type_uses_field_integer_representation(const struct type *type);
const struct type *type_field_integer(unsigned width, bool is_unsigned);
/* Includes a fixed enum compatible with bool. */
bool type_is_boolean(const struct type *type);
bool type_is_floating(const struct type *type);
bool type_is_scalar(const struct type *type);
bool type_is_object(const struct type *type);
bool type_is_complete_object(const struct type *type);
/* Semantic value width is separate from target object storage size.
 * Codegen only supports widths for which source lowering is enabled. */
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
