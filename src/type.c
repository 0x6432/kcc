#include "type.h"

#include <assert.h>
#include <string.h>

const struct type type_nullptr = { .kind = type_kind_nullptr };
const struct type type_void = { .kind = type_kind_void };
const struct type type_bool = { .kind = type_kind_bool };
const struct type type_char = { .kind = type_kind_char };
const struct type type_schar = { .kind = type_kind_schar };
const struct type type_uchar = { .kind = type_kind_uchar };
const struct type type_short = { .kind = type_kind_short };
const struct type type_ushort = { .kind = type_kind_ushort };
const struct type type_int = { .kind = type_kind_int };
const struct type type_uint = { .kind = type_kind_uint };
const struct type type_long = { .kind = type_kind_long };
const struct type type_ulong = { .kind = type_kind_ulong };
const struct type type_long_long = { .kind = type_kind_long_long };
const struct type type_ulong_long = { .kind = type_kind_ulong_long };

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
	if (type->kind == type_kind_enum)
		return type_enum_definition(type)->complete;
	for (size_t i = 0; i < sizeof(integer_properties) / sizeof(integer_properties[0]); i++)
		if (integer_properties[i].kind == type->kind)
			return true;
	return false;
}

bool type_is_scalar(const struct type *type)
{
	return type_is_integer(type) || type->kind == type_kind_pointer || type->kind == type_kind_nullptr;
}

bool type_is_object(const struct type *type)
{
	return type_is_scalar(type) || type_is_record(type) || type->kind == type_kind_enum || type->kind == type_kind_array ||
		type->kind == type_kind_void;
}

bool type_is_complete_object(const struct type *type)
{
	if (type_is_record(type))
		return type_record_definition(type)->complete;
	if (type->kind == type_kind_array)
		return ((const struct array_type *)type)->count != 0;
	return type_is_scalar(type);
}

unsigned type_value_width(const struct type *type)
{
	if (type->kind == type_kind_pointer || type->kind == type_kind_nullptr)
		return 64;
	return type_integer_width(type);
}

uint64_t type_object_size(const struct type *type)
{
	assert(type_is_complete_object(type));
	if (type_is_record(type))
		return type_record_definition(type)->size;
	if (type->kind == type_kind_array) {
		const struct array_type *array = (const struct array_type *)type;

		return type_object_size(array->element) * array->count;
	}
	return type_value_width(type) / 8;
}

unsigned type_object_alignment(const struct type *type)
{
	assert(type_is_complete_object(type));
	if (type_is_record(type))
		return type_record_definition(type)->alignment;
	if (type->kind == type_kind_array)
		return type_object_alignment(((const struct array_type *)type)->element);
	return type_value_width(type) / 8;
}

struct array_type *type_new_incomplete_array(struct arena *arena, const struct type *element)
{
	struct array_type *array;

	assert(type_is_complete_object(element));
	array = arena_alloc(arena, sizeof(*array));
	if (array)
		*array = (struct array_type) {
			.type = { .kind = type_kind_array, .qualifiers = element->qualifiers },
			.element = element,
			.count = 0,
		};
	return array;
}

struct array_type *type_new_array(struct arena *arena, const struct type *element,
	uint64_t count)
{
	struct array_type *array;

	assert(type_is_complete_object(element));
	assert(count && count <= UINT64_MAX / type_object_size(element));
	array = arena_alloc(arena, sizeof(*array));
	if (array)
		*array = (struct array_type) {
			.type = { .kind = type_kind_array, .qualifiers = element->qualifiers },
			.element = element,
			.count = count,
		};
	return array;
}

struct pointer_type *type_new_pointer(struct arena *arena, const struct type *referent)
{
	struct pointer_type *pointer = arena_alloc(arena, sizeof(*pointer));

	assert(type_is_object(referent) || referent->kind == type_kind_function);
	if (pointer)
		*pointer = (struct pointer_type) {
			.type = { .kind = type_kind_pointer },
			.referent = referent,
		};
	return pointer;
}

