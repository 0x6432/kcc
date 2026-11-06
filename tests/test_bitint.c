#include "bitint.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>

static uint64_t bits(int value, unsigned width)
{
	return (uint64_t)value & ((UINT64_C(1) << width) - 1);
}

static void test_layout(void)
{
	unsigned size, alignment;
	for (unsigned width = 1; width <= 64; width++) {
		unsigned expected = width <= 8 ? 1 : width <= 16 ? 2 : width <= 32 ? 4 : 8;
		size = alignment = 0;
		assert(bitint_amd64_layout((struct bitint_type){width, true}, &size, &alignment) == bitint_ok);
		assert(size == expected && alignment == expected);
		if (width >= 2) {
			size = alignment = 0;
			assert(bitint_amd64_layout((struct bitint_type){width, false}, &size, &alignment) == bitint_ok);
			assert(size == expected && alignment == expected);
		}
	}
	size = alignment = 99;
	assert(bitint_amd64_layout((struct bitint_type){1, false}, &size, &alignment) == bitint_invalid_width);
	assert(size == 99 && alignment == 99);
	assert(bitint_amd64_layout((struct bitint_type){65, true}, &size, &alignment) == bitint_invalid_width);
	assert(size == 99 && alignment == 99);
}

static void test_literal_width(void)
{
	struct bitint_type type = { 17, true };

	assert(bitint_literal_type(0, false, &type) == bitint_ok && type.width == 2 && !type.is_unsigned);
	assert(bitint_literal_type(1, false, &type) == bitint_ok && type.width == 2);
	assert(bitint_literal_type(2, false, &type) == bitint_ok && type.width == 3);
	assert(bitint_literal_type(UINT64_C(0x7fffffffffffffff), false, &type) == bitint_ok && type.width == 64);
	assert(bitint_literal_type(UINT64_C(0x8000000000000000), false, &type) == bitint_invalid_width);
	assert(type.width == 64 && !type.is_unsigned);
	assert(bitint_literal_type(0, true, &type) == bitint_ok && type.width == 1 && type.is_unsigned);
	assert(bitint_literal_type(1, true, &type) == bitint_ok && type.width == 1);
	assert(bitint_literal_type(2, true, &type) == bitint_ok && type.width == 2);
	assert(bitint_literal_type(UINT64_MAX, true, &type) == bitint_ok && type.width == 64);
}

static void test_conversions(void)
{
	struct bitint_type out = { 12, false };

	assert(bitint_promote((struct bitint_type){ 3, true }, &out) == bitint_ok);
	assert(out.width == 3 && out.is_unsigned);
	assert(bitint_promote((struct bitint_type){ 1, false }, &out) == bitint_invalid_width);
	assert(out.width == 3 && out.is_unsigned);
	assert(bitint_common_type((struct bitint_type){ 5, false },
		(struct bitint_type){ 4, true }, &out) == bitint_ok);
	assert(out.width == 5 && !out.is_unsigned);
	assert(bitint_common_type((struct bitint_type){ 5, true },
		(struct bitint_type){ 5, false }, &out) == bitint_ok);
	assert(out.width == 5 && out.is_unsigned);
	assert(bitint_common_type((struct bitint_type){ 3, false },
		(struct bitint_type){ 4, true }, &out) == bitint_ok);
	assert(out.width == 4 && out.is_unsigned);
}

static void test_small_signed(void)
{
	for (unsigned width = 2; width <= 7; width++) {
		struct bitint_type type = { width, false };
		int min = -(1 << (width - 1)), max = (1 << (width - 1)) - 1;
		for (int a = min; a <= max; a++) {
			for (int b = min; b <= max; b++) {
				uint64_t result, a_bits = bits(a, width), b_bits = bits(b, width);
				int order;
				const enum bitint_operation ops[] = { bitint_add, bitint_subtract, bitint_multiply };
				const int expected[] = { a + b, a - b, a * b };

				assert(bitint_compare(type, a_bits, b_bits, &order) == bitint_ok);
				assert(order == (a > b) - (a < b));
				for (unsigned i = 0; i < 3; i++) {
					enum bitint_status status;
					result = UINT64_MAX;
					status = bitint_binary(type, ops[i], a_bits, b_bits, &result);
					if (expected[i] < min || expected[i] > max)
						assert(status == bitint_overflow && result == UINT64_MAX);
					else
						assert(status == bitint_ok && result == bits(expected[i], width));
				}
				for (unsigned i = 0; i < 2; i++) {
					enum bitint_status status;
					result = UINT64_MAX;
					status = bitint_binary(type, i ? bitint_remainder : bitint_divide, a_bits, b_bits, &result);
					if (!b)
						assert(status == bitint_division_by_zero && result == UINT64_MAX);
					else if (a == min && b == -1)
						assert(status == bitint_overflow && result == UINT64_MAX);
					else
						assert(status == bitint_ok && result == bits(i ? a % b : a / b, width));
				}
			}
		}
	}
}

