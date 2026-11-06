/* Target math comparison helpers. Host must match target IEEE float/double.
 * Build without fast-math or LTO so quiet NaN comparisons retain the host
 * C library/compiler's non-signaling comparison semantics. */
#include <math.h>

#define KCC_COMPARE(name) \
int __kcc_##name##_f(float a, float b) { return name(a, b) != 0; } \
int __kcc_##name##_d(double a, double b) { return name(a, b) != 0; }

KCC_COMPARE(isgreater)
KCC_COMPARE(isgreaterequal)
KCC_COMPARE(isless)
KCC_COMPARE(islessequal)
KCC_COMPARE(islessgreater)
KCC_COMPARE(isunordered)
