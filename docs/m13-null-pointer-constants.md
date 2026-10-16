# M13m: traditional null pointer constants (design before implementation)

Use the shared typed ICE evaluator to recognize integer constant expressions with
value zero, and explicit casts of such expressions to unqualified void *, per
N3096 6.3.2.3. This is deliberately distinct from the later C23 nullptr/nullptr_t
milestone and from arbitrary integer/pointer representation conversions.

A sema-only pure predicate queries an integer expression, or recognizes an
explicit ast_cast_expression to pointer-to-unqualified-void whose checked integer
operand is an ICE zero. Do not treat a zero-valued variable, arbitrary pointer
value, integer assignment/comma, pointer cast from another pointer, conditional
pointer result or explicit int * zero cast as a null pointer constant. Invalid
arithmetic is not proof of zero. Parentheses add no AST and do not change form.
Qualified void referents are not void * null constants; top-level cast target
qualification is already removed by ordinary cast value rules.

Make assignment-like conversion expression-aware before the old type-only
constraint checker. Any recognized null constant may convert to any implemented
pointer type, including function pointers and incomplete-array pointers, without
relaxing compatibility for other expressions. Keep ast_conversion_expression
with the checked original operand, exact target type, source location and depth;
keep explicit ast_cast_expression/type syntax for explicit zero-to-pointer casts.
No new literal AST, source rewrite or global constant folding is needed. Existing
QBE conversion emits/extents integer zero to the target's all-bits-zero 64-bit
null representation; this LP64 target choice must be documented, not inferred
for other targets. Evaluating a valid ICE at runtime has no side effects; sizeof
and skipped branches retain their already tested no-evaluation semantics.

Apply null conversions for ==/!= only, in either operand order, before common
pointer construction. Do not allow pointer < 0 or subtraction with integer zero
as a pointer difference (ordinary pointer+integer offset rules remain distinct).
For conditional arms preserve the existing arithmetic case first. If one arm
is a pointer and the other is a null constant, select that pointer's exact type
before applying the generic compatible/object-void pointer common type rules.
This ordering matters for function pointers versus (void *)0 and qualifier union:
a void null constant must not force an object's result type to void *.

Explicit casts permit the same proved-zero source to pointer types; all other
integer-to-pointer and pointer-to-non-bool-integer casts remain unsupported in
this milestone. Pointer-zero casts to int */function * yield typed null values,
not new null constant forms. No function/object pointer bridge or call adapter
is added. Initializers/assignment/arguments/returns already share conversion.

Test all integer ranks/bool/character forms, zero through unsigned wrap and
sizeof/alignof differences, short-circuit/conditional ICEs, void casts and exact
nonconstant near misses. Cover initialization/assignment/calls/returns, equality
both orders, conditional common types/qualifiers, object/void/function/nested/
unknown-array pointers and once-only effects on non-null operands. Never
execute null dereferences, null calls, null pointer arithmetic, invalid constant
arithmetic or incompatible pointer calls. Test compile-only relational/cast
constraints and exact typed-depth boundaries. Add typed conversion/cast/common-
result units, both-direction host ABI and mixed stack/callback cases, both-host
sanitizers, full regression/QBE/fuzz/CI. Update obsolete null-rejection fixtures
with nonzero or variable forms rather than dropping constraint coverage.

Next consumer: M23a2 adds the nullptr keyword with its own distinct scalar type,
not an integer/pointer macro alias. See m23-nullptr-constant.md for pre-implementation
AST/type/conversion/equality/conditional decisions and declaration/header limits.
