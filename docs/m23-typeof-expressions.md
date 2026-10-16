# M23d2: typeof and typeof_unqual expression operands

Design before implementation, N3096 6.7.2.5 and 6.3.2.1. Extend M23d1 without
changing its type-name node: add a distinct ast_typeof_expression_syntax with
one expression operand and the unqualification flag. No tagged universal payload,
GNU spelling macro or whole-file token collection. The RDP contents rule becomes
("typeof" | "typeof_unqual") "(" (type-name | expression) ")". One demand peek
chooses current declaration-specifier starts; otherwise Pratt floor zero accepts
a full expression including comma. Typedef ambiguity remains M14 work. Both kinds
share the existing 64-query nesting guard, restored on failure.

Resolve expression queries in their lexical declaration/prototype scope using
sema_expression(..., false). This suppresses ONLY the immediate lvalue load and
array/function decay, preserving the operand's actual type and qualifiers. Child
expressions still undergo their required conversions and constraints. Cache the
resolved immutable type; typeof shares it, typeof_unqual removes root qualifiers
using the existing helper (array qualification follows elements until a pointer).
An operand can name a previous local/parameter/function; the declared object's
own identifier is not in scope before its declarator finishes. Prototype names
remain type-only bindings, not extra runtime spill slots.

All currently supported operand types are non-variably-modified: never generate
operand evaluation, even for calls, assignments, increments, comma/conditional
expressions or a potentially invalid runtime dereference. Still diagnose bad
names, calls, lvalues and types inside unevaluated operands. Existing string
registration can conservatively retain static data for an unevaluated literal;
this is not operand execution. No new consteval/codegen expression case is needed;
query syntax is consumed by declaration/cast/sizeof/alignof resolution. Distinct
nullptr types become directly nameable via typeof(nullptr); exercise object,
pointer, function-result and parameter interactions through existing scalar ABI.
Do not claim stddef.h exposure or VM evaluation/bit-field support.

Keep alias-derived bare function declarations and sole typeof(void) parameter
normalization explicitly deferred, as in M23d1. Existing postfix/prefix and
assignment/conditional result types must be reviewed rather than making typeof
silently unqualify everything. Tests must retain semantic cache/operand identity,
root const/array/function types and child conversions, query nesting, scopes,
source positions, no additional runtime locals and non-evaluation evidence in IL.

Validation: original-source C23 programs on kcc/QBE; compare the same original
source only when actual typeof and typeof_unqual keyword probes succeed. Exact
legacy diagnostic absence is not an agreement; never rewrite with __typeof__.
Add compile-only constraint/subset tests, callbacks, adjusted prototype scopes,
sizeof/static_assert/bounds and both-direction primitive ABI tests, plus seeds.
Run full normal/QBE regression, both-host targeted ASan/UBSan and bounded lexer/
pipeline fuzz; arbitrary generated C and runtime-UB fixtures are never executed.
Commit/push and record actual local versus separately observed CI results.