static void test_boundaries(void)
{
	struct bitint_type s64 = { 64, false }, u64 = { 64, true };
	struct bitint_type s5 = { 5, false }, u3 = { 3, true }, invalid = { 65, false };
	uint64_t out = 77;

	assert(!bitint_type_valid((struct bitint_type){ 1, false }));
	assert(bitint_type_valid((struct bitint_type){ 1, true }));
	assert(bitint_binary(invalid, bitint_add, 1, 2, &out) == bitint_invalid_width && out == 77);
	assert(bitint_binary(s5, bitint_add, 32, 1, &out) == bitint_invalid_value && out == 77);
	assert(bitint_binary(s64, bitint_add, INT64_MAX, 1, &out) == bitint_overflow && out == 77);
	assert(bitint_binary(s64, bitint_multiply, UINT64_C(1) << 63, UINT64_MAX, &out) == bitint_overflow && out == 77);
	assert(bitint_binary(s64, bitint_divide, UINT64_C(1) << 63, UINT64_MAX, &out) == bitint_overflow && out == 77);
	assert(bitint_binary(s64, bitint_remainder, UINT64_C(1) << 63, UINT64_MAX, &out) == bitint_overflow && out == 77);
	assert(bitint_binary(u64, bitint_add, UINT64_MAX, 1, &out) == bitint_ok && out == 0);
	assert(bitint_binary(u64, bitint_multiply, UINT64_MAX, 2, &out) == bitint_ok && out == UINT64_MAX - 1);
	assert(bitint_binary(u3, bitint_subtract, 0, 1, &out) == bitint_ok && out == 7);
	assert(bitint_binary(u3, bitint_multiply, 7, 7, &out) == bitint_ok && out == 1);
	assert(bitint_binary(u3, bitint_divide, 7, 2, &out) == bitint_ok && out == 3);
	assert(bitint_binary(u3, bitint_remainder, 7, 2, &out) == bitint_ok && out == 1);
	assert(bitint_binary(u3, bitint_xor, 7, 3, &out) == bitint_ok && out == 4);
	assert(bitint_convert(s5, u64, 31, &out) == bitint_ok && out == UINT64_MAX);
	assert(bitint_convert(s5, u3, 30, &out) == bitint_ok && out == 6);
	assert(bitint_convert(u3, s5, 7, &out) == bitint_ok && out == 7);
}

static void test_unary_and_shifts(void)
{
	struct bitint_type s5 = {5, false}, u3 = {3, true}, s64 = {64, false};
	uint64_t out = 77;
	assert(bitint_unary(s5, bitint_unary_minus, 16, &out) == bitint_overflow && out == 77);
	assert(bitint_unary(s5, bitint_unary_minus, 31, &out) == bitint_ok && out == 1);
	assert(bitint_unary(u3, bitint_unary_minus, 1, &out) == bitint_ok && out == 7);
	assert(bitint_unary(u3, bitint_complement, 5, &out) == bitint_ok && out == 2);
	assert(bitint_shift(s5, bitint_shift_right, 16, 2, &out) == bitint_ok && out == 28);
	assert(bitint_shift(s64, bitint_shift_right, UINT64_C(1)<<63, 63, &out) == bitint_ok && out == UINT64_MAX);
	assert(bitint_shift(u3, bitint_shift_left, 7, 2, &out) == bitint_ok && out == 4);
	assert(bitint_shift(s5, bitint_shift_left, 4, 2, &out) == bitint_overflow && out == 4);
	assert(bitint_shift(s5, bitint_shift_left, 31, 0, &out) == bitint_overflow && out == 4);
	assert(bitint_shift(s5, bitint_shift_right, 2, 5, &out) == bitint_invalid_shift && out == 4);
}

int main(void)
{
	test_layout();
	test_literal_width();
	test_conversions();
	test_small_signed();
	test_boundaries();
	test_unary_and_shifts();
	puts("Bounded bit-precise arithmetic primitives passed");
	return 0;
}
