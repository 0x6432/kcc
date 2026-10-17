# M15c1: register parameter declarations and actual spill identity

Design recorded before implementation after fully validated, documented and
pushed M23e3 checkpoint 6a07c0c1c84ba4c4ce50d36cfe06088f81c83d6f. Local HEAD
matched remote development and the worktree was clean. M23e2 CI completed
successfully in all three jobs; new M23e3 CI is independently pending.

## Scope and normative distinctions

N3096 6.7.6.3p2 permits only register as a parameter storage-class specifier.
Support it at any declaration-specifier position, including alias/query bases,
in prototypes, definitions, nested function declarators, callbacks and unnamed
C23 definition parameters, for currently supported adjusted complete scalar
parameter types. No K&R declarations, variadics, VM/static/restrict array forms,
other parameter classes, aggregates, globals or real register allocation.

Register is not part of a function type or compatibility/composite signature.
6.7.6.3p12 ignores the storage hint outside an actual definition, but 6.5.3.2p1's
address constraint is phrased in terms of an object DECLARED WITH register.
Preserve written provenance on prototype-only objects for unevaluated later
parameter queries, without giving them runtime storage. Both native modern
hosts reject prototype typeof(&x) after register x, while accepting typeof(x).
This is a source-address restriction, NOT propagation of a hint through a type.

Actual named definition parameters get ordinary adjusted spill locals carrying
THAT declaration's written flag. A register prototype must not make a later
unadorned definition's parameter unaddressable; an unadorned prototype must not
strip a register definition's restriction. Unnamed parameters remain ABI members
without source binding or spill. Hints/flags never enter immutable type graphs.

Array/function parameter adjustment happens before binding, so register int a[2]
and register int g(int) are pointer OBJECTS, not register arrays/functions.
Indexing/decaying the ordinary array referent and calling g are valid. &a / &g
are forbidden, while &a[0] / &*a / &*g are not addresses of the register pointer.
Written array/function syntax caches must not be rewritten into pointer syntax.

Conservatively refuse direct/query-derived register void marker forms as an
explicit subset limit, NOT required native constraints: GCC 14 rejects the
unnamed register void case while Clang 18 accepts it; do not invent native
agreement or execute such probes. Plain (void), empty lists and query-derived
void markers keep their existing zero-slot normalization. Other old parameter
constraints/unsupported forms remain.

## Parser and concrete AST

Move/reuse the existing private enum declarator_context before shared specifier
scanning rather than adding a second context framework. Pass it through the
private specifier functions. NULL head still forbids all outer storage in type
names; parameter context with a non-NULL head accepts only register and rejects
auto/typedef immediately with existing context diagnostics, BEFORE parsing more
specifiers/type queries. Local/external/consumed-alias contexts remain unchanged.
Nested function types call the same parameter parser, not hidden global context.

parse_parameters scans specifiers with a local declaration_head and parameter
context, then uses existing derived-parameter parsing. Add is_register (default
false) to concrete ast_parameter; set it from that declaration's register token.
Do not discard a direct void node as a sole empty marker when register was
written: retain it for explicit semantic subset refusal. A plain void shortcut
and query-derived void handling remain as before. Names still publish only after
their COMPLETE declarator, before later parameters, respecting own-bound typedefs
and nested prototype lifetimes. No inferred auto enters parameter grammar.

## Semantic bindings and stage contracts

bind_prototype_parameter copies parameter.is_register onto the existing ephemeral
ast_local_declaration after adjusted type resolution. No parameter.local, local
slot/count/storage or function runtime list is allocated for prototypes. Queries
continue to capture these exact type-only objects, not later actual spill locals.

resolve_function_syntax rejects register+resolved-void before accepting a void
marker; otherwise existing adjustment and unqualified signature construction stay
unchanged. No register information enters function_parameter_type, composites,
canonical function symbols or alias/query type copies.

sema_function_body sets each named actual parameter.local.is_register from its
OWN definition ast_parameter, then uses the existing bind_local adjusted-type
wrapper. No new binding phase or initializer policy. Existing unary address
identity checks cover it; pointee addresses stay valid. Register local rejection
of function/array objects is not applied to adjusted pointer parameters.

No QBE/type/ABI interface change. Definition spills use ordinary slots with
existing const/width/sign rules; the hint does not promise physical registers.
Aliases/prototypes allocate no runtime storage, adjusted array/function syntax
retains its source cache, and all existing capture/scope/resource invariants stay.

## Validation

Four-host original-source positives for all primitive ranks/full-width values,
source class positions, const and ordinary typeof/inferred copies, pointer,
adjusted row arrays and function callbacks; unnamed parameters; compatible
register/unadorned prototypes/definitions in BOTH flag directions. Only defined
curated positive C executes. C23 typeof/auto examples use independent exact legacy
feature probes and do not count feature absence as agreement.

Nested callbacks/prototype scopes with different outer/inner parameter widths;
later queries see adjusted objects, own declarator bounds still see outer
aliases, body and block restoration preserve meanings. Capture before inner
shadowing keeps object/function identity. &source rejects even inside sizeof,
typeof, array bounds and nested callback queries; &pointee and &ordinary copied
objects work. Keep parameter auto/typedef and type-name register forbidden,
duplicate register and same-scope name conflicts rejected. Register void forms
stay compile-only subset refusals, not native constraint agreements or runtime.

AST assertions cover written flags/defaults, no flag in signatures/composites,
prototype-only flag/capture without runtime slots, actual named spill identity,
prototype-to-definition flag isolation, adjusted array/function source cache vs
pointer storage, const/copy flags and exact slots/reverse lists. Exact 128/129
parameters, 256/257 locals including spills, 1 MiB adjusted storage, 4096 items,
128 expanded-type/64 declarator and nested prototype boundaries. Generated C
boundaries compile only. Twenty-four both-direction mixed-stack primitive ABI
arrangements per host, plus fixed pointer/row/callback integration originals.

