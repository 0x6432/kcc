#include "consteval.h"
#include "type.h"
#include "sema.h"

#include <assert.h>
#include <stdint.h>
#include <string.h>

static uint64_t integer_mask(const struct type *type)
{
	unsigned width = type_integer_width(type);

	return width == 64 ? UINT64_MAX : (UINT64_C(1) << width) - 1;
}

static struct constant_result constant_success(const struct ast_expression *expression, uint64_t bits)
{
	return (struct constant_result) {
		.status = constant_value,
		.type = expression->type,
		.bits = bits & integer_mask(expression->type),
		.location = expression->location,
	};
}

static struct constant_result constant_failure(const struct ast_expression *expression,
	enum constant_status status, const char *message)
{
	return (struct constant_result) {
		.status = status,
		.type = expression->type,
		.location = expression->location,
		.message = message,
	};
}

/* Decode without an implementation-defined out-of-range unsigned cast. */
static int64_t signed_value(struct constant_result value)
{
	uint64_t mask = integer_mask(value.type);
	uint64_t sign = UINT64_C(1) << (type_integer_width(value.type) - 1);

	assert(!type_is_unsigned(value.type));
	return value.bits & sign ? -1 - (int64_t)(mask - value.bits) : (int64_t)value.bits;
}

static uint64_t converted_bits(struct constant_result value, const struct type *target)
{
	uint64_t bits = value.bits;

	if (target->kind == type_kind_bool)
		return bits != 0;
	if (!type_is_unsigned(value.type))
		bits = (uint64_t)signed_value(value);
	return bits & integer_mask(target);
}

static struct constant_result evaluate_initializer_condition(const struct ast_expression *expression);
static struct constant_result compare_initializer_addresses(const struct ast_binary_expression *node);
static struct constant_result difference_initializer_addresses(const struct ast_pointer_difference_expression *node);

static struct constant_result evaluate(const struct ast_expression *expression, bool evaluated, bool initializer_condition);

static struct constant_result evaluate_unary(const struct ast_unary_expression *node, bool evaluated, bool initializer_condition)
{
	const struct ast_expression *expression = &node->expression;
	struct constant_result operand = evaluate(node->operand, evaluated, initializer_condition);
	uint64_t sign = UINT64_C(1) << (type_integer_width(expression->type) - 1);

	if (operand.status != constant_value)
		return operand;
	if (!evaluated)
		return constant_success(expression, 0);
	switch (node->operation) {
	case unary_plus:
		return constant_success(expression, operand.bits);
	case unary_not:
		return constant_success(expression, !operand.bits);
	case unary_complement:
		return constant_success(expression, ~operand.bits);
	case unary_minus:
		if (!type_is_unsigned(operand.type) && operand.bits == sign)
			return constant_failure(expression, constant_invalid, "signed overflow in constant negation");
		return constant_success(expression, UINT64_C(0) - operand.bits);
	}
	assert(0 && "unknown constant unary operator");
	return constant_failure(expression, constant_not_constant, "unknown unary operator");
}

static struct constant_result evaluate_binary(const struct ast_binary_expression *node, bool evaluated, bool initializer_condition)
{
	const struct ast_expression *expression = &node->expression;
	struct constant_result left;
	if (initializer_condition && (node->left->type->kind == type_kind_pointer ||
		node->left->type->kind == type_kind_nullptr))
		return compare_initializer_addresses(node);
	left = evaluate(node->left, evaluated, initializer_condition);
	struct constant_result right;
	unsigned width;
	uint64_t mask;
	bool unsigned_type;
	int64_t a = 0;
	int64_t b = 0;
	int64_t maximum;
	int64_t minimum;
	uint64_t bits;

	if (left.status != constant_value)
		return left;
	right = evaluate(node->right, evaluated, initializer_condition);
	if (right.status != constant_value)
		return right;
	if (!evaluated)
		return constant_success(expression, 0);
	width = type_integer_width(left.type);
	mask = integer_mask(left.type);
	unsigned_type = type_is_unsigned(left.type);
	maximum = (int64_t)(mask >> 1);
	minimum = -maximum - 1;
	if (!unsigned_type)
		a = signed_value(left);
	if (!type_is_unsigned(right.type))
		b = signed_value(right);
	switch (node->operation) {
	case binary_add:
		if (!unsigned_type && ((b > 0 && a > maximum - b) || (b < 0 && a < minimum - b)))
			break;
		bits = left.bits + right.bits;
		return constant_success(expression, bits);
	case binary_subtract:
		if (!unsigned_type && ((b > 0 && a < minimum + b) || (b < 0 && a > maximum + b)))
			break;
		bits = left.bits - right.bits;
		return constant_success(expression, bits);
	case binary_multiply:
		if (!unsigned_type) {
			uint64_t magnitude_a = a < 0 ? UINT64_C(0) - (uint64_t)a : (uint64_t)a;
			uint64_t magnitude_b = b < 0 ? UINT64_C(0) - (uint64_t)b : (uint64_t)b;
			uint64_t limit = (a < 0) != (b < 0) ? UINT64_C(1) << (width - 1) : (uint64_t)maximum;

			if (magnitude_b && magnitude_a > limit / magnitude_b)
				break;
		}
		return constant_success(expression, left.bits * right.bits);
	case binary_divide:
	case binary_remainder:
		if (!right.bits)
			return constant_failure(expression, constant_invalid, "division by zero in integer constant expression");
		if (!unsigned_type) {
			if (a == minimum && b == -1)
				break;
			bits = (uint64_t)(node->operation == binary_divide ? a / b : a % b);
		} else {
			bits = node->operation == binary_divide ? left.bits / right.bits : left.bits % right.bits;
		}
		return constant_success(expression, bits);
	case binary_shift_left:
	case binary_shift_right:
		if ((!type_is_unsigned(right.type) && b < 0) || right.bits >= width)
			return constant_failure(expression, constant_invalid, "invalid shift count in integer constant expression");
		if (node->operation == binary_shift_right) {
			bits = !unsigned_type && a < 0 ? (uint64_t)(-1 - ((-1 - a) >> right.bits)) : left.bits >> right.bits;
			return constant_success(expression, bits);
		}
		if (!unsigned_type) {
			if (a < 0)
				return constant_failure(expression, constant_invalid, "negative left operand in constant shift");
			if (a > (maximum >> right.bits))
				break;
		}
		return constant_success(expression, left.bits << right.bits);
	case binary_bit_and:
		return constant_success(expression, left.bits & right.bits);
	case binary_bit_xor:
		return constant_success(expression, left.bits ^ right.bits);
	case binary_bit_or:
		return constant_success(expression, left.bits | right.bits);
	case binary_equal:
		return constant_success(expression, left.bits == right.bits);
	case binary_not_equal:
		return constant_success(expression, left.bits != right.bits);
	case binary_less:
		return constant_success(expression, unsigned_type ? left.bits < right.bits : a < b);
	case binary_less_equal:
		return constant_success(expression, unsigned_type ? left.bits <= right.bits : a <= b);
	case binary_greater:
		return constant_success(expression, unsigned_type ? left.bits > right.bits : a > b);
	case binary_greater_equal:
		return constant_success(expression, unsigned_type ? left.bits >= right.bits : a >= b);
	}
	return constant_failure(expression, constant_invalid, "signed overflow in integer constant expression");
}

