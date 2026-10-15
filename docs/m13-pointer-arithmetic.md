# M13d: scaled object-pointer arithmetic and ordering (design before implementation)

After equality, add pointer+integer, integer+pointer, pointer-integer, compatible
pointer subtraction and relational comparisons. Referents are currently complete
scalar object types only; void/function/array/qualified types remain later work.
Null pointer constants remain separate: never guess that an integer value zero
is a pointer. Existing source restrictions and lifetime/array rules still apply.

Introduce type_object_size for the currently implemented scalar objects: target
storage width/8 (bool 1, chars 1, shorts 2, int 4, longs 8, pointers 8), independent
of rank or host sizeof. The constructor's current scalar-referent restriction
must be revisited explicitly when other object categories arrive. No language
sizeof/alignof operator or array layout is implied by this small target-size API.

After analyzing/loading binary operands, sema lowers pointer offsets/differences
to separate concrete ast_pointer_offset_expression/ast_pointer_difference_expression
nodes, replacing the generic parsed binary expression through its slot. Never
reinterpret one struct layout as another. Arena ownership retains the old node
until compilation end; operands are shared, not duplicated or reanalyzed. Check
new typed depth before replacement. Offsets preserve pointer type and promote
only their integer operand. Pointer differences have target ptrdiff_t = signed
long and require compatible referents. Pointer+pointer and integer-pointer remain
constraint errors. Same-array relational comparisons produce int.

Codegen widens a canonical word index by its promoted type's signedness (extsw/
extuw), leaves long indices' bits alone, scales by element size and adds/subtracts
from the base address. This is backend representation lowering, NOT an invented
semantic conversion of every index to signed long. Pointer difference subtracts
addresses then signed-divides by element size. Relational comparisons use full
unsigned address ordering for the selected flat LP64 target; dispatch before
integer signedness queries. Every operand is evaluated once in a C-permitted
order; integer+pointer may lower base-first without promising source left-first.

Only arithmetic/ordering within the same live array object (including one-past)
is defined. A standalone scalar is treated as an array of one element. Out-of-
bounds arithmetic, dereferencing one-past, unrelated pointer subtraction/order
and nonrepresentable differences remain undefined; no test may execute them.
Curated QBE 1.2 probe passed GCC/Clang: negative signed word and positive unsigned
word indices, size-four scaling, negative element distance and pointer ordering,
using real live host arrays. Large-index extension can be asserted in IL, not
"tested" by executing impossible out-of-bounds pointer arithmetic.

Test all primitive and pointer referent sizes with host-created arrays, both
linkage directions, positive/negative/unsigned and promoted small indices, signed
distances, all six comparisons and one-past/scalar cases. Add AST promotion/size/
replacement-depth units, once-only side effects and explicit invalid combinations.
Replace earlier now-valid pointer+1/relational rejection fixtures with permanently
invalid multiplication/division, recording the coverage change. Run every old
regression, both hosts/sanitizers, bounded fuzz and exact-source CI.
