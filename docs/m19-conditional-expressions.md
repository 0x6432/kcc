# M19b: conditional expressions (design before implementation)

Implement C23 N3096 6.5.15 for the currently implemented integer, pointer and void
types. No structure/union, floating, nullptr_t or integer null-constant support is
implied. In particular pointer/0 remains an explicit unsupported constraint,
not a literal-only fake implementation of integer constant evaluation.

conditional-expression ::= logical-OR-expression
                         | logical-OR-expression "?" expression ":" conditional-expression

Add exact ? and : language tokens after preprocessing. A concrete
ast_conditional_expression contains condition, then_value and else_value plus its
common expression header. Syntax depth is max(all three child depths)+1.
The Pratt table puts ?: at power 2 between assignment 1 and logical-or (raised
from 2 to 3); raise the intervening binary powers, retaining prefix 30 and
multiplicative 20. A named RDP helper consumes the middle full expression at
floor 0, requires colon, and parses the final conditional-expression at floor 2.
Thus the middle admits assignment/comma, the third excludes unparenthesized
assignment, and nesting associates right. No GNU omitted-middle extension.
Keep parser recursion and structural depth checks; no rewind/token vectors.

Sema analyzes all three operands, including skipped arms. Condition undergoes
ordinary value conversions and must be scalar, not necessarily promoted to int.
Both arms undergo ordinary conversions. Integer arms use usual arithmetic
conversions (bool/bool therefore gives int); both void gives void; pointer arms
must have immediate unqualified-compatible referents or the object/void rule.
Construct the composite referent even if pointer types compare compatible, so
known/unknown array-bound information is not lost. Union immediate qualifiers;
never grant deeper covariance or object/function bridging. Convert both arms to
the common pointer/value type using checked explicit conversion nodes. Reuse a
small common-pointer constructor for comparison and conditional rules without
fabricating a binary AST for a ternary expression. Conditionals are never
lvalues. Recompute typed max-child depth after all conversions.

QBE uses one condition evaluation, jnz to two arm blocks and a merge. Only the
selected arm executes. For scalar results emit a word/long phi with actual final
predecessor labels after nested arm control flow. Each arm is canonical already;
no eager evaluation, bool truncation or pointer truth-width shortcuts. A void
conditional in discard position emits branch/merge only, no dummy result/phi.
Discarded scalar conditionals still evaluate only one arm.

Test exact lexer spelling and macro-produced punctuation, precedence and
right-association, comma/assignment in middle, parentheses in third, arithmetic
rank/sign pairs and bool promotion, pointer/object/void/qualified composite
shapes, function-designator and array decay, wide conditions and values,
selected once-only effects and nonexecution of invalid-at-runtime skipped arms.
Still diagnose semantic constraints in skipped arms. Test nested phi predecessor
labels and void branching, both-host QBE/reference/ABI calls and dirty narrow
returns, typed AST annotations and exact syntax/conversion depth limits.
Extend both sanitized fuzz seeds and run complete regression/CI before claiming
this checkpoint. Continue recording M19 switch/labels/goto/other operators and
unsupported type families separately.
