# M22: bounded integer and enum bit-fields

## Target and supported declarations

On Linux x86-64 SysV, named fields declared as `int` (including plain or
`signed int`) or `unsigned int`, optionally `const`, accept integer constant
expression widths 1 through 32. Typedefs and enum constants in widths work
within existing compiler limits. Plain `int` fields are signed. Unnamed `int` and `unsigned int` fields accept
widths 0 through 32; a zero width aligns the next struct member to a 32-bit
unit without itself raising the record alignment. Nonzero unnamed fields occupy
bits but do not raise record alignment or consume initializer entries. Records
without any named member remain rejected. Named `_Bool` / `bool` fields
accept width 1; unnamed boolean fields accept widths 0 or 1. Boolean fields
use byte-sized allocation units and one-byte natural alignment; zero-width
boolean separators align the next member to a byte boundary. Assignments convert
values to 0 or 1 before storage. Named `char`, `signed char` and `unsigned
char` fields accept widths 1 through 8; unnamed ones accept widths 0 through
8. Their allocation units and natural alignment are one byte, plain `char`
is signed on this target, and zero-width separators align to a byte. Named
`signed short` and `unsigned short` fields accept widths 1 through 16;
unnamed fields accept widths 0 through 16. They use two-byte allocation units
and natural alignment, with zero-width separators aligning to a two-byte
boundary. Named signed/unsigned `long` and `long long` fields accept widths
1–64; unnamed fields accept 0–64. They use eight-byte allocation
units and natural alignment, with zero-width separators aligning to eight-byte
boundaries. Named widths 33–63 have additional expression restrictions below. Enums
compatible with `int` or `unsigned int`, including ordinary int-compatible enums
and fixed-underlying enums, use the corresponding 32-bit unit and accept named
widths 1–32 or unnamed widths 0–32. Unnamed fields and zero-width separators
can use either a direct enum tag, such as `enum E : 0`, or an enum typedef.
Other enum base types remain unsupported. Structs,
unions, anonymous-record promotion, arrays of records, and flexible arrays
retain the existing record restrictions.

Layout follows the target's little-endian, low-bit-first 32-bit allocation
units and natural four-byte int alignment. A field that does not fit in the
current unit starts in the next one. Adjacent fields may start at any bit
within a byte, share bytes, or cross byte boundaries within a unit. Ordinary
members start at their normal alignment after the occupied bits, and union
alternatives overlap. For example, `unsigned a:3, b:4;` shares one byte;
`unsigned a:3, b:31;` places `b` in the next unit. These int allocation-unit rules do not apply to boolean, character, short or long-base fields. This is not
general SysV bit-field coverage.

## Values, initialization and expressions

Reads mask to the declared width and sign-extend signed fields. Writes keep the
low bits; out-of-range conversion to a signed field uses the target's
low-bit/two's-complement result. Assignment and compound-assignment values and
prefix updates reflect the narrowed stored value; postfix updates return the
old value. Mutations evaluate the field base once and preserve other bytes or
bits. Narrow `unsigned int` fields and supported long-base fields below 32 bits
promote to `int` in integer-promotion contexts; 32-bit signed long-base fields
promote to `int`, and 32-bit unsigned long-base fields to `unsigned int`.
Full 64-bit fields retain their declared long-base types. These rules apply to
arithmetic, shifts, conditional operands and variadic calls. For named 33–63-bit
long-base fields, direct storage, reads, conversions, assignment and updates
are supported, but uncast arithmetic, comparisons, conditional operands,
variadic arguments and other rank-sensitive operations are rejected. Cast to a
standard integer type first. Unpromoted `_Generic` and `typeof` forms are also
rejected: GCC and Clang differ on the compatible type of these fields.
Within existing initializer limits, static and automatic, positional and
designated initializers, scalar braces, record copies and pointer-based host
interop are supported. Adjacent fields are merged bitwise; repeated field
designators replace only that field. A partial-bit field initializer that
overrides an earlier whole-record copy or another nonzero scalar storage write
is rejected, as is a later byte-range override that partially covers a field.
Overlapping fields with different bit ranges are rejected if initializer union
selection has not already discarded the earlier alternative. Bounded aggregate
calls and returns are also available;
see `m21-aggregate-abi.md`. Named fields are classified from their occupied
bits even when their byte offsets are not int-aligned.

