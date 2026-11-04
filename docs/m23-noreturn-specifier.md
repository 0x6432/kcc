# `_Noreturn` function specifier

The deprecated `_Noreturn` function specifier is accepted for direct and
typedef-derived function declarations, at file and block scope. It is rejected
for objects, typedef declarations, parameters and type names. The compiler
records the spelling but does not optimize based on it or diagnose a function
that returns; returning from such a function has undefined behavior under C.
The deprecated `<stdnoreturn.h>` fallback defines `noreturn` as `_Noreturn`.

The compiler has been built, but the added regression cases have not been run.
The C23 `[[noreturn]]` attribute remains unsupported.