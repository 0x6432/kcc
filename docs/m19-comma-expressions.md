# M19a: sequenced comma expressions (design)

Bring forward this independent M19 operator increment after M14i. It directly
uses M14g's discarded-expression emitter and closes the distinction between
full expressions and assignment-expressions before later initializer/typedef
work. This does not complete M14 or the rest of M19 (switch/labels/goto/operators).

Reference: public C23 working draft N3096, 6.5.17:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

expression ::= assignment-expression { ',' assignment-expression }
assignment-expression ::= the existing assignment-or-tighter Pratt subset

Add a separate concrete ast_comma_expression with left/right expressions, not
an arithmetic or list node. Put comma at Pratt powers 0/1, below assignment's
unchanged 1/1. Comma associates left; assignment still associates right. Existing
operator powers do not need renumbering. A full-expression call uses floor 0;
argument expressions and unparenthesized scalar initializers use floor 1. Calls
and declaration lists own their separator commas. Parentheses and array subscripts
still admit full expressions, so f((a,b),c) has two arguments while f(a,b,c) has
three. Do not buffer tokens or split/reparse an expression to recognize commas.

Sema types both operands with ordinary load/array/function value conversion.
The left operand is evaluated as a discarded expression and may have void type.
The result has the converted right operand's type/value, possibly void, and is
never an lvalue. Preserve both side effects and count max(left_depth,right_depth)
plus one against the existing 128 typed-depth limit. No promotions or usual
arithmetic conversion occur between the two operands. Preserve pointer/array
shape on the right, and reject void-result uses in scalar contexts through the
existing guards. Neither assignment nor address-of may treat comma as an lvalue.

Codegen must emit left through the discarded-expression helper, then right.
A scalar result uses ordinary codegen_expression for right; a discarded void
comma recursively discards both sides. Add the needed forward declaration rather
than duplicating call/void emission. This guarantees left completion before the
right, including short-circuit control flow and void callbacks. Do not flatten
commas into an unsequenced argument list or invent a scalar value for void.

Tests: assignment precedence, left associativity and sequenced side effects;
full return/condition/for/subscript expressions; parenthesized comma arguments
versus real argument separators; declaration initializer commas versus grouped
expressions; every primitive/pointer/function-pointer right result; arrays and
function designators on the right; void on either/both sides, calls/short-circuit
branches and statement discards; both ABI linkage directions and narrow/full-width
results. Check concrete AST children, types, no-lvalue result and exact depth.
Migrate the old f((1,2)) rejection to an actual wrong-argument-count constraint.
Negative tests retain missing operands, missing separators, invalid lvalues,
void scalar contexts and declaration-name/scope constraints. Full GCC regression,
GCC/Clang targeted QBE/runtime/ABI, bounded sanitized fuzz, immutable matrices and
exact-source CI are required. No arbitrary or undefined fuzz C is executed.
