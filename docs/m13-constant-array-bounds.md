# M13l1: fixed integer constant-expression array bounds (design before implementation)

Replace the former integer-token-only bound subset with assignment-expression
syntax, per the array-declarator grammar, and use the shared M18b1 ICE query to
retain only fixed, strictly positive bounds. This is not VLA or general VM type
support. The prior empty-bound/composite/parameter-adjustment rules stay intact.

ast_array_type_syntax owns element syntax and an optional ast_expression *bound;
NULL means unspecified, never a zero-size array. Remove token-only has_bound and
bound metadata instead of maintaining two sources of truth. Resolve the checked
bound AST in sema, preserve its type/conversion nodes, then query the evaluator.
Use canonical bits and source signedness to reject negative/zero values before
converting to a count; retain the overflow-safe count <= 1 MiB / element_size
check and per-function aggregate automatic-storage accounting. Bound expressions
never emit QBE. No token vector, reparsing, runtime bound or optimizer is added.

The parser uses Pratt floor 1 (assignment-expression): unparenthesized comma
cannot run past a bound separator; parentheses allow the full grammar and ICE
form checks reject evaluated comma/assignment. Existing 128 expression recursion,
64 declarator recursion/dimension/pointer/function limits remain, including
cross-recursion through sizeof(type-with-bound). Type caches stay immutable.

Parameter-bound name visibility must not accidentally capture an outer local.
During function-type resolution enter an ephemeral prototype scope, resolve
parameters left-to-right, and bind each named adjusted parameter only after its
whole declarator. A bound within its own declarator therefore sees an outer name,
not itself. Bindings use arena-owned diagnostic/type-only local ASTs with no slot,
no function-local list membership and no initializer; actual definition parameter
locals are still created/bound by sema_function_body as before. Nested function
prototypes get nested scopes. Restore the outer scope on every error/success.
Resolve derived return syntax while the completed parameter scope is visible
(e.g. pointer-to-array returns with sizeof a parameter), then discard the scope.
No runtime expression from these type-only bindings can reach QBE: only fixed
ICE bounds are retained and sizeof operands are already opaque. Typedef names,
VLA dependencies, static/qualified parameter brackets and [*] remain unsupported.

Tests: all integer/boolean/character kinds; expressions/conditional/short-circuit
bounds; sizeof/alignof, macros, known/unknown composites; fixed multidimensional
and grouped/abstract declarations; prior-local sizeof, own-name shadowing,
prototype parameter shadowing/adjusted arrays/nested callbacks and derived return
types. Reject nonconstant forms, signed negative/zero/overflow, invalid shifts,
evaluated comma/assignment, huge unsigned values and storage excess, never execute
those cases. Check parser/typed/cross-type recursion and exact resource limits.
Native references must use truly constant bounds (not silently depend on a host
VLA extension), with strict static assertion of resulting sizeof when suitable.
Use original QBE programs and both-direction host ABI checks, typed-cache/scope
units, both-host sanitizers, all regressions, bounded fuzz and exact-source CI.
Update older rejection fixtures that used now-supported [true]/[1+1]/[sizeof]
forms, replacing them with genuinely unsupported VLA forms and documenting this
coverage change, not dropping rejection coverage.