/* Even a skipped arm must meet 6.6p8's integer operand/cast form rules.
 * Only arithmetic evaluation and the comma prohibition depend on evaluated.
 */
static struct constant_result evaluate(const struct ast_expression *expression, bool evaluated, bool initializer_condition)
{
	assert(expression && expression->type && expression->depth <= ast_max_expression_depth);
	if (initializer_condition && !evaluated)
		return (struct constant_result) { .status = constant_value, .type = expression->type,
			.bits = 0, .location = expression->location };
	if (initializer_condition && !type_is_integer(expression->type))
		return evaluate_initializer_condition(expression);
	if (!type_is_integer(expression->type))
		return constant_failure(expression, constant_not_constant, "integer constant expression requires integer operands");
	switch (expression->kind) {
	case expression_enumerator:
		return constant_success(expression, ((const struct ast_enumerator_expression *)expression)->bits);
	case expression_integer:
		return constant_success(expression, ((const struct ast_integer_expression *)expression)->value);
	case expression_boolean:
		return constant_success(expression, ((const struct ast_boolean_expression *)expression)->value);
	case expression_character:
		return constant_success(expression, (uint64_t)((const struct ast_character_expression *)expression)->value);
	case expression_sizeof:
		return constant_success(expression, ((const struct ast_sizeof_expression *)expression)->size);
	case expression_sizeof_type:
		return constant_success(expression, ((const struct ast_sizeof_type_expression *)expression)->size);
	case expression_alignof:
		return constant_success(expression, ((const struct ast_alignof_expression *)expression)->alignment);
	case expression_cast:
	case expression_conversion: {
		const struct ast_expression *operand = expression->kind == expression_cast ?
			((const struct ast_cast_expression *)expression)->operand :
			((const struct ast_conversion_expression *)expression)->operand;
		struct constant_result value = evaluate(operand, evaluated, initializer_condition);

		if (initializer_condition && expression->type->kind == type_kind_bool &&
			!type_is_integer(operand->type) && value.status == constant_value)
			return constant_success(expression, value.bits != 0);
		if (value.status != constant_value)
			return value;
		return constant_success(expression, evaluated ? converted_bits(value, expression->type) : 0);
	}
	case expression_unary:
		return evaluate_unary((const struct ast_unary_expression *)expression, evaluated, initializer_condition);
	case expression_binary:
		return evaluate_binary((const struct ast_binary_expression *)expression, evaluated, initializer_condition);
	case expression_pointer_difference:
		if (initializer_condition)
			return difference_initializer_addresses((const struct ast_pointer_difference_expression *)expression);
		return constant_failure(expression, constant_not_constant,
			"operand is not an integer constant expression");
	case expression_logical: {
		const struct ast_logical_expression *node = (const struct ast_logical_expression *)expression;
		struct constant_result left = evaluate(node->left, evaluated, initializer_condition);
		struct constant_result right;
		bool evaluate_right;

		if (left.status != constant_value)
			return left;
		evaluate_right = evaluated && (node->operation == logical_and ? left.bits != 0 : left.bits == 0);
		right = evaluate(node->right, evaluate_right, initializer_condition);
		if (right.status != constant_value)
			return right;
		return constant_success(expression, evaluated && (node->operation == logical_and ?
			left.bits && right.bits : left.bits || right.bits));
	}
	case expression_conditional: {
		const struct ast_conditional_expression *node = (const struct ast_conditional_expression *)expression;
		struct constant_result condition = evaluate(node->condition, evaluated, initializer_condition);
		struct constant_result then_value;
		struct constant_result else_value;

		if (condition.status != constant_value)
			return condition;
		then_value = evaluate(node->then_value, evaluated && condition.bits != 0, initializer_condition);
		if (then_value.status != constant_value)
			return then_value;
		else_value = evaluate(node->else_value, evaluated && condition.bits == 0, initializer_condition);
		if (else_value.status != constant_value)
			return else_value;
		return constant_success(expression, evaluated ? (condition.bits ? then_value.bits : else_value.bits) : 0);
	}
	case expression_comma: {
		const struct ast_comma_expression *node = (const struct ast_comma_expression *)expression;
		struct constant_result left;
		struct constant_result right;

		if (evaluated)
			return constant_failure(expression, constant_not_constant, "evaluated comma is not an integer constant expression");
		left = evaluate(node->left, false, initializer_condition);
		if (left.status != constant_value)
			return left;
		right = evaluate(node->right, false, initializer_condition);
		return right.status == constant_value ? constant_success(expression, 0) : right;
	}
	default:
		return constant_failure(expression, constant_not_constant, "operand is not an integer constant expression");
	}
}