Replace the existing register-parameter subset refusals across affected suites
with explicit new positive/constraint coverage; retain NULL type-name register
refusals and auto parameter prohibition, and document exact count changes. Search
current tests/source before changing expectations; do not regenerate old fixtures.
Add focused suite to both Makefile recipes, both-host targeted sanitizers and
compile/lex corpus. Serial helpers before frozen full normal/QBE/both-host
sanitizer/bounded compile-only fuzz runs. Verify source manifests and unaffected
corpus equivalence; update version/design/handoff/coverage/contracts/limits/ledger,
commit/push promptly, check exact CI independently. Not full C23 conformance.

## Pre-freeze implementation review

The source changes reuse declarator_context in the shared scanner and one
ast_parameter.is_register provenance flag. Prototypes copy it onto ephemeral
objects; definitions copy their own flag onto adjusted spill locals. There are
no type/QBE changes. Register void forms are retained and explicitly refused
before void-marker normalization; plain/query-derived void behavior stays intact.

Four-host focus: 50 unchanged standard originals and 12 C23 originals; both
modern hosts strictly agree on all 62 programs and reject 29 constraints. Legacy
hosts agree on the 50 standard originals and reject 21 applicable constraints;
C23 keyword absence is independently and exactly probed, never counted as an
agreement. Eight subset probes compile only, including five register-void forms;
no claim of required native register-void rejection. All four hosts pass 24
both-direction mixed-width/full-value primitive-result ABI arrangements spanning
six registers and two stack arguments, plus two row/callback arrangements.

Exact parameter grouping is 63 accepted / 64 rejected inside the enclosing
function declarator: the shared budget is 64 TOTAL nested declarators, not 64
extra groups per parameter. Nested register function parameter lists also pass
63 layers and reject 64. The first test draft mistakenly put register after a
pointer star; kcc rejected it before execution. Its corrected original puts
storage in declaration-specifiers, and all native hosts agree unchanged. Tests
never execute refusal/boundary programs. AST assertions also test failed address
queries with captured register prototype identity but no symbol/type completion.

Removed five old register-parameter subset refusals only with replacement new
positive coverage: scalar-register suite 3 -> 0, array-register 6 -> 5, local
binding 3 -> 2. The register-auto parameter refusal is still invalid: moved it
from subset refusals to required constraints with the precise auto diagnostic;
modern native constraints 34 -> 35 and subset refusals 9 -> 8. All affected suites
and parameter/typedef scope regressions passed with all four native hosts.
Implementation/test drafts and compiler field-name assertion mistakes were fixed
before final freeze. No result from an earlier source snapshot substitutes for
final full validation.

## Completion evidence

Full make test passed with GCC 11.5, GCC 14.2.1 and Clang 18.1.8 as native
comparison hosts; normal compiler/helpers were built serially with GCC 11/C11.
Full QBE 1.2 make test-codegen passed with both modern native hosts. GCC 11 and
Clang 15 ASan/UBSan lexer/sema plus 24 targeted suites passed in isolated trees;
parameter, inferred-typedef, register-auto, auto and binding suites also passed
with Clang 18 as native oracle. Frozen 378-file primary/isolated source/test/
Makefile manifests matched before/after. Bounded sanitized compile-only fuzz:
13,801 lexer / 43,173 pipeline inputs, 26 seconds each. No invalid curated or
generated C executed. Logs/manifests /data/tools/m15c1-*, isolated trees
/data/validation-m15c1/{gcc,clang}. The prior 6a07c0c sanitized compiler and this
frozen compiler have byte-identical return codes/stdout/stderr on all 152 old
compile corpus files (120 accepted / 32 rejected), excluding the new seed.

Focused final four-host suite: 50 standard + 12 C23 unchanged originals;
GCC 14/Clang 18 agree on all 62 and reject 29 required constraints. GCC 11/Clang 15
agree on all 50 applicable originals and reject 21 constraints; exact independent
C23 keyword absence is NOT an agreement. All hosts pass 24 both-direction
mixed-width/full-value primitive-result ABI arrangements spanning six registers
and two stack arguments, plus two row/callback arrangements. Eight subset forms
compile only; five register-void forms are explicit conservative refusals, NOT
required native constraints (GCC 14 and Clang 18 differ on unnamed register void).

AST checks prove prototype type-only register identity without parameter.local,
ordinary/register prototype-to-definition isolation both ways, immutable declared
array/function versus adjusted pointer types and source caches, exact real spill
slots/reverse lists, ordinary typeof copies without register flags, independent
nested callback/outer query captures and failed address queries without completed
function type/symbol/IL. Boundaries: 128/129 parameters, 256/257 locals including
128 named spills, unnamed parameters not consuming locals, 1 MiB/overflow storage,
4096/4097 items, 63/64 grouped parameter and nested function layers under the
SHARED total 64 declarator nesting limit, and 128/129 expanded types. Generated
boundary and invalid programs compile only, never execute.

Five obsolete parameter subset refusals were replaced with positive coverage:
register-scalars 3 -> 0, register-arrays 6 -> 5, binding-phases 3 -> 2. The old
register-auto parameter refusal remains rejected with the precise auto diagnostic;
it moved to required constraints (modern 34 -> 35, subset 9 -> 8). All affected
suites and parameter/typedef scope regressions reran on all four native hosts;
previous native keyword/macro/for-typedef gap counts remain separately classified.

M23e3 exact-commit CI run 38988250769 completed/success with all three jobs green.
M15c1 exact-commit CI is pending until independently checked after push. Local
validation never implies a remote pass.
