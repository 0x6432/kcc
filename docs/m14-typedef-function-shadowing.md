# M14l2d: block typedefs hiding file-scope functions

Design before implementation. Functions and typedef names occupy the ordinary
identifier namespace. A block typedef may hide a file-scope function, including
the function whose body contains it, without replacing the function symbol.
File-scope function/typedef collisions remain genuine constraints. Block function
declarations are still unsupported, so no same-block function binding exists.

Permit the new typedef binding only in a semantic block/loop scope. The parser
already distinguishes typedef names on demand and restores names on scope exit.
Before resolving an expression name to a local or function, reject a visible
typedef name with a dedicated not-an-expression diagnostic. Also exclude visible
typedef names from the bare-call undeclared-function shortcut so calls use that
same name check. Otherwise a hidden function could accidentally remain callable.
The existing prohibition on typedef/object hiding in either direction makes the
visible-typedef check unambiguous; do not generalize this ordering to ordinary
object shadowing without a scope-aware unified namespace design.

Keep type-name lookup separate from value use. A hidden function spelling used
in casts, sizeof/alignof type operands or typeof type-name operands names the
alias, not the function. Previously constructed function designators and pointers
remain bound to their immutable function symbols, and scope exit restores later
function calls. No type, AST representation, runtime storage or backend change
is required. Existing declaration and expanded-type limits remain in force.

Test self-name hiding, prototypes/definitions, nested typedefs, source order,
function pointers captured before and used during hiding, restoration after
blocks/loops, and original C23 queries. Reject calls, addresses and value uses of
the hidden function and all same-scope/file conflicts without executing them.
Verify AST aliases and captured/restored designators retain distinct identities,
with no alias local. Retain exact native for-typedef gap probes, four-host original
program differentials, 24 both-direction primitive ABI arrangements, full normal/
QBE regressions, both-host targeted sanitizers and nonexecuting bounded fuzz.