struct constant_result evaluate_integer_constant(const struct ast_expression *expression)
{
	return evaluate(expression, true, false);
}

/* Initializer selection is distinct from strict ICE operand validation: an
 * unselected pointer branch may contain an otherwise valid load or call.
 * Both branches have already passed sema; this query only evaluates selection. */
/* The source is checked before assignment conversion. Arbitrary nullptr_t
 * values, pointer loads, address expressions and pointer arithmetic are not
 * proved constant merely because their runtime value might be null.
 */
static struct null_initializer_result evaluate_pointer_null(const struct ast_expression *expression);

struct null_initializer_result evaluate_null_initializer(const struct ast_expression *expression)
{
	assert(expression && expression->type && expression->depth <= ast_max_expression_depth);
	return evaluate_pointer_null(expression);
}

/* Address context names storage without reading it. In particular, rejecting
 * indirection here is handled by the separate checked cancellation proof.
 * The query neither registers strings nor marks functions referenced.
 */
static struct address_initializer_result direct_address(const struct ast_expression *expression,
	const struct type *origin_type)
{
	struct address_initializer_result result = {
		.status = constant_value, .location = expression->location, .origin_type = origin_type,
	};

	switch (expression->kind) {
	case expression_compound_literal: {
		const struct ast_compound_literal_expression *literal =
			(const struct ast_compound_literal_expression *)expression;

		if (!literal->object) {
			if (literal->storage != ast_compound_literal_static)
				break;
			result.address.kind = static_address_compound_literal;
			result.address.base.compound_literal = literal;
			return result;
		}
		if (literal->object->is_thread_local)
			break;
		result.address.kind = static_address_object;
		result.address.base.object = literal->object;
		return result;
	}
	case expression_external_object:
		if (((const struct ast_external_object_expression *)expression)->object->is_thread_local)
			return (struct address_initializer_result) {
				.status = constant_not_constant, .location = expression->location,
				.message = "thread-local object address is not a static address constant",
			};
		result.address.kind = static_address_object;
		result.address.base.object = ((const struct ast_external_object_expression *)expression)->object;
		return result;
	case expression_function_designator:
		result.address.kind = static_address_function;
		result.address.base.function = ((const struct ast_function_designator_expression *)expression)->function;
		return result;
	case expression_string:
		result.address.kind = static_address_string;
		result.address.base.string = (const struct ast_string_expression *)expression;
		return result;
	default:
		break;
	}
	return (struct address_initializer_result) {
		.status = constant_not_constant, .location = expression->location,
		.message = "file-scope pointer initializer requires a supported null or direct address constant expression",
	};
}

/* Assignment-like pointer edges preserve immediate referent qualifiers.
 * Checked explicit casts are handled separately with guaranteed alignment and
 * no invented arithmetic domain; integer/object-function detours stay excluded.
 */
static bool direct_pointer_conversion(const struct type *source, const struct type *target)
{
	const struct type *a;
	const struct type *b;

	if (source->kind != type_kind_pointer || target->kind != type_kind_pointer)
		return false;
	a = ((const struct pointer_type *)source)->referent;
	b = ((const struct pointer_type *)target)->referent;
	if (a->qualifiers & ~b->qualifiers)
		return false;
	return type_unqualified_compatible(a, b) ||
		(a->kind == type_kind_void && type_is_object(b)) ||
		(b->kind == type_kind_void && type_is_object(a));
}

/* Private provenance survives pointer/void casts, but a cast never creates a
 * domain through a void detour. Character views explicitly capture the pointed
 * object's byte extent. One-past is a position, not a new object.
 */
struct address_path {
	const struct record_member *members[ast_max_expression_depth];
	unsigned count;
	bool ambiguous;
	const struct type *recovery_root;
	uint64_t recovery_start;
	unsigned recovery_prefix;
	const struct type *recovery_target;
	uint64_t recovery_address;
	uint64_t recovery_domain_start, recovery_stride, recovery_extent;
	unsigned recovery_count;
	bool recovery_known_extent;
};

struct address_domain {
	struct address_path path;
	const struct type *element;
	uint64_t extent;
	uint64_t stride;
	uint64_t start;
	bool known_extent;
};

struct address_proof {
	struct address_path path;
	struct address_path byte_view_path;
	bool is_null; /* Separate value category, never an integer address sentinel. */
	struct address_domain original_domain;
	const struct type *storage_type; /* Immutable source-point root, not a later composite. */
	const struct type *byte_view_type;
	uint64_t byte_view_start;
	struct address_initializer_result result;
	const struct type *element;
	uint64_t extent;
	uint64_t stride;
	uint64_t position;
	uint64_t start;
	bool known_extent;
	unsigned base_alignment;
	bool explicit_cast;
};

static struct address_proof address_failure(const struct ast_expression *expression,
	enum constant_status status, const char *message)
{
	return (struct address_proof) { .result = {
		.status = status, .location = expression->location, .message = message,
	} };
}

static unsigned address_alignment(const struct type *type)
{
	while (type->kind == type_kind_array)
		type = ((const struct array_type *)type)->element;
	return type_is_complete_object(type) ? type_object_alignment(type) : 1;
}

static struct address_proof address_base(const struct ast_expression *expression,
	const struct ast_expression *operand, bool decay)
{
	struct address_proof proof = { .result = direct_address(operand, expression->type) };
	const struct type *type = operand->type;

	if (proof.result.status != constant_value)
		return proof;
	proof.base_alignment = address_alignment(type);
	proof.storage_type = type;
	if (decay && type->kind == type_kind_array) {
		const struct array_type *array = (const struct array_type *)type;

		if (type_is_complete_object(array->element)) {
			proof.element = array->element;
			proof.extent = array->count;
			proof.known_extent = array->count != 0;
			proof.stride = type_object_size(array->element);
		}
	} else if (!decay && (operand->kind == expression_external_object || operand->kind == expression_string ||
		operand->kind == expression_compound_literal) &&
		type_is_complete_object(type)) {
		proof.element = type;
		proof.extent = 1;
		proof.known_extent = true;
		proof.stride = type_object_size(type);
	}
	return proof;
}

