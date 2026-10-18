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
