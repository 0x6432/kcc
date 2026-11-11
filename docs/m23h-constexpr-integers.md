# C23 constexpr objects

KCC supports explicit-type integer, finite floating and pointer `constexpr` object definitions at file and
block scope, including `static` and block-scope `register`; inferred `constexpr auto` is supported for integer, finite floating and null-pointer values at file and block
scope, including block-scope `static`; direct constexpr record values can also
be used for inferred constexpr records. Enum and supported `_BitInt`
integer types are included. The object is const-qualified and retains actual
storage and addressability; file-scope definitions have internal linkage.
Integer named constants can participate in constant expressions, including
static assertions, enumerators, fixed array bounds, bit-field widths, case
labels, static initializers and zero-valued null pointer constants.

Floating objects support finite arithmetic constant expressions and enforce exact
representability when converting to the target type. Floating named constants
can be immediate operands of integer casts in integer constant expressions.
Floating evaluation uses the existing finite IEEE binary32/binary64 subset.

An integer initializer must be an integer constant expression whose value is exactly
representable in the target type. Pointer initializers must be provably null,
with normal pointer assignment constraints. Null pointer and `nullptr_t` named
constants can initialize compatible pointer objects and retain real addressable
storage; pointer-typed named constants are not null pointer constants or integer
constant expressions. Explicit types accept an expression, an empty initializer,
or a single scalar expression nested in braces. The declared identifier is not
available within its initializer, even in an unevaluated operand. Existing
checks reject attempted modification, incompatible storage classes, unsupported
qualifiers, missing initializers and multiple declarators.

Explicit-type constexpr arrays, structs and unions are supported at file and block scope,
including static locals, unknown outer array bounds, nested aggregates, designated
initializers, zero-filled members, and character strings. Integer (including bit-fields) and finite
floating struct members accessed through direct member selection are named
constants; null pointer members can initialize compatible pointers. Array
subscripts do not form named constants. Floating automatic constexpr initializers
are materialized from their translation-time value, independent of runtime rounding.
Bit-field initializers must be exactly representable in their declared field width.
Direct union-member access can form a constant expression only for the initialized
active member; empty-initialized unions select their first named member.
Direct constexpr record values and direct record-member values of the same record
definition can initialize constexpr records, or records with static storage.
Copies preserve nested arrays, bit-fields, string data and scalar constants without
re-evaluating the source initializer.

The same bounded scalar, array, struct and union types are supported in C23 constexpr
compound literals, including automatic, static and register storage where valid.
Scalar compound literal constants and direct struct-member selections participate
in supported constant expressions. They retain real const-qualified storage;
initializer and representability rules are the same as constexpr objects.

This is not complete C23 constexpr support. Anonymous union members, record copies
containing unions, flexible arrays, general aggregate copy expressions, non-ASCII narrow strings targeting char or signed char, non-finite floating
values and non-constexpr file-scope or static inferred auto remain unsupported.
The compiler's existing type, initializer, ABI and resource limits also apply.
`tests/test_constexpr_integer.py`, `tests/test_constexpr_pointers.py`, `tests/test_constexpr_floating.py`, `tests/test_constexpr_aggregates.py`, and `tests/test_constexpr_literals.py` cover executable cross-feature examples,
range and constraint refusals, and file-scope symbol linkage. Native C23
constexpr agreement is not claimed unless a supporting host is separately used.