static void save_address_domain(struct address_proof *proof)
{
	if (proof->element && !proof->original_domain.element)
		proof->original_domain = (struct address_domain) {
			.element = proof->element, .extent = proof->extent, .stride = proof->stride,
			.start = proof->start, .known_extent = proof->known_extent, .path = proof->path,
		};
}

static bool restore_address_domain(struct address_proof *proof, const struct type *target)
{
	const struct address_domain *domain = &proof->original_domain;
	uint64_t addend = (uint64_t)proof->result.address.byte_addend;
	uint64_t position;

	if (!domain->element || !type_unqualified_compatible(domain->element, target) ||
		addend < domain->start || (addend - domain->start) % domain->stride)
		return false;
	position = (addend - domain->start) / domain->stride;
	if (domain->known_extent && position > domain->extent)
		return false;
	proof->path = domain->path;
	proof->element = domain->element;
	proof->extent = domain->extent;
	proof->stride = domain->stride;
	proof->start = domain->start;
	proof->known_extent = domain->known_extent;
	proof->position = position;
	return true;
}

enum { subobject_search_work_limit = 16384, subobject_search_memo_size = 1024 };
struct subobject_search_failure {
	const struct type *root;
	const struct type *target;
	uint64_t relative;
};
struct subobject_search {
	const struct address_path *desired_path;
	size_t work;
	bool exhausted;
	struct subobject_search_failure failures[subobject_search_memo_size];
};

static bool find_actual_domain(const struct type *root, uint64_t start, uint64_t address,
	const struct type *target, struct address_proof *proof, unsigned depth,
	struct subobject_search *search);

/* Recover only an ACTUAL captured subobject at this address. This is not
 * sizeof(target)-based reinterpretation: no array of short is invented inside
 * an int. Arrays preserve their real element domain; records preserve each
 * member's singleton or nested-array domain. */
static bool find_actual_domain_step(const struct type *root, uint64_t start, uint64_t address,
	const struct type *target, struct address_proof *proof, unsigned depth,
	struct subobject_search *search)
{
	if (!root || depth > ast_max_expression_depth || address < start)
		return false;
	uint64_t relative = address - start;
	if (!relative && type_unqualified_compatible(root, target) && type_is_complete_object(root)) {
		proof->element = root;
		proof->extent = 1;
		proof->known_extent = true;
		proof->position = 0;
		proof->start = start;
		proof->stride = type_object_size(root);
		return true;
	}
	if (root->kind == type_kind_array) {
		const struct array_type *array = (const struct array_type *)root;
		if (!type_is_complete_object(array->element))
			return false;
		uint64_t stride = type_object_size(array->element);
		uint64_t index = relative / stride;
		if (type_unqualified_compatible(array->element, target) && relative % stride == 0 &&
			(!array->count || index <= array->count)) {
			proof->element = array->element;
			proof->extent = array->count;
			proof->known_extent = array->count != 0;
			proof->position = index;
			proof->start = start;
			proof->stride = stride;
			return true;
		}
		return (!array->count || index < array->count) &&
			find_actual_domain(array->element, start + index * stride, address, target, proof, depth + 1, search);
	}
	if (type_is_record(root) && type_is_complete_object(root)) {
		bool found = false;
		struct address_proof selected = *proof;
		for (const struct record_member *member = type_record_definition(root)->members; member; member = member->next) {
			if (++search->work > subobject_search_work_limit) {
				search->exhausted = true;
				return false;
			}
			if (search->desired_path && (proof->path.count >= search->desired_path->count ||
				search->desired_path->members[proof->path.count] != member))
				continue;
			if (relative < member->offset || relative - member->offset >= type_object_size(member->type))
				continue;
			struct address_proof candidate = *proof;
			if (candidate.path.count >= ast_max_expression_depth) {
				search->exhausted = true;
				return false;
			}
			candidate.path.members[candidate.path.count++] = member;
			if (find_actual_domain(member->type, start + member->offset, address, target, &candidate, depth + 1, search)) {
				if (!found)
					selected = candidate;
				else
					selected.path.ambiguous = true;
				found = true;
				if (!type_record_definition(root)->is_union)
					break;
			}
			if (search->exhausted)
				return false;
		}
		if (found) {
			*proof = selected;
			return true;
		}
	}
	return false;
}

/* Failure memoization collapses shared union/type DAGs. A separate work cap
 * bounds distinct subobject paths even when the memo table fills. Query-local
 * state never changes AST/type/arena storage or allocates recursive heap state. */
static bool find_actual_domain(const struct type *root, uint64_t start, uint64_t address,
	const struct type *target, struct address_proof *proof, unsigned depth,
	struct subobject_search *search)
{
	if (!root || address < start)
		return false;
	if (search->exhausted || depth > ast_max_expression_depth || search->work++ >= subobject_search_work_limit) {
		search->exhausted = true;
		return false;
	}
	uint64_t relative = address - start;
	size_t slot = (((uintptr_t)root >> 3) ^ ((uintptr_t)target >> 3) ^
		(size_t)(relative * UINT64_C(11400714819323198485))) & (subobject_search_memo_size - 1);
	size_t empty = subobject_search_memo_size;
	for (size_t i = 0; !search->desired_path && i < subobject_search_memo_size; i++) {
		size_t index = (slot + i) & (subobject_search_memo_size - 1);
		const struct subobject_search_failure *failure = &search->failures[index];
		if (!failure->root) {
			empty = index;
			break;
		}
		if (failure->root == root && failure->target == target && failure->relative == relative)
			return false;
	}
	if (find_actual_domain_step(root, start, address, target, proof, depth, search))
		return true;
	if (!search->exhausted && empty < subobject_search_memo_size)
		search->failures[empty] = (struct subobject_search_failure) { root, target, relative };
	return false;
}

