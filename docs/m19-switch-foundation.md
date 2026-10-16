# M19f1: switch selection and independent jump contexts

Design before implementation, following N3096 6.8.4.2 and 6.8.6.2/3. This is a
small foundation increment: accept switches without case/default labels, then
add case/default collection and dispatch in M19f2. Do not claim full switch
support while case/default remain rejected. Attributes and variably modified
types remain unsupported.

Add a demand-language switch keyword and concrete ast_switch_statement with
control expression and body. RDP parses switch-statement ::= "switch" "("
expression ")" statement with the usual bounded statement nesting and explicit
BNF comments. The condition is an integer expression, not just any scalar;
sema inserts its integer promotion, without booleanizing or altering shared
types. Check the entire body, including unreachable declarations/statements.
Selection/body scopes follow existing if/loop scope conventions.

Replace loop-only contexts with a simple enclosing-control stack for sema and
codegen. Every loop and switch pushes its own statement identity. Break binds
the nearest context; continue searches outward past switches to the nearest
loop. Record exact target statement pointers in existing jump ASTs. Codegen
looks up that validated target, rather than assuming every jump targets the
topmost loop. Push/pop must restore parents even when sema fails. No synthetic
objects, typedefs, universal unions or whole-TU token vector.

For a switch without case/default, evaluate its promoted control exactly once
and jump directly to the exit. Emit the full body in a predecessor-free block,
under the switch context, so an explicit goto can reach an internal named label.
A normal switch entry never executes the body. A goto into the body bypasses
the controlling expression; a break exits this switch, while continue still
reaches an enclosing loop's condition/step. Emit the exit conservatively, just
as loops do; do not infer whole-function reachability.

Test all implemented integer categories, side effects and phi-producing control,
empty/compound/secondary bodies, nested switch/loop break/continue binding,
goto into bodies and bypassed control evaluation, dead-body diagnostics,
integer constraints, exact syntax/nesting bounds, source locations and explicit
promotion/target identity. Use original strict native programs with GCC/Clang
and both-direction mixed-stack ABI. Run full normal/QBE, both-host targeted
ASan/UBSan and bounded lexer/pipeline fuzz; never execute generated fuzz C.
Commit/push and update handoff/contracts/limitations before the case-label stage.
