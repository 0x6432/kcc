# M15b1: non-decaying fixed register arrays

Design recorded before implementation, following validated/pushed 1c65282.
M15a1 source hashes matched after full validation and before commit. Keep
register parameter support separate: its definition/prototype distinction is not an array policy.

## Standard and intentionally bounded scope

N3096 6.3.2.1 paragraph 3 gives register-array-to-pointer conversion undefined
behavior; 6.7.1 footnote 142 explains that only sizeof and typeof operators can
apply directly to a register array. These rules do not prohibit declaring a
fixed register array or querying its size/type without decay. Four native hosts
accepted the unchanged sizeof-only original; GCC 14/Clang 18 also accepted a
typeof array copy whose ordinary storage is then indexed. Probes were syntax
compiled only, not executed. Never execute register-array decay programs.

Accept complete fixed block/for register arrays, including typedef and query
bases. They retain ordinary local allocation/count/storage constraints. Preserve
current array-initializer, incomplete-object and variable-length-array limits.
Reject unary & of the direct array with the existing register-object constraint.
At the single semantic array-value conversion boundary reject a direct resolved
register-array name before allocating a decay node. Label this refusal explicitly
as unsupported register-array-to-pointer conversion, not a native constraint.

The narrow policy also refuses decay inside non-evaluated surrounding operations
(e.g. sizeof(a[0]) or typeof(a+0)); no evaluation-context propagation is added.
Direct sizeof(a), typeof(a), typeof_unqual(a), and queries of the copied type are
supported. Ordinary array copies obtained through typeof are not register and
remain addressable/decaying. All indirect ordinary array referents through
register pointers remain unaffected. No new aliasing escape is introduced.

## Component interactions

Remove only the semantic blanket rejection of register array local types. Keep
register function rejection. In sema_expression's existing value_required array
branch, inspect expression_name -> resolved declaration -> is_register and
reject conversion before pointer allocation or AST rewrite. No lexer/parser/AST,
semantic type or QBE interface change. Direct names, including parenthesized
names, have already resolved their captured identity. Sizing and typeof paths
request no value conversion and retain the array type; assignment/update rules
still reject array lvalues independently.

## Validation

Curated defined originals: each primitive element, multidimensional/const,
alias-based/comma lists, mixed scalar/array groups, own-bound alias visibility,
nested scope restoration and for declarations. C23 originals copy register-array
types with typeof/typeof_unqual, then address/index ONLY ordinary copies. Verify
&array is a native constraint without executing; decay/subscript/call/comparison
sources are compile-only rejected unsupported/UB probes, never executed or
claimed native constraints. Keep non-decaying-but-internally-converting queries
as separate valid-C subset rejections. Parameters remain unsupported.

AST tests: array register flags, normal slots, identity of unevaluated query
operands, immutable array type reuse, and no storage-class propagation to copies.
Exact 256/257 locals, 4096/4097 items, 1 MiB/overflow storage and expanded depth
limits. Both-direction mixed-stack ABI via ordinary scalar results derived from
safe register-array sizes; four-host originals; full normal/QBE; both-host
ASan/UBSan; bounded lexer/pipeline compile-only fuzz on frozen source. Helpers
built serially; no source changes during validation. Update docs/ledger/version,
commit and push promptly; check exact-commit CI independently of local passes.

## Completion evidence

Implemented the deliberately non-decaying subset above. Read the M15b1 ledger
for exact full/QBE/original/ABI/sanitizer/boundary/fuzz evidence, pre-freeze test
corrections and independent CI status. The old scalar suite's two blanket array
refusals were replaced by this new positive suite; parameter refusals remain.
Queries with inner decay stay explicit compile-only refusals, not claimed native
constraints. No full C23 conformance claim.
