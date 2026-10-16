# M19d1: additive compound assignment (design before implementation)

Implement += and -= only, for current integer and complete-object pointer
lvalues. Other compound operators follow separately. Follow N3096 6.5.16.2:
E1 op= E2 behaves like E1=E1 op E2 except E1 is evaluated once. Do not expand
syntax or share an AST subtree that gets emitted twice.

Raw preprocessing already keeps +=/-= punctuators. Add post-pp tokens, assignment
Pratt binding powers 1/1 and BNF assignment-expression ::= conditional-expression
| unary-expression ("=" | "+=" | "-=") assignment-expression. Keep separator
commas and the conditional middle/last arm rules unchanged. A concrete
ast_compound_assignment_expression retains left/right, binary add/subtract
operation, calculation type and pointer element stride. Its expression header
carries the unqualified stored result type, non-lvalue status and checked depth.

Sema checks the left with root load/decay suppressed, requires a modifiable
integer/pointer lvalue and checks the right normally. Integer updates use the
usual arithmetic conversions: record the common calculation type, explicitly
convert the right subtree to that type and retain the left's stored type for a
single backend load/conversion. Pointer updates require an integer RHS (promoted
explicitly) and a complete object referent before reading layout; record its
stride and preserve exact pointer/referent qualification. Bool RHS is promoted;
nullptr/pointer RHS is not an integer offset. No pointer difference compound
assignment, void/function/incomplete referent arithmetic or non-lvalue update.
The result is the stored unqualified type, not the arithmetic common type.
Consteval rejects evaluated compound assignment forms; sizeof checks constraints
without executing them. VLA bounds remain a separately labelled subset limit.

Factor existing scalar conversion emission into a value-based helper and keep
the expression-based wrapper. This lets a loaded old value and a computed result
use exactly the same extension, narrowing and bool truth conversion as explicit
conversion ASTs, without synthetic loads or duplicated addresses. QBE evaluates
the right, computes the left address once, loads once, converts to calculation
type, adds/subtracts and converts back, stores once and returns the stored value.
This RHS-first choice is permitted by C; tests must not demand an unspecified
operand order. For pointers extend the already promoted index using its signedness
and scale by checked stride, matching existing pointer offset lowering. Never
use pointer signedness helpers or integer properties on nullptr_t.

Test all 12 integer types and mixed ranks/widths/signedness, narrowing/unsigned
wrap/bool truth, right association and precedence, complete pointer strides and
negative/promoted indices, once-only effectful lvalue and RHS calls, sizeof and
short circuit/conditional/comma, mixed-stack/narrow-return ABI in both directions,
exact typed depth and compile-only constraints. Curated runtime avoids signed
arithmetic overflow, invalid pointer range and unsequenced conflicting effects.
Fuzz never executes generated C. Run both-host target/sanitizer checks plus full
normal/QBE/fuzz, then checkpoint/push and update limits/coverage/handoff.
