# M14k1: semantic normalization of query-derived void parameter lists

Design before implementation. N3096 6.7.6.3p9 permits a single unnamed void
parameter to mean no parameters; a typeof-derived void must work just like the
existing literal (void) spelling. Keep the established parser fast path for sole
literal unqualified void, but do not make the parser evaluate typeof syntax.
Preserve the query-derived ast_parameter and its type syntax as written; do not
manufacture a runtime parameter, rewrite the syntax list or invent a name.

Add an explicit semantic is_void_marker annotation on ast_parameter. During
function-type resolution only a sole unnamed, unqualified resolved void is this
marker. Set its checked type and annotation; omit it from the semantic signature
and prototype bindings. Named void, qualified void and void mixed with real
parameters remain diagnosed. Parsed parameter_count continues to describe written
parameter nodes; function_type.parameter_count describes actual ABI parameters.
Update assertions to state this distinction rather than changing counts silently.

Move the driver's semantic zero-argument main check after type resolution, using
the semantic signature count. The function-definition backend must skip the
marker in both header and spill-index traversals, before any void width query.
The marker introduces no runtime local. Calls, callbacks, prototype compatibility,
sizeof/typeof of function pointers and both-direction zero-argument host ABI must
all observe the semantic zero-parameter type. Existing literal void, empty lists
and unnamed real C23 parameters retain their old representation and ABI.

Cover typeof(void), typeof_unqual(const void) and typeof((void)0), direct/indirect
calls, main, return types, nested signatures, prototypes versus definitions and
source/marker/cache identity. Keep bare query-derived function declarations,
block-scope function declarations, typedefs, storage classes, variadics and VM
normalization explicitly deferred. Add exact constraints, fuzz seeds, full normal/
QBE, both-host targeted ASan/UBSan, reference/ABI and bounded compile-only fuzz.
Commit/push and update limits/contracts/handoff only after actual validation.
