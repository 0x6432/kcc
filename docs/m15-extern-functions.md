# M15d1: explicit extern spelling for file-scope functions

Design recorded before implementation against fully validated, documented and
pushed M15c1 checkpoint 15abaaf5bd687385fe21265b43024238e2f11605. The worktree
was clean and HEAD matched origin/development. M23e3 CI completed successfully
in all three jobs; M15c1 exact-commit CI is independently pending.

## Scope and normative basis

N3096 6.2.2p5 already gives a function declared with no storage class the linkage
it would have with extern; all currently supported function symbols are external.
Support explicit extern for single file-scope function prototypes and definitions,
at any declaration-specifier position, including alias/query-derived functions,
callbacks, register parameters, recursion and compatible later declarations.
This is an explicit bounded storage-class milestone, NOT globals or new linkage.
No block-scope function declarations, file-scope objects/tentative definitions,
static/internal linkage, inline, thread storage, multiple function declarators,
or inferred extern objects. Existing unsupported forms remain explicit refusals.

N3096 6.7.1p2 allows auto with extern, unlike typedef. Do NOT mislabel inferred
extern auto objects as a forbidden storage combination: they are outside the
current file/block-object subset. Explicitly typed extern+auto violates p4's
inference requirement and can use the existing combined-auto constraint. Reject
parameter extern under 6.7.6.3p2 and type-name extern; block extern remains a
subset refusal, not a required native diagnostic. No invalid curated C executes.

## Component interactions

lex.h/lex.c: one token_extern, converted from preprocessing identifiers only at
the existing final keyword conversion. Remove extern from unsupported keywords;
add spelling/name mapping, demand peek/keyword-macro/raw-preprocessing tests.
No preprocessing directive engine or full token-vector change.

parse.c: declaration starts and shared storage scanner recognize extern. Reuse
private declaration_head.keyword; retain independent auto token. Duplicate extern
is a constraint. Reject mutually exclusive ordinary classes (typedef/register/
extern) in either order; auto+typedef remains forbidden, auto+register/extern only
permits inferred syntax. Existing auto/register diagnostics/counts stay precise.
A NULL head forbids outer type-name extern. Parameter context permits only
register and diagnoses extern immediately before later type-query parsing. Local
context explicitly refuses block-scope extern as unsupported before publication,
including the consumed-alias start path. Do not accidentally turn it into a real
local/spill. Nested parameter contexts remain independent of the outer class.
External parsing accepts extern and follows the unchanged concrete direct or
query/alias-derived function path; objects stay refused when classified.

No new public AST flag/type qualifier/linkage enum is needed merely to distinguish
extern from the already identical implicit external function semantics. The
written class is checked in the declaration head, just as explicit automatic
storage need not be retained. Future static/linkage work must design provenance
then, not claim support here. Existing function_symbol identity/composite types,
source-order visibility and captured function pointers stay unchanged. Prototypes
allocate no runtime storage. QBE keeps existing exported definitions and ordinary
unresolved external calls; no alias export/function duplication or backend change.

## Validation

Unchanged standard originals all four hosts for every primitive return/parameter
rank and full-width values, class/specifier order, compatible implicit/explicit
prototypes and definitions both ways, mutual/direct recursion, void functions,
function pointer calls/address identity, typedef-derived function declarations,
nested callbacks, const and adjusted array/function parameters with register
provenance. Modern-only original query/nullptr/bool cases use exact independent
keyword absence probes on legacy hosts; no source rewriting or syntax failure
counted as agreement. Keyword-named macro conversion is tested directly; do not
mistake optional native keyword-macro warnings for a language constraint.

Constraint compile-only cases: duplicate/mixed classes both orders, parameter
extern, type-name extern and forbidden explicit extern+auto combinations; function
compatibility/redefinition, hidden aliases/functions, undeclared-before-prototype
and source scopes. Subset refusals: local extern declarations, objects/globals,
inferred extern objects, comma-separated function declarations, static/inline.
Native accepts subset forms where permitted, but no fake native rejection claim.

AST invariants: explicit/implicit declarations share one canonical function symbol,
composite signatures retain known bounds, written alias/query type caches are not
mutated, captured pointers bind exact symbol, parameter register belongs to each
own definition, no prototype/alias runtime locals or duplicate IL definitions.
Exact 512/513 external declarations, 256/257 functions, 128/129 parameters,
256/257 locals including named spills, 1 MiB storage, 4096 block items, 64 nested
declarators/128 expanded types and existing limits. Generated boundaries compile
only. Twenty-four both-direction mixed-stack primitive arrangements per host plus
row/callback cross-object linkage, inspect nm/object exports for external symbols.

