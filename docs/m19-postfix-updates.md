# M19c2: postfix increment/decrement (design before implementation)

Extend the completed prefix update rules with postfix ++/--. Use a separate
concrete ast_postfix_update_expression, not a prefix flag or a universal union.
Its typed fields mirror the prefix node: operand lvalue, operation, calculation
type and checked pointer element size. The result type is the unqualified
operand type and the result is not an lvalue; the value is the old stored value.

Parser BNF: postfix-update-suffix ::= "++" | "--". Add this suffix to the existing
on-demand iterative call/subscript suffix loop, preserving left association and
postfix precedence. Atoms and parenthesized expressions use the same loop.
Existing shared parsed-depth checks apply after each suffix. This distinguishes
*p++ (indirection of the old pointer) from (*p)++ (update of its referent), and
supports p++[0]/p[0]++ without reparsing or textual rewriting.

Factor the existing semantic operand check into one named helper used by both
concrete nodes: suppress root load/decay, require a modifiable integer/pointer
lvalue, reject const/array/function/nullptr operands, check complete pointer
referents before layout, preserve qualifications and record promoted calculation
type/stride. Keep source locations and one operand subtree; no implicit second
address evaluation. Both results remain non-lvalues. Type/depth checks are not
skipped inside sizeof. Consteval's default form rejection applies to either
update kind, even in a skipped arithmetic branch; sizeof remains opaque.

Factor QBE address/load/arithmetic/back-conversion/store into a helper returning
a small backend-only pair {previous,current}. Prefix selects current; postfix
selects previous. This is not another AST payload/type or an ABI adapter. The
helper computes/stores exactly once, including _Bool truth conversion and narrow
integer canonicalization. Immediate store is a valid evaluation choice; tests
must not rely on unsequenced reads/modifications or call ordering permitted to
vary by C. Only defined same-array/one-past pointer updates are executed.

Test old/new values for every integer category, unsigned/narrow boundaries,
boolean transitions, primitive/row/nested/const-referent pointer strides,
indirection/subscript/call addresses, pointer-versus-element precedence, loops,
short-circuit/conditional/comma/sizeof and both-direction narrow/stack ABI.
Compile-only constraints include repeated postfixes, prefix/postfix result
updates, arrays/functions/const/void/incomplete/nullptr and non-ICE/VLA limits.
Replace the obsolete for-header i++ rejection with an undefined-name case,
retaining loop diagnostic coverage. Run both-host units/normal/QBE/sanitizer
checks and bounded lexer/pipeline fuzz, then checkpoint/push and update handoff.
