# C23 constexpr scalar objects

KCC supports explicit-type integer and pointer `constexpr` object definitions at file and
block scope, including `static` and block-scope `register`; inferred `constexpr auto` is supported for integer and null-pointer values at file and block
scope, including block-scope `static`. Enum and supported `_BitInt`
integer types are included. The object is const-qualified and retains actual
storage and addressability; file-scope definitions have internal linkage.
Integer named constants can participate in constant expressions, including
static assertions, enumerators, fixed array bounds, bit-field widths, case
labels, static initializers and zero-valued null pointer constants.

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

This is not complete C23 constexpr support. Floating, array, struct
and union constexpr objects, constexpr compound
literals and non-constexpr file-scope or static inferred auto remain unsupported.
The compiler's existing type, initializer, ABI and resource limits also apply.
`tests/test_constexpr_integer.py` and `tests/test_constexpr_pointers.py` cover executable cross-feature examples,
range and constraint refusals, and file-scope symbol linkage. Native C23
constexpr agreement is not claimed unless a supporting host is separately used.
