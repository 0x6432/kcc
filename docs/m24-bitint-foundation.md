# M24: bounded `_BitInt` values and layout

On the Linux x86-64 LP64 SysV target, `_BitInt(N)` supports signed widths
2–64 and unsigned widths 1–64; N must be an integer constant expression.
Types retain their declared width and signedness and are distinct from standard
integer types. Size and alignment are both 1 byte for widths 1–8, 2 for 9–16,
4 for 17–32, and 8 for 33–64. Widths outside the range are rejected.

Typedefs, qualification, `typeof`, generic associations, pointers, arrays,
ordinary record members, automatic/static objects, casts, initializers,
assignments, integer/floating conversions, operators and constant expressions
use the declared width. Bit-precise values are not normally integer-promoted;
rank and mixed arithmetic follow the target's C23 rules. QBE carriers are words
or longs but every relevant operation, conversion and load normalizes to N
bits, including signed extension. Unsigned values wrap modulo 2^N; signed
out-of-range conversions use the target's two's-complement behavior. Signed
overflow and invalid shifts remain undefined at runtime and are diagnosed in
integer constant expressions. Padding bits are not part of the value.

Fixed scalar parameters and results, variadic arguments and `va_arg` are lowered for every supported width.
Native Clang 15 x86-64 cross-object tests exercise both calling directions,
register and stack parameters, mixed floating-point variadic arguments, `va_copy`, indirect calls, returned values, external
objects, arrays, and pointers to records. This is targeted evidence for the
specified ABI, not a claim of full C23 or multi-platform conformance.

The narrower ABI boundaries are intentional:

- Records or unions containing non-native-width members by value are rejected
  at aggregate call/return boundaries, including nested/large records. Local
  objects and pointers to records are supported. Existing aggregate ABI bounds
  continue to apply to native-width members.
- Atomic bit-precise objects remain limited to 8/16/32/64. Their existing
  libatomic implementation has surrogate, not native atomic `_BitInt`,
  interoperability coverage. Atomic record members are rejected.
- Bit-precise bit-fields and fixed enum underlying types remain unsupported.

`src/bitint.c` retains independent internal arithmetic building blocks through
64 bits; `tests/test_bitint.c` checks them. `tests/test_bitint_abi_atomics.py`
checks native-width fixed and variadic calls, bounded aggregates and atomics,
using native `_BitInt` where available and labeled integer surrogates otherwise.
Atomic cross-object checks use surrogates, not a native atomic `_BitInt` oracle.

`wb`/`WB` literals use their exact minimal valid width up to 64, including
unsigned width 1 and signed width 2. Signed literals requiring 65 bits are
rejected. Preprocessing uses its separate 64-bit intmax/uintmax model. Existing
compiler restrictions continue to apply. The driver emits IL only for the
Linux x86-64 LP64 SysV model; invoke QBE with `-t amd64_sysv`.

## Focused tests

`make test-bitint-native QBE=/path/to/qbe CLANG=/path/to/clang` requires a
Clang with C2x `_BitInt`. It checks scalar cross-object calls in both directions
for all 127 valid signed/unsigned types, variadic cross-calls in both directions, a runtime cross-width conversion
matrix, wb literal typing and focused arithmetic, and an independent Clang type
oracle. `tests/test_bitint_rejection.py` checks the explicit ABI/atomic gates;
`tests/test_bitint.c`, `tests/test_type.c`, and the existing BitInt tests cover
other primitives and regressions. These do not replace a full conformance suite,
fuzzing, other targets, aggregate ABI validation or atomic concurrency testing.
