# M15e1: file-scope internal-linkage functions and use provenance

Design recorded before implementation against fully validated, documented and
pushed M15d2 checkpoint 267a27f8874b5d4127a477685858aeeb99a74e61. Local HEAD
matched remote development and the worktree was clean. M15c1/M15d1 exact CI
runs completed successfully in all three jobs; new M15d2 CI is independently
pending. No static objects or block storage implied.

## Scope and normative decisions

Support static on file-scope function prototypes/definitions and prototype lists,
including alias/query bases, callbacks, adjusted/register parameters, direct and
mutual recursion and internal function pointers crossing an exported wrapper ABI.
N3096 6.2.2p3 makes file-scope static functions internal. Under p4/p5 a later
extern OR unadorned function declaration inherits a visible prior internal linkage;
a later ordinary definition must remain internal. Repeated static is compatible.
A static declaration after a prior external one produces both linkages under p7:
conservatively refuse as UB, not a required-native-constraint claim. Never execute
those probes. Type compatibility/ordinary namespace constraints remain separate.

No static globals/local objects, block functions, inline/thread storage, inferred
static objects or physical allocation policy. Auto+static is allowed storage
grammar under 6.7.1p2, but p4 requires inference when combined: typed combinations
are constraints; inferred static objects remain a subset refusal, not a forbidden
combination. Parameter/type-name static is forbidden. Array [static N] parameter
forms remain unsupported. Main is required to be an external Linux entry point;
conservatively refuse static main explicitly without claiming a generic native
constraint if host behavior differs.

## Source provenance, canonical identity and QBE

lex.h/lex.c add token_static at final pp identifier conversion, preserving raw
identifiers/macros/demand peeks. Remove only static from unsupported keyword list.
Shared scanner uses the existing ordinary storage token plus independent auto;
include static in duplicate/conflict/typed-combined-auto checks. Local static
refuses before publication/storage in shared local tail, including alias/inferred
starts. External prototype/definition/list parsing carries the written static
bool to each existing concrete ast_function_declaration or unresolved
ast_external_type_declaration; nested function type/parameter nodes do NOT inherit
it. Concrete AST default false means extern/unadorned are equivalent here, not a
new type qualifier or a storage enum for hypothetical object implementations.

Add canonical function_symbol.is_internal and is_referenced flags in sema.h.
register_function receives the written static flag; a newly registered symbol
sets internal from it. Existing internal symbols stay internal through later
extern/unadorned declarations. Existing external + written static refuses the
mixed-linkage UB before mutation. Keep type compatibility/composites/captured
symbol identity unchanged. Actual parameter flags come only from own definitions.
No flag in immutable function types, typedefs, typeof copies or signature lists.

QBE function emission uses the canonical symbol linkage, NOT the actual definition
spelling: emit export only for external symbols. Ordinary local function naming
and direct/function-pointer calls stay unchanged; no new mangling is needed for
Linux object-local symbols. Alias/prototype declarations emit no storage/IL. nm
must show t for internal definitions, T for exported wrappers; two object files
with same-named private helpers must link without collision/interposition.

## Required definition constraint and unevaluated lifetimes

N3096 6.9p3 requires an internal definition if its name is used in an expression,
except constant sizeof/alignof and non-VM typeof operands. Do NOT simply require
all static prototypes to have definitions (unused/query-only prototypes are valid),
or allow a missing private definition to bind another TU's external symbol.

Add explicit semantic unevaluated-expression context, distinct from existing
value_required (which controls load/decay, not evaluation). For current non-VM
subset, sizeof expression and typeof expression operands run with a saved/restored
unevaluated flag while retaining ALL constraints/type checks. Nested operands
restore the previous state on success/failure. Use a small private checked helper
if it makes this lifetime clearer and is reused by both paths; never re-analyze
an already-lowered expression or mutate cached type queries. sizeof/alignof type
queries reach expression operands only through already unevaluated queries or
ICE bounds in this non-VM subset; audit every expression/type entry before coding.
If necessary wrap the type-query resolution too, documenting the same saved-state
lifetime. Future VM/atomic work must revise these explicit exceptions.

At the one ordinary-name -> function-designator resolution point, mark canonical
is_referenced only outside unevaluated context. Calls (including argument trees),
address uses, discarded expressions and syntactically present dead/short-circuit
branches count; querying typeof/sizeof must not count. Type cache reads never
create a second use later. After all declarations resolve, check referenced
internal symbols for a definition. Existing duplicate-definition check covers
at-most-one. Unused and query-only prototypes pass with empty IL; external
unresolved calls remain permitted for link-time resolution. No runtime local or
ABI budget is consumed by these flags.

