#include "consteval.h"
#include "type.h"

#include <assert.h>
#include <stdint.h>

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

static struct constant_result evaluate(const struct ast_expression *expression, bool evaluated);

static struct constant_result evaluate_unary(const struct ast_unary_expression *node, bool evaluated)
{
	const struct ast_expression *expression = &node->expression;
	struct constant_result operand = evaluate(node->operand, evaluated);
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

static struct constant_result evaluate_binary(const struct ast_binary_expression *node, bool evaluated)
{
	const struct ast_expression *expression = &node->expression;
	struct constant_result left = evaluate(node->left, evaluated);
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
	right = evaluate(node->right, evaluated);
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
static struct constant_result evaluate(const struct ast_expression *expression, bool evaluated)
{
	assert(expression && expression->type && expression->depth <= ast_max_expression_depth);
	if (!type_is_integer(expression->type))
		return constant_failure(expression, constant_not_constant, "integer constant expression requires integer operands");
	switch (expression->kind) {
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
		struct constant_result value = evaluate(operand, evaluated);

		if (value.status != constant_value)
			return value;
		return constant_success(expression, evaluated ? converted_bits(value, expression->type) : 0);
	}
	case expression_unary:
		return evaluate_unary((const struct ast_unary_expression *)expression, evaluated);
	case expression_binary:
		return evaluate_binary((const struct ast_binary_expression *)expression, evaluated);
	case expression_logical: {
		const struct ast_logical_expression *node = (const struct ast_logical_expression *)expression;
		struct constant_result left = evaluate(node->left, evaluated);
		struct constant_result right;
		bool evaluate_right;

		if (left.status != constant_value)
			return left;
		evaluate_right = evaluated && (node->operation == logical_and ? left.bits != 0 : left.bits == 0);
		right = evaluate(node->right, evaluate_right);
		if (right.status != constant_value)
			return right;
		return constant_success(expression, evaluated && (node->operation == logical_and ?
			left.bits && right.bits : left.bits || right.bits));
	}
	case expression_conditional: {
		const struct ast_conditional_expression *node = (const struct ast_conditional_expression *)expression;
		struct constant_result condition = evaluate(node->condition, evaluated);
		struct constant_result then_value;
		struct constant_result else_value;

		if (condition.status != constant_value)
			return condition;
		then_value = evaluate(node->then_value, evaluated && condition.bits != 0);
		if (then_value.status != constant_value)
			return then_value;
		else_value = evaluate(node->else_value, evaluated && condition.bits == 0);
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
		left = evaluate(node->left, false);
		if (left.status != constant_value)
			return left;
		right = evaluate(node->right, false);
		return right.status == constant_value ? constant_success(expression, 0) : right;
	}
	default:
		return constant_failure(expression, constant_not_constant, "operand is not an integer constant expression");
	}
}

struct constant_result evaluate_integer_constant(const struct ast_expression *expression)
{
	return evaluate(expression, true);
}

/* The source is checked before assignment conversion. Arbitrary nullptr_t
 * values, pointer loads, address expressions and pointer arithmetic are not
 * proved constant merely because their runtime value might be null.
 */
struct null_initializer_result evaluate_null_initializer(const struct ast_expression *expression)
{
	assert(expression && expression->type && expression->depth <= ast_max_expression_depth);
	if (type_is_integer(expression->type)) {
		struct constant_result value = evaluate_integer_constant(expression);

		if (value.status == constant_invalid)
			return (struct null_initializer_result) { value.status, value.location, value.message };
		if (value.status == constant_value && value.bits == 0)
			return (struct null_initializer_result) { constant_value, expression->location, NULL };
	} else if (expression->kind == expression_address &&
		((const struct ast_address_expression *)expression)->operand->kind == expression_indirection) {
		const struct ast_indirection_expression *indirection =
			(const struct ast_indirection_expression *)((const struct ast_address_expression *)expression)->operand;

		/* &* cancels without accessing the pointed object, even for null. */
		return evaluate_null_initializer(indirection->operand);
	} else if (expression->kind == expression_nullptr) {
		return (struct null_initializer_result) { constant_value, expression->location, NULL };
	} else if ((expression->kind == expression_cast || expression->kind == expression_conversion) &&
		(expression->type->kind == type_kind_pointer || expression->type->kind == type_kind_nullptr)) {
		const struct ast_expression *operand = expression->kind == expression_cast ?
			((const struct ast_cast_expression *)expression)->operand :
			((const struct ast_conversion_expression *)expression)->operand;

		return evaluate_null_initializer(operand);
	}
	return (struct null_initializer_result) {
		constant_not_constant, expression->location,
		"file-scope pointer initializer requires a supported null constant expression",
	};
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
	case expression_external_object:
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
		return (struct address_initializer_result) {
			.status = constant_not_constant, .location = expression->location,
			.message = "file-scope pointer initializer requires a supported null or direct address constant expression",
		};
	}
}

