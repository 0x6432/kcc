# M13a: pointer type syntax and declaration values (design before implementation)

Follow the existing concrete-node architecture rather than encoding pointers as
an integer rank or a flat count on a declaration. Add an AST type-syntax common
header, concrete integer-type syntax and concrete pointer-type syntax (referent
child), each with source location. Locals, parameters, function return syntax and
cast target syntax all reference these nodes instead of a bare specifier enum.
Sema resolves/caches syntax to types; parser syntax never holds a semantic pointer
before analysis. The integer specifier enum remains the base syntax's spelling
classification, not a replacement for the semantic type graph.

Restricted grammar: type-name = integer-type { '*' }; named declarators append
one identifier, optional names remain allowed in prototypes, and function syntax
remains the existing name '(' parameter-list ')'. One pointer layer is one syntax
node, maximum 64 layers, checked before allocation. Stars wrap the base type in
source order. Full parenthesized/function/array declarators, qualifiers and void
remain their own later increments, explicitly rejected rather than guessed.

Add concrete semantic pointer_type with common struct type first and referent
child. Object pointers are 64-bit LP64 values, size/alignment eight. Compatibility
is recursive through referents; distinct integer referents remain distinct.
Resolve a syntax node once into the same arena to avoid re-allocating parameter
pointer types when synthesizing their local storage. Keep all syntax/type lifetime
ownership explicit and bounded. No custom typedefs or union type payload.

M13a accepts pointer objects, fixed parameters/returns, compatible assignment/
initialization/casts, passing/returning pointer values and scalar truth (including
pointer-to-_Bool). No address-of/dereference yet: those are M13b, where lvalue
address lowering replaces local-slot-only access. Pointer arithmetic/comparison,
integer/pointer casts, null pointer constants, void/function pointers and arrays
are explicit later work. In particular, do not accept integer zero by pretending
all integers convert to pointers. Dedicated constraint diagnostics must prevent
integer promotion/opcode helpers from seeing a pointer.

Generalize backend scalar width/memory/ABI selection for pointers without routing
them through integer rank/signedness. Pointers use l/loadl/storel/alloc8 and l ABI;
canonical sub-word normalization remains integer-only. Integer conversion uses
existing rank rules, pointer conversion only compatible types or _Bool. Unary !,
logical expressions and control-flow conditions accept either scalar category;
unary arithmetic and binary arithmetic/comparison remain integer-only for now.
Main must still return int, checked using its resolved return type.

Tests must retain every integer AST/type/depth behavior after syntax migration,
check syntax/referent identity and exact 64/65 depth bounds, reject incompatible
referents and pointer/integer operations before codegen, and inspect l ABI/storage.
Host-driven separate-object tests supply real live object pointers to kcc identity/
forwarding functions and receive the identical address back, both GCC and Clang,
including eight mixed arguments, pointer-to-pointer and bool truth. Do not execute
uninitialized pointers or fabricate addresses to make standalone examples work.
QBE/reference integer regressions, both hosts/sanitizers, fuzz/CI remain required.
