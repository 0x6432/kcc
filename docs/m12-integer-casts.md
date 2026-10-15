# M12d: explicit int/unsigned casts (design before implementation)

Add cast-expression = '(' integer-type ')' cast-expression to the existing
prefix/Pratt layer. The parser consumes '(' then inspects one current token:
a supported integer-type starter selects a cast, otherwise parse a grouped
expression. Factor postfix suffix parsing so grouped expressions still allow
calls, while cast syntax binds at prefix power. No second lookahead, token
vector or typedef-name heuristic is required for the current type subset.
Keep grouped expressions as existing AST expressions (not a wrapper node).

Add a concrete ast_cast_expression with requested integer specifier and operand,
separate from sema-inserted conversion nodes. Sema value-converts the operand,
sets the requested int/uint result, checks depth and always makes it non-lvalue.
No extra implicit conversion wrapper is needed: the cast node itself records
conversion. QBE lowers same-width casts with a word copy, preserving the target's
two's-complement bits. Syntax/typing changes must not be hidden in codegen.

Tests: cast-vs-group disambiguation, nested casts/prefix operators, operand call
binding, high-bit signed/unsigned round trips, explicit cast changing division/
comparison/right shift, grouped named calls, invalid lvalue assignment/type
syntax and parser/typed structural depth. Inspect concrete typed cast nodes and
loads. Run independent full-value host/QBE programs, existing ABI/regressions,
both sanitizer matrices and bounded fuzz seeds. No void/pointer/wider casts,
compound literals, typedef ambiguity or complete cast grammar is claimed yet.
