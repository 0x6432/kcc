#include "bitint.h"

#include <stddef.h>

bool bitint_type_valid(struct bitint_type type)
{
	return type.width <= 64 && type.width >= (type.is_unsigned ? 1u : 2u);
}

static uint64_t mask_for(unsigned width)
{
	return width == 64 ? UINT64_MAX : (UINT64_C(1) << width) - 1;
}

static bool negative(struct bitint_type type, uint64_t value)
{
	return !type.is_unsigned && (value & (UINT64_C(1) << (type.width - 1))) != 0;
}

static uint64_t magnitude(uint64_t value, uint64_t mask, bool sign)
{
	return sign ? ((~value + 1) & mask) : value;
}

enum bitint_status bitint_literal_type(uint64_t value, bool is_unsigned,
	struct bitint_type *result)
{
	unsigned bits = 0;
	uint64_t remaining = value;

	while (remaining) {
		bits++;
		remaining >>= 1;
	}
	if (!is_unsigned && bits == 64)
		return bitint_invalid_width;
	result->width = is_unsigned ? (bits ? bits : 1) : (bits ? bits + 1 : 2);
	result->is_unsigned = is_unsigned;
	return bitint_ok;
}

enum bitint_status bitint_promote(struct bitint_type type, struct bitint_type *out)
{
	if (!bitint_type_valid(type))
		return bitint_invalid_width;
	*out = type;
	return bitint_ok;
}

enum bitint_status bitint_common_type(struct bitint_type left, struct bitint_type right,
	struct bitint_type *out)
{
	if (!bitint_type_valid(left) || !bitint_type_valid(right))
		return bitint_invalid_width;
	/* Ranks increase with width; signed and unsigned partners have equal rank.
	 * A wider signed type represents every value of a narrower unsigned type. */
	if (left.width != right.width)
		*out = left.width > right.width ? left : right;
	else
		*out = (struct bitint_type) { left.width, left.is_unsigned || right.is_unsigned };
	return bitint_ok;
}

enum bitint_status bitint_binary(struct bitint_type type, enum bitint_operation op,
	uint64_t left, uint64_t right, uint64_t *out)
{
	uint64_t mask, result = 0, a, b, limit;
	bool sa, sb, sr;

	if (!bitint_type_valid(type))
		return bitint_invalid_width;
	mask = mask_for(type.width);
	if ((left & ~mask) || (right & ~mask))
		return bitint_invalid_value;
	sa = negative(type, left);
	sb = negative(type, right);
	switch (op) {
	case bitint_add:
		result = (left + right) & mask;
		sr = negative(type, result);
		if (!type.is_unsigned && sa == sb && sr != sa)
			return bitint_overflow;
		break;
	case bitint_subtract:
		result = (left - right) & mask;
		sr = negative(type, result);
		if (!type.is_unsigned && sa != sb && sr != sa)
			return bitint_overflow;
		break;
	case bitint_multiply:
		if (type.is_unsigned) {
			result = (left * right) & mask;
			break;
		}
		a = magnitude(left, mask, sa);
		b = magnitude(right, mask, sb);
		limit = UINT64_C(1) << (type.width - 1);
		if (sa == sb)
			limit--;
		if (b && a > limit / b)
			return bitint_overflow;
		result = (a * b) & mask;
		if (sa != sb)
			result = (~result + 1) & mask;
		break;
	case bitint_divide:
	case bitint_remainder:
		if (!right)
			return bitint_division_by_zero;
		a = magnitude(left, mask, sa);
		b = magnitude(right, mask, sb);
		/* MIN / -1 and MIN % -1 are both undefined for signed C. */
		if (!type.is_unsigned && sa && sb && a == (UINT64_C(1) << (type.width - 1)) && b == 1)
			return bitint_overflow;
		result = op == bitint_divide ? a / b : a % b;
		if ((op == bitint_divide ? sa != sb : sa))
			result = (~result + 1) & mask;
		break;
	case bitint_and: result = left & right; break;
	case bitint_or: result = left | right; break;
	case bitint_xor: result = left ^ right; break;
	default: return bitint_invalid_value;
	}
	*out = result;
	return bitint_ok;
}

enum bitint_status bitint_compare(struct bitint_type type, uint64_t left,
	uint64_t right, int *out)
{
	uint64_t mask;
	bool sa, sb;

	if (!bitint_type_valid(type))
		return bitint_invalid_width;
	mask = mask_for(type.width);
	if ((left & ~mask) || (right & ~mask))
		return bitint_invalid_value;
	sa = negative(type, left);
	sb = negative(type, right);
	*out = sa != sb ? (sa ? -1 : 1) : (left > right) - (left < right);
	return bitint_ok;
}

enum bitint_status bitint_convert(struct bitint_type from, struct bitint_type to,
	uint64_t value, uint64_t *out)
{
	uint64_t from_mask;

	if (!bitint_type_valid(from) || !bitint_type_valid(to))
		return bitint_invalid_width;
	from_mask = mask_for(from.width);
	if (value & ~from_mask)
		return bitint_invalid_value;
	if (negative(from, value))
		value |= ~from_mask;
	*out = value & mask_for(to.width);
	return bitint_ok;
}
