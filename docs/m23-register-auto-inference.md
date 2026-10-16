# M23e2: inferred auto with register storage

Design recorded before implementation after fully locally validated and pushed
9a1044b (M23e1). Frozen primary/isolated manifests matched and the remote branch
matched HEAD after push. M23e1 CI is independently pending, not implied by local
passes. Research probes were compile-only and no probe programs executed.

## Standard and scope

N3096 6.7.1p2 allows auto with another storage class except typedef. Constraint
6.7.1p4 REQUIRES inference when auto accompanies another storage class (or occurs
at file scope). Therefore `auto register int x=42` is a constraint violation,
NOT an old-C valid explicit-auto declaration; GCC 14 and Clang 18 both reject it.
6.7.1p14 ignores auto only for storage duration/linkage, not that constraint.
Both modern hosts accept inferred `register auto x=42` / `auto register x=42`.

Extend ONLY M23e1's initialized single-identifier block/for subset with register,
in either order and with existing const qualifier positions. Keep inferred name
unavailability, converted initializer type, one-pass analysis and scalar limits.
Address-of applies to the new real register object's identity, including in
queries. Ordinary inferred copies inherit no storage hint. Pointer referents
remain addressable. Inferred arrays/functions still decay to pointers; there is
no new array object inference and register-array decay remains refused.
Globals, other storage classes, register parameters, attributes/constexpr/VM,
visible-typedef ambiguities and inferred derived declarators remain unsupported.
Multiple underspecified identifiers/prior same-scope names remain UB refusals,
not required native diagnostics; none execute.

## Parser representation and interactions

Replace the optional single storage-token output with a small concrete private
parse.c result containing two tokens: one ordinary storage class (typedef or
register) and an independent optional auto token. The tokens preserve exact
locations and duplicate diagnostics. Do not add a semantic type/storage bit,
synthetic language token, whole-token replay, optional flags in every AST type,
or generalized extensibility framework.

NULL result still refuses ALL storage classes in type names/parameters exactly
as before. The scanner allows one auto plus one register, rejects duplicates
and auto/typedef or register/typedef mixtures, and diagnoses auto+register when
any explicit type is present, including alias/query/void bases. Only no-type
with auto constructs the existing inferred syntax. Ordinary register without a
type is still an error, not implicit inference. Missing auto-type syntax does
not expose an old typedef disambiguation fallback.

Update callers together: local/consumed-alias tails use the ordinary token for
typedef-vs-object dispatch and is_register; independent auto presence retains
the explicit-auto direct-function check. External classes remain unsupported
before symbol registration. All explicit auto declarations and shared comma
bases retain their old grammar/behavior. Parameter/prototype lifetimes and
ephemeral objects remain unchanged and storage-free.

No sema/type/QBE change should be needed: M23e1 reserves and completes the same
local, preserving its is_register flag; existing unary address checks resolve
that exact declaration. Ordinary copy types carry no hint. Initializers analyze
once and budgets count one real local, not one per specifier.

## Acceptance and full validation

Original-source modern comparisons for both orders, qualifier positions, all
primitive ranks/full-width values, pointer/function/string/array-decay initializers,
queries and ordinary copies; initializer side effects once, nested/for capture
and restoration. Only defined curated positive C runs. Independently probe
inference support; legacy native linkage is not source inference agreement.

Compile-only direct address constraints including sizeof/typeof and pointer
object versus pointee identity; explicit-type auto/register constraints on
primitive/alias/query/void bases; duplicate/typedef mixtures; unavailable-name
initializers; missing/derived/multiple declarations and retained subset limits.
Never count UB acceptance as a missing native constraint.

AST checks require concrete inferred syntax, true register flag only on the
source object, no copied flag, cached completed types, one load/decay/string
occurrence and exact local/list identity. Exact 256/257 locals including named
spills, 4096 items, 1 MiB storage, 64 declarator grouping and 128 expanded-typedef
depth. Twenty-four both-direction mixed-stack ABI arrangements per host with
inferred register kcc objects and ordinary native helpers/drivers.

Replace the four old inferred-combination subset refusals in auto_explicit and
auto_inference with explicit new positive coverage, not test deletion without
replacement. Keep explicit-type combined forms as native constraint negatives.
Add focused suite to both Makefile recipes and both-host targeted sanitizers,
plus compile/lex fuzz seeds. Serial helpers before parallel frozen full normal/
QBE modern/legacy/sanitizer/fuzz runs. Verify all source manifests, update current
handoff/coverage/contracts/limits/ledger/version, commit/push with identity and
credential scan, then check exact CI independently. No full C23 claim.

## Completion evidence

Full make test passed with GCC 11.5/GCC 14.2.1/Clang 18.1.8 as native
comparison hosts; normal C11 helpers were built with GCC 11. Full make
test-codegen passed with QBE 1.2 and both modern native hosts. GCC 11 and Clang
15 ASan/UBSan lexer/sema plus 22 targeted suites passed; register-inference,
ordinary inference and binding suites also passed with Clang 18 as native oracle.
Normal helpers were built serially before parallel validation. Frozen primary
and isolated source/test/Makefile manifests matched before/after. Bounded
compile-only sanitized fuzz passed 9,040 lexer / 30,885 pipeline inputs in
26 seconds each. No invalid curated or generated C executed. Logs/manifests
/data/tools/m23e2-*, isolated trees /data/validation-m23e2/{gcc,clang}.

The previous M23e1 sanitized compiler and frozen M23e2 compiler have identical
return codes/stdout/stderr on all 150 pre-existing compile corpus files
(118 accepted / 32 rejected), compiled only, excluding the new register seed.

Focused register-inference suite: 52 original C23 programs passed through kcc/
QBE; GCC 14 and Clang 18 strictly agree on all 52, with no original rewriting or
new gap exceptions. Thirty-four native constraint rejections include twelve
unavailable-name barriers, direct/query register addresses, const modification,
explicit-type combined storage, duplicate/typedef mixtures and no implicit-int
fallback. Three UB refusals and nine subset refusals remain compile-only. Legacy
GCC 11/Clang 15 have exact independently probed inference absence, not native
inference agreements. All four hosts pass 24 both-direction mixed-stack primitive
ABI arrangements using inferred register kcc code and ordinary native helpers/
drivers; linkage is not a claim of legacy inferred-source support.

Ordinary inference, explicit auto, binding and both register suites reran on all
four hosts. Their original native gap counts remain unchanged. Four former
combined-inference subset refusals in auto_explicit/auto_inference were replaced
by explicit new positive coverage; their subset counts are now three/eleven.
AST checks prove inferred syntax/cache identity, register flags only on source
objects, const removal in ordinary copies, captured loads, one static string,
pointer sharing and four exact real slots/reverse-list entries. Exact 256/257
locals including 128 named spills, 4096/4097 items, 1 MiB/overflow storage,
64/65 grouping and 128/129 expanded-typedef boundaries pass. One register object
allocates one slot regardless of two specifiers; aliases/prototypes still none.

M23e0 CI run 38979609085 completed/success, all three jobs green.
M23e1 CI run 38982126026 is pending; no remote pass is claimed.
New M23e2 exact-commit CI is pending until checked after push.
