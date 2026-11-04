#ifndef KCC_BITINT_H
#define KCC_BITINT_H

#include <stdbool.h>
#include <stdint.h>

/* Bounded, target-independent arithmetic foundation. This is NOT yet an ABI,
 * object layout, language type, or permission to accept _BitInt in source.
 * Values use the low N bits of a two's-complement representation; no host
 * signed overflow or shifts by 64 are required. Signed widths are 2..64,
 * unsigned widths 1..64. Larger widths must be rejected, not truncated.
 */
struct bitint_type {
	unsigned width;
	bool is_unsigned;
};

enum bitint_status {
	bitint_ok,
	bitint_invalid_width,
	bitint_invalid_value,
	bitint_overflow,
	bitint_division_by_zero,
};

enum bitint_operation {
	bitint_add, bitint_subtract, bitint_multiply, bitint_divide, bitint_remainder,
	bitint_and, bitint_or, bitint_xor,
};

bool bitint_type_valid(struct bitint_type type);
/* Minimal C23 wb/WB literal type for nonnegative spelling value. A signed
 * value requiring 65 bits is outside this implementation's bound. */
enum bitint_status bitint_literal_type(uint64_t value, bool is_unsigned,
	struct bitint_type *result);
/* Ordinary (non-bit-field) bit-precise integer operands are not promoted.
 * These helpers cover only bit-precise/bit-precise operands; mixing a standard
 * integer or a bit-field requires the full C23 conversion and rank rules. */
enum bitint_status bitint_promote(struct bitint_type type, struct bitint_type *out);
enum bitint_status bitint_common_type(struct bitint_type left, struct bitint_type right,
	struct bitint_type *out);
/* Same-type operations only: callers must perform C's conversions first.
 * The input and output are canonical low-width bits. On failure *out is
 * unchanged. Signed overflow and division by zero are errors; unsigned wraps.
 */
enum bitint_status bitint_binary(struct bitint_type type, enum bitint_operation op,
	uint64_t left, uint64_t right, uint64_t *out);
/* Return -1/0/1 after comparing canonical same-type operands. */
enum bitint_status bitint_compare(struct bitint_type type, uint64_t left,
	uint64_t right, int *out);
/* Conversion uses the target's two's-complement modulo representation, an
 * implementation choice for out-of-range conversions to signed types. */
enum bitint_status bitint_convert(struct bitint_type from, struct bitint_type to,
	uint64_t value, uint64_t *out);

#endif