Native constraints may be reported only as warnings for missing internal defs.
Probe all four hosts compile-only (-c if syntax-only suppresses the diagnostic),
keep exact source/status/full-record classifier controls, and record diagnostic
agreements separately from nonzero rejections; never execute these invalid cases
or invent native agreement on silent/unknown diagnostics. Explicitly classify
real diagnostic feature gaps if present rather than masking arbitrary failure.

## Validation

Four-host unchanged originals for all primitive full-width values, class ordering,
static/extern/unadorned chains in BOTH valid directions, list/shared alias bases,
recursion, returns of internal function pointers, adjusted row/function callbacks,
register provenance and ordinary copies. Modern typeof/bool/nullptr/auto cases
have independent exact legacy syntax probes. Query-only/unused static prototypes
must compile/link with no definition; an unevaluated query followed by ordinary
use must restore state and require the definition. Nested sizeof/typeof and
constraints inside unevaluated operands retain normal checks and captured identity.

Compile-only required constraints: duplicate definitions/signature conflicts,
missing referenced internal definition incl addresses/discarded/dead branches,
parameter/type-name static and illegal class mixtures. UB refusals: external first
then static (prototype or definition/list/alias/query). Subsets: static objects,
local static, inferred static objects, static main, VM/static array forms and
inline/thread. Search/remove old static FUNCTION subset probes only with new
positive coverage; keep object/array restrictions. No invalid curated/fuzz C runs.

AST assert written static provenance versus inherited canonical linkage, one
symbol across lists/redeclarations, immutable source/query/composite caches,
evaluated-use flag false for unused/queries and true for ordinary/dead/address
uses, saved/restored context after nested queries, exact original captured symbol,
prototype-only no slots, own parameter spills and function types with no linkage.

At least 24 both-direction mixed-stack primitive ABI arrangements per host plus
row/callback/function-pointer-return cases; two independent kcc objects with the
same private helper name and host exported helper collision verify no leakage.
nm/QBE export count checks for local/exported symbols. Exact 512/513 concrete
items, 256/257 distinct symbols, 128/129 parameters, 256/257 local/spill and 1 MiB
storage, 4096 items, 64 declaration nesting and 128 expanded-type limits; generated
boundaries compile only. Add focused suite, Makefile, lex/compile corpus, AST and
both-host sanitizer matrix. Serial helpers, frozen source manifests, full normal/
QBE/both-host ASan/UBSan and bounded lexer/pipeline fuzz; compare unaffected old
corpus and classify deliberate feature changes explicitly. Draft completion docs
outside while frozen, apply only after all passes, commit/push promptly and check
exact CI independently. Not full C23 conformance, no subagents.

## Retained native compile-only probes

/data/tools/m15e1-native-definition-probes.log: all four hosts accept unused and
sizeof-address-only static prototypes and static -> extern -> unadorned definition.
Direct/address/dead-branch missing internal definitions: GCC11/GCC14 status 1
with exact "'f' used but never defined" error; Clang15/Clang18 status 0 with exact
-Wundefined-internal warning plus "used here" note. The Clang warning is already
a required diagnostic, NOT a compiler gap or native rejection. No C was executed.
External-first -> static is rejected by all four, but remains a mixed-linkage UB
refusal classification under 6.2.2p7, not a fabricated required constraint claim.

Audit refinement: wrap TYPE query resolution in saved unevaluated context as well
as expression queries. A non-VM typeof(type-name), sizeof(type-name) or alignof
(type-name) can contain array-bound syntax with semantically unevaluated nested
expressions; do not accidentally count a function use in a non-VM query just
because the type resolver ordinarily checks an ICE bound. Small private wrappers
for checked expression analysis and type resolution can reuse one saved/restored
flag without token replay/second traversal; preserve failure restoration. Normal
array-bound syntax outside such queries still counts syntactically present uses.

Pre-freeze test audit: the existing integer-constant evaluator conservatively
refuses a dead function call in an array bound, even inside a type query.
Do not silently broaden that independent constant-expression subset here. Query
bound positives use sizeof(&f), a supported ICE; retain dead-call bounds as
compile-only subset probes. Initial implementation stopped on an exact-match
assertion because address-of also uses value_required=false; only sizeof was
changed after auditing both sites. Address-of remains evaluated.

