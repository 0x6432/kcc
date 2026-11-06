# M24: bounded `_BitInt` layout-query slice

On the Linux x86-64 LP64 target, direct type names in `sizeof`, `alignof` /
`_Alignof`, and `alignas` / `_Alignas` accept `_BitInt(N)` and `signed` or
`unsigned _BitInt(N)`. `N` must be a checked integer constant expression:
2–64 for signed, 1–64 for unsigned. Signedness may occur before or after the
specifier. `const` and `volatile` are accepted; atomic and restrict types are
not. The query's size and alignment in bytes are both 1 for widths 1–8, 2 for
9–16, 4 for 17–32, and 8 for 33–64. The ordinary `sizeof`/`alignof` result is
`unsigned long`. The width expression can itself contain supported constant
expressions and layout queries. No width is silently truncated.

The syntax is intentionally limited to the **direct** queried type: aliases,
`typeof` wrappers, pointer/array/function-derived types and compound literals
are not accepted. The semantic type system does not yet represent bit-precise
types. In particular, the layout query is not a standard integer type alias:
no `_BitInt` object, typedef, record member, cast, expression, `_Generic`
association, parameter, return, variadic use or other ABI exposure is accepted.
Values, type identity/compatibility, promotions, mixed conversions, arithmetic,
initializers, storage and function ABI remain unimplemented. `wb`/`WB` literals
and evaluated preprocessor uses remain rejected. Widths beyond 64 are rejected;
no wider runtime library or backend support is implied. The target layout is an
implementation choice; this checkpoint does not claim host interoperability for
objects or calls.

`src/bitint.c` also retains independent internal arithmetic building blocks:
distinct `(width, signedness)` descriptors; minimal `wb` width selection;
bit-precise-only promotion/common-type rules; checked operations, comparisons,
shifts and conversions on canonical low-width bits. These helpers are not yet
integrated into expression semantics. The layout helper validates the same
width limits and does not imply support for value representation or ABI.

`tests/test_bitint_layout.py` covers every accepted width and sign, all layout
transitions, ICE constraints, direct query forms and the rejected boundaries;
when `QBE` is set it links and runs a query-only program. It compares the layout
table with the native compiler when that compiler supports `_BitInt` on Linux
x86-64; this is a layout oracle, not a value or call ABI test. `tests/test_bitint.c`
checks the helper and internal arithmetic; `tests/test_bitint_rejection.py`
checks remaining source and literal rejection. These focused checks are not a
substitute for full suites, fuzzing, or a host `_BitInt` ABI oracle.
