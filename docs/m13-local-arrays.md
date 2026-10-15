# M13f: fixed one-dimensional local arrays (design before implementation)

Add local declarations of the form integer-type {'*'} name '[' integer-token ']'
';'. The element is an implemented scalar, including pointers. One positive
integer literal (including existing bases/suffixes/separators or an expanded
macro) is the intentionally restricted bound grammar. General integer constant
expressions, variable-length/incomplete/multidimensional arrays, parameter array
adjustment, globals and array/string initializers remain later increments. Never
present this bound parser as a constant-expression evaluator.

Concrete ast_array_type_syntax holds the element syntax and bound token. A
separate semantic array_type holds element type/count; compatibility compares
both. The complete-object predicate must explicitly include arrays so &array
can infer pointer-to-array even though spelling pointer-to-array declarators is
still unsupported. Keep type_is_scalar and integer property APIs scalar/integer
only. type_object_size extends to checked element-size times count; add target
object alignment independently of QBE's stronger local allocation alignment.

Validate nonzero bounds and a per-function sum of declared object storage at
most 1 MiB, including parameter spill objects, with overflow-safe division before
multiplication. This is an educational resource budget, not a C language limit
or an exact bound on QBE's final stack frame. Existing 256-local and source/type/
expression limits remain. Reset the sum for every function; retain accounting
across nested scopes because all local slots are allocated at entry.

Array expressions denote nonmodifiable object lvalues. In ordinary value
contexts insert a concrete ast_array_decay_expression that holds the original
array lvalue and yields pointer-to-element; do not load array bytes as a scalar.
Address-of suppresses decay and yields pointer-to-array. Array assignment and
initialization diagnose before the scalar conversion helper; preserve scalar
initializers and point-of-declaration rules. Indirection/subscripts that yield
arrays follow the same decay path, so (&a)[0][i] works without new backend tricks.
Every decay/offset/indirection/load contributes to typed depth.

Codegen emits decay by the existing object-address helper, without a memory load.
Entry slots use target object size/alignment (QBE allocation alignment at least
four); scalar loads/stores/ABI helpers must never receive an array. Array objects
are not zero initialized. Tests must write every element before reading it.
&array arithmetic scales by the entire array; decay arithmetic scales by one
element. Pointer-to-array compatibility retains the bound, rather than silently
treating &a as element-pointer. No flat-layout pointer cast shortcut is allowed.

Test all twelve primitive element types and pointer arrays: loops, reads/writes,
pointer decay/calls/returns, same-array distances, &array identity/stride and
(&array)[0][i], explicit assignment conversions, scope/lifetime-safe host ABI in
both linkage directions. Add parsed/resolved type-cache/decay units, exact size/
alignment/resource limits and typed-depth boundaries. Compile only—not execute—
large-limit fixtures. Update earlier array-declaration rejection tests to retain
constraints on genuinely unsupported forms (e.g. incomplete local arrays), with
an explicit coverage note. Run all prior regressions, both hosts, bounded fuzz,
and queue isolated GCC/Clang normal/sanitizer matrices with exact-source CI.