Taking a field's address, applying `sizeof`, `typeof` or `typeof_unqual`
directly to it, and using it in an `offsetof` designator are rejected. Const
fields are not modifiable, and alignment specifiers on fields are rejected.
Unpromoted narrow field values in `_Generic` controls are rejected because
host compilers differ on their compatible type; `_Generic(+field, ...)` is
supported. Ordinary expressions formed from fields follow existing rules.

## Explicit boundaries

Enum base types other than `int`/`unsigned int`, `_BitInt` base types,
volatile and atomic fields are rejected. The named long/long-long widths 33–63
retain the rank-sensitive operation restrictions above. Known GNU
layout-changing scoped attributes (`packed`, `aligned`, `ms_struct`,
`scalar_storage_order`) are rejected. Other unknown/vendor attributes retain
the compiler's existing ignore policy and must not be relied upon to change
layout; GNU attribute syntax is not supported. This is not general bit-field
support or M22 completion. Invalid widths and valid-but-unsupported declarations
can share the legacy M22 diagnostic.

## Validation

`tests/test_enum_bit_fields.py` checks 288 ordinary-enum layouts with matching
GCC/KCC declarations in both call directions, plus 448 fixed-enum layouts
against separately compiled representation-compatible primitive-field
surrogates. GCC 11 cannot compile C23 fixed enums, so the surrogate checks are
not native C23 syntax or semantics agreements. `tests/test_long_bit_fields.py` checks 924 named long/long-long layouts and
512 unnamed floating/mixed layouts across by-value calls in both host/KCC
directions, using the selected host-compatible ABI mode, plus static and local initialization, signed/unsigned conversions,
updates and 64-bit-unit zero-width pointer layout. `tests/test_unnamed_wide_bit_fields.py`
checks 868 layouts with widths 33–63, prefixes 1–7 and signed/unsigned long and
long-long base types in both host/KCC directions, plus union and nested records.
`tests/test_named_wide_bit_fields.py` checks 868 named width/prefix/base
combinations in both host/KCC directions, plus unions, nested records, calls,
updates and explicit semantic guards. Historical unsupported-long fixtures now
use unsupported volatile fields; valid newly supported examples have positive
coverage. `tests/test_short_bit_fields.py` checks 480 signed/unsigned layouts and
`tests/test_char_bit_fields.py` checks 112 signed/unsigned layouts across
by-value calls in both host/KCC directions. `tests/test_bool_bit_fields.py` checks boolean conversion, packing,
initialization and cross-compiler aggregate calls. `tests/test_bit_fields.py`,
`tests/test_narrow_bit_fields.py` and
`tests/test_packed_bit_fields.py` compile owner and companion translation units in all four host/KCC combinations using the
pinned QBE 1.2 backend. They cover full units, byte-start narrow fields,
including sub-byte adjacent fields, all widths 1 through 32 after bit offsets
1 through 7 in both host/KCC directions, signed and unsigned values, static and
automatic initialization,
field updates and single-evaluation bases, promotions (including variadic calls),
layout, unions, flexible arrays, small and memory-class aggregate calls,
`_BitInt` integration boundaries, and unsupported cases. The unnamed-field test also covers 231 layouts with separators and padding in
both host/KCC pointer-interoperation directions; bounded 17–1024-byte MEMORY-class
aggregates containing zero-width barriers are supported by value. Register-class
aggregates with barriers are supported when their recursively contained by-value
members have no floating types, subject to the existing ABI limits; floating
register records with barriers are supported in the default ABI only when every
barrier is at an effective eightbyte offset. Other mixed floating/barrier register
records remain rejected by default; legacy Clang mode accepts representable
shapes only for hosts known to use the older convention, while the separate
`--gcc12-zero-width-abi` mode targets compatible GCC 12+ hosts. Nonzero unnamed
fields are supported by the bounded aggregate ABI. KCC uses GCC's x86-64 classification for nonzero unnamed bit-fields.
Clang 18.1 uses a different classification: mixed KCC/Clang by-value calls can
produce incorrect results even when each compiler's self-calls work. Do not
mix such aggregates across those compiler boundaries in the default mode. The
bounded `--legacy-clang-abi` mode can interoperate with the older convention
for representable shapes; see `m21-aggregate-abi.md` for its explicit limits.
This is not a layout or pointer-interoperability claim. LLVM describes its classification change in
[PR 217847](https://github.com/llvm/llvm-project/pull/217847); do not assume
that a particular Clang release has the change without testing it. These checks
do not replace cross-platform ABI validation, fuzzing, or full C23 conformance
testing.
