# Fixed-bound array-parameter qualifiers and static contracts

An outermost array declarator in a function parameter may use `const` inside
the brackets, with or without a fixed bound; `restrict` may also appear there. It qualifies the adjusted pointer
object, not the array elements; the function type omits that top-level
qualification. `static` may precede or follow `const` and requires a positive
integer constant bound within the existing 1 MiB array-type limit. In a call,
`static` expresses the C minimum-accessible-elements contract; no runtime
checks or optimizer assumptions are introduced. Calling with insufficient
accessible elements violates the language contract.

Bracket qualifiers and `static` are rejected outside parameter declarators and
on inner or pointed-to arrays. An outermost `[*]` is accepted in prototype
scope only; its array spelling adjusts immediately to a pointer. Nonconstant
integer outer bounds in prototypes are analyzed but not evaluated, and also
adjust immediately to a pointer. This includes `static` bounds; no dynamic
minimum check is emitted. A definition may use integer expressions over earlier non-atomic integer
parameters, enumerators, and literals as its outer bound. Supported assignments
and increments of earlier parameters are evaluated in the function prologue;
pure expressions are omitted because their values are discarded by adjustment.
Casts, calls, indirect accesses, compound literals, nested `[*]`, nested variable
bounds, `volatile`,
and atomic pointer qualification remain unsupported. This checkpoint builds;
the dedicated regression suite and QBE runtime coverage have not yet been run.