Add focused suite to both Makefile recipes, corpus and both-host targeted sanitizer
matrix. Build helpers serially, then freeze source/tests/Makefile for full normal
GCC11/GCC14/Clang18 native-oracle and modern QBE runs, both-host ASan/UBSan and
bounded compile-only lexer/pipeline fuzz. Compare unaffected compile corpus with
M15c1 binary byte-for-byte; exact manifest matching before/after. Completion docs
are drafted outside while frozen and applied only after all validation passes.
Commit/push promptly and independently inspect exact-commit CI. No full C23 claim.

## Pre-freeze review

Four-host original-source focus passed: 46 standard + 8 C23 positives (54 modern
strict native agreements / 46 legacy applicable agreements), 21 modern / 15
legacy constraints, 12 explicit subset refusals compiled only. Exact independent
legacy typeof keyword absence is not a source agreement. All four hosts passed
24 both-direction mixed-stack primitive and two adjusted row/callback ABI
arrangements; nm checks confirm exported definitions and unresolved references.
Shared register-auto/register-parameter/typedef-placement/queried-function suites
also passed on all four hosts with prior native gap counts kept separate.

Only lex.h/lex.c/parse.c/main.c implementation changes are needed; no public AST,
sema/type/QBE implementation changes. AST tests verify exact canonical symbol
identity through alias/direct/query/implicit declarations, immutable unknown
array bound in old alias/source caches versus known composite bound three,
register definition provenance, ordinary definition addressability, function
capture identity and real-slot reverse lists without prototype storage.

Initial outside-tree implementation stopped on a local-tail anchor before parser
writes (the existing NULL-base guard was part of that tail). The already-applied
lexer changes were inspected and preserved; only the unapplied remainder was
completed with the correct guard. No duplicate application or reset. New test
expected-diagnostic wording was corrected to the existing undeclared-call
message. All of this precedes the final freeze; preliminary results are not
substitutes for full final-source validation. Completion evidence follows only
after that exact frozen full normal/QBE/sanitizer/fuzz matrix finishes.

## Completion evidence

Full make test passed with GCC 11.5/GCC 14.2.1/Clang 18.1.8 native comparison
hosts; compiler/normal C11 helpers were built serially with GCC 11 before parallel
validation. Full QBE 1.2 make test-codegen passed with both modern native hosts.
Both GCC 11/Clang 15 ASan/UBSan lex/raw-pp/sema plus 25 targeted suites passed in
isolated trees; extern, register-parameter, inferred-typedef, register-auto, auto
and binding suites also passed with Clang 18 as native oracle. Frozen 381-file
primary/isolated source/test/Makefile manifests matched before/after. Bounded
sanitized compile-only fuzz: 13,934 lexer / 45,071 pipeline inputs, 26 seconds
each. No invalid curated/generated C executed. Logs/manifests /data/tools/m15d1-*,
isolated trees /data/validation-m15d1/{gcc,clang}. Prior 15abaaf sanitized compiler
and this frozen compiler have identical return codes/stdout/stderr on 153 old
compile corpus files (121 accepted / 32 rejected), excluding the new extern seed.

Focused four-host suite: 46 unchanged standard + 8 C23 originals. Both modern
hosts strictly agree on all 54 and reject 21 required constraints; legacy hosts
agree on 46 applicable originals and reject 15 constraints, with exact independent
C23 keyword absence not counted as agreement. Twelve subset probes compile only,
including file-scope objects, inferred extern objects, local extern, multiple
function declarators and static/inline forms. No claim that these valid but
unsupported C forms require native diagnostics. All hosts pass 24 both-direction
mixed-stack/full-width primitive ABI arrangements plus two row/callback
arrangements. QBE/object nm inspection verifies defined functions exported as T
and unresolved external references as U, without duplicate prototype exports.

AST checks verify alias/direct/query/implicit declarations share one canonical
function symbol while source alias/unknown-array-bound caches stay immutable and
the composite retains known bound three. Function designators/decays capture that
exact symbol; own register definition and ordinary later definition keep correct
spill identity. Prototypes/aliases add no runtime storage or IL definitions.
Exact 512/513 external declarations, 256/257 functions, 128/129 parameters,
256/257 locals including 128 spills, 1 MiB storage, 4096 items, shared 64 nested
declarator and 128 expanded-type budgets pass; generated boundaries compile only.
Demand keyword conversion and raw preprocessing identifiers have focused C tests.
Shared register-auto, register-parameter, typedef-placement and queried-function
suites reran on all four hosts with existing native gap classifications unchanged.

M15c1 exact-commit CI run 39009008993 is pending; no remote pass claimed.
New M15d1 exact-commit CI is pending until independently checked after push.
Local validation never implies a remote pass.
