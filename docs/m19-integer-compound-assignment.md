# M19d2: remaining integer compound assignments (design before implementation)

Extend the concrete compound node with *= /= %= &= ^= |= <<= >>=. Reuse the
existing binary_operator enum; do not add a generic AST or duplicate assignments.
Add language punctuator tokens and all eight right-associative Pratt 1/1 entries.
Raw preprocessing already preserves these punctuators, including token pasting.
BNF comments list every supported assignment operator.

Sema keeps the existing one left modifiable lvalue path. Only +=/-= allow a
pointer left; all remaining operators require integer operands. Arithmetic and
bitwise operators calculate using the usual arithmetic conversions; shifts
independently promote left and right, retaining the promoted left calculation
type rather than imposing a common type. The result is converted back to the
unqualified stored type. For pointer arithmetic retain the existing explicit
RHS promotion, complete-object guard and stride unchanged. Diagnostics describe
constraints, not a runtime guarantee. sizeof remains checked/unevaluated and
consteval rejects evaluated compound assignments.

QBE uses existing binary_instruction for integer operations, including signed
versus unsigned division/remainder/right shift. Pointer compound operations keep
explicit add/sub because binary_instruction intentionally handles pointer
comparisons only. Factor the existing word-size shift-count normalization into
a value helper shared by ordinary binary and compound expressions: QBE consumes
a word count, but only defined C count ranges are curated runtime tests. Keep
one address, one old load, one RHS, one converted store and stored-value result.
No constant-folding shortcut, AST expansion or implied evaluation order.

Test every operator and all integer storage categories, mixed ranks/widths,
unsigned division/remainder and signed negatives, sign-sensitive right shift,
independent shift promotions (unsigned RHS must not turn signed left logical),
64-bit counts converted for QBE, narrow back-conversion and whole-value boolean
truth. Exercise right association, precedence, skipped paths/sizeof, and
once-only effectful lvalue/RHS calls without unsequenced conflicts. Cross-object
both-direction ABI includes narrow results and stack-passed counts. Reject
pointer/noninteger RHS and const/non-lvalue LHS constraints (compile only).
Division by zero, signed overflow and invalid shift counts are not executed.
Use sanitized fuzz to explore them only through compilation, never generated-C
execution. Rerun additive/update suites, both-host sanitizer units and full
normal/QBE/fuzz before checkpoint/push. Record exact validation and limitations.
