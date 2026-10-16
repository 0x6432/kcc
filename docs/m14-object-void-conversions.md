# M14h: object/void pointer conversions and mixed equality (design)

Reference: public C23 working draft N3096, sections 6.3.2.3p1,
6.5.9p2/p6 and 6.5.16.1p1:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

Build on M14g's real incomplete void type. Permit bidirectional conversion
between void * and a pointer to any object type for initialization, assignment,
fixed arguments, returns and explicit casts. This is a value-conversion rule,
not type compatibility: void * and int * remain distinct incompatible types;
functions declared with those differing parameter or return types still conflict.
Keep compatible function-pointer conversions separate. No implicit or explicit
object/function pointer bridge is added by this increment. Other incompatible
object pointer casts remain a future explicit-cast increment.

Use a small named semantic predicate that checks both types are pointers and
one immediate referent is void while the other is an object type. The predicate
must not recurse: int ** can convert to void * because its referent int * is an
object, but int ** cannot convert to void **. Likewise a pointer to a function
pointer object converts to void *, while a function pointer itself does not.
Known- and unknown-bound array referents are object types; converting back to
the original appropriately aligned type is valid and must preserve its shape.
Do not give incomplete void a size or stride, and do not weaken completeness
constraints for arithmetic/subscripts/differences.

Insert an ordinary concrete ast_conversion_expression for non-compatible
object/void conversions. Keep the original operand and target type explicit,
preserve expression locations and count the extra typed-depth edge. Cast syntax
uses the same constraint check while retaining its concrete cast node. QBE uses
its existing pointer-width copy: no memory access, truncation, integer detour or
fake representation is needed. LP64 pointer representation is already shared.

For == and != only, if the pointer types differ by this rule, convert the
object-pointer operand to the existing void-pointer operand's type, in either
source order. The typed comparison must then have compatible operands and an
int result. Do not silently make mixed relational comparisons valid. Existing
compatible object-pointer ordering remains unchanged; no invalid ordering is
executed in tests. Null pointer constants and nullptr are deliberately not
implemented here, and integer zero still cannot initialize a pointer.

Tests: every implemented primitive object leaf, pointers-to-pointers, fixed and
unknown-bound array pointers, function-pointer objects, direct/indirect calls,
returned void/object pointers, assignments and explicit round trips, mixed ==/!=
in both orders with once-only operand effects. Use only real correctly aligned
objects and restore the original type before dereferencing. Host-provided null
pointers may test conversion/cancellation, without accepting integer null syntax
early. Both ABI linkage directions must cover void arguments/returns and mixed
register/stack pointers. Typed units inspect conversion nodes/types/depth and
unchanged compatibility. Reject function bridges, recursive void ** conversions,
conflicting signatures, mixed ordering and incomplete arithmetic. Migrate only
former rejection fixtures that this design intentionally makes valid. Run full
regression, both hosts/QBE, sanitized bounded fuzz, isolated matrices and CI.
