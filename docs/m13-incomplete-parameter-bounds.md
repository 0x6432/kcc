# M13k: omitted outer array parameter bounds (design before implementation)

Allow the outermost parameter array suffix to omit its bound: int a[] and
int a[][3]. Local arrays still require every positive literal bound; inner
parameter dimensions remain complete literal bounds. General expression/VLA/
static/qualifier forms and full pointer-to-array declarators remain later work.
Reuse one suffix parser with an explicit parameter-context flag.

AST array syntax gets an explicit has_bound flag; a present zero token remains
invalid, not confused with omission. Add a separate semantic incomplete-array
constructor, reserving array_type.count == 0 for unknown cardinality (never a
zero-length array). Elements must still be complete. Complete-object queries
exclude this type; size/alignment APIs retain their complete-type precondition.
Array compatibility permits an unknown versus known outer count when element
types are compatible. Keep positive complete-array construction invariants.

Resolve and cache the actual declared incomplete array, then use M13j's ordinary
one-level parameter adjustment. Its effective pointer/spill type is complete,
so no incomplete array object is allocated or assigned a fake size. Do not
replace the syntax cache with a pointer or arbitrary bound one. Unknown outer
metadata does not weaken inner row-shape compatibility. The parameter remains
a modifiable pointer object inside the function.

This increment does not expose incomplete local/global objects or general
pointers-to-incomplete arrays. The current pointer constructor still requires a
complete referent; adjusted parameter element types satisfy that invariant.
M14's full declarators will need explicit object-versus-complete predicates and
pointer arithmetic constraints before broadening that constructor. Do not call
this complete support for incomplete C types or infer size zero from count zero.

Test all scalar/pointer leaves, named/unnamed mixed []/[literal] prototypes,
matrices and compatible row shapes, string/array decay, pointer rebinding and both
host ABI directions including stack arguments. Add declared-incomplete versus
effective-pointer cache units, compatibility and complete-object predicates,
explicit zero and omitted-inner rejection, and pointer-sized storage budgets.
Replace earlier now-valid parameter [] rejection fixtures with incomplete inner
bounds or unsupported static forms, retaining local [] rejection coverage.
Run all regressions, both hosts, bounded sanitizer fuzz, isolated matrices and
exact-source CI. Do not execute uninitialized or out-of-bounds array accesses.
