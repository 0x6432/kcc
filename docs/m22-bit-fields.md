# M22: bounded named int bit-fields

## Target and supported declarations

On Linux x86-64 SysV, named fields declared as `int` (including plain or
`signed int`) or `unsigned int`, optionally `const`, accept integer constant
expression widths 1 through 32. Typedefs and enum constants in widths work
within existing compiler limits. Plain `int` fields are signed. Structs,
unions, anonymous-record promotion, arrays of records, and flexible arrays
retain the existing record restrictions.

Layout follows the target's little-endian, low-bit-first 32-bit allocation
units and natural four-byte int alignment. A field that does not fit in the
current unit starts in the next one. Every accepted field must start on a byte
boundary. Thus adjacent 8-, 16-, and 24-bit fields can share units, and fields
of any width can be interleaved with ordinary members when their calculated
starts are byte-aligned. For example, `unsigned a:3; char b;` is accepted,
but `unsigned a:3; unsigned b:4;` is rejected because `b` starts at bit 3.
A 16- or 24-bit field may start at an unaligned byte offset. Union alternatives
overlap normally. Layouts outside these rules are rejected rather than
approximated; this is not complete SysV bit-field coverage.

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
interop are supported. Aggregate-by-value ABI remains unsupported.

Taking a field's address, applying `sizeof`, `typeof` or `typeof_unqual`
directly to it, and using it in an `offsetof` designator are rejected. Const
fields are not modifiable, and alignment specifiers on fields are rejected.
Unpromoted narrow field values in `_Generic` controls are rejected because
host compilers differ on their compatible type; `_Generic(+field, ...)` is
supported. Ordinary expressions formed from fields follow existing rules.

## Explicit boundaries

Unnamed fields (including zero-width separators), `_Bool`, enum, other integer
base types, `_BitInt`, volatile and atomic fields are rejected. Fields beginning
at a non-byte bit offset (including sub-byte sharing) are not implemented.
Known GNU layout-changing scoped attributes (`packed`, `aligned`, `ms_struct`,
`scalar_storage_order`) are rejected. Other unknown/vendor attributes retain
the compiler's existing ignore policy and must not be relied upon to change
layout; GNU attribute syntax is not supported. This is not general bit-field
support or M22 completion. Invalid widths and valid-but-unsupported declarations
can share the legacy M22 diagnostic.

## Validation

`tests/test_bit_fields.py` and `tests/test_narrow_bit_fields.py` compile owner
and companion translation units in all four host/KCC combinations using the
pinned QBE 1.2 backend. They cover full units, byte-start narrow fields,
including packed adjacent fields, all widths 1 through 32 in both host/KCC
directions, signed and unsigned values, static and automatic initialization,
field updates and single-evaluation bases, promotions, layout, unions, flexible
arrays, and unsupported cases. These checks do not replace cross-platform ABI
validation, fuzzing, or full C23 conformance testing.