Initial frozen full regression caught three old parameter-array probes expecting
static to remain an unsupported lexer keyword. Recognizing static deliberately
changed that path to an unhelpful integer-literal error. All live validators were
stopped before edits; initial logs/manifests/isolated trees were retired under
/data/tools/m15e1-retired-initial-candidate. Add an explicit static-array-bound
subset diagnostic in the shared suffix parser and update ONLY those three exact
expectations. No static array support or program rewrite. A new freeze and entire
matrix must pass; partial initial passes do not count as final validation.

After the corrected full matrix passed, final grammar review found the shared
scanner's BNF comment still omitted static and the allowed inferred-auto pairing.
That comment-only source change requires another exact frozen snapshot under the
user's policy. The passing intermediate logs/manifests/trees were preserved in
/data/tools/m15e1-retired-grammar-review-candidate; final evidence must come from
the fresh entire matrix including the corrected grammar comments.

## Completion evidence

Normal helpers/compiler were built serially with GCC11/C11 before the frozen
matrix. Full make test passed with GCC11/GCC14/Clang18 native comparison hosts;
full QBE1.2 make test-codegen passed with both modern hosts. Actual GCC11/Clang15
ASan/UBSan builds passed lex/raw-pp/sema and 27 targeted suites; eight suites also
used Clang18 native comparisons. Frozen 387-file primary and isolated manifests
matched before/after. Bounded sanitized compile-only fuzz passed 14130 lexer /
37096 pipeline inputs, 26 seconds each. Logs /data/tools/m15e1-*; isolated
trees /data/validation-m15e1/{gcc,clang}. Prior frozen 267a27f and current compiler
have byte-identical return codes/stdout/stderr on all 155 prior compile corpus
files (123 accepted / 32 rejected), excluding only the new static-function seed.

Four-host focused suite: 53 unchanged baseline + 13 C23-keyword originals.
GCC14/Clang18 agree on 66 positives and reject 23 applicable constraints; legacy
GCC11/Clang15 agree on 53 and reject 17, with exact independent C23-keyword gaps.
Missing internal definitions are diagnosed on 14 modern / nine legacy originals:
GCC rejects, Clang warns with exit status zero. Full exact error/warning/note
records, original source membership, exit status and negative controls are checked;
source-specific unused-value warnings are recognized only for the five discarded
expression/query originals. Warnings are diagnostic agreements, NOT rejections or
feature gaps. Five mixed-linkage UB refusals and 14 subset refusals compile only.
No invalid curated/generated C executed; original programs are never rewritten.

All four hosts pass 24 both-direction full-width mixed-stack primitive ABI
arrangements plus two row/callback arrangements. Internal helpers cross public
wrappers; function-pointer returns execute. Two kcc objects with same-named private
helpers link successfully, and a native exported helper does not interpose on the
kcc private namesake. nm verifies local t versus exported T and unresolved U.
Unused/alias/query-only prototype IL is empty and inherited definitions stay local.

New 11-node AST fixture asserts written static versus inherited canonical linkage,
shared list bases, distinct symbols, unused/query-only unreferenced state, ordinary
and dead-branch referenced state, saved nested-query context, exact captured symbol
identity and immutable compatible type caches. Prototype register provenance does
not leak into ordinary definition spills; actual register definition spill keeps
its own restriction and slot. Existing typedef scope/cache/identity tests pass.
Exact 512/513 concrete list names, 511/512 after a prior declaration, 256/257 unique
symbols, 128/129 parameters, 256/257 locals including 128 spills, 1 MiB storage,
4096 items, 64 declarator nesting and 128 expanded depth pass compile-only.
Only two obsolete static-function refusals were removed with positive replacements:
extern suite 11 -> 10 subsets and declaration-list suite seven -> six subsets.
Three existing static-array probes now expect the explicit shared-suffix subset
diagnostic rather than a removed unsupported-keyword classification. The initial
frozen candidate was retired when full regression caught that diagnostic path;
all final evidence is from a fresh complete matrix, not partial initial passes.
A passing intermediate candidate was also retired after correcting the parser
BNF comment; the final full matrix includes that comment-only source change.

Previous exact M15d2 CI run 39014365465: completed successfully, all three jobs green. New M15e1 CI remains
pending until independently checked after push. Local validation never proves
remote success.
