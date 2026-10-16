# M18a: fixed sizeof and type alignment (design before implementation)

Bring forward the independent fixed-layout subset of M18 using the existing
Linux x86-64 SysV LP64 type layout. Reference C23 N3096 6.5.3.4 and 6.5.3:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

sizeof-expression ::= "sizeof" unary-expression | "sizeof" "(" type-name ")"
alignof-expression ::= ("alignof" | "_Alignof") "(" type-name ")"

No expression alignof extension, void/function sizes, VLAs, bit-fields, type
inference or integer constant evaluator is claimed. Literal-only array bounds
stay literal-only even though measured values are integer constants in C23.
Both alignof spellings share semantics, with exact separate debug tokens.
Raw preprocessing is unchanged. size_t/standard headers are not supplied.
The target's sizeof/alignof result type is unsigned long, not host size_t.

Add concrete ast_sizeof_expression (operand), ast_sizeof_type_expression
(type_syntax) and ast_alignof_expression (type_syntax), each with its own header
and computed uint64_t result. Do not fabricate an integer literal or evaluate a
child to discover its size. Type forms have expression depth 1; expression forms
have operand depth+1. Existing type/declarator budgets bound type syntax.

Parser disambiguates one already-consumed '(' with begins_declaration_specifier,
without rewind or lexer hacks. A type form uses the existing abstract declarator
parser and requires ')'. An expression form parses a parenthesized full expression,
requires ')', and then takes any postfix suffix as part of the unary operand.
For nonparenthesized operands the existing prefix binding floor handles unary
operators and stops before binary operators. sizeof sizeof x is valid; sizeof
(int) x is not a cast operand; sizeof((int)x) is. Named helpers carry exact BNF.

Sema resolves/checks the operand even though it will not execute. sizeof's
immediate expression uses sema_expression(..., false): no root lvalue load,
array decay or function decay. Nested expression conversions still happen
normally, so sizeof(a) differs from sizeof(a+0) and invalid skipped assignments
still diagnose. Reject function/incomplete/void operand types before calling
layout APIs. Read type_object_size/type_object_alignment only on complete object
types. Qualified types keep their actual shape and sizes. Array/function
parameters have adjusted local types; sizeof sees the effective pointer type.
Keep the typed operand and recompute checked depth; QBE only emits the computed
unsigned-long constant, with no operand code/calls/loads/stores/branches. Literal
strings may remain in the semantic string list as harmless unreferenced private
data; do not mutate semantic source/type caches merely to suppress unused data.

Tests: all primitive, pointer, const and array type sizes/alignments; function
pointers versus functions, unknown arrays versus known composites, effective
parameter sizes, strings including embedded NUL/concatenation, true/false and
conditional promotion. Verify no evaluation of calls, writes, uninitialized reads,
invalid-at-runtime dereferences or out-of-bounds address calculations in fixed
unevaluated operands. Constraints still check malformed/undeclared/const-write
operands. Inspect AST root no-decay and computed unsigned-long types, nested
conversions and exact depth budgets. Cross-object sizeof result ABI is unsigned
long in both directions. Use native alignof hosts or explicitly labelled
#define alignof _Alignof compatibility oracles for legacy hosts. Full regression,
QBE/runtime, both-host sanitizer units, bounded nonexecuting fuzz and exact CI.
