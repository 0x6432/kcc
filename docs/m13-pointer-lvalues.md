# M13b: address-of and indirection (design before implementation)

Add concrete ast_address_expression and ast_indirection_expression, not a new
meaning hidden in integer unary opcode selection. Prefix grammar accepts '&'
cast-expression and '*' cast-expression at existing prefix binding power; binary
& and * keep their Pratt entries. BNF comments and one-token cache remain intact.

Sema analyzes & operand without lvalue-to-rvalue conversion and requires an object
lvalue, producing pointer-to-its-type. Indirection analyzes its operand as a value,
requires an implemented object-pointer type and yields a modifiable lvalue of the
referent type. Existing value-context handling inserts ast_load nodes around
indirection just as around names. Both inserted loads and pointer-expression
nodes count toward checked typed depth. Reject &rvalue, *integer and unsupported
function designators before codegen. No null-constant/integer-pointer shortcut.

Replace named-slot-only assignment/load lowering with codegen_address(): names
produce an l temporary copying their %v slot address; indirection evaluates its
pointer operand once and returns that address temporary. Value loads and stores
then select the referent's byte/halfword/word/long operation. Initializer/parameter
spills can keep known slots; general expression lvalues cannot. & and * do not
perform an unnecessary pointee load: &*E evaluates E once without touching the
pointee, valid even for a null pointer supplied by a host caller. Dereferencing
null/dangling pointers remains undefined and must never be executed by tests.

Assignment evaluates each address and value once, using C-permitted operand
order (do not create tests depending on unspecified relative order). Returned
assignment values already reflect declared-type conversion. Cover **pp, *&x,
&*p, mutations via calls and every integer/pointer object load/store size. Real
host pointer mutations in both directions must verify address identity, lifetime,
signed small loads, bool normalization and eight mixed arguments. Pointer-return
helpers with an explicit counter test once-only pointer-operand side effects.

Test exact semantic depth: 63 dereferences of a 63-layer parameter require 128
nodes including loads and pass; 64 layers/dereferences exceed typed depth and
must diagnose (syntax's separate 64-layer limit is unchanged). Run all integer/
pointer regressions, both hosts, sanitizer matrix and bounded fuzz without
executing arbitrary generated programs. Arithmetic/comparison, null constants,
arrays/strings and general declarators remain later increments.
