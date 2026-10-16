# M14b: pointers to incomplete arrays and composite declarations (design)

Extend M14a's object declarators to allow unknown bounds behind pointers, such as
int (*p)[] and int (*p[2])[]. Keep count zero as unknown cardinality, not a zero-
length array. Unknown arrays are object types but not complete object types;
pointers themselves remain complete objects. Add type_is_object separately from
type_is_complete_object and relax pointer construction only to object referents.
Void/function pointers remain outside this increment.

Parse absent bounds without assigning a fake bound. Sema rejects incomplete
array elements and allocating incomplete local objects before any layout query;
complete arrays of pointers to incomplete arrays are valid. Parameter adjustment
still removes one outer array layer; pointers to unknown arrays are not adjusted
again. Casts may explicitly name compatible complete/unknown array pointers.
Dereferencing such a pointer yields an incomplete array lvalue: address-of and
one-level element decay are valid and need no array load or fabricated size.
Thus (*p)[i] can address a complete element, whereas p[i], p+0 and pointer
subtraction require a complete pointed-to object and must be diagnosed before
stride/size queries. Test both subtraction operands, not just the left. Keep
compatible equality/ordering and scalar truth under their existing contracts.

Unknown/known array compatibility is not transitive. A function redeclaration
must form a composite type, recursively retaining known array bounds through
pointers and parameter lists. Otherwise unknown -> [3] -> [4] would incorrectly
pass by comparing every declaration only with the first unknown shape. Add an
explicit type_composite helper for compatible implemented integer/pointer/array/
function types; return arena-owned merged derived nodes without mutating prior
syntax caches. Update the symbol's visible signature after each successful
compatible redeclaration. Definition parameter locals keep their own declared
shape, so an incomplete definition parameter cannot gain arithmetic merely from
an earlier complete prototype. Prior call expressions retain their typed argument
nodes; pointer representation/ABI does not change when a later declaration
contributes a known bound.

Tests: every primitive/pointer leaf, unknown-array dereference/decay, address-of
cancellation, compatible casts/assignment, arrays of unknown-row pointers and
both host linkage directions including eight pointer arguments. Inspect object/
complete predicates, unknown cache/known composite separation, and three-way
redeclaration conflicts at nested pointer/array depths. Cover both-order mixed
complete/incomplete subtraction, zero offset/subscript rejection, incomplete
locals/elements, explicit zero and existing exact resource/depth limits. Keep
local [] unsupported as an allocation constraint, not a parser-only accident.
Full regression/QBE/reference and both hosts, bounded sanitized fuzz, isolated
matrices and exact-source CI remain required. No unknown object is allocated;
no uninitialized, invalid or arbitrary fuzz-generated C program executes.
