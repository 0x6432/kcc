# M19f2: case/default labels and linear switch dispatch

Design before implementation, N3096 6.8.1, 6.8.2 and 6.8.4.2. Build on M19f1's
integer-promoted switch control and separate break/continue target lookup.

Add demand-language case/default keywords. Each has its own concrete label type,
block-item wrapper and secondary labeled-statement wrapper. A block case/default
label stands alone, including before a declaration or at block end (C23); a
secondary label requires a following statement. Case parses conditional-expression
at Pratt floor 2 before its colon; nested conditional colons belong to the
expression. Parenthesized comma/assignment forms still undergo ICE checking.
Keep one demand peek and existing bounded recursive statement parsing.

Sema searches enclosing control contexts for the nearest switch, skipping loops.
Labels outside one are constraints, even in dead syntax. Case operands must be
integer ICEs: analyze normally, insert explicit conversion to the promoted control
type and query the existing pure evaluator. Never use host signed arithmetic to
fold values. Compare canonical converted bits for duplicates. Store case values
and a linked collection on the owning switch; at most one separate default label.
Nested switches own independent collections. No case expression emits runtime
code. A local name is not a constant just because initialized with a literal.

Reserve a separate function-wide switch-label index range after named goto label
IDs; retain named-label count/index semantics unchanged. Function records the
switch-label total; case/default nodes retain their own target indices. Cap total
switch labels at 4096/function and 1024 per switch (including default), independently
of block-item/nesting/named-label limits. Failed checks prevent any IL output.

Backend evaluates the control once and emits a readable linear chain of width-
correct equality tests against converted case bits, jumping to reserved target IDs.
After no match, jump to default or exit. Generate the complete body from a fresh
predecessor-free block; each standalone case/default label terminates any open
predecessor then starts its reserved target. Secondary forms start target then
emit child. Fallthrough is ordinary ordered block traversal; return/goto/break do
not gain false fallthrough edges. Nested labels in if/loop bodies use their normal
enclosing contexts. Continue skips switches as before. No jump-table optimization,
GNU ranges/computed goto, attributes or VLA jump-scope support is implied.

Tests: all 12 integer controls and promotions, signed/unsigned and 32/64-bit case
conversion, converted duplicates and separate nested namespaces, bool promotion,
short-circuit ICE forms, invalid/nonconstant ICEs and checked arithmetic failures,
fallthrough/default placement/no-match, once-only control, labels nested in loops/
branches, switch nested in loops, Duff-style finite entry, goto and phi interaction,
C23 declaration/end labels with exact old-host grammar gaps, syntax/depth/resource
bounds, typed target ownership and both-direction mixed-stack ABI. Execute only
curated defined programs. All source/tests remain frozen during full normal/QBE,
both-host sanitizer and bounded lexer/pipeline fuzz validation. Update coverage,
contracts, limitations and handoff, then commit/push the tested checkpoint.
