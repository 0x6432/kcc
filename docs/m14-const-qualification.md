# M14j: const qualification (design before implementation)

Reference: public C23 draft N3096, 6.2.5p31, 6.3.2.1p1/p2, 6.3.2.3p2,
6.5.4p6, 6.5.9, 6.5.16.1, 6.7.3p6/p10/p11 and 6.7.6.3p4/p14:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

Return to M14 after the independent M19a comma increment. Implement const, not
volatile/restrict/atomic or typedefs. Retain the current literal-bound array,
fixed-signature and explicit storage subsets. Bracket parameter qualifiers and
static/VLA array bounds remain a separate increment, rather than being ignored.

## Representation and immutable type operations

Add a qualifier bit set to the common semantic type header (only const now),
not a new wrapper kind that every scalar/layout helper must accidentally unwrap.
Use designated header initializers throughout to avoid missing-field warnings.
Integer/void globals stay canonical and unqualified. Add checked arena helpers
for qualification and unqualification, preserving the correct concrete type's
size and children. Never mutate a shared singleton or a syntax cache after it
is published. Pointer qualification changes only that pointer, not its referent.

C23 qualifies an array and its element identically. Array constructors inherit
the element's immediate qualifier set; qualifying/unqualifying an array applies
recursively through array elements, but not through pointer referents. Thus
const int a[2][3] has qualified rows/elements, int *const a[2] has const pointer
elements, and const int *a[2] has mutable pointers to const ints. Unknown bounds
remain unknown and do not acquire a stride. Layout/ABI helpers still dispatch
on the same kind and ignore const for representation only, not for constraints.

Compatibility requires identical qualification at each corresponding level.
Add a deliberate unqualified-compatibility operation that ignores only the root
qualification (and the equivalent array-element qualification); recursion below
a pointer remains strict. Composite pointer reconstruction preserves its root
qualifiers, and array reconstruction preserves the element/array invariant.
No generic recursive removal of pointee qualification is permitted.

## Syntax

Recognize const in language-token conversion, not raw pp lexing. Unify the
existing builtin-specifier scanner to accept const before, between and after
integer specifiers or void, retaining existing integer conflict diagnostics.
Repeated const is idempotent. A qualifier without an actual type specifier is
not implicit int. Use a separate concrete qualified-type syntax node around the
builtin base and around each const-qualified pointer star. These nodes retain
source provenance; the mutable declarator hole remains in the actual pointer's
referent. Parenthesized/function/abstract declarators use the same parser.

The sole empty parameter marker remains exactly unnamed unqualified void;
qualified void is not a stored parameter or a substitute empty marker. Native
GCC/Clang both reject it under -std=c2x -pedantic-errors. const void * remains
an ordinary valid pointer type. Both const and void must stay out of the integer
specifier permutation classifier's semantic result enum.

## Sema and value conversion

An lvalue retains its declared qualifiers; ordinary lvalue conversion strips
only its top-level qualifiers, preserving const pointees. Assignment rejects
const lvalues before evaluating conversion helpers. Initialization targets the
unqualified version of the declared object type while the binding/storage type
remains qualified. Explicit scalar casts produce the unqualified version of the
named type (6.5.4p6); their syntax cache still records the written qualification.
Pointer casts may remove pointee const, but modifying a truly const-defined
object that way is undefined and must never be executed in tests.

Function returns are the unqualified version of the declared return type under
6.7.6.3p4, without removing pointee qualifiers. Keep definition parameter.type
as the effective adjusted, possibly const object type for local binding/spills.
Construct the function signature's parameter types from their top-level
unqualified versions for compatibility/calls, per 6.7.6.3p14. Never strip const
from a named parameter's local just to make prototype compatibility pass.

Implicit pointer conversion may add immediate referent const but cannot remove
it. Compare immediate referents with unqualified compatibility and require the
target qualifier set to include the source set. Object/void conversion also
honors this inclusion. Do not recurse: int ** to const int ** remains invalid;
int ** to int *const * is a different valid one-level qualification conversion.
Explicit pointer casts retain M14i's broader category rule, not implicit rules.

Pointer equality/ordering accepts the allowed qualified/unqualified compatible
referent cases; mixed object/void equality forms a void referent with the union
of qualifiers. Construct a real common pointer type and explicit conversions,
without dropping const or weakening function compatibility. Mixed object/void
ordering stays invalid. Pointer subtraction permits qualification differences
on compatible referents, but still requires both complete object referents and
never guesses a void/incomplete stride. Check each inserted conversion depth.

## Codegen and tests

No const-specific memory opcode or read-only automatic storage is required.
QBE types/ABI/layout remain kind-based; sema enforces modification constraints.
Do not optimize away source effects or let qualifier handling create a void
load, object size or dummy function value. Preserve explicit typed conversion,
load, array/function decay, cast and comma nodes.

Tests cover all primitive/pointer leaves, qualifier positions/repetition,
parenthesized and abstract declarators, local/parameter modifiability, explicit
casts back to mutable views of actually mutable objects, function return and
parameter top-level normalization, immutable caches, arrays/rows/unknown bounds,
one-level safe/unsafe pointer qualification, mixed equality/ordering/differences,
void qualifiers, callbacks and both narrow/full-width register/stack ABI
linkage directions. Negative tests must reject real const writes and implicit
qualifier removal, not reject newly valid syntax. Exercise exact type/depth
budgets and lexical pp/token contracts. Run full regression, both hosts/QBE,
bounded sanitized fuzz, independent matrices and exact-source CI; document
legacy-host C23 array-qualification disagreements rather than hiding them.
