# M14f: function designators, pointers and indirect fixed calls (design)

Build on M14e's concrete fixed-function syntax. Pointer construction may refer
to an object OR function, while object/complete-object predicates continue to
exclude functions. Functions are not object lvalues, have no object layout and
cannot receive array/object loads or arithmetic strides. Keep fixed implemented
scalar return/parameter ABIs, compatible pointer conversions and existing target
limits; void types, variadics, qualifiers and typedefs remain later work.

Resolve expression names against locals first, then declared function symbols.
For a function, replace the parsed name through its slot with a new concrete
ast_function_designator_expression holding the symbol and invocation location;
never reinterpret ast_name_expression storage or invent a local object binding.
In ordinary value contexts insert a concrete ast_function_decay_expression with
a pointer-to-function type, counting its node in typed depth. A named function
and pointer indirection to a function are designators, not lvalues. Unary &
accepts a function designator without decay; * accepts a pointer to a function
and yields a designator. Existing &* cancellation must evaluate the pointer once
and must not dereference a host-provided null. Adjust declared function-type
parameters once to effective function pointers; retain declared syntax caches.

Generalize calls to analyze the callee once in value context, require a function
pointer, and snapshot its function_type signature for argument constraints and
result typing. Keep an optional direct function symbol only for a pure recognized
function-designator decay; this preserves direct QBE calls/diagnostics without
special-casing semantic argument rules. Undeclared bare-name calls retain their
specific diagnostic. Local function-pointer objects may shadow a function name;
local nonfunction calls still reject. Argument count/conversions and complete
callee/argument typed depth remain checked, including skipped/unreachable source.
Do not omit decay nodes just to preserve an obsolete direct-call depth boundary.

QBE address emission accepts an object lvalue or function designator. A named
designator copies $function into a long temporary; function indirection forwards
the evaluated pointer. Function decay uses that address, never a memory load.
Direct calls retain call $name; indirect calls evaluate their target temporary
once before arguments, finish every argument's IL, then emit call %tN. Existing
scalar return canonicalization remains mandatory for indirect narrow returns.
Only the pure direct designator can skip materializing an unused address copy.
Arrays of function pointers and functions returning function pointers then use
ordinary storage/array decay/call paths, not special backend stubs.

Compatible function pointer ==/!= and scalar truth are supported. Relational
comparison requires object referents and rejects function pointers. Existing
complete-object checks reject function pointer offsets/subscripts/difference,
even +0 or p-p. Reject object/function pointer conversions, incompatible fixed
signatures and integer/null-pointer source conversions under current limitations.
No function size, alignment or object storage query is permitted.

Tests: named function decay/address, * and &* cancellation, compatible casts,
function-typed parameter adjustment, local callback shadows, arrays of callbacks,
callbacks returned from factories, recursion and once-only computed call targets.
Exercise every integer/pointer return type with both host linkage directions,
mixed eight-argument callbacks and dirty-upper-bit narrow callback returns.
Inspect exact designator/decay/signature/type-cache ASTs and positional parameter
spills. Migrate former parser/feature-only callback negatives into positive
coverage or real mismatched-signature/object/constraint cases. Recompute exact
typed depth fixtures accounting for newly explicit callee decay; never raise the
128 limit to hide a regression. Keep parser nesting/layer/resource limits, full
regression/QBE/reference, both hosts, bounded sanitized fuzz, isolated matrices
and exact-source CI. Never execute null calls, unrelated pointer arithmetic,
invalid signatures, uninitialized callbacks or arbitrary generated C programs.
