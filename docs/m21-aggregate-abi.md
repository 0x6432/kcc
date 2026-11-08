# M21: bounded aggregate-by-value ABI

## Target and accepted boundary

On Linux x86-64 SysV with QBE 1.2, evaluated direct and indirect calls and
function definitions can pass and return complete struct and union values of
1–64 bytes with alignment at most 8, provided they have no flexible array member
and each occupied ABI eightbyte has a representable class. Types may contain
nested records, unions, fixed arrays, integers, enums, pointers, `float` and
`double`, subject to the compiler's existing type and qualifier restrictions.
Explicit alignment up to 8 is supported. Function prototypes and unevaluated
calls may describe larger or otherwise unsupported records, but an evaluated
call or definition with such an ABI is diagnosed. Existing C type compatibility
rules still apply; ABI shape alone never makes C types compatible.

This is not the entire SysV ABI. Size 65 or more, alignment above 8, flexible
array members, unrepresentable/empty ABI eightbytes, unsupported types and
unaligned scalar fields are refused rather than passed as pointers. Aggregate
arguments after an ellipsis and `va_arg` of aggregate type remain unsupported.
Fixed aggregate parameters of a variadic function are supported alongside the
existing scalar variadic subset. Supported named int, short, char, boolean, bounded long-base and int-compatible enum bit-fields are documented
in `m22-bit-fields.md`; their actual occupied bits are classified as INTEGER,
including fields starting at byte offsets not aligned for `int`. Other bit-field base types, vectors,
`long double`, complex types and aggregate atomics are not added by this slice.

## Lowering and resource policy

The compiler classifies actual subobjects, recursively merging union alternatives
and ignoring padding. Up to 16 bytes, each eightbyte is INTEGER if any part is
integer-class, otherwise SSE if it contains floating data. A compact synthetic
QBE aggregate preserves the exact size, alignment and per-eightbyte classes;
QBE performs register assignment, all-or-stack rollback and return lowering.
Records of 17–64 bytes use a QBE opaque MEMORY type of the real size and
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
The 64-byte ceiling also bounds QBE's proportional aggregate-copy expansion.
A temporary stream collects IL so deduplicated ABI types can precede all uses.

Nonzero unnamed int, short, char, boolean, supported long-base and int-compatible enum bit-fields contribute INTEGER classes for their occupied
bits. Records containing zero-width barriers are conservatively rejected by
value, including nested and MEMORY-class records: the available GCC 11 host
passed a float/zero-width/float record differently from a classifier ignoring
the zero-width field. Pointer-based interoperation remains supported.

`--warn-legacy-clang-abi` conservatively warns at evaluated calls and function
definitions whose by-value record contains a nonzero unnamed bit-field, even
when nested inside arrays, structs or unions. It does not follow pointers or
check unused prototypes, and may warn for layouts that happen to agree. The
option changes no target ABI, emitted QBE or success status; the absence of a
warning is not a general interoperability guarantee. Records rejected by the
existing ABI rules are still rejected. Token-dump modes cannot use the option.

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
syntax agreements. `tests/test_long_bit_fields.py` checks 924 named and 132 unnamed long-base
layouts by value in both host/KCC directions.
`tests/test_unnamed_field_aggregate_abi.py` covers 288 floating and mixed
nonzero-unnamed-field layouts by value in both directions and exercises a union,
a MEMORY-class record and register pressure. See the commit
handoff for exact commands and results.
This focused evidence is not full ABI validation or M21 completion. Full test,
sanitizer, fuzz and broader cross-compiler/target matrices remain release gates.
