# M22: named full-width int bit-fields

## Supported slice

On the Linux x86-64 SysV target, a named bit-field whose declared type resolves
to `int` (including plain `int` and `signed int`) or `unsigned int`, optionally
`const`, and whose integer constant expression width is exactly 32 is supported.
Typedefs and enum constants in the width work within existing compiler limits.
Mixed ordinary members, comma-separated declarators, structs, unions, anonymous
record promotion, arrays of records and flexible arrays retain the existing
record restrictions. A full-width field occupies an entire naturally aligned
four-byte allocation unit, so the existing ordinary int member layout and
load/store machinery is valid for this particular slice. The field marker is
retained even after promotion through anonymous records.

Within existing expression and initializer limits, values, conversions,
assignment, compound assignment, increment/decrement, aggregate initializers,
record copies and pointer-based cross-compiler access are supported. The width
is the full width of the declared type, so its integer promotion and storage
value are the same as the corresponding ordinary `int` or `unsigned int`. A
member base is evaluated once for mutation. Taking the field's address, applying
`sizeof` or `typeof`/`typeof_unqual` directly to it, and using it in an
`offsetof` designator are rejected. Applying those operators to an ordinary
value produced from a field follows the existing expression rules. Const
fields are not modifiable. Alignment specifiers on fields are rejected.

## Explicit boundaries

Narrow fields, unnamed fields (including zero-width separators), `_Bool`,
enum, extended and `_BitInt` base types, other widths, volatile and atomic
fields are not implemented and are rejected; no packing or masking is guessed.
This is not general bit-field support or M22 completion. Aggregate-by-value
ABI, packed layouts and other existing compiler restrictions still apply.
The width must be an integer constant expression; invalid expressions and
valid-but-unsupported fields can share the legacy M22 diagnostic. Ignored
unknown attributes do not provide packed layout.

## Focused validation at this checkpoint

`tests/test_bit_fields.py` runs unchanged owner and companion translation units
in four host/KCC combinations through the pinned QBE 1.2 backend, including
static and automatic initializers, signed and unsigned values, surrounding
members, a union, anonymous promotion, record copying, single-evaluation writes,
updates, `_Generic`, sizes and alignment. It also runs an extra positive and
explicit rejection checks. The existing record-layout regression was run.
These focused checks do not replace full suites, sanitizers, fuzzing, aggregate
ABI validation, or exact-commit CI.
