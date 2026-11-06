# M24: bounded `_BitInt` values and layout

On the Linux x86-64 LP64 target, direct type names in `sizeof`, `alignof` /
`_Alignof`, and `alignas` / `_Alignas` accept `_BitInt(N)` and `signed` or
`unsigned _BitInt(N)`. `N` must be an integer constant expression: 2–64 for
signed, 1–64 for unsigned. The size and alignment in bytes are both 1 for
widths 1–8, 2 for 9–16, 4 for 17–32, and 8 for 33–64. The query result is
`unsigned long`. Direct queries also accept `const` and `volatile`, but not
atomic or restrict types. Widths outside the range are rejected.

## Value slice

Only widths **32 and 64** have semantic types and values, both signed and
unsigned. They are distinct from each other and from all standard integer
types. Typedefs, qualifications, `typeof`, generic associations, pointers,
arrays, ordinary record members, automatic and static objects, compound
literals, casts, initialization, assignment, integer and floating conversion,
operators and constant expressions use these types. Their rank is below the
standard integer type of the same width and above types of smaller width;
ordinary bit-precise values are not integer-promoted. Mixed arithmetic follows
the usual arithmetic conversions. The value representation, scalar loads,
stores and arithmetic reuse the existing 32- and 64-bit QBE paths, including
unsigned modulo arithmetic and two's-complement signed conversion behavior.
Normal C signed-overflow and invalid-shift rules still apply. The target object
layout for these widths is 4/4 and 8/8 bytes respectively.

Other widths remain **layout-query only**: declarations, aliases, derived
types and value expressions involving them are diagnosed, not lowered as a
standard integer. Bit-precise by-value parameters, return types, variadic
arguments and `va_arg` are rejected; pointer parameters are supported by the
existing pointer ABI. Aggregate calls or returns containing bit-precise members
by value are also rejected pending ABI validation. Bit-precise bit-fields, fixed enum underlying types,
atomic bit-precise objects and `wb`/`WB` literals remain unsupported. Existing
aggregate-by-value and other compiler restrictions also apply. No host call or
object interoperability is claimed by this checkpoint; widths above 64 remain
unsupported. This is not a full C23 `_BitInt` implementation.

`src/bitint.c` also retains independent internal arithmetic building blocks
for all validated widths through 64; they are not a source-value implementation
for the layout-only widths. `tests/test_bitint_values.py` runs 32/64 value and
rejection tests through QBE; `tests/test_bitint_layout.py` covers the entire
layout-only range and can compare with a native compiler if available.
`tests/test_bitint.c` checks the independent arithmetic helpers. These focused
checks are not a substitute for full conformance tests, fuzzing or a host ABI
oracle.
