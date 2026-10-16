# M14g: void types, functions and discarded expressions (design)

Reference: public C23 working draft N3096 (2023-04-01), sections 6.2.5p24,
6.3.2.1p1, 6.3.2.2p1, 6.3.2.3p1, 6.5.3.2 and 6.8.6.4p1:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

Add a concrete ast_void_type_syntax and singleton semantic type_void. The draft
classifies void as an incomplete object type that cannot be completed; therefore
it is an object but is neither complete nor scalar. Never give it size zero,
a scalar value width, a QBE value type or an object spill. Functions may return
void; arrays may not have void elements and stored locals/parameters may not
have void type. Pointers to void are complete scalar objects. Initially retain
compatible pointer value operations; object/void pointer conversions and mixed
pointer equality are a separately designed M14h increment, not implicitly done.

General declaration specifiers and cast disambiguation must recognize void,
without adding void to the integer-specifier permutation loop. Parse each fixed
parameter through the normal declarator path; a sole unnamed un-derived void
immediately before ')' means zero parameters. Named void, void with other
parameters and arrays of void are constraints. void * parameters must not be
mistaken for the sole marker. Function pointer syntax and fixed calls may have
void returns without being classified as object values.

Allow return-statement ::= 'return' [ expression ] ';'. A void function accepts
only return without an expression; a nonvoid function requires an expression.
Reject even return void_expression in a void function under N3096 6.8.6.4p1,
rather than adopting the host's possible extension. A void function may fall
through to a bare ret. Keep nonvoid/main fallthrough policy explicit and unchanged.

A cast to void discards its operand (including another void expression) but
retains side effects. Ordinary expression statements and for initializer/step
expressions may discard void. Scalar-required contexts must reject nonexistent
void values before internal scalar helpers: conditions, !, logical operands,
arithmetic/comparisons, assignment, call arguments, scalar casts and nonvoid
returns. Audit every sema_expression caller, not just assignments. Common scalar
conversion constraints must diagnose non-scalar sources rather than assert when
new valid syntax exposes a user constraint failure.

Unary * of void * has void type and is not an lvalue (6.3.2.1p1 excludes void).
Address-of still accepts the result of unary * by its special constraint, so
&*p is valid cancellation even for host-provided null; evaluate p once without
memory access. Bare void indirection is only usable for discarded side effects;
never issue a void load. Invalid/null indirection must not execute in tests.
Complete-referent checks continue to reject void-pointer arithmetic/subscript/
difference, including zero offsets. Void remains an object type for pointer
category rules; do not confuse its incompleteness with function designators.

Factor common call emission into a helper with an optional output-value pointer:
scalar calls allocate/canonicalize a result temporary, void calls emit bare call
with no fabricated result. codegen_expression remains scalar-valued. Add an
explicit discarded-expression emitter: scalar expressions use normal emission;
void calls use the no-result path; void casts recursively discard their operand;
void indirection evaluates only its pointer operand. Route expression statements
and for initializer/step through this emitter. Function signature/return emission
omits the QBE result type for void and emits bare ret, both direct and indirect.
Do not use a fake integer zero or an uninitialized/sentinel temporary as a void
value. Preserve target-before-arguments once-only evaluation and narrow callback
return canonicalization in the factored scalar path.

Tests: direct/indirect void calls with side effects, callbacks/factories returning
void, early returns/fallthrough, casts/discards and for-header effects; both host
linkage directions and mixed register/stack ABI. Host-supplied void pointers test
compatible values and &* cancellation without implementing conversions early.
Typed units inspect real void syntax/types, absent return expressions, no void
loads/spills and scalar caller constraints. Check every void misuse category,
void marker versus void * parsing, arrays/incomplete locals, function declaration
compatibility, pointer completeness and exact type/expression limits. Do not run
programs containing undefined discarded null dereferences or void return values.
Full regression, both hosts/QBE/reference/ABI, bounded sanitized fuzz, isolated
matrices and exact-source CI remain required. Keep normative draft references and
legacy-host extension gaps explicit; this is not full C23 conformance.