static const struct integer_properties *integer_properties_for(const struct type *type)
{
	if (type->kind == type_kind_enum) {
		assert(type_enum_definition(type)->complete);
		type = type_enum_definition(type)->compatible_type;
	}
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
	if (type->kind == type_kind_enum)
		type = type_enum_definition(type)->compatible_type;
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
		.type = { .kind = type_kind_function },
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

/* Replace only top-level qualification. Arrays and their elements have the
 * same qualification in C23; pointer referents are separate type levels. */
static const struct type *type_with_qualifiers(struct arena *arena, const struct type *type,
	unsigned qualifiers)
{
	struct type *leaf;

	assert(!(qualifiers & ~type_qualifier_const));
	assert(type->kind != type_kind_function || !qualifiers);
	if (type->qualifiers == qualifiers)
		return type;
	if (type->kind == type_kind_array) {
		const struct array_type *array = (const struct array_type *)type;
		const struct type *element = type_with_qualifiers(arena, array->element, qualifiers);
		struct array_type *copy;

		if (!element)
			return NULL;
		copy = array->count ? type_new_array(arena, element, array->count) :
			type_new_incomplete_array(arena, element);
		return copy ? &copy->type : NULL;
	}
	if (type->kind == type_kind_pointer) {
		const struct pointer_type *pointer = (const struct pointer_type *)type;
		struct pointer_type *copy = type_new_pointer(arena, pointer->referent);

		if (!copy)
			return NULL;
		copy->type.qualifiers = qualifiers;
		return &copy->type;
	}
	if (type->kind == type_kind_enum) {
		struct enum_type *copy = arena_alloc(arena, sizeof(*copy));
		if (copy) {
			*copy = *(const struct enum_type *)type;
			copy->type.qualifiers = qualifiers;
		}
		return copy ? &copy->type : NULL;
	}
	if (type_is_record(type)) {
		struct record_type *copy = arena_alloc(arena, sizeof(*copy));

		if (copy) {
			*copy = *(const struct record_type *)type;
			copy->type.qualifiers = qualifiers;
		}
		return copy ? &copy->type : NULL;
	}
	assert(type_is_integer(type) || type->kind == type_kind_void || type->kind == type_kind_nullptr);
	leaf = arena_alloc(arena, sizeof(*leaf));
	if (leaf)
		*leaf = (struct type) { .kind = type->kind, .qualifiers = qualifiers };
	return leaf;
}

const struct type *type_qualified(struct arena *arena, const struct type *type,
	unsigned qualifiers)
{
	return type_with_qualifiers(arena, type, type->qualifiers | qualifiers);
}

const struct type *type_unqualified(struct arena *arena, const struct type *type)
{
	return type_with_qualifiers(arena, type, 0);
}

/* Array elements repeat their array's qualifier, not a new pointer level. */
static bool compatible_types(const struct type *left, const struct type *right,
	bool ignore_root_qualifiers, bool require_same_type)
{
	const struct function_type *left_function;
	const struct function_type *right_function;
	const struct function_parameter_type *left_parameter;
	const struct function_parameter_type *right_parameter;

	/* Shared immutable types denote the same type without another traversal. */
	if (left == right)
		return true;
	if (!ignore_root_qualifiers && left->qualifiers != right->qualifiers)
		return false;
	if (left->kind == type_kind_enum || right->kind == type_kind_enum) {
		if (left->kind == type_kind_enum && right->kind == type_kind_enum)
			return type_enum_definition(left) == type_enum_definition(right);
		if (require_same_type)
			return false;
		const struct type *enumeration = left->kind == type_kind_enum ? left : right;
		const struct type *integer = left->kind == type_kind_enum ? right : left;
		struct enum_definition *definition = type_enum_definition(enumeration);
		return definition->complete && integer->kind == definition->compatible_type->kind;
	}
	if (left->kind != right->kind)
		return false;
	if (type_is_record(left))
		return type_record_definition(left) == type_record_definition(right);
	if (type_is_integer(left) || left->kind == type_kind_void || left->kind == type_kind_nullptr)
		return true;
	if (left->kind == type_kind_pointer) {
		const struct pointer_type *a = (const struct pointer_type *)left;
		const struct pointer_type *b = (const struct pointer_type *)right;

		return compatible_types(a->referent, b->referent, false, require_same_type);
	}
	if (left->kind == type_kind_array) {
		const struct array_type *a = (const struct array_type *)left;
		const struct array_type *b = (const struct array_type *)right;

		return (require_same_type ? a->count == b->count :
			(!a->count || !b->count || a->count == b->count)) &&
			compatible_types(a->element, b->element, ignore_root_qualifiers, require_same_type);
	}
	left_function = (const struct function_type *)left;
	right_function = (const struct function_type *)right;
	if (!compatible_types(left_function->return_type, right_function->return_type, false, require_same_type) ||
		left_function->parameter_count != right_function->parameter_count)
		return false;
	left_parameter = left_function->parameters;
	right_parameter = right_function->parameters;
	while (left_parameter && right_parameter) {
		if (!compatible_types(left_parameter->type, right_parameter->type, false, require_same_type))
			return false;
		left_parameter = left_parameter->next;
		right_parameter = right_parameter->next;
	}
	return !left_parameter && !right_parameter;
}

bool type_compatible(const struct type *left, const struct type *right)
{
	return compatible_types(left, right, false, false);
}

bool type_unqualified_compatible(const struct type *left, const struct type *right)
{
	return compatible_types(left, right, true, false);
}

/* Unlike compatibility, unknown array bounds are not wildcard typedef identities. */
bool type_same(const struct type *left, const struct type *right)
{
	return compatible_types(left, right, false, true);
}

const struct type *type_composite(struct arena *arena, const struct type *left,
	const struct type *right)
{
	assert(type_compatible(left, right));
	/* Retain a nominal enum constraint through its compatible integer;
	 * otherwise int/enum/int composites could erase conflicting identities. */
	if (right->kind == type_kind_enum && left->kind != type_kind_enum)
		return right;
	if (left == right || left->kind == type_kind_enum || type_is_record(left) || type_is_integer(left) || left->kind == type_kind_void || left->kind == type_kind_nullptr)
		return left;
	if (left->kind == type_kind_pointer) {
		const struct pointer_type *a = (const struct pointer_type *)left;
		const struct pointer_type *b = (const struct pointer_type *)right;
		const struct type *referent = type_composite(arena, a->referent, b->referent);
		struct pointer_type *pointer;

		if (!referent)
			return NULL;
		if (referent == a->referent)
			return left;
		pointer = type_new_pointer(arena, referent);
		if (pointer)
			pointer->type.qualifiers = left->qualifiers;
		return pointer ? &pointer->type : NULL;
	}
	if (left->kind == type_kind_array) {
		const struct array_type *a = (const struct array_type *)left;
		const struct array_type *b = (const struct array_type *)right;
		const struct type *element = type_composite(arena, a->element, b->element);
		uint64_t count = a->count ? a->count : b->count;
		struct array_type *array;

		if (!element)
			return NULL;
		if (count == a->count && element == a->element)
			return left;
		array = count ? type_new_array(arena, element, count) : type_new_incomplete_array(arena, element);
		return array ? &array->type : NULL;
	}
	if (left->kind == type_kind_function) {
		const struct function_type *a = (const struct function_type *)left;
		const struct function_type *b = (const struct function_type *)right;
		const struct type *return_type = type_composite(arena, a->return_type, b->return_type);
		const struct function_parameter_type *a_parameter = a->parameters;
		const struct function_parameter_type *b_parameter = b->parameters;
		struct function_type *function;
		struct function_parameter_type **tail;

		if (!return_type)
			return NULL;
		function = type_new_function(arena, return_type, NULL, 0);
		if (!function)
			return NULL;
		function->parameter_count = a->parameter_count;
		tail = &function->parameters;
		while (a_parameter && b_parameter) {
			const struct type *type = type_composite(arena, a_parameter->type, b_parameter->type);
			struct function_parameter_type *parameter;

			if (!type)
				return NULL;
			parameter = arena_alloc(arena, sizeof(*parameter));
			if (!parameter)
				return NULL;
			*parameter = (struct function_parameter_type) { .type = type };
			*tail = parameter;
			tail = &parameter->next;
			a_parameter = a_parameter->next;
			b_parameter = b_parameter->next;
		}
		assert(!a_parameter && !b_parameter);
		return &function->type;
	}
	assert(0 && "unknown composite type");
	return NULL;
}

bool type_is_record(const struct type *type)
{
	return type->kind == type_kind_struct || type->kind == type_kind_union;
}

struct record_definition *type_record_definition(const struct type *type)
{
	return type_is_record(type) ? ((const struct record_type *)type)->definition : NULL;
}

struct record_type *type_new_record(struct arena *arena, bool is_union)
{
	struct record_type *record = arena_alloc(arena, sizeof(*record));
	struct record_definition *definition = arena_alloc(arena, sizeof(*definition));

	if (!record || !definition)
		return NULL;
	*definition = (struct record_definition) { .is_union = is_union };
	*record = (struct record_type) {
		.type = { .kind = is_union ? type_kind_union : type_kind_struct },
		.definition = definition,
	};
	return record;
}

/* Checked storage walk stops at nominal records and pointer objects; it never
 * follows referents. Nested arrays are checked before multiplying. */
static bool checked_member_layout(const struct type *type, unsigned depth,
	uint64_t *size, unsigned *alignment)
{
	if (depth > 64)
		return false;
	if (type->kind == type_kind_array) {
		const struct array_type *array = (const struct array_type *)type;
		uint64_t element_size;

		if (!array->count || !checked_member_layout(array->element, depth + 1,
			&element_size, alignment) || !element_size ||
			array->count > UINT64_MAX / element_size ||
			array->count > type_max_record_size / element_size)
			return false;
		*size = element_size * array->count;
		return true;
	}
	if (!type_is_complete_object(type))
		return false;
	*size = type_object_size(type);
	*alignment = type_object_alignment(type);
	return *size && *size <= type_max_record_size && *alignment &&
		!(*alignment & (*alignment - 1)) && *alignment <= 16;
}

static bool checked_align(uint64_t value, unsigned alignment, uint64_t *result)
{
	uint64_t padding = (alignment - value % alignment) % alignment;

	if (value > UINT64_MAX - padding || value + padding > type_max_record_size)
		return false;
	*result = value + padding;
	return true;
}

bool type_record_layout(struct record_definition *definition)
{
	uint64_t size = 0;
	unsigned alignment = 1;
	size_t count = 0;

	/* First pass is transactional: invalid input changes no published layout. */
	for (struct record_member *member = definition->members; member; member = member->next) {
		uint64_t member_size;
		unsigned member_alignment;

		if (++count > 1024 || !checked_member_layout(member->type, 0,
			&member_size, &member_alignment))
			return false;
		if (member->alignment) {
			if (member->alignment < member_alignment || member->alignment > 16 ||
				(member->alignment & (member->alignment - 1)))
				return false;
			member_alignment = member->alignment;
		}
		if (member_alignment > alignment)
			alignment = member_alignment;
		if (definition->is_union) {
			if (member_size > size)
				size = member_size;
		} else {
			if (!checked_align(size, member_alignment, &size) ||
				member_size > UINT64_MAX - size || member_size > type_max_record_size - size)
				return false;
			size += member_size;
		}
	}
	if (!count || !checked_align(size, alignment, &size))
		return false;
	uint64_t cursor = 0;
	for (struct record_member *member = definition->members; member; member = member->next) {
		uint64_t member_size;
		unsigned member_alignment;
		bool valid = checked_member_layout(member->type, 0, &member_size, &member_alignment);

		assert(valid);
		(void)valid;
		if (member->alignment)
			member_alignment = member->alignment;
		if (definition->is_union)
			member->offset = 0;
		else {
			valid = checked_align(cursor, member_alignment, &cursor);
			assert(valid);
			member->offset = cursor;
			cursor += member_size;
		}
	}
	definition->size = size;
	definition->alignment = alignment;
	definition->member_count = count;
	definition->complete = true;
	return true;
}

static bool member_name_equal(const struct token *left, const struct token *right)
{
	return left->kind == token_identifier && right->kind == token_identifier &&
		left->length == right->length &&
		memcmp(left->spelling_location.source->data + left->spelling_location.offset,
			right->spelling_location.source->data + right->spelling_location.offset,
			left->length) == 0;
}

static const struct record_member *find_record_member(const struct type *type,
	const struct token *name, uint64_t *offset, unsigned depth, size_t *budget,
	bool *ambiguous)
{
	struct record_definition *definition = type_record_definition(type);
	const struct record_member *found = NULL;
	uint64_t found_offset = 0;

	if (!definition || !definition->complete || depth > 64)
		return NULL;
	for (const struct record_member *member = definition->members; member; member = member->next) {
		const struct record_member *candidate = NULL;
		uint64_t candidate_offset = 0;

		if (!*budget) {
			*ambiguous = true;
			return NULL;
		}
		--*budget;
		if (member_name_equal(&member->name, name))
			candidate = member;
		else if (member->anonymous)
			candidate = find_record_member(member->type, name, &candidate_offset,
				depth + 1, budget, ambiguous);
		if (candidate) {
			if (found || candidate_offset > UINT64_MAX - member->offset) {
				*ambiguous = true;
				return NULL;
			}
			found = candidate;
			found_offset = member->offset + candidate_offset;
		}
	}
	if (found)
		*offset = found_offset;
	return found;
}

const struct record_member *type_record_find_member(const struct type *type,
	const struct token *name, uint64_t *offset)
{
	uint64_t result_offset = 0;
	size_t budget = 65536;
	bool ambiguous = false;
	const struct record_member *member = find_record_member(type, name, &result_offset,
		0, &budget, &ambiguous);

	if (ambiguous)
		return NULL;
	if (member && offset)
		*offset = result_offset;
	return member;
}

struct enum_definition *type_enum_definition(const struct type *type)
{
	return type->kind == type_kind_enum ? ((const struct enum_type *)type)->definition : NULL;
}

struct enum_type *type_new_enum(struct arena *arena)
{
	struct enum_type *type = arena_alloc(arena, sizeof(*type));
	struct enum_definition *definition = arena_alloc(arena, sizeof(*definition));
	if (!type || !definition)
		return NULL;
	*definition = (struct enum_definition) { 0 };
	*type = (struct enum_type) { .type = { .kind = type_kind_enum }, .definition = definition };
	return type;
}
