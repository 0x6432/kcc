# M13e: pointer subscripts (design before implementation)

Add postfix-expression '[' expression ']' for the existing integer-object pointer
subset, including the symmetric i[p] form. Local array declarations, array-to-
pointer decay, strings, aggregate layout and complex declarators are not part of
this increment. Host-created live arrays exercise valid subscripting meanwhile.

Lexer conversion maps raw [ and ] and <:/:> digraph punctuators to left/right bracket
language tokens, without changing raw preprocessing spelling or caching. Token
names print canonical brackets, just as brace digraph conversion does. Existing
unsupported-token fixtures must be inspected and updated only if now valid.

Parser keeps a concrete ast_subscript_expression containing left/right operands.
Extend the existing postfix suffix loop to alternate calls and subscripts with
one token of lookahead. Each suffix checks parsed AST depth. The index expression
uses existing assignment-expression precedence (the comma operator is still
unsupported). Document the exact BNF at each changed parser function. Nested
index parsing must enter the existing expression nesting budget, not bypass it.

Sema analyzes/loads each operand once. Require exactly one pointer and one integer;
promote only the integer as for pointer addition. Reuse a clearly factored typed
pointer-offset builder rather than synthesizing/reanalyzing a fake parsed binary.
Replace the parsed subscript through its slot with a concrete indirection node
around the offset, annotate its referent type, lvalue category and checked depth,
and share the ordinary value-context load path. Do not cast struct layouts.
The compiler arena retains the replaced syntax node until compilation ends.

This deliberately lowers E1[E2] to *(E1+E2), so codegen needs no new subscript
address/load/store path: general indirection addresses and existing typed memory
operations already implement mutation and address-of. Every inserted offset,
indirection, promotion and value load counts toward the semantic depth budget.
Evaluation order is C-permitted, not promised source left-to-right.

Validate p[0], 0[p], negative indices from an interior array pointer, chained
pointer-to-pointer subscripts, stores/assignment results/address identity and
call/subscript precedence. Use independent counters to avoid unsequenced writes.
&end[0] (end one-past) forms the address without loading a pointee, just as
&*end; do not execute end[0] as a value. Do not claim null+0 is defined.
Host array fixtures cover all primitive sizes and pointer elements in both ABI
linkage directions, with GCC/Clang reference outputs. Add typed AST replacement,
promotion and depth tests, malformed brackets/operands, lexer/digraph tests and
fuzz seeds. Run every previous regression and bounded sanitizer fuzz before the
checkpoint, then queue isolated full matrices and verify exact-source CI.