/* Use captured expression types, not a canonical symbol's later composite.
 * No reinterpret casts (including incompatible function signatures), qualifier
 * removal, integer detours or object/function cross-conversions are admitted.
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
 * domain or changes its stride. One-past is a position, not a new object.
 */
struct address_proof {
	struct address_initializer_result result;
	const struct type *element;
	uint64_t extent;
	uint64_t stride;
	uint64_t position;
	uint64_t start;
};

static struct address_proof address_failure(const struct ast_expression *expression,
	enum constant_status status, const char *message)
{
	return (struct address_proof) { .result = {
		.status = status, .location = expression->location, .message = message,
	} };
}

static struct address_proof address_base(const struct ast_expression *expression,
	const struct ast_expression *operand, bool decay)
{
	struct address_proof proof = { .result = direct_address(operand, expression->type) };
	const struct type *type = operand->type;

	if (proof.result.status != constant_value)
		return proof;
	if (decay && type->kind == type_kind_array) {
		const struct array_type *array = (const struct array_type *)type;

		if (array->count && type_is_complete_object(array->element)) {
			proof.element = array->element;
			proof.extent = array->count;
			proof.stride = type_object_size(array->element);
		}
	} else if (!decay && operand->kind == expression_external_object &&
		type_is_complete_object(type)) {
		proof.element = type;
		proof.extent = 1;
		proof.stride = type_object_size(type);
	}
	return proof;
}

static struct address_proof prove_address(const struct ast_expression *expression)
{
	const struct ast_expression *operand;
	struct address_proof proof;

	switch (expression->kind) {
	case expression_address:
		operand = ((const struct ast_address_expression *)expression)->operand;
		/* Subscripts are already lowered to *(base + index). The address
		 * operator cancels that indirection; one-past needs no dereference.
		 */
		if (operand->kind == expression_indirection)
			return prove_address(((const struct ast_indirection_expression *)operand)->operand);
		return address_base(expression, operand, false);
	case expression_array_decay:
		operand = ((const struct ast_array_decay_expression *)expression)->operand;
		if (operand->kind == expression_indirection) {
			const struct array_type *array = (const struct array_type *)operand->type;

			proof = prove_address(((const struct ast_indirection_expression *)operand)->operand);
			if (proof.result.status != constant_value)
				return proof;
			/* A row/subarray must actually exist: unlike &*, decay forms
			 * an address of its first element. Never turn a one-past row
			 * into a new in-bounds array domain.
			 */
			if (!proof.element)
				break;
			if (proof.position == proof.extent)
				return address_failure(expression, constant_invalid,
					"static pointer decay requires an existing array subobject");
			if (!array->count || !type_is_complete_object(array->element))
				break;
			proof.start = (uint64_t)proof.result.address.byte_addend;
			proof.position = 0;
			proof.extent = array->count;
			proof.element = array->element;
			proof.stride = type_object_size(array->element);
			proof.result.origin_type = expression->type;
			return proof;
		}
		return address_base(expression, operand, true);
	case expression_function_decay:
		return address_base(expression, ((const struct ast_function_decay_expression *)expression)->operand, false);
	case expression_cast:
	case expression_conversion:
		operand = expression->kind == expression_cast ?
			((const struct ast_cast_expression *)expression)->operand :
			((const struct ast_conversion_expression *)expression)->operand;
		if (!direct_pointer_conversion(operand->type, expression->type))
			break;
		proof = prove_address(operand);
		if (proof.result.status != constant_value)
			return proof;
		if (direct_pointer_conversion(proof.result.origin_type, expression->type))
			return proof;
		break;
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
			(!backward && magnitude > proof.extent - proof.position))
			return address_failure(expression, constant_invalid,
				"static pointer offset is outside its captured object bounds");
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
	return prove_address(expression).result;
}
