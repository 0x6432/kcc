# M14i: explicit object and function pointer casts (design)

Reference: public C23 working draft N3096, 6.3.2.3p7/p8 and 6.5.4:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

Separate explicit cast constraints from assignment-like conversion constraints.
Permit an explicit cast between pointers to object types, including incomplete
void/array types, and separately between pointers to function types. Do not make
incompatible object/function pointers implicitly assignable, comparable, valid
arguments/returns or compatible declarations. In particular, int ** to void **
becomes a valid explicit pointer cast, not an implicit value conversion. No
object/function pointer bridge, integer/pointer mapping, null constants or
qualifiers are added by this milestone.

Keep a small check_cast helper in sema: classify both immediate referents when
both source and target are pointers. Accept object/object or function/function;
otherwise retain the existing conversion constraint path and diagnostics. A
non-pointer source or target follows the existing scalar rules. A cast to void
keeps its existing effect-only special case. The separate concrete cast AST
retains both operand and target syntax/cache, source location and exact typed
depth. No general implicit-conversion predicate is weakened.

Existing QBE pointer-width copies suffice; there is no integer reinterpretation,
load or ABI change. Do not fake a dereference with an incompatible type. Object
cast alignment and effective-type rules remain the source program's runtime
obligations, not a reason to accept implicit conversions. Character pointers may
inspect and modify an object's representation, so use defined unsigned-character
accesses to test this behavior on the explicit little-endian x86-64 target.

Function pointers may be converted to another function type and back, preserving
equality. Calling through an incompatible function type is undefined, so runtime
tests must cast back to the actual function type before calling. A cast is not a
function adapter and must not change the call signature or parameter adjustment.
The compiler does not attempt whole-program detection of incompatible indirect
runtime targets; sema continues typing each call against its visible signature.

Tests: all primitive object leaves round-trip through character pointers; arrays,
incomplete arrays, pointer-to-pointer objects and nested pointers round-trip
without aliasing misuse. Character-byte access checks representation rather than
relying only on pointer equality. Function pointers round-trip through distinct
return/parameter signatures, then invoke only their original signature. Verify
both host ABI linkage directions, mixed stack callbacks, once-only pointer
producers, typed cast nodes/cache/depth and host-provided null round trips.
Migrate only former explicit-cast rejections; preserve implicit incompatibility,
function/object bridges, mixed comparisons, null-constant and incomplete-stride
constraints. Full regressions, GCC/Clang host/QBE runs, bounded sanitizer fuzz,
isolated matrices and exact-source CI remain required.
