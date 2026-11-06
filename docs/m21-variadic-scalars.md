# M21: bounded scalar variadic support

On x86-64 SysV, variadic prototypes, definitions, direct and indirect calls
support promoted integers, pointers and `double` arguments. `float` arguments
receive the default promotion to `double`. Aggregate variadic arguments remain unsupported. Fixed aggregate parameters
and aggregate returns are supported within the separate bounded slice in
`m21-aggregate-abi.md`.

The compiler provides a fallback `stdarg.h` when no explicit include directory
supplies one. It defines a SysV-compatible 24-byte `va_list` and macros for
`va_start`, `va_arg`, `va_copy`, and `va_end`. `va_start` requires a variadic
function definition; optional arguments to the C23 form are ignored. `va_arg`
accepts promoted `int`, `unsigned int`, long and long long types, `double`, and
pointers; other types are rejected. `va_copy` copies the 24-byte state; `va_end`
evaluates its argument and otherwise performs no operation. QBE's `vastart` and
`vaarg` implement the target ABI. These newly added argument-access paths have
been built, but have not yet been integration-tested. This is not full C23
conformance or M21 completion.

## C23 nullptr_t variadic arguments

`nullptr_t` values, including the `nullptr` constant, are passed unchanged
through an ellipsis and can be retrieved with `va_arg(ap, nullptr_t)`. The
existing target represents them in the same 64-bit QBE scalar class as object
pointers. `nullptr_t` remains a distinct C type. C23 nevertheless permits a
`nullptr_t` actual argument to be retrieved as a pointer type with character-
pointer-compatible representation and alignment; this target uses the same
64-bit representation for its pointers. The converse retrieval is not generally
permitted. Other existing variadic and
aggregate ABI limits remain.

The compiler build and focused compile/IL and rejection checks were run. One
example was lowered through pinned QBE and assembled; generated-program runtime,
host ABI interop, regression fixtures and fuzzing remain pending. This is not
M21 completion or a general ABI conformance claim.

## Promoted-compatible enum va_arg types

`va_arg` accepts complete enum types compatible with their own integer-promoted
type, such as int-compatible enums and fixed long-compatible enums. The result
retains the requested enum type, using the existing integer QBE class. A
subword-compatible enum that promotes to int remains rejected in `va_arg`;
passing such an enum through an ellipsis continues to use the existing integer
promotions. Callers remain responsible for the actual C `va_arg` type and value
rules; this does not validate dynamic argument types.

The compiler build and focused compile/IL and rejection checks succeeded; one
example was lowered using pinned QBE and assembled. Generated-program runtime,
ABI interop, regression fixtures and fuzzing remain unrun.