/* Preserve the search origin so an overlapping union conversion can later
 * be matched to a specific named member domain, rather than guessed by offset. */
static bool find_cast_domain(const struct type *root, uint64_t start, uint64_t address,
	const struct type *target, struct address_proof *proof, struct subobject_search *search)
{
	unsigned prefix = proof->path.count;
	bool inherited_alias = proof->path.ambiguous && proof->path.recovery_root;
	if (!find_actual_domain(root, start, address, target, proof, 0, search))
		return false;
	if (!inherited_alias) {
		proof->path.recovery_root = root;
		proof->path.recovery_start = start;
		proof->path.recovery_prefix = prefix;
		proof->path.recovery_target = target;
		proof->path.recovery_address = address;
		proof->path.recovery_domain_start = proof->start;
		proof->path.recovery_stride = proof->stride;
		proof->path.recovery_extent = proof->extent;
		proof->path.recovery_known_extent = proof->known_extent;
		proof->path.recovery_count = proof->path.count;
	}
	return true;
}

static bool recover_cast_domain(struct address_proof *proof, const struct type *target)
{
	uint64_t address = (uint64_t)proof->result.address.byte_addend;
	struct address_proof candidate = *proof;
	struct subobject_search search = { 0 };

	if (proof->byte_view_type)
		candidate.path = proof->byte_view_path;
	if (proof->byte_view_type && find_cast_domain(proof->byte_view_type,
		proof->byte_view_start, address, target, &candidate, &search)) {
		*proof = candidate;
		return true;
	}
	if (!proof->element || (proof->known_extent && proof->position >= proof->extent))
		goto failure;
	candidate.path = proof->path;
	if (type_is_record(proof->element) && find_cast_domain(proof->element, address,
		address, target, &candidate, &search)) {
		*proof = candidate;
		return true;
	}
	/* 6.7.2.1 initial-member/union reciprocal conversion: both the containing
	 * record and its initial member must really exist at this source address. */
	struct address_proof member = *proof;
	candidate.path = (struct address_path) { 0 };
	if (type_is_record(target) && find_actual_domain(target, address, address,
		proof->element, &member, 0, &search) && find_cast_domain(proof->storage_type, 0,
		address, target, &candidate, &search)) {
		*proof = candidate;
		return true;
	}
failure:
	if (search.exhausted) {
		proof->result.status = constant_invalid;
		proof->result.message = "static address subobject proof exceeds work limit (16384)";
	}
	return false;
}

/* Written member identity includes anonymous promotion ancestors. The bounded
 * lookup never substitutes offset equality for nominal member identity. */
static bool append_member_path(const struct type *record, const struct record_member *selected,
	struct address_path *path, unsigned *work)
{
	if (!type_is_record(record) || ++*work > subobject_search_work_limit ||
		path->count >= ast_max_expression_depth)
		return false;
	for (const struct record_member *member = type_record_definition(record)->members; member; member = member->next) {
		if (++*work > subobject_search_work_limit)
			return false;
		unsigned count = path->count;
		path->members[path->count++] = member;
		if (member == selected || (member->anonymous &&
			append_member_path(member->type, selected, path, work)))
			return true;
		path->count = count;
	}
	return false;
}

/* Member selection forms a NEW actual subobject domain. It never reuses an
 * enclosing array/record extent, even if adjacent members share an address. */
static struct address_proof prove_address(const struct ast_expression *expression);

static struct address_proof prove_member_address(const struct ast_expression *expression,
	const struct ast_member_expression *member, bool decay)
{
	const struct ast_expression *operand = member->operand;
	const struct type *record = operand->type;
	const struct type *selected = member->expression.type;
	struct address_proof proof;
	uint64_t addend;

	if (member->indirect) {
		record = ((const struct pointer_type *)record)->referent;
		proof = prove_address(operand);
	} else if (operand->kind == expression_indirection) {
		proof = prove_address(((const struct ast_indirection_expression *)operand)->operand);
	} else if (operand->kind == expression_member) {
		proof = prove_member_address(expression,
			(const struct ast_member_expression *)operand, false);
	} else {
		proof = (struct address_proof) { .result = direct_address(operand, expression->type) };
		proof.base_alignment = address_alignment(record);
		proof.storage_type = record;
		if (type_is_complete_object(record)) {
			proof.element = record;
			proof.stride = type_object_size(record);
			proof.extent = 1;
			proof.known_extent = true;
		}
	}
	if (proof.result.status != constant_value)
		return proof;
	if (!type_is_record(record) || !type_is_complete_object(record) || !proof.element ||
		!type_unqualified_compatible(proof.element, record))
		return address_failure(expression, constant_not_constant,
			"static member address requires a proven record subobject");
	if (proof.known_extent && proof.position >= proof.extent)
		return address_failure(expression, constant_invalid,
			"static member address requires an existing record subobject");
	unsigned path_work = 0;
	if (!append_member_path(record, member->member, &proof.path, &path_work))
		return address_failure(expression, constant_invalid,
			"static member identity proof exceeds work limit (16384)");
	addend = (uint64_t)proof.result.address.byte_addend;
	if (member->offset > (uint64_t)INT64_MAX - addend)
		return address_failure(expression, constant_invalid,
			"static pointer offset exceeds the relocation addend limit");
	addend += member->offset;
	proof.result.address.byte_addend = (int64_t)addend;
	proof.result.origin_type = expression->type;
	proof.original_domain = (struct address_domain) { 0 };
	proof.byte_view_type = NULL;
	proof.start = addend;
	proof.position = 0;
	proof.known_extent = true;
	proof.element = selected;
	proof.extent = 1;
	proof.stride = type_object_size(selected);
	if (decay) {
		const struct array_type *array = (const struct array_type *)selected;

		assert(selected->kind == type_kind_array && array->count);
		proof.element = array->element;
		proof.extent = array->count;
		proof.stride = type_object_size(array->element);
	}
	return proof;
}

static struct address_proof prove_address(const struct ast_expression *expression)
{
	const struct ast_expression *operand;
	struct address_proof proof;

