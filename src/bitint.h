#ifndef KCC_BITINT_H
#define KCC_BITINT_H

#include <stdbool.h>
#include <stdint.h>

/* Bounded, target-independent arithmetic foundation. Except for the explicit
 * amd64 layout query below, this is not an ABI or a semantic language type.
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
	bitint_invalid_shift,
};

enum bitint_unary_operation { bitint_unary_plus, bitint_unary_minus, bitint_complement };
enum bitint_shift_operation { bitint_shift_left, bitint_shift_right };

enum bitint_operation {
	bitint_add, bitint_subtract, bitint_multiply, bitint_divide, bitint_remainder,
	bitint_and, bitint_or, bitint_xor,
};

bool bitint_type_valid(struct bitint_type type);
/* Linux x86-64 storage layout used by bounded direct type queries. Invalid
 * widths leave both outputs unchanged. No value or calling ABI is implied. */
enum bitint_status bitint_amd64_layout(struct bitint_type type,
	unsigned *size, unsigned *alignment);
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
/* Unary operands are already promoted. Shift counts must be nonnegative and
 * are supplied as an unsigned magnitude; a count >= width is rejected.
 * Signed right shift of negative values is arithmetic in this target model.
 * As above, invalid inputs leave *out unchanged. */
enum bitint_status bitint_unary(struct bitint_type type, enum bitint_unary_operation op,
	uint64_t value, uint64_t *out);
enum bitint_status bitint_shift(struct bitint_type type, enum bitint_shift_operation op,
	uint64_t value, uint64_t count, uint64_t *out);
/* Return -1/0/1 after comparing canonical same-type operands. */
enum bitint_status bitint_compare(struct bitint_type type, uint64_t left,
	uint64_t right, int *out);
/* Conversion uses the target's two's-complement modulo representation, an
 * implementation choice for out-of-range conversions to signed types. */
enum bitint_status bitint_convert(struct bitint_type from, struct bitint_type to,
	uint64_t value, uint64_t *out);

#endif
