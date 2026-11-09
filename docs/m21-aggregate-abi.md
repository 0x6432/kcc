# M21: bounded aggregate-by-value ABI

## Target and accepted boundary

On Linux x86-64 SysV with QBE 1.2, evaluated direct and indirect calls and
function definitions can pass and return complete struct and union values of
1–1024 bytes with alignment at most 8, provided they have no flexible array member
and each occupied ABI eightbyte has a representable class. Types may contain
nested records, unions, fixed arrays, integers, enums, pointers, `float` and
`double`, subject to the compiler's existing type and qualifier restrictions.
Explicit alignment up to 8 is supported. Function prototypes and unevaluated
calls may describe larger or otherwise unsupported records, but an evaluated
call or definition with such an ABI is diagnosed. Existing C type compatibility
rules still apply; ABI shape alone never makes C types compatible.

This is not the entire SysV ABI. Size 1025 or more, alignment above 8, flexible
array members, unrepresentable/empty ABI eightbytes, unsupported types and
unaligned scalar fields are refused rather than passed as pointers. Aggregate arguments after an ellipsis and `va_arg` of unqualified aggregate types
are supported under the same limits. Fixed aggregate parameters of a variadic
function are also supported alongside the existing scalar variadic subset. Supported named int, short, char, boolean, bounded long-base and int-compatible enum bit-fields are documented
in `m22-bit-fields.md`; their actual occupied bits are classified as INTEGER,
including fields starting at byte offsets not aligned for `int`. Other bit-field base types, vectors,
`long double`, complex types and aggregate atomics are not added by this slice.

## Lowering and resource policy

The compiler classifies actual subobjects, recursively merging union alternatives
and ignoring padding. Up to 16 bytes, each eightbyte is INTEGER if any part is
integer-class, otherwise SSE if it contains floating data. A compact synthetic
QBE aggregate preserves the exact size, alignment and per-eightbyte classes;
QBE performs register assignment, all-or-stack rollback and return lowering.
Records of 17–1024 bytes use a QBE opaque MEMORY type of the real size and
alignment. QBE chooses the hidden return pointer and stack layout. This is not
a pointer ABI approximation.

Arguments are evaluated once, in the compiler's existing chosen order, and
copied into distinct entry-allocated, eightbyte-rounded staging buffers. Callees
copy named aggregate parameters to their ordinary local objects. Aggregate
return values are address-backed; returns stage into a rounded buffer and QBE
allocates call-result storage. Rounding protects small objects and tail
subobjects from QBE 1.2's whole-eightbyte loads. Record call results, parameter
materializations, argument staging and return staging are conservatively charged
to the existing 256 record-temporary and 1 MiB per-function storage limits.
The 1024-byte ceiling bounds QBE's proportional aggregate-copy expansion.
A temporary stream collects IL so deduplicated ABI types can precede all uses.

Nonzero unnamed int, short, char, boolean, supported long-base and int-compatible enum bit-fields contribute INTEGER classes for their occupied
bits. Register-class records containing zero-width barriers are supported by
value when their recursively contained by-value members have no floating types,
subject to the existing size, alignment and representability limits. Pointers
do not count their referents. In the default ABI, register-class records combining floating members
and barriers are supported only when every barrier's effective offset (including
nested arrays and unions) is an eightbyte boundary. Other floating/barrier
register records remain rejected by default: GCC 11 can pass a float/zero-width/float
record differently from a classifier ignoring the barrier. Bounded 17–1024-byte
MEMORY-class records can contain barriers, including nested and union members;
the backend uses the whole object's size and alignment. Supported byte-width
bit-precise integer members use INTEGER classification, within the same limits.
Pointer-based interoperation remains supported.

`--legacy-clang-abi` opts into the older Clang x86-64 behavior that ignores
nonzero unnamed bit-fields and zero-width separators during aggregate
classification. This affects by-value arguments and returns, including nested
records; object layout is unchanged. Floating records with off-eightbyte barriers
remain rejected in the default ABI and can use an explicit mode only with a host
known to follow the selected convention.
Use the option consistently on all KCC translation units that share affected
interfaces and only with a native compiler known to use this older convention.
The default continues to classify those fields like GCC. The mode is bounded by
the same size, alignment and type restrictions as the default. In particular,
QBE 1.2 cannot represent a NO_CLASS register eightbyte; such layouts are rejected
rather than given a fabricated register class. Pointer-only access is unaffected.
The mode and `--warn-legacy-clang-abi` are mutually exclusive, and neither is
accepted in token-dump modes. This is not general Clang ABI coverage.