	if (type_is_integer(expression->type)) {
		struct constant_result integer = evaluate_integer_constant(expression);
		if (integer.status == constant_value && !integer.bits)
			return (struct address_proof) { .is_null = true, .result = {
				.status = constant_value, .location = expression->location,
			} };
		return address_failure(expression, integer.status == constant_invalid ? constant_invalid : constant_not_constant,
			integer.status == constant_invalid ? integer.message : "integer source is not a null pointer constant");
	}
	switch (expression->kind) {
	case expression_nullptr:
		return (struct address_proof) { .is_null = true, .result = {
			.status = constant_value, .location = expression->location,
		} };
	case expression_conditional: {
		const struct ast_conditional_expression *node = (const struct ast_conditional_expression *)expression;
		struct constant_result condition = evaluate_initializer_condition(node->condition);

		if (condition.status != constant_value)
			return address_failure(expression, condition.status, condition.message);
		return prove_address(condition.bits ? node->then_value : node->else_value);
	}
	case expression_address:
		operand = ((const struct ast_address_expression *)expression)->operand;
		/* Subscripts are already lowered to *(base + index). The address
		 * operator cancels that indirection; one-past needs no dereference.
		 */
		if (operand->kind == expression_indirection)
			return prove_address(((const struct ast_indirection_expression *)operand)->operand);
		if (operand->kind == expression_member)
			return prove_member_address(expression, (const struct ast_member_expression *)operand, false);
		return address_base(expression, operand, false);
	case expression_array_decay:
		operand = ((const struct ast_array_decay_expression *)expression)->operand;
		if (operand->kind == expression_member)
			return prove_member_address(expression, (const struct ast_member_expression *)operand, true);
		if (operand->kind == expression_indirection) {
			const struct array_type *array = (const struct array_type *)operand->type;

			proof = prove_address(((const struct ast_indirection_expression *)operand)->operand);
			if (proof.result.status != constant_value)
				return proof;
			/* A row/subarray must actually exist: unlike &*, decay forms
			 * an address of its first element. Never turn a one-past row
			 * into a new in-bounds array domain.
			 */
			if (!proof.element || !type_unqualified_compatible(proof.element, operand->type))
				break;
			if (proof.known_extent && proof.position == proof.extent)
				return address_failure(expression, constant_invalid,
					"static pointer decay requires an existing array subobject");
			if (!array->count || !type_is_complete_object(array->element))
				break;
			proof.start = (uint64_t)proof.result.address.byte_addend;
			proof.position = 0;
			proof.extent = array->count;
			proof.known_extent = true;
			proof.element = array->element;
			proof.stride = type_object_size(array->element);
			proof.result.origin_type = expression->type;
			proof.original_domain = (struct address_domain) { 0 };
			proof.byte_view_type = NULL;
			return proof;
		}
		return address_base(expression, operand, true);
	case expression_function_decay:
		operand = ((const struct ast_function_decay_expression *)expression)->operand;
		if (operand->kind == expression_indirection)
			return prove_address(((const struct ast_indirection_expression *)operand)->operand);
		return address_base(expression, operand, false);
	case expression_cast:
	case expression_conversion: {
		const struct type *source;
		const struct type *target;
		unsigned alignment;
		bool explicit_cast = expression->kind == expression_cast;

		operand = explicit_cast ? ((const struct ast_cast_expression *)expression)->operand :
			((const struct ast_conversion_expression *)expression)->operand;
		if (expression->type->kind != type_kind_pointer && expression->type->kind != type_kind_nullptr)
			break;
		proof = prove_address(operand);
		if (proof.result.status != constant_value)
			return proof;
		if (proof.is_null)
			return proof;
		if (operand->type->kind != type_kind_pointer || expression->type->kind != type_kind_pointer)
			break;
		source = ((const struct pointer_type *)operand->type)->referent;
		target = ((const struct pointer_type *)expression->type)->referent;
		if (!explicit_cast && !direct_pointer_conversion(operand->type, expression->type))
			break;
		if ((source->kind == type_kind_function) != (target->kind == type_kind_function))
			break;
		/* Function-to-function casts preserve one function identity, not a
		 * promise that an incompatible signature can safely be called.
		 */
		if (target->kind == type_kind_function) {
			proof.explicit_cast |= explicit_cast;
			return proof;
		}
		alignment = address_alignment(target);
		if (proof.base_alignment < alignment ||
			(uint64_t)proof.result.address.byte_addend % alignment != 0)
			break;
		/* An implicit void detour cannot silently discard the original
		 * type/qualifier proof. A checked explicit object cast may do so,
		 * but must satisfy the target's guaranteed alignment.
		 */
		if (!explicit_cast && !proof.explicit_cast &&
			!direct_pointer_conversion(proof.result.origin_type, expression->type))
			break;
		proof.explicit_cast |= explicit_cast;
		if (target->kind == type_kind_void)
			return proof;
		if ((!proof.element || !type_unqualified_compatible(proof.element, target)) &&
			restore_address_domain(&proof, target))
			return proof;
		if ((!proof.element || !type_unqualified_compatible(proof.element, target)) &&
			recover_cast_domain(&proof, target))
			return proof;
		if (proof.result.status != constant_value)
			return proof;
		if (proof.element && !type_unqualified_compatible(proof.element, target)) {
			bool character = target->kind == type_kind_char || target->kind == type_kind_schar ||
				target->kind == type_kind_uchar;

			bool old_character = proof.element->kind == type_kind_char || proof.element->kind == type_kind_schar ||
				proof.element->kind == type_kind_uchar;

			if (character && old_character) {
				proof.element = target;
				return proof;
			}
			save_address_domain(&proof);
			if (character && type_is_complete_object(proof.element) &&
				(!proof.known_extent || proof.position < proof.extent)) {
				/* A character view covers the pointed object, not an invented
				 * larger enclosing array. &array legitimately views all its bytes.
				 */
				proof.byte_view_path = proof.path;
				proof.byte_view_type = proof.element;
				proof.byte_view_start = (uint64_t)proof.result.address.byte_addend;
				proof.extent = type_object_size(proof.element);
				proof.known_extent = true;
				proof.start = (uint64_t)proof.result.address.byte_addend;
				proof.position = 0;
				proof.stride = 1;
				proof.element = target;
			} else {
				/* Reinterpreting an address does not manufacture an array of
				 * the new type. Direct storage is legal; arithmetic needs a domain.
				 */
				proof.element = NULL;
			}
		}
		return proof;
	}
	case expression_pointer_offset: {
		const struct ast_pointer_offset_expression *offset =
			(const struct ast_pointer_offset_expression *)expression;
		struct constant_result index;
		uint64_t magnitude;
		bool negative = false;
		bool backward;
		const struct type *referent = ((const struct pointer_type *)offset->base->type)->referent;

		proof = prove_address(offset->base);
		if (proof.result.status != constant_value)
			return proof;
		if (proof.is_null)
			return address_failure(expression, constant_not_constant,
				"pointer arithmetic on null is not a static address constant");
		index = evaluate_integer_constant(offset->index);
		if (index.status != constant_value) {
			proof.result.status = index.status;
			proof.result.location = index.location;
			proof.result.message = index.message;
			return proof;
		}
		/* Neither a later composite nor a cast-to-complete type can supply
		 * missing source extent. Nested decay preserves each subobject's own
		 * captured bound, not the larger enclosing storage extent.
		 */
		if (!proof.element || !type_unqualified_compatible(proof.element, referent) ||
			proof.stride != offset->element_size)
			break;
		magnitude = index.bits;
		if (!type_is_unsigned(index.type)) {
			uint64_t sign = UINT64_C(1) << (type_integer_width(index.type) - 1);

			negative = (index.bits & sign) != 0;
			if (negative)
				magnitude = (integer_mask(index.type) - index.bits) + 1;
		}
		backward = offset->subtract != negative;
		if ((backward && magnitude > proof.position) ||
			(!backward && proof.known_extent && magnitude > proof.extent - proof.position))
			return address_failure(expression, constant_invalid,
				"static pointer offset is outside its captured object bounds");
		if (!backward && magnitude > UINT64_MAX - proof.position)
			return address_failure(expression, constant_invalid,
				"static pointer offset exceeds the relocation addend limit");
		proof.position = backward ? proof.position - magnitude : proof.position + magnitude;
		if (proof.position > ((uint64_t)INT64_MAX - proof.start) / proof.stride)
			return address_failure(expression, constant_invalid,
				"static pointer offset exceeds the relocation addend limit");
		proof.result.address.byte_addend = (int64_t)(proof.start + proof.position * proof.stride);
		return proof;
	}
	default:
		break;
	}
	return address_failure(expression, constant_not_constant,
		"file-scope pointer initializer requires a supported null or direct address constant expression");
}

