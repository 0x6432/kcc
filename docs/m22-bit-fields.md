# M22: bounded int bit-fields

## Target and supported declarations

On Linux x86-64 SysV, named fields declared as `int` (including plain or
`signed int`) or `unsigned int`, optionally `const`, accept integer constant
expression widths 1 through 32. Typedefs and enum constants in widths work
within existing compiler limits. Plain `int` fields are signed. Unnamed `int` and `unsigned int` fields accept
widths 0 through 32; a zero width aligns the next struct member to a 32-bit
unit without itself raising the record alignment. Nonzero unnamed fields occupy
bits but do not raise record alignment or consume initializer entries. Records
without any named member remain rejected. Structs,
unions, anonymous-record promotion, arrays of records, and flexible arrays
retain the existing record restrictions.

Layout follows the target's little-endian, low-bit-first 32-bit allocation
units and natural four-byte int alignment. A field that does not fit in the
current unit starts in the next one. Adjacent fields may start at any bit
within a byte, share bytes, or cross byte boundaries within a unit. Ordinary
members start at their normal alignment after the occupied bits, and union
alternatives overlap. For example, `unsigned a:3, b:4;` shares one byte;
`unsigned a:3, b:31;` places `b` in the next unit. These rules apply only to
the supported int-based declarations, not general SysV bit-field coverage.

## Values, initialization and expressions

Reads mask to the declared width and sign-extend signed fields. Writes keep the
low bits; out-of-range conversion to a signed field uses the target's
low-bit/two's-complement result. Assignment and compound-assignment values and
prefix updates reflect the narrowed stored value; postfix updates return the
old value. Mutations evaluate the field base once and preserve other bytes or
bits. Narrow `unsigned int` fields promote to `int` in integer-promotion
contexts, including arithmetic, shifts, conditional operands and variadic calls.
Within existing initializer limits, static and automatic, positional and
designated initializers, scalar braces, record copies and pointer-based host
interop are supported. Adjacent fields are merged bitwise; repeated field
designators replace only that field. A partial-bit field initializer that
overrides an earlier whole-record copy or another nonzero scalar storage write
is rejected, as is a later byte-range override that partially covers a field.
Overlapping fields with different bit ranges are rejected if initializer union
selection has not already discarded the earlier alternative. Bounded aggregate
calls and returns are also available;
see `m21-aggregate-abi.md`. The aggregate classifier currently rejects some
otherwise-supported layouts, including fields at byte offsets not aligned for `int` in small records (whether
or not the bit start is byte-aligned), rather than guessing their ABI.

Taking a field's address, applying `sizeof`, `typeof` or `typeof_unqual`
directly to it, and using it in an `offsetof` designator are rejected. Const
fields are not modifiable, and alignment specifiers on fields are rejected.
Unpromoted narrow field values in `_Generic` controls are rejected because
host compilers differ on their compatible type; `_Generic(+field, ...)` is
supported. Ordinary expressions formed from fields follow existing rules.

## Explicit boundaries

`_Bool`, enum, other integer base types, `_BitInt`, volatile and atomic fields are rejected. Known GNU
layout-changing scoped attributes (`packed`, `aligned`, `ms_struct`,
`scalar_storage_order`) are rejected. Other unknown/vendor attributes retain
the compiler's existing ignore policy and must not be relied upon to change
layout; GNU attribute syntax is not supported. This is not general bit-field
support or M22 completion. Invalid widths and valid-but-unsupported declarations
can share the legacy M22 diagnostic.

## Validation

`tests/test_bit_fields.py`, `tests/test_narrow_bit_fields.py` and
`tests/test_packed_bit_fields.py` compile owner and companion translation units in all four host/KCC combinations using the
pinned QBE 1.2 backend. They cover full units, byte-start narrow fields,
including sub-byte adjacent fields, all widths 1 through 32 after bit offsets
1 through 7 in both host/KCC directions, signed and unsigned values, static and
automatic initialization,
field updates and single-evaluation bases, promotions (including variadic calls),
layout, unions, flexible arrays, small and memory-class aggregate calls,
`_BitInt` integration boundaries, and unsupported cases. The unnamed-field test also covers 231 layouts with separators and padding in
both host/KCC pointer-interoperation directions; aggregates containing unnamed
fields are conservatively rejected by value pending ABI validation. These checks do not replace
cross-platform ABI validation, fuzzing, or full C23 conformance testing.
