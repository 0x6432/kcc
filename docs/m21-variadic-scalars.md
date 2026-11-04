# M21: bounded scalar variadic support

On x86-64 SysV, variadic prototypes, definitions, direct and indirect calls
support promoted integers, pointers and `double` arguments. `float` arguments
receive the default promotion to `double`. Aggregate variadic arguments and
aggregate call/return ABI are not implemented.

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