struct address_initializer_result evaluate_address_initializer(const struct ast_expression *expression)
{
	assert(expression && expression->type && expression->depth <= ast_max_expression_depth);
	struct address_proof proof = prove_address(expression);
	if (proof.result.status == constant_value && proof.is_null)
		return (struct address_initializer_result) { .status = constant_not_constant,
			.location = expression->location, .message = "null constant is not a symbolic address" };
	return proof.result;
}

static struct null_initializer_result evaluate_pointer_null(const struct ast_expression *expression)
{
	struct address_proof proof = prove_address(expression);
	if (proof.result.status == constant_invalid)
		return (struct null_initializer_result) { proof.result.status, proof.result.location, proof.result.message };
	if (proof.result.status == constant_value && proof.is_null)
		return (struct null_initializer_result) { constant_value, expression->location, NULL };
	return (struct null_initializer_result) { constant_not_constant, expression->location,
		"file-scope pointer initializer requires a supported null constant expression" };
}

static struct constant_result evaluate_initializer_condition(const struct ast_expression *expression)
{
	if (type_is_integer(expression->type))
		return evaluate(expression, true, true);
	struct address_proof proof = prove_address(expression);
	return (struct constant_result) { .status = proof.result.status,
		.bits = proof.result.status == constant_value && !proof.is_null,
		.location = proof.result.location, .message = proof.result.message };
}

/* Symbol identity is enough for same-object equality and offsets. Do not
 * invent linker placement or assume distinct potentially merged strings differ. */
static struct constant_result compare_initializer_addresses(const struct ast_binary_expression *node)
{
	const struct ast_expression *expression = &node->expression;
	struct address_proof left_proof = prove_address(node->left);
	struct address_proof right_proof = prove_address(node->right);
	struct address_initializer_result left = left_proof.result, right = right_proof.result;
	bool equal;
	int order = 0;