`--gcc12-zero-width-abi` is a separate opt-in for GCC 12+ zero-width separator
classification. GCC 11 and GCC 12+ differ for some floating/barrier records;
the default remains the conservative GCC 11-compatible subset and is never
silently switched based on the build or host compiler. Use the new mode for all
KCC objects sharing affected by-value interfaces with a compatible GCC 12+ host.
Unlike legacy Clang mode, it retains GCC's classification of nonzero unnamed
fields. The two ABI modes are mutually exclusive, and neither works in token-dump
modes. Existing size, alignment, type and QBE representability limits
still apply. Layout and pointer-only use are unchanged.

`--warn-legacy-clang-abi` conservatively warns at evaluated calls and function
definitions whose by-value record contains a nonzero unnamed bit-field, even
when nested inside arrays, structs or unions. It does not follow pointers or
check unused prototypes, and may warn for layouts that happen to agree. The
option changes no target ABI, emitted QBE or success status; the absence of a
warning is not a general interoperability guarantee. Records rejected by the
existing ABI rules are still rejected. Token-dump modes cannot use the option.

## Aggregate variadic arguments

Arguments passed after an ellipsis use the same supported aggregate classifier as
fixed arguments. `va_arg` for a complete, unqualified supported record fetches
from the SysV 24-byte `va_list` register-save area when every required INTEGER
and SSE slot is available, or from the overflow stack area otherwise. Register
allocation rolls back as a whole when either class is exhausted. The resulting
record is copied into an entry-allocated rounded temporary, charged to the
existing record-temporary and storage limits; `va_copy` preserves both cursors.
QBE's scalar-only `vaarg` instruction is not used for records. These paths are
specific to the existing Linux x86-64 SysV target and inherit the existing ABI
mode, field, alignment and representability restrictions.

`tests/test_aggregate_varargs.py` checks cross-object calls in both directions
with GCC 11 and Clang 15, including 1–16-byte records, 17–1024-byte memory
records, mixed INTEGER/SSE and union shapes, va_copy, register exhaustion and
rollback, fixed aggregate parameters, and stack advancement. These are focused
checks, not full ABI or C conformance.

## Focused validation and remaining gates

`tests/test_aggregate_abi.py` links separately compiled GCC and kcc objects in
both directions using pinned QBE 1.2. It exercises byte sizes 1–16, 24 and 64,
INTEGER/SSE mixtures, unions, arrays, alignment 8, indirect calls, register
exhaustion and rollback, memory returns, fixed parameters of variadic functions,
`va_start`, recursion, discarded results, tail subobjects and limits/rejections.
`tests/test_bitfield_aggregate_abi.py` additionally exercises 448 named signed
and unsigned field layouts by value in both host/KCC directions, plus mixed
INTEGER/SSE, unions, nested records and register pressure.
`tests/test_enum_bit_fields.py` checks 288 ordinary-enum and 448 fixed-enum
surrogate layouts in both host/KCC directions; the latter are not native C23
syntax agreements. `tests/test_long_bit_fields.py` checks 924 named and 512 unnamed long-base
layouts by value in both host/KCC directions.
`tests/test_unnamed_field_aggregate_abi.py` covers 288 floating and mixed
nonzero-unnamed-field layouts by value in both directions and exercises a union,
a MEMORY-class record and register pressure. See the commit
handoff for exact commands and results. `tests/test_zero_width_memory_abi.py`
checks 35 zero-width-barrier MEMORY cases, including indirect calls, stack and
register pressure, nested arrays, unions, and a fixed variadic parameter, in
four host/KCC combinations and both KCC ABI modes. A further 36 mixed-field
layouts are checked in both directions and modes. `tests/test_zero_width_integer_abi.py`
checks 504 integer-only register layouts in both directions and modes, plus
register pressure, fixed variadic parameters, nested records, unions and
rejection boundaries. `tests/test_zero_width_aligned_float_abi.py` checks 75
register and 106 MEMORY layouts in both modes and directions, 35 refused
unaligned cases, and unnamed-field, nested, union and pressure interactions.
`tests/test_zero_width_legacy_float_abi.py` checks 216 separator and 119 combined
unnamed-field layouts, 480 deterministic nested record/array/union layouts
(including 240 with named fields), pressure, fixed variadic arguments
and NO_CLASS refusal. Clang 18.1 cross-calls run only when that host is available;
other hosts run self-calls. `tests/test_zero_width_gcc12_abi.py` runs the same
216 separator, 119 unnamed-field and 480 nested layouts in GCC 12 mode; native
cross-calls are only counted with a detected GCC 12+ host. In the default ABI,
register records with unaligned
effective barriers and floating members remain rejected. Records above 1024 bytes
and unsupported bit-precise widths remain rejected in both modes.
This focused evidence is not full ABI validation or M21 completion. Full test,
sanitizer, fuzz and broader cross-compiler/target matrices remain release gates.