	if (left.status != constant_value)
		return constant_failure(expression, left.status, left.message);
	if (right.status != constant_value)
		return constant_failure(expression, right.status, right.message);
	if (left_proof.is_null || right_proof.is_null) {
		if (node->operation != binary_equal && node->operation != binary_not_equal)
			return constant_failure(expression, constant_not_constant, "null address ordering is not a constant condition");
		equal = left_proof.is_null == right_proof.is_null;
	} else {
		bool same = left.address.kind == right.address.kind;
		if (same) {
			switch (left.address.kind) {
			case static_address_object: same = left.address.base.object == right.address.base.object; break;
			case static_address_function: same = left.address.base.function == right.address.base.function; break;
			case static_address_string: same = left.address.base.string == right.address.base.string; break;
			case static_address_compound_literal:
				same = left.address.base.compound_literal == right.address.base.compound_literal;
				break;
			}
		}
		if (!same) {
			bool distinct = left.address.kind == static_address_function &&
				right.address.kind == static_address_function;
			if (left.address.kind == static_address_object && right.address.kind == static_address_object &&
				!left.address.byte_addend && !right.address.byte_addend) {
				struct token a = left.address.base.object->name, b = right.address.base.object->name;
				const char *prefix = ".Lkcc.literal.";
				size_t length = 14;
				bool literal_a = a.length >= length && !memcmp(a.spelling_location.source->data +
					a.spelling_location.offset, prefix, length);
				bool literal_b = b.length >= length && !memcmp(b.spelling_location.source->data +
					b.spelling_location.offset, prefix, length);
				distinct = !literal_a && !literal_b;
			}
			if (distinct && (node->operation == binary_equal || node->operation == binary_not_equal))
				return constant_success(expression, node->operation == binary_not_equal);
			return constant_failure(expression, constant_not_constant,
				"comparison of distinct symbolic bases is not a supported constant condition");
		}
		order = (left.address.byte_addend > right.address.byte_addend) -
			(left.address.byte_addend < right.address.byte_addend);
		equal = order == 0;
	}
	switch (node->operation) {
	case binary_equal: return constant_success(expression, equal);
	case binary_not_equal: return constant_success(expression, !equal);
	case binary_less: return constant_success(expression, order < 0);
	case binary_less_equal: return constant_success(expression, order <= 0);
	case binary_greater: return constant_success(expression, order > 0);
	case binary_greater_equal: return constant_success(expression, order >= 0);
	default: return constant_failure(expression, constant_not_constant, "unsupported constant address operation");
	}
}

/* A suitably converted union pointer may designate each compatible member.
 * Resolve only cast-produced alternatives against the other operand's nominal
 * path. Direct .a and .b accesses never acquire this conversion alias. */
static void resolve_cast_alias(struct address_proof *proof, const struct address_path *desired)
{
	if (!proof->path.ambiguous || !proof->path.recovery_root || !proof->element)
		return;
	unsigned prefix = proof->path.recovery_prefix;
	if (prefix > desired->count || prefix > proof->path.count ||
		memcmp(proof->path.members, desired->members, prefix * sizeof(desired->members[0])))
		return;
	struct address_proof candidate = *proof;
	struct subobject_search search = { .desired_path = desired };
	candidate.path.count = prefix;
	candidate.path.ambiguous = false;
	unsigned recovered_count = proof->path.recovery_count;
	if (recovered_count > proof->path.count || desired->count != proof->path.count ||
		memcmp(proof->path.members + recovered_count, desired->members + recovered_count,
			(proof->path.count - recovered_count) * sizeof(desired->members[0])))
		return;
	if (find_actual_domain(proof->path.recovery_root, proof->path.recovery_start,
		proof->path.recovery_address, proof->path.recovery_target, &candidate, 0, &search) &&
		candidate.start == proof->path.recovery_domain_start && candidate.stride == proof->path.recovery_stride &&
		candidate.known_extent == proof->path.recovery_known_extent &&
		(!candidate.known_extent || candidate.extent == proof->path.recovery_extent) &&
		candidate.path.count == recovered_count &&
		!memcmp(candidate.path.members, desired->members, recovered_count * sizeof(desired->members[0]))) {
		memcpy(proof->path.members, candidate.path.members, recovered_count * sizeof(desired->members[0]));
		proof->path.ambiguous = false;
	}
	if (search.exhausted) {
		proof->result.status = constant_invalid;
		proof->result.message = "static address subobject proof exceeds work limit (16384)";
	}
}

/* Only the private address-initializer predicate context admits this form.
 * Strict integer/arithmetic constant expression operand rules are unchanged. */
static struct constant_result difference_initializer_addresses(const struct ast_pointer_difference_expression *node)
{
	const struct ast_expression *expression = &node->expression;
	struct address_proof left = prove_address(node->left), right = prove_address(node->right);
	if (left.result.status != constant_value)
		return constant_failure(expression, left.result.status, left.result.message);
	if (right.result.status != constant_value)
		return constant_failure(expression, right.result.status, right.result.message);
	bool same = left.result.address.kind == right.result.address.kind;
	if (same) {
		switch (left.result.address.kind) {
		case static_address_object:
			same = left.result.address.base.object == right.result.address.base.object; break;
		case static_address_function:
			same = left.result.address.base.function == right.result.address.base.function; break;
		case static_address_string:
			same = left.result.address.base.string == right.result.address.base.string; break;
		case static_address_compound_literal:
			same = left.result.address.base.compound_literal == right.result.address.base.compound_literal; break;
		}
	}
	if (same && !left.is_null && !right.is_null) {
		resolve_cast_alias(&right, &left.path);
		resolve_cast_alias(&left, &right.path);
		if (left.result.status != constant_value)
			return constant_failure(expression, left.result.status, left.result.message);
		if (right.result.status != constant_value)
			return constant_failure(expression, right.result.status, right.result.message);
	}
	if (!same || left.is_null || right.is_null || !left.element || !right.element ||
		!node->element_size || left.stride != node->element_size || right.stride != node->element_size ||
		left.start != right.start || left.known_extent != right.known_extent || (left.known_extent && left.extent != right.extent) ||
		left.path.ambiguous || right.path.ambiguous || left.path.count != right.path.count ||
		memcmp(left.path.members, right.path.members, left.path.count * sizeof(left.path.members[0])) ||
		!type_unqualified_compatible(left.element, right.element))
		return constant_failure(expression, constant_not_constant,
			"static pointer difference requires the same captured array domain");
	uint64_t a = (uint64_t)left.result.address.byte_addend, b = (uint64_t)right.result.address.byte_addend;
	bool negative = a < b;
	uint64_t magnitude = negative ? b - a : a - b;
	if (magnitude % node->element_size)
		return constant_failure(expression, constant_not_constant,
			"static pointer difference is not an integral element distance");
	magnitude /= node->element_size;
	uint64_t sign = UINT64_C(1) << (type_integer_width(expression->type) - 1);
	if (magnitude > (negative ? sign : sign - 1))
		return constant_failure(expression, constant_invalid,
			"static pointer difference is not representable in ptrdiff_t");
	return constant_success(expression, negative ? UINT64_C(0) - magnitude : magnitude);
}
