# Handoff

## Current checkpoint

M15h1 adds file-scope static tentative scalar storage; M15h2 adds complete fixed
static arrays. Read m15-static-objects.md. Written static/extern provenance is
separate from canonical internal linkage and from immutable type captures.
Existing first-tentative anchors emit one local aligned zero datum with no new
runtime slots or backend operations.

Object linkage deliberately differs from function inheritance. Extern after
static preserves internal linkage; an unadorned object after static mixes
linkages and is refused before canonical mutation. Complete prior composites
permit later omitted-bound static array redeclarations. An initially incomplete
internal tentative array is a source-point semantic/UB refusal, never a fallback-[1]
candidate; incomplete pointer referents remain unchanged.

Full normal/QBE and ASan/UBSan normal/QBE integration passed locally with
GCC11/QBE1.2. Subsequent test-only native-oracle corrections also passed focused
Clang18/QBE checks and sanitized-KCC/GCC checks. The new remote GCC/Clang CI must
still be checked independently; no pending run is a success claim. Neighbor regressions,
AST/source captures, private same-name TUs, both-direction ABI, local storage
layout, resource boundaries and output failures remain required gates.

Explicit initializers, block storage, thread/inline, VM/VLA, aggregates and
additional scalar kinds remain deferred. Do not weaken native diagnostic
classifiers or count unsupported-host C23 syntax as agreement. The next bounded
increment is checked integer-constant scalar initialization with a separate
full-definition/duplicate-ownership design, not symbolic or runtime initialization.

## Previous checkpoint: M15g2

M15g2 extends tentative file-scope ownership to existing fixed arrays and arrays
with unknown OUTER bounds. After the entire ordered TU and internal-function
checks, a private semantic pass replaces only anchored, still-unknown canonical
arrays with fresh one-element types. Later known composites win; extern-only
unknown arrays stay incomplete/unowned. Scalars and pointer referents are not
recursively completed. Earlier declaration, typedef, query, expression and
function-return captures remain immutable. Read m15-tentative-arrays.md.

Existing first-tentative anchors emit one explicitly aligned exported zero datum
using final canonical layout. No new AST fields, public symbol list, backend
operation, local slot, initializer interpreter or startup stores. Existing decay,
row strides, element updates and indirect callbacks reuse global addresses.

The exact final freeze contains 399 src/tests/Makefile files. Normal helpers were
built serially BEFORE independent validation makes. Full make test passed with
GCC11/GCC14/Clang18 native hosts; full make test-codegen passed with QBE1.2 and
both modern hosts. Actual GCC11 and Clang15 isolated ASan/UBSan builds passed
lex/raw-pp/sema plus 31 targeted suites and twelve extra Clang18 native comparison
suites each. Primary and both isolated before/after manifests match. Bounded
sanitized compile-only fuzz passed 6002 lexer / 13040 pipeline inputs.
Logs /data/tools/m15g2-*; isolated trees /data/validation-m15g2/{gcc,clang}.
No invalid curated, resource-boundary or fuzz-generated C was executed.

All 159 prior corpus sources (127 accepted / 32 rejected) retain byte-identical
status/stdout/stderr versus frozen 49aeb82. Six obsolete tentative-array refusals
were removed with new positive coverage; void-object diagnostic wording is now
storage-neutral. Full normal preflight and independent rejection-fixture audit
preceded freezing. Production grammar comments and all test changes are included
in the one final snapshot, not patched during validation.

Focused unchanged-source suite: 74 sole-owner zero-storage pairs, including 48
fixed/unknown-outer primitive arrangements in both driver directions. GCC14 passes
74 native agreements; Clang18 passes 70 agreements and identifies four EXACT native
storage bugs, never linked/executed. Both modern hosts pass 74 QBE paired runtimes
and 29 native constraints. GCC11 passes 70 agreements; Clang15 passes 68 plus two
EXACT non-executed storage bugs. Legacy hosts each have four independently probed
keyword-gated native pairs, 26 applicable native constraints and 73 QBE pairs with
one nullptr-companion keyword gap. Every host checks 29 kcc constraints, nine subset
refusals and six unavailable-inference barriers. Companions extern-declare storage
only; -fno-common and ownership checks prevent second definitions/common merging.

Optional status-zero final-one warnings on correctly sized valid objects are
separately counted agreement candidates only after layout and runtime success.
The Clang15 fixed-row logical warning/note is separately source-bound. These are
not constraint rejections or keyword gaps. Clang18 incorrectly allocates one
element/row in four later-known-completion originals (Clang15 two non-keyword
ones): items 4 instead of 12 bytes, rows 12 instead of 24. N3096 6.9.2p2 requires
the FINAL composite bound; the retained compile-only assembly/section audit
confirms actual undersized storage, not merely missing/wrong ELF symbol metadata.
See the committed m15-tentative-arrays-native-audit.md for exact originals and
assembly/section evidence.
Originals remain unchanged. GCC allocates the required known bounds. Correct kcc/
QBE runtime checks are independent; undersized native originals never execute.

Classifiers probe compiler family/target macros and log exact version rather than
assuming vendor version/executable aliases. Exact frozen source, flags, status,
complete ordered diagnostic records, object freshness and exact owned layouts are
mandatory. Unknown messages/layouts fail closed; changed source/status/target,
missing/extra/duplicate/reordered diagnostics, wrong kind/size/count and stale/
missing-object controls pass. Corrected storage cannot match an old bug category.
Mutable objects require B/D; R is accepted only for exact const ownership records.
Actual Ubuntu CI evidence remains separate from local portability reasoning.

QBE1.2 omits ELF data .size metadata. The initial focused harness assumption that
nm -S alone supplied kcc data sizes was corrected BEFORE the final freeze, not by
relaxing native guards. kcc allocation evidence combines exact IL zero size/align,
assembly .fill directives, unique B symbols/offsets and readelf NOBITS extent with
alignment padding. Native nm -S sizes remain mandatory. Pure negative controls
reject truncated allocations, wrong alignment/offset/section extent, duplicates,
unknown ownership and mutable R. /dev/full still reports output failure.

The 31-declaration/14-object AST fixture verifies exact anchors, final known/[1]
canonical types versus immutable source/typedef/query/address/function-return
snapshots, unowned externs, no recursive pointer completion, rows/callbacks and no
extra runtime locals. Six isolated compile-only linker-wrapper probes establish
finalizer-specific allocation failure at the tentative anchor with empty stdout,
unwrapped correct-size success, three no-finalizer-call controls and a distinct
resolver-allocation failure. The wrapped compiler's source manifest matches the
final production source; no allocator API or stage architecture was changed.

Prior M15g1 exact CI run 39060376796: test (gcc) success, fuzz success, test (clang) in_progress. Pending jobs are not local-pass claims.
New M15g2 CI remains pending until independently checked after push. Local results
never establish remote success. Subagents supplied tests, AST and independent
source/standards/native-layout review; main owns integration and final snapshot.

Only current scalar/array tentative definitions are supported. Static objects,
explicit initializers (including zero/empty), block extern/functions, inferred
file objects, thread/inline, VM/VLA, aggregates, incomplete inner rows, function/
void elements, array assignment/copy/return and additional scalar kinds remain
deferred. Tentative objects named main remain a Linux hosted-target subset
refusal. Earlier sizeof or whole-array arithmetic on unknown arrays still fails,
even if later declarations or TU-end finalization supply storage. Fallback [1]
runtime fixtures access only element zero (row zero for rows); callback elements
are assigned before calling. No full C23 conformance claim.

Keep the existing 1 MiB PER ARRAY TYPE ceiling, including complete rows used by
fallback [1]. This is not a combined global-byte budget: independent 256 canonical
objects, 256 functions, 512 concrete declarations and local-storage/depth/query
budgets remain separate. Maximal/invalid/resource/fuzz programs compile only.
Initialized definitions need a separate precedence/duplicate-ownership design;
static objects need distinct canonical linkage work.

## Previous checkpoint: M15g1

M15g1 adds unadorned file-scope tentative definitions of existing complete
scalar types: integers, const scalars, object/function pointers and typeof(nullptr).
Written extern provenance stays on concrete declarations. A canonical symbol's
first successful tentative declaration is its unique emission anchor; compatible
repeats and extern interleavings preserve identity and immutable earlier type
captures. Query/alias roots still classify by resolved type, not storage spelling.
Read m15-tentative-scalars.md.

QBE emits exactly one exported, explicitly aligned zero datum using the FINAL
canonical scalar layout, even for unused owned objects. Pure extern scalars and
arrays still emit no storage. No runtime initialization, local allocation/slot,
common-symbol merging, new initializer AST or public symbol list is introduced.
All-zero pointer/nullptr representations are an amd64 SysV target policy, not a
portable C assertion. Native companions only extern-declare kcc-owned objects.

Final exact source freeze contains 396 src/tests/Makefile files. Normal helpers
were built serially BEFORE independent normal/QBE validations. Full make test
passed with GCC11/GCC14/Clang18 native hosts; full make test-codegen passed with
QBE1.2 and both modern hosts. Actual GCC11 and Clang15 isolated ASan/UBSan builds
passed lex/raw-pp/sema plus 30 targeted suites and eleven extra Clang18 native
comparison suites each. Primary and both isolated before/after manifests match.
Bounded sanitized compile-only fuzz passed 7107 lexer / 13449 pipeline inputs.
Logs /data/tools/m15g1-*; isolated trees /data/validation-m15g1/{gcc,clang}.
No invalid curated, resource-boundary or fuzz-generated C was executed.

Two full candidates were retired for obsolete negatives, not production defects:
test_compile.py expected trailing int x; after a function to fail; later,
test_pointer_values.py still refused int (*f)(void);. Remaining validators were
stopped, and exact source/partial logs preserved separately in
m15g1-retired-trailing-object-candidate and m15g1-retired-pointer-object-candidate.
The trailing refusal became a still-unsupported explicit initializer plus a real
sole-owner trailing-tentative positive; the obsolete callback-object refusal was
removed with existing g1 ownership positives retained. A full normal preflight
and independent rejection-fixture audit preceded the new freeze. ALL final
batches were rerun against one candidate; retired partials are not final evidence.

Focused suite: 72 sole-owner initialized-by-default pairs, including 24 simple
primitive and 24 distinct mixed-stack primitive arrangements in both driver
directions. GCC14/Clang18 each pass 72 unchanged native agreements and 72 QBE pairs.
GCC11/Clang15 each pass 64 agreements and 70 QBE pairs; eight independently probed
keyword-gated native pairs and two nullptr-companion gaps are not agreements.
All hosts check 24 kcc constraints, 14 subset refusals and six compile-only
unavailable-inference barriers. Modern hosts reject 24 native constraints;
legacy hosts reject 21 applicable ones. Native constraints use real -c -fno-common:
GCC14 accepts void cell; in syntax-only mode but rejects its TU-end definition
when compiling to an object; Clang18 rejects both. No source rewrite or waiver.

IL/assembly/nm checks prove unique strong ownership (never common .comm/.lcomm),
exact zero-data size/alignment for all twelve primitive types and four const/
pointer/nullptr cases, no duplicate companion definition, external-only U versus
owned B/D and native const R acceptance. /dev/full returns status 1 with exactly
kcc: error: cannot write QBE output. Callback objects are assigned before calling;
zero pointers are never dereferenced. Trailing objects after functions retain
one owner. Query-only private functions still create no runtime references.

The 31-node AST fixture checks written extern flags and exact first-tentative
anchors through concrete/query repeats, alias/function classification, canonical
row-pointer composites versus immutable earlier declaration/query/address types,
distinct symbols and no global runtime locals/spills. Local/register-parameter
hiding and restored global lookup preserve captured bindings. Independent source
review found no production correctness defect; focused compile-only/IL evidence
is separate from the full main-owned frozen matrix.

All 158 prior corpus sources (126 accepted / 32 rejected) retain byte-identical
status/stdout/stderr versus frozen e0a3b24. Obsolete plain-scalar, pointer and
mixed-list refusals were removed only where newly supported, with positive
coverage; array/static/initializer refusals remain explicit. Exact object/
function/declaration, parameter/local/storage and depth limits pass compile-only.

Prior M15f2 exact CI run 39056814296 completed successfully: all three jobs green.
New M15g1 CI remains pending until independently checked after push. Local passes
never establish remote success. Parallel agents supplied focused tests, AST and
review; main integration and one final exact matrix establish committed evidence.

Only existing COMPLETE SCALARS gain tentative ownership. Tentative arrays,
unknown-array size-one finalization, explicit initializers (including zero/empty),
static objects, block extern/functions, inferred file objects, thread/inline, VM,
aggregate and additional scalar kinds remain deferred. Arrays remain explicit
extern declarations only. Tentative objects named main are a Linux hosted-target
subset refusal, not a fabricated universal C constraint. Ordinary const objects
are not ICEs; writes remain refused. No full C23 conformance claim.

The one-anchor representation is sufficient only while initialized definitions
are unsupported. Future initialized definitions need a separate ownership and
duplicate-definition design; static objects need canonical linkage work. Shared
256 object / independent 256 function / 512 declaration pools and existing local,
array-type, depth and query budgets are unchanged. No new global-byte budget.

## Previous checkpoint: M15f2

M15f2 extends explicit file-scope extern objects to fixed arrays and arrays with
unknown outer bounds, retaining complete elements and existing scalar support.
Mixed function/scalar/array lists, aliases, typeof/typeof_unqual, rows, pointer
arrays and function-pointer arrays reuse the current concrete object nodes and
canonical symbols. The only production semantic change admits scalar OR array,
not arbitrary object kinds. Array-suffix grammar comments distinguish incomplete
extern declarations from complete local storage. Read m15-extern-arrays.md.

Unknown outer arrays decay to pointers to their complete elements; subscripts and
row strides reuse current lowering and $symbol addresses. Whole-array addresses
retain array types, and sizeof/whole-array pointer arithmetic still require
completeness. Canonical unknown-to-known composites never rewrite earlier source,
query, address or expression snapshots. Extern arrays allocate no data/local slots.
The resolver retains its existing 1 MiB PER ARRAY TYPE ceiling, even though native
storage is elsewhere; independent arrays do not consume a global byte budget.

Final exact source freeze contains 393 src/tests/Makefile files. Normal helpers
were built serially BEFORE independent normal/QBE validation makes. Full make
test passed with GCC11/GCC14/Clang18 native hosts; full make test-codegen passed
with QBE1.2 and both modern hosts. Actual GCC11 and Clang15 ASan/UBSan isolated
builds passed lex/raw-pp/sema plus 29 targeted suites and ten extra Clang18 native
comparison suites each. Primary and both isolated before/after manifests match.
Bounded sanitized compile-only fuzz passed 4751 lexer / 7572 pipeline inputs.
Logs /data/tools/m15f2-*; isolated trees /data/validation-m15f2/{gcc,clang}.
No invalid curated, resource-boundary or fuzz-generated C was executed.

All 157 prior corpus sources (125 accepted / 32 rejected) have byte-identical
status/stdout/stderr versus frozen b64e0f9. Existing scalar extern suites pass all
four hosts; only two obsolete array refusals were removed with positive replacements
and the void subset diagnostic updated. Source grammar comments are included in
this freeze; no production source/test changes were made during validation.

Focused suite: 74 initialized native-owner pairs, including 48 distinct fixed/
unknown-outer primitive array arrangements in both driver directions. Modern
GCC14/Clang18 each pass 74 QBE paired runtimes, 73 unchanged strict native agreements
and one EXACT array-unqualification native feature gap. Legacy GCC11/Clang15 each
pass 68 native agreements and 73 QBE pairs, with six independently probed keyword-
gated native pairs and one nullptr-owner keyword gap. All hosts check 34 kcc
constraints, nine subset refusals and six compile-only inferred-name barriers;
modern hosts reject all 34 native constraints, legacy hosts reject 30 applicable
ones. Original native programs are never rewritten to manufacture agreement.

The one-dimensional typeof_unqual(array-expression) original remains unchanged.
N3096 6.7.2.5p5/example2 and 6.2.5p31 require removing array/element const, not pointer
referent const. Both native hosts retain const here; exact original membership,
status 1 and complete normalized error/warning/note records are required for the
gap classification. Changed sources/statuses/signals/extra/missing/duplicate
records fail negative controls. Rejected native originals never link or execute;
QBE runs the standards-valid original against a separately compiled valid owner.
This is not native agreement or a kcc bug. The pre-implementation standards audit
and the existing separate multidimensional gap precedent are recorded in the design.

The 18-node AST fixture verifies shared specifiers; unknown/known/repeated canonical
identity; immutable source/typeof/whole-address snapshots; element/row sizeof and
decay; indirect callback-element calls; const decay; no global runtime locals or
slots. Focused IL/nm verifies U references without B/D definitions, no data/alloc,
private t/exported T functions, unused/non-VM query-only linker erasure, including
callback arrays queried from an undefined private function. Runtime cases check
fixed/unknown whole-array versus element addresses, row strides, pointer/callback
slot mutation, const reads, nullptr leaves, own/local/repeated/same-list bound
visibility, parameter-query adjustment and scope restoration.

Exact 512/513 declarations, 256/257 shared scalar/array objects, independent 256
functions and mixed 512 totals pass. Complete/unknown-row/multidimensional array
1 MiB limits and one-element-over failures, 64/65 dimensions, independent large
extern arrays and an unchanged 1 MiB local storage allowance pass compile-only.
The retained scalar/static/declarator suites cover the other existing resource
and mixed-stack ABI contracts; array arrangements are not relabeled scalar ABI.

Prior M15f1 exact CI run 39052481142 completed successfully, all three jobs green.
New M15f2 CI remains pending until independently checked after push. Local passes
never establish remote CI success. Parallel subagents prepared/reviewed tests,
AST and standards; one main-owned final exact snapshot establishes this evidence.

Only explicit extern declarations gain arrays. All definitions, initializers,
tentative/plain/static objects, block extern/functions, inferred extern, VM/VLA,
aggregate additions, thread storage/inline and remaining qualifiers stay deferred.
Unknown INNER rows, void/function elements and invalid constant bounds remain
errors. Unknown outer arrays are not tentative definitions and are not completed
to one element at TU end. Referenced native storage must exist at link time; every
executed index in curated tests is backed by initialized owner storage. No full
C23 conformance claim. Earlier array exclusions are superseded only for this slice.

## Previous checkpoint: M15f1

M15f1 supports file-scope explicit extern declarations of current complete scalar
objects: integers, object/function pointers and typeof(nullptr). Compatible
redeclarations reuse canonical external-object symbols; composite refinements
never rewrite earlier syntax/query/expression type snapshots. Mixed extern
function/object lists share immutable specifiers and preserve source order.
Native translation units own storage. kcc emits external addresses and existing
typed loads/stores/updates/indirect calls, never data or local slots for these
declarations. Read m15-extern-objects.md.

Concrete external-object declarations and lowered external-object lvalues remain
separate from functions and real locals. Query/alias-root declarations retain
written extern permission and resolve to exactly one function or object symbol.
Nearer typedefs/locals/parameters hide globals; inferred unavailable locals reject
self-use without falling back to outer objects. File ordinary-namespace conflicts
are checked before canonical mutations. Function-pointer objects remain indirect
calls, while query-only internal functions remain unreferenced.

Normal compiler/helpers were built serially before the exact frozen source matrix.
Full make test passed with GCC11/GCC14/Clang18 native hosts; full QBE1.2
make test-codegen passed with both modern hosts. Actual GCC11/Clang15 ASan/UBSan
builds passed lex/raw-pp/sema and 28 targeted suites, plus 9 extra Clang18
native comparison suites. Frozen 390-file primary/isolated manifests matched
before/after. Sanitized compile-only fuzz passed 12063 lexer / 28278 pipeline
inputs. Logs: /data/tools/m15f1-*; isolated trees: /data/validation-m15f1/.
All 156 prior corpus files (124 accepted / 32 rejected) retain byte-identical
status/stdout/stderr versus the frozen 1b44e97 compiler. No invalid curated or
fuzz-generated C was executed. Original native test programs were not rewritten.

Focused unchanged-source evidence: 79 initialized native-owner pairs per modern
host, with 79 native agreements and 79 QBE paired runtimes; 30 native constraints,
14 explicit subset refusals and six kcc-only inferred-name visibility barriers.
Legacy GCC11/Clang15 agree on 70 pairs and reject 25 applicable constraints;
nine pairs have independently probed exact C23 keyword gaps. QBE runs 77 pairs
with each legacy owner toolchain; two nullptr-owning pairs require modern owners.
Simple object-reference and mixed-stack primitive ABI arrangements are separately
counted: 24 each, all four hosts. Mixed-stack cases use six integer register and
two stack arguments and observe initialized native-owned storage in both driver
directions. Callback objects include void and pointer returns; parameter queries,
typeof_unqual, captured incomplete-row pointers and source-order shadowing pass.
All 512/513 declaration, 256/257 object/function independent mixed-pool,
128/129 parameter, 256/257 local including spills, 1 MiB storage, 4096 item,
64 nesting and 128 expanded-depth boundaries pass compile-only. IL/nm verifies
external U references, private t/exported T functions, no global allocation/data,
no extra local slots and no references from unused/non-VM query-only names.
All four-host results are retained in /data/tools/m15f1-four-host-focused.log.

The 11-node AST fixture checks shared specifiers, source-order global captures,
canonical known-bound row-pointer composites versus immutable earlier unknown
snapshots, resolved query object/function distinction, exact object identity,
query-only internal function state, indirect callbacks, register-parameter/local
shadowing and exact runtime-local slot chains. External declarations add no slots.
Removed only three obsolete extern-object refusals and one mixed-list refusal;
extern initializer remains an explicit definition subset refusal. The original
function-declaration delimiter diagnostic is preserved. All grammar comments and
final source/test changes are included in this frozen validation, not patched
after it. Parallel subagents supplied semantic review, focused tests and AST tests;
main integration and one final matrix establish the committed evidence.

Prior M15e1 exact CI run 39017514042 completed successfully with all three jobs
green. New M15f1 CI remains pending until independently checked after push;
local validation never establishes remote success.

Only explicit file-scope extern scalar declarations are added. Object definitions,
initializers, tentative/plain/static object declarations, externally declared object
arrays, block extern/function declarations, inferred extern, thread/inline storage,
VM/aggregate/remaining qualifier support and full C23 remain unsupported. Pointers
to incomplete arrays are scalar objects and retain existing composite rules.
Ordinary const objects are not constant expressions. Missing external storage is
a linker error, not an invented per-TU definition requirement. No full C23 claim.
Earlier global-object exclusions are superseded only for this documented slice.

## Previous checkpoint: M15e1

M15e1 supports file-scope static function declarations, definitions and prototype
lists, including alias/query prototypes, callbacks, register/adjusted parameters,
recursion and internal function pointers returned through exported wrappers.
Written static is recorded only on concrete external declarations. Canonical
function symbols retain internal linkage through later extern OR unadorned
prototypes/definitions; QBE omits export using that canonical linkage. Function
types/caches do not acquire a linkage qualifier. Read m15-static-functions.md.

Ordinary function-designator resolution records syntactic uses, including dead
branches, addresses and discarded expressions. Saved/restored unevaluated context
for sizeof/alignof/typeof expression AND type queries preserves constraints but
excludes non-VM query-only uses. After the whole unit, referenced internal symbols
must have a definition; unused/query-only prototypes remain valid and emit no IL.
Alias/prototype names still consume no runtime locals, spills or storage.

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

Only file-scope functions gain static/internal linkage. Static/global/local
objects, tentative definitions, block function declarations, inline/thread storage,
inferred static objects, static array parameters and static main remain explicit
subset refusals. External-first then static is conservatively refused mixed-linkage
UB (6.2.2p7), not a required constraint claim. Auto+static grammar is valid but
explicit-type combinations require inference under 6.7.1p4. Existing register-void,
VM/aggregate/qualifier/inference and constant-expression subsets remain; dead calls
in array bounds are still refused by the ICE-only bound subset inside type
queries; no claim that a dead-call bound itself is non-VM is made. Future VM support must revise the explicit unevaluated-use exceptions.
Not full C23 conformance.

Previous exact M15d2 CI run 39014365465: completed successfully, all three jobs green. New M15e1 CI remains
pending until independently checked after push. Local validation never proves
remote success.

User authorizes continuing, superseding historical STOP. No subagents, discarded
stashes/work, forced pushes, stale fixture regeneration or committed credentials.
Inspect origin/worktree/tools after resets. Completion docs were drafted outside
and applied only after all frozen validators/manifests passed. Initial exact-match
assertion stopped halfway; remaining edits were applied selectively, not rerun.
Pre-freeze AST pointer-equality assertion was corrected to type compatibility:
canonical composite replacement does not rewrite a captured source type cache.
All final tests ran from a fresh frozen snapshot. Do not rerun old generators.
Continue with a new documented small milestone against the pushed checkpoint.

## Earlier M15d2 checkpoint (historical)

M15d2 supports file-scope function declaration lists with one shared specifier
base and distinct concrete declarators, including extern, builtin/typedef bases,
query/alias-derived function prototypes, callbacks and pointer-returning functions.
Read m15-function-declaration-lists.md. A private external-declarator tail counts
and links each concrete name once, leaves the common base immutable, and keeps
per-function parameter scopes separate. Each earlier function is registered by
sema before later parameter/type queries, preserving source-order capture. Only
a sole direct function declarator introduces a body; list members are prototypes.
Existing single alias/query body/initializer diagnostics remain unchanged.
No public AST/semantic/type/QBE interface changes or runtime prototype storage.

Full make test passed with GCC 11.5/GCC 14.2.1/Clang 18.1.8 native comparison
hosts; compiler/normal C11 helpers were built serially with GCC 11 before parallel
runs. Full QBE 1.2 make test-codegen passed with both modern native hosts. GCC 11
and Clang 15 ASan/UBSan lex/raw-pp/sema plus 26 targeted suites passed; list,
extern, register-parameter, inferred-typedef, register-auto, auto and binding
suites also passed with Clang 18 as native oracle. Frozen 384-file primary and
isolated source/test/Makefile manifests matched before/after. Bounded sanitized
compile-only fuzz: 13,575 lexer / 42,790 pipeline inputs, 26 seconds each.
No invalid curated or generated C executed. Logs/manifests /data/tools/m15d2-*,
isolated trees /data/validation-m15d2/{gcc,clang}. Prior 0b5fcb4 sanitized compiler
and frozen current compiler have identical return codes/stdout/stderr on all 154
old compile corpus files (122 accepted / 32 rejected), excluding the new list seed.

Four-host focused list suite: 43 baseline + 8 C23-keyword unchanged originals.
GCC 14 agrees on 51 and Clang 18 on 46 with five exact top-level return-qualifier
gaps under N3096 6.7.6.3p4. GCC 11 agrees on 43; Clang 15 on 38 with those same
five gaps, plus independently probed absence of eight C23-keyword originals.
Modern hosts reject 12 constraints; legacy hosts reject nine applicable ones.
Exact qualifier-gap classification requires membership in the five original
sources, status 1 and the complete error/note sequence for f and g; wrong sources,
exit codes/signals and extra warning/note/fatal/duplicate records are negative
controls. Original programs are never rewritten to fake native agreement. Seven
subset probes compile only; no required native rejection claim for valid but
unsupported objects/local extern/alias bodies/static/inferred extern forms.

All four hosts pass 24 both-direction mixed-width/full-value primitive ABI
arrangements across six registers/two stack arguments plus two row/callback
arrangements. AST asserts 13 concrete external nodes in exact order, one common
return specifier base with separate derived graphs/parameter syntax, pointer
return wrapping the same base, shared alias/query syntax caches with distinct
symbols, restored outer typedef in sibling parameter lists, later query capture
of the earlier function's exact symbol, own register definition spill and no
prototype runtime storage. Existing extern composite-bound/cache AST checks stay.
Plain/extern/alias/query prototype-only IL is empty, one definition exports once,
and unsupported list members emit no partial IL.

Exact 512/513 names in ONE list and 511/512 combined with one prior declaration,
256/257 unique symbols versus 512 compatible repeated names, 128/129 parameters,
256/257 locals including 128 spills, 1 MiB storage, 4096 items, shared 64 declarator
nesting and 128 expanded-type limits pass; generated cases compile only. Removed
only two obsolete list refusals with replacement positive coverage: extern subset
12 -> 11 and queried-function subset 13 -> 12. All affected extern/query/typedef-
foundation/typedef-placement/register-parameter suites passed on all four hosts;
other native gap classifications remain separate.

Only function prototypes form ordinary comma lists. No global objects/tentative
definitions, mixed object/function lists, function bodies in lists, alias/query-
derived function bodies, block function declarations, static/internal linkage,
inline/thread storage or inferred extern objects. Existing register-void,
qualifier/VM/aggregate/inference/resource restrictions remain. Shared bases are
immutable; no token vector/replay or second semantic/cache owner. Not full C23.

M15c1 exact-commit CI run 39009008993 and M15d1 run 39010665350 both completed
successfully with all three jobs green. New M15d2 exact-commit CI is pending until
checked after push; local passes never imply remote success.

User authorizes continuing, superseding historical STOP; no subagents, discarded
stashes, forced pushes, regenerated stale snapshots or source credentials. Inspect
worktree/tools/origin after resets. The first implementation tool call did not run;
retained tree was inspected, tools restored and design applied once. Completion
docs were drafted outside and applied after all final validators/manifests passed.
Do not rerun implementation generators already applied. Next small increment
needs a fresh design against this pushed checkpoint.

## Earlier M15d1 checkpoint (historical)

M15d1 supports explicit extern on single file-scope function declarations and
definitions at any specifier position, including typedef/query-derived function
prototypes, callbacks, adjusted/register parameters and ordinary compatible
redeclarations. Read m15-extern-functions.md. All supported functions already
have external linkage: explicit extern reuses that exact existing symbol/type/
QBE export policy, not a new linkage model. New token_extern is converted only
after preprocessing; raw identifiers and keyword-macro conversion stay intact.
The private scanner diagnoses duplicates/mutually exclusive classes, preserves
valid auto+extern inference grammar as a subset refusal, and rejects typed
combined auto for its actual inference constraint. Local extern fails before
name publication/runtime locals, including consumed-alias/inferred-name starts.
Parameter/type-name extern remains forbidden. No public AST flag, semantic/type/
backend implementation changes or alias storage.

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

Only single file-scope function declarations/definitions are added. Global or
local extern objects, tentative definitions, block-scope function declarations,
static/internal linkage, inline/thread storage, multiple function declarators
and inferred extern objects remain unsupported. No function storage/type flag is
needed while explicit/implicit declarations have identical external semantics;
future linkage work must separately design provenance and visibility. Existing
register-void, scalar inference, qualifier/VM/aggregate and resource restrictions
remain. Not full C23 conformance.

M15c1 exact-commit CI run 39009008993 is pending; no remote pass claimed.
New M15d1 exact-commit CI is pending until independently checked after push.
Local validation never implies a remote pass.

User authorizes continuous work, superseding historical STOP; no subagents,
force push, discarded stashes, stale snapshot regeneration or source credentials.
Tools/worktree/origin must be inspected after resets. The partial initial
outside-tree implementation script stopped on an anchor before parser writes;
only unapplied parts were completed, never blindly rerun over applied changes.
Final validation used one frozen source snapshot. Next increment requires a
recorded design; single-specifier function declaration lists are research only.

## Earlier M15c1 checkpoint (historical)

M15c1 supports register parameter declarations in prototypes/definitions,
nested callbacks and unnamed C23 parameter positions, including supported
array/function adjustment and typedef/query bases. Read m15-register-parameters.md.
The existing private declarator context reaches the shared scanner: only register
is permitted in parameters; outer type-name storage and parameter auto/typedef
remain forbidden. Concrete ast_parameter.is_register records written provenance,
not a type qualifier or signature flag. Prototype objects retain the address
restriction with no runtime slots; actual named spills use their OWN definition's
flag. Register prototypes never poison ordinary definitions, or vice versa.
Adjusted array/function parameters are register POINTER objects: index/call and
pointee addresses work, but &parameter is forbidden even in sizeof/typeof/bounds.
Source syntax caches, composites, captures and ordinary copied types remain
unchanged. No physical-register allocation or type/QBE implementation change.

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

Register void (direct/query/alias) markers remain conservatively unsupported;
plain and unregistered query-derived void markers retain zero-ABI normalization.
Only supported complete scalar adjusted parameters are implemented: no K&R,
variadics, VM/static/restrict array forms, aggregates or other parameter storage.
Globals, static/extern/thread storage and real linkage expansion remain deferred.
Existing register-array conversion refusal and inferred-auto limitations remain.
Not full C23 conformance.

M23e3 exact-commit CI run 38988250769 completed/success with all three jobs green.
M15c1 exact-commit CI is pending until independently checked after push. Local
validation never implies a remote pass.

User authorizes continuous work and supersedes historical STOP. No subagents,
stashes discarded, historical snapshot regeneration, force pushes or credentials
in source. Verify worktree, tools and origin/development after resets. Completion
was applied only after frozen final validation; no source edits during validation.
The next researched increment is explicit file-scope extern function spelling;
it still needs its design copied/recorded against this pushed checkpoint before
implementation. No globals/linkage implementation is implied by that research.

## Earlier M23e3 checkpoint (historical)

M23e3 inferred identifiers may hide outer typedef names at block/for scope,
bare or parenthesized, including register inference. Read
m23-inferred-typedef-shadowing.md and the latest ledger/contracts/coverage/limits.
The scanner uses one demand peek at '=' after an auto-prefixed visible alias
and explicitly returns that consumed identifier, not an old alias type. A small
inferred-identifier grammar handles balanced names without misclassifying a
typedef as a function parameter. Private declaration_head preserves storage/auto
and consumed-name tokens; no replay, token vector or new public interface.

The same syntax object mask and reserved-untyped semantic local hide the alias
throughout initialization; sizeof/typeof/dead branches cannot use it. Completion
exposes the same inferred object; block/for exit restores prior type meaning.
Explicit auto T x / T auto x and old shared declaration bases remain unchanged.
No sema/type/QBE source changes, alias runtime storage or second initialization.

Full make test passed with GCC 11.5/GCC 14.2.1/Clang 18.1.8 as native
comparison hosts; normal C11 helpers were built with GCC 11. Full make
test-codegen passed with QBE 1.2 and both modern native hosts. GCC 11 and Clang
15 ASan/UBSan lexer/sema plus 23 targeted suites passed; inferred-typedef,
register-inference, ordinary inference and binding suites also passed with Clang
18 as native oracle. Normal helpers were built serially before parallel runs.
Frozen primary and isolated source/test/Makefile manifests matched before/after.
Bounded compile-only sanitized fuzz passed 10,381 lexer / 19,799 pipeline inputs
in 26 seconds each. No invalid curated or generated C executed. Logs/manifests
/data/tools/m23e3-*, isolated trees /data/validation-m23e3-final/{gcc,clang}.

The previous M23e2 sanitized compiler and frozen M23e3 compiler have identical
return codes/stdout/stderr on all 151 pre-existing compile corpus files
(119 accepted / 32 rejected), compiled only, excluding the new typedef seed.

Focused inferred-typedef suite: 54 unchanged original C23 programs passed through
kcc/QBE; Clang 18 strictly agrees on all 54 and rejects 43 constraints, including
36 unavailable-name barriers. GCC 14 supports basic inference but rejects the
exact independent typedef-name inference probe with two known grammar errors;
zero new source agreements or semantic constraint agreements are counted on
that host. Legacy GCC 11/Clang 15 lack basic inference on the separate exact
probe; likewise zero new agreements. No originals rewritten to explicit types
or native failures masked. The grammar-gap classifier requires exact probe text,
status 1 and complete diagnostic records; wrong text/status, signals, extra notes,
warnings, fatal errors and duplicate records are negative-tested.

All four hosts pass 24 both-direction mixed-stack primitive ABI arrangements
with inferred kcc code and ordinary native helpers/drivers; linkage does not
masquerade as native syntax support. Five UB refusals and nine subset refusals
compile only. Ordinary/register inference, explicit auto, binding and both
register suites reran on all four hosts with existing native gap counts unchanged.
Two old visible-typedef subset refusals in auto_inference were replaced by this
new positive coverage; that suite now has nine subset refusals.

AST assertions cover bare, grouped and register forms: old shared typedef bases
and captured object addresses remain identical, outer alias stays long while the
new inferred object is int, completed typeof/loads capture the new declaration,
ordinary copies have no register flag, and four real slots/reverse-list entries
exclude alias storage. Failed bare/grouped self-size initializers capture the
reserved untyped INNER object, not the old alias, with no completed runtime local
or IL. A string-inference IL probe has one static string and one real slot;
existing AST string-occurrence invariants remain in the sanitizer matrix.
Exact 256/257 locals (including 128 named spills), 4096/4097 items, 1 MiB/overflow
storage, 64/65 grouped typedef identifiers and 128/129 expanded-type depth pass.
Generated sibling-block and other boundary programs compile only, never execute.

Only initialized single identifiers, optionally grouped, and implemented complete
scalar inference are supported. Derived/braced/incomplete/nonobject inference,
register parameters, globals/other storage, constexpr/attributes/VM/aggregates
remain unsupported. Same-scope prior aliases/objects and multiple underspecified
identifiers are UB refusal probes under N3096 6.7p12, NOT required native
constraint diagnostics; none execute. Combined auto/register with explicit types
is still a 6.7.1p4 constraint. Existing register-array conversion refusal, ordinary
own-bound/initializer rules and all resource/ABI limits remain. Not full C23.

M23e1 CI run 38982126026 completed/success, all three jobs green.
M23e2 CI run 38984165289 completed/success, all three jobs green.
New M23e3 exact-commit CI is pending until checked after push; local validation
never implies remote success. User authorizes continued work and supersedes
historical STOP. No stashes discarded or subagents used. Preserve historical
named stashes if a reset restores them. Do not rerun historical snapshots or
current outside implementation scripts already applied once. Verify tools,
worktree and origin/development after resets. Next increment needs a fresh
recorded design; register parameter storage is still research only.

## Earlier M23e2 checkpoint (historical)

M23e2 register + inferred auto is implemented and locally validated at block/
for scope, in either order with existing const positions. Read
m23-register-auto-inference.md and the latest ledger/contracts/coverage/limits.
A private parser result carries ordinary storage and auto tokens independently. Existing inferred
syntax/one-pass sema complete the same real local with its register flag intact.
Direct address-taking is rejected, even in unevaluated queries; ordinary copies
inherit no storage hint. Pointer referents remain addressable. No sema/type/QBE
implementation or public API change, extra runtime local or token replay.

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

C23 6.7.1p4 requires inference when auto accompanies another storage class:
auto register int x=42 is a CONSTRAINT violation, not valid traditional explicit
auto. Those explicit primitive/alias/query/void forms remain rejected. Register
alone without a type does not silently infer or default to int. Duplicate/typedef
mixtures still reject. Register parameters, globals, other storage classes,
attributes/constexpr/VM, visible-typedef ambiguities and inferred derived/braced
forms remain unsupported. Multiple underspecified identifiers and prior same-
scope declarations are UB refusal probes, not native constraint requirements;
none execute. This is still an incomplete C23 subset.

M23e0 CI run 38979609085 completed/success, all three jobs green.
M23e1 CI run 38982126026 is pending; no remote pass is claimed.
New M23e2 exact-commit CI is pending until checked after push. Local validation
never proves remote success. User authorizes continued development and supersedes
historical STOP. No stashes discarded; preserve historical named stashes if a
reset restores them. No subagents or old snapshot scripts used. Current outside
implementation scripts were already applied once; do not rerun. Verify tools,
source/worktree and origin/development after resets. Next increment requires a
fresh recorded design; register parameter and visible-alias inference questions
have only outside-tree research, no implementation/design commitment yet.

## Earlier M23e1 checkpoint (historical)

M23e1 single-identifier block/for inferred auto is implemented and locally
validated. Read m23-auto-inference.md and the latest ledger/contracts/coverage/
limitations. An assignment initializer is analyzed once with value conversions;
its complete scalar type, plus written const, completes one ordinary local.
Array/string/function initializers decay to pointers; nullptr stays distinct.
The concrete inferred syntax owns qualifiers, not a duplicate initializer.
A reserved no-type name hides outer namesakes during initialization and reports
unavailability even inside sizeof/typeof/dead branches. Completed definitions
then expose the same real local. Ordinary explicit declarations/parameter spills,
shared bases, scope restoration, no-alias storage and QBE/ABI remain unchanged.

Full make test passed with GCC 11.5/GCC 14.2.1/Clang 18.1.8 as native
comparison hosts; normal C11 helpers were built with GCC 11. Full make
test-codegen passed with QBE 1.2 and both modern native hosts. GCC 11 and Clang
15 ASan/UBSan lexer/sema plus 21 targeted suites passed; the new inference and
binding suites also passed with Clang 18 as native oracle. Normal helpers were
built serially before parallel validation. Frozen primary and isolated source,
test and Makefile manifests matched before/after. Bounded compile-only sanitized
fuzz passed 11,433 lexer / 28,284 pipeline inputs in 26 seconds each. No invalid
curated or generated C executed. Logs/manifests /data/tools/m23e1-*, isolated
trees /data/validation-m23e1/{gcc,clang}.

The previous M23e0 sanitized compiler and frozen M23e1 compiler have identical
return codes/stdout/stderr on all 149 pre-existing compile corpus files
(117 accepted / 32 rejected), compiled only, excluding the new inference seed.

Focused inference suite: 65 original C23 programs passed through kcc/QBE;
GCC 14 and Clang 18 strictly agree on all 65, without rewriting originals or
adding gap exceptions. Independent inferred-auto probes identify exact legacy
GCC 11/Clang 15 absence (zero inference agreements, not an implicit-int fallback).
Each of four hosts passes 24 both-direction mixed-stack primitive ABI
arrangements with inferred kcc code and ordinary native helpers/drivers; native
linkage does not masquerade as inferred-source support. Sixteen unavailable-name
barriers plus four other constraints are rejected by both modern native hosts;
three UB refusals and thirteen subset refusals are compile-only, never executed.
Auto-explicit/binding/both register suites were rerun on all four hosts with
existing native gap counts unchanged. Old unsupported block-inference assertions
were explicitly replaced by this new positive coverage; file-auto diagnostics
were updated, not silently dropped. Their subset counts are now five/three.

AST assertions verify concrete syntax and cached qualifiers/types, root const
loss on value conversion, no register flag propagation, captured load/array/
function/string identities, one static-string occurrence and seven exact real
slots/reverse-list entries. A failed self-size initializer captures the reserved
INNER local with no type/storage, not the outer typed object; no IL is emitted.
Exact 256/257 locals, 4096/4097 items, 1 MiB/overflow storage, 64/65 parenthesized
identifier nesting and 128/129 expanded-typedef depth boundaries pass. Extra
128 named spills plus inferred local/storage tests retain shared accounting.

Only bare/parenthesized identifiers without a visible typedef ambiguity are
supported. Visible typedef T in auto T=42 or auto (T)=42 remains explicitly
outside this first subset; explicit auto T x is unchanged. Inferred derived
declarators, braced initializers, register combinations, globals, attributes,
constexpr and VM types remain unsupported. Multiple underspecified identifiers
and prior same-scope declarations have UB under N3096 6.7p12: refusal probes
compile only and are NOT required native diagnostics. Register parameters remain
unsupported. This is not full C23 conformance.

M15a2 CI run 38977217404 completed/success, all three jobs green.
M23e0 CI run 38979609085 is still pending; no remote pass is claimed.
New M23e1 exact-commit CI is pending until checked after push; no remote pass
is implied. User authorizes continued work and supersedes historical STOP.
No stashes discarded or old snapshot generators rerun; no subagents used.
Implementation scripts under /data/tools were applied once; do not rerun.
Preserve historical named stashes if a reset restores them. Verify tools/remote
before continuing after any reset. Next increment needs its own recorded design;
register parameter storage has only outside-tree compile-only research so far.

## Earlier M23e0 checkpoint (historical)

M23e0 local-binding semantic preparation is implemented and locally validated.
Read m23-auto-binding-phases.md, m23-auto-inference-research.md and the latest
ledger/contracts/coverage/limits. Private name reservation, storage completion
and initializer analysis functions preserve the old ordinary bind_local order.
Named parameter spills still use adjusted types; prototype names allocate no
runtime storage. No inferred auto or new syntax/type/backend interface was added.
Existing explicit auto/register behavior and all resource/scope invariants remain.

Full make test passed with GCC 11.5/GCC 14.2.1/Clang 18.1.8; full make
test-codegen passed with QBE 1.2 and both modern native hosts. GCC 11 and Clang
15 ASan/UBSan lexer/sema plus 20 targeted suites passed, with the new binding
suite also checked against Clang 18. Normal helpers were built serially before
parallel validation. Primary and isolated source/test/Makefile manifests matched
before/after. Bounded compile-only sanitized fuzz passed 9,612 lexer / 17,298
pipeline inputs in 26 seconds each. No invalid curated or generated C executed.
Logs/manifests /data/tools/m23e0-*, isolated trees /data/validation-m23e0/{gcc,clang}.
Prior M15a2 and frozen M23e0 compiler outputs match byte-for-byte on 149 curated
compile corpus files (117 accepted / 32 rejected), with no C execution.

Read the ledger for four-host original/ABI counts, AST one-pass identity checks,
exact budgets including 128 parameter spills, and the pre-freeze fixture fix.
Inferred auto still needs a fresh final design: outer namesakes are hidden during
initialization but the new name is not yet usable. Multiple underspecified
identifiers are UB in N3096, not a required constraint diagnostic. Never execute
those probes or infer a native compiler bug merely from acceptance.

M15a1 CI run 38972442575 and M15b1 CI run 38974794979 completed/success.
M15a2 CI run 38977217404 remains pending; no remote pass is claimed.
New M23e0 exact-commit CI is pending until checked after push; local passes never
imply remote success. User authorizes continued work; historical STOP superseded.
No stashes discarded; preserve historical named stashes if restored. No historical
snapshot scripts rerun or subagents used. Current implementation scripts under
/data/tools were already applied once; do not rerun. Verify tools after resets.

## Earlier M15a2 checkpoint (historical)

M15a2 explicit-type auto objects is implemented and locally validated. Read
m15-auto-explicit.md and the latest ledger/contracts/coverage/limits. Explicit
auto block/for objects use the ordinary path: same addressability/slots/ABI,
shared bases, complete-declarator publication and no extra storage/type flag.
Missing explicit types/inferred auto, file scope and auto/register combinations
remain explicit refusals. Parameter/type-name auto is forbidden. Register scalar
and non-decaying fixed-array support remains; register parameters, globals, VM
types, array initializers and other storage classes remain unsupported.

Full normal GCC 11/GCC 14/Clang 18, full QBE with both modern hosts, four-host
focused/ABI and both-host ASan/UBSan lexer/sema plus 19 suites passed. Bounded
compile-only fuzz: 9,919 lexer / 28,732 pipeline inputs in 26 seconds
each; no invalid/generated C executed. Serial helpers before parallel runs;
frozen primary/isolated manifests matched. Logs /data/tools/m15a2-*, isolated
trees /data/validation-m15a2/. Read ledger for exact source diagnostic classifiers,
strict C23 agreements versus separate C11 corroborations and boundary evidence.
Do not rewrite valid originals to work around native auto/for-typedef gaps.

M15a1 CI run 38972442575 completed/success, all three jobs green.
M15b1 CI run 38974794979 remains pending; no remote pass is claimed.
New M15a2 exact-commit CI is pending until checked after push, not implied by
local passes. User authorizes continuous work and supersedes historical STOP.
No stashes discarded; preserve historical named stashes if restored. No historical
snapshot generators rerun, and no subagents used. Current /data/tools scripts
were applied once; do not rerun. Next milestone needs a fresh pre-implementation
design; inferred auto has different initializer/name lifetimes. Verify tools
and source/remote state after resets.

## Earlier M15b1 checkpoint (historical)

M15b1 non-decaying fixed register arrays is implemented and locally validated.
Read m15-register-arrays.md and the latest ledger/contracts/coverage/limits.
Complete fixed register arrays use ordinary local slots and support direct
sizeof/typeof queries without decay. Ordinary type copies retain no storage
flag and may decay/index normally. Direct & is still a constraint; decay of the
register array is explicitly refused, even inside an outer unevaluated query.
Never execute register-array decay probes. Register parameters, VM types,
incomplete objects and array initializers remain unsupported. No parser/AST/type
or QBE interface change; scoped identities, shared bases and budgets remain.

Full normal GCC 11/GCC 14/Clang 18, full QBE with both modern hosts, four-host
focused/ABI and both-host ASan/UBSan lexer/sema plus 18 suites passed. Bounded
compile-only fuzz: 7,057 lexer / 30,806 pipeline inputs, 26 seconds
each. Frozen primary/isolated manifests matched; helpers built serially before
parallel validation. No invalid/generated C executed. Read the ledger for exact
counts, explicit subset/refusal categories and pre-freeze fixture corrections.
Logs /data/tools/m15b1-*, isolated sanitizer trees /data/validation-m15b1/.

M15a1 CI run 38972442575 is still pending; no remote pass is claimed.
New M15b1 exact-commit CI is pending until checked after push. Do not infer remote
success from local validation. User authorizes continued development; historical
STOP REQUEST is superseded. No stashes were discarded; preserve historical
named stashes if restored. No old snapshot generators rerun or subagents used.
Current /data/tools implementation scripts were applied once; do not rerun them.
Next increment needs its own pre-implementation design. Verify reset tool paths.

## Earlier M15a1 checkpoint (historical)

M15a1 scalar block/for register objects is implemented and locally validated.
Read m15-register-scalars.md and the latest ledger/contracts/coverage/limits.
Register is declaration storage, not a type qualifier/hardware-register promise.
Objects use ordinary slots; unary & of the register object is rejected even in
unevaluated queries; ordinary pointee addresses remain valid. Type queries carry
no storage class. Shared comma bases, point of declaration, scope restoration,
identity and no-alias-storage invariants remain. Register arrays and parameters
are unsupported valid-C subsets; prototype/definition lifetimes need a separate
design before parameter implementation. Other storage/globals/VM remain absent.

Full normal GCC 11/GCC 14/Clang 18, full QBE with both modern hosts, four-host
focused/ABI and both-host targeted ASan/UBSan lexer/sema plus 17 suites passed.
Bounded compile-only fuzz: 9,125 lexer / 37,520 pipeline inputs in
26 seconds each; no invalid/generated C executed. Frozen primary/isolated
manifests match; helpers built serially before parallel validation. See ledger
for exact native agreements, Clang's keyword-macro diagnostic gap and fixture
corrections. Logs /data/tools/m15a1-*, isolated trees /data/validation-m15a1/.

M14l4 CI run 38958469583 is completed/success, all three jobs green. New M15a1
exact-commit CI is pending until checked after push, not implied by local passes.
The user authorizes continuous development and supersedes the old STOP REQUEST.
No stashes were present/discarded; preserve historical named stashes if restored.
No historical snapshot generators were rerun. Current implementation/test scripts
under /data/tools were already applied once; do not rerun them. No subagents used.
Next increment needs its own pre-implementation design. Verify tools after resets.

## Earlier M14l4 checkpoint (historical)

M14l4 typedef specifier placement is implemented and locally validated. Read
m14-typedef-specifier-placement.md and the latest ledger/contracts/coverage/limits.
One shared specifier scan selects existing concrete alias/ordinary tails at
file/block/for scope, including consumed alias starts. Parameters/type names
reject typedef; duplicate typedefs and all prior constraints remain errors.
Shared bases, actual keyword locations, complete-declarator publication, scoped
bindings and no-alias-storage invariants are tested. Other storage classes,
globals, VM types and bare alias-derived definitions remain unsupported.

Full normal regressions with GCC 11/GCC 14/Clang 18, full QBE with both modern
hosts, both-host targeted ASan/UBSan lexer/sema plus 16 suites, four-host focused
original/ABI checks and exact resource boundaries passed. Frozen manifest/logs:
/data/tools/m14l4-*, isolated sanitizer copies /data/validation-m14l4/{gcc,clang}.
Bounded compile-only fuzz: 6,924 lexer / 17,277 pipeline inputs
in 26/26 seconds; no invalid/generated C executed. Helpers built serially
before parallel validation. Source/test/Makefile hashes matched before/after.
Read the ledger for exact native agreements/gaps and pre-freeze fixture fixes.

a7a9528 correction CI run 38954615388 completed successfully.
The failed c3cc992 GCC run is not retroactively green; a7a9528 was the independent
exact-source native diagnostic correction. New M14l4 exact-commit CI is pending
until queried after push. Local passes are not remote evidence.

The user authorizes continued development; the old STOP REQUEST is superseded.
No stashes were present or discarded; preserve the two historical named stashes
if they reappear after another reset. No old fixture/snapshot generators were
rerun. /data/tools/implement-m14l4-current.py was applied once for this increment;
do not rerun it. No next milestone source/design was implemented; plan its scope
before coding. No subagents were used. Verify tool paths/versions after resets.

## Earlier M14l3b native-oracle correction (historical)

M14l3b's native for-typedef test-oracle correction is locally validated. Read
m14-parameter-native-diagnostics.md and the latest ledger entry. c3cc992 remote
CI failed GCC's normal suite on the valid C23 for-typedef fixture; Clang and fuzz
passed. The exact GCC error spelling is now classified alongside Clang's exact
spelling, only for the unchanged original and ordinary failure status 1. Wrong
sources, signals and additional errors/warnings remain fatal. kcc acceptance,
compiler sources/headers, curated C, Makefile and version are unchanged. Never
rewrite that fixture or reintroduce a C17 for-initializer typedef restriction.

Full normal/QBE with both modern oracles, four-host focused originals/ABI,
verified both-host targeted sanitizers and bounded compile-only fuzz passed:
17,844 lexer / 57,918 pipeline inputs in 26 seconds each. Frozen manifest and
logs are /data/tools/m14l3b-native-* (completed reruns use native-final-*).
System compiler/runtime packages had disappeared between turns; they were
restored before complete validation reruns. New exact-commit CI is pending until
checked after push; the failed predecessor run is not claimed green.

The user continues to authorize development; the old historical STOP REQUEST
remains superseded. No stashes were present or discarded. No subagents used.
Next language increment still needs a separate pre-implementation design.

## Earlier M14l3b checkpoint (historical)

M14l3b is implemented and locally validated. Read
m14-parameter-typedef-shadowing.md, then the latest coverage/limitations/contracts
and ledger entries. The user's explicit resume request on 2026-10-16 superseded
the historical STOP REQUEST below; it is not a new standing pause. No old
snapshot scripts or fixtures were regenerated. Resumed by fresh public clone:
HEAD and origin/development were 966995b, clean; no local stashes existed and
none were discarded. Keep the two historical named stashes if they reappear.

Local validation passed: full normal regressions with GCC 11.5/GCC 14.2.1/Clang
18.1.8 native oracles, full QBE suites with both modern hosts, both-host targeted
ASan/UBSan lexer/sema plus 15 suites, and bounded compile-only fuzz (6,930 lexer /
20,923 pipeline inputs, 26 seconds each). Frozen source/test/Makefile manifests
matched. Focused 48 standard + 6 C23 originals and 24 both-direction mixed-stack
ABI arrangements per host passed; exact GCC named-void and Clang for-typedef gaps
are separate, never native agreements. Read the ledger for complete evidence.
No invalid curated C or fuzz-generated C was executed. Normal helpers were built
serially before parallel validation.

The previous 966995b and all three preceding shadowing checkpoints were verified
green on GitHub. New exact-commit CI remains pending until checked after push;
local passes are not proof of remote CI.

Tool restoration: pinned QBE was rebuilt with scripts/build_qbe.sh at
/data/tools/qbe-1.2/qbe. Native hosts are /usr/bin/gcc (11.5), /usr/bin/clang
(15.0.7), /usr/bin/gcc14-gcc (14.2.1) and /usr/bin/clang-18 (18.1.8), installed
from system packages; no source-rewriting wrappers. Sanitizer runtime packages
are installed. Both targeted sanitizer builds use non-PIE executables to avoid
sandbox ASLR/runtime mapping conflicts. Exact frozen copies are under
/data/validation-m14l3b/{gcc,clang}; logs and manifest are /data/tools/m14l3b-*.
These paths are disposable and must be verified after any sandbox reset.

Next work needs its own small design; do not broaden typedef storage-class
permutations or alias-derived function definitions by merely removing a guard.
Preserve on-demand lexing, shared specifier caches, declaration identity,
no-alias-storage invariants and all existing resource bounds. No next milestone
source or generators have been created. No subagents were used or authorized.

## Earlier M14l3a checkpoint (historical)

M14L3A is implemented and locally validated. Read m14-object-typedef-shadowing.md.
Only changed source/tests/Makefile were copied from /data/next-m14l3a; both
frozen manifest checks matched. Never replace current docs with stale snapshot
docs. Preserve both old stashes. All implementation/test generators were already
applied; do not rerun them. This checkpoint follows 99bbdf0.


M14L3A validation: complete normal/QBE regressions, complete normal
regressions with original-source GCC 14.1.0 and Clang 18.1.8 oracles, and both
GCC 11 / Clang 15 targeted ASan/UBSan lexer/sema/typedef/query/nullptr/control
suites passed. Bounded sanitized fuzz executed 20,122 lexer /
90,589 pipeline inputs in 26/26 seconds. No invalid or generated C
was executed. Four-host focused checks: 44 standard + 5 C23 originals, 8 native constraint rejections, and 24 both-direction
mixed-stack primitive ABI arrangements per host passed. Legacy hosts agree on 44
originals; modern hosts agree on all 49. Expanded for suite: 45+4 originals; GCC 14
agrees on all 49 / 4 constraints; other hosts report exact grammar gaps separately.
AST assertions verify shared written base syntax, captured object identity, nested
alias/object restoration, the implicit long-to-int return conversion and four
object slots with no alias storage.
Frozen manifest /data/tools/m14l3a-source.sha256 matched before and after
integration. Normal test helpers were built serially before parallel validation.
Remote GitHub CI is tracked separately; local passes do not prove remote success.

M14l1c ba11e45 remote run 38927868330 passed ALL jobs. M14l1b dc8967a and
foundation 721e9fd also passed all jobs. Last queried remote runs: 50e457a
38929197527 GCC/fuzz success with Clang sanitizers pending; 3c79ce0 38930527428
fuzz success, GCC sanitizers and Clang QBE pending. Recheck rather than infer.

All four resumed shadowing milestones are landed in predecessor order:
543815c nested aliases; 2a65a40 aliases hiding functions; 99bbdf0 aliases hiding
outer objects/parameters; this commit adds objects hiding aliases. Each passed
its own complete local validation before integration. Existing CI recipes run
all newly added suites and include the new lexer/pipeline fuzz corpus seeds.

STOP REQUEST: the user asked to stop after completing in-progress work to conserve
tokens. Do not start another milestone without a new request. No M14l3b source or
design was implemented. Next work would need a fresh prototype/parameter scope
plan; named parameters hiding aliases remain deliberately unsupported.

M14l3a initial AST test assumptions were corrected before freezing: the translation
unit starts with a typedef (not a function), and returning long from int main
contains an implicit conversion node above its load. An intermediate mistaken
written-cast expectation was stopped, not counted as a pass. Final AST tests,
four-host original-source/ABI focus, full regressions, sanitizers and fuzz passed.
The initial relative-path design write failed; the already drafted design was
persisted during isolated testing, before landing. All generators were already
applied; do not regenerate fixtures. Frozen source manifest and logs are under
/data/tools/m14l3a-*. Resume from GitHub development if the sandbox is stale.

Latest public GitHub CI query before the final commit (not the final commit's
results):
- 99bbdf0 run 38933282375: in_progress, no conclusion yet.
- 2a65a40 run 38932980365: in_progress, no conclusion yet.
- 543815c run 38931895075: in_progress, no conclusion yet.
- 3c79ce0 run 38930527428: in_progress, no conclusion yet.
- 50e457a run 38929197527: completed, success.

## Earlier checkpoint (historical)

M14l1 is implemented and validated. Read m14-file-typedef-foundation.md, including
the shape-safety refinement. All three implementation/test/shape scripts under
/data/tools were already applied; do NOT rerun them. The test generator initially
inserted functions into embedded C strings; this was repaired by placing complete
units before the actual line-anchored test main. No compiler acceptance changed
for that test insertion error. Exact source hashes: /data/tools/m14l1-source.sha256.

M14l1 validation: complete normal and QBE regression, complete normal regression
with original-source native Clang 18.1.8, both GCC 11 / Clang 15 targeted ASan/UBSan
lexer/sema/query/nullptr/control/compound suites, and bounded sanitized fuzz passed.
Fuzz executed 19,290 lexer / 71,849 pipeline inputs in 26/26 seconds; no generated
C or invalid curated source ran. Focused typedef suite: 42 standard + 10 C23
original programs, 13 strict native constraint rejections, 24 mixed-stack ABI
arrangements per host, canonical AST/cache identity and exact external/function/
item/expanded-shape/depth boundaries. GCC 11 / Clang 15 agree on all 42 standard
programs; GCC 14.1 / Clang 18 agree on all 52 originals, with no query rewriting.
Only the exact keyword-macro fixture needs Clang's style warning disabled; the
unchanged source and pedantic errors remain. Public CI is not a local-pass claim.
The full normal run and GCC targeted void suite preceded the independent native-
warning classifier correction; final focused void checks and complete QBE/modern
Clang runs include that correction. No compiler source changed during validation.

Independent test-only correction 9bf0a40 is committed/pushed. Runs 38922632027 /
38922740646 passed fuzz but failed GCC's old named-void nonzero-status assertion.
GCC 14 emits two exact warnings and strictly rejects the other ten fixtures;
Clang 18 strictly rejects all twelve. Classify only exact sources and single
warnings, separately from strict rejection/runtime agreements; no kcc rule change.
Read m14-void-native-diagnostics.md. Four-host normal and both frozen sanitizer
binaries with both modern native oracles passed. Its CI remains pending.

Next M14l1b same-type typedef redeclarations is already implemented ONLY in
/data/next-m14l1b. Read m14-typedef-redeclarations.md. Its scripts are already
applied. Focused four-host tests and full/sanitizer/fuzz runs have separate logs
/data/tools/m14l1b-*. Do not copy its source into the primary checkout until this
foundation is committed and that exact frozen snapshot finishes validation.
Transfer only changed source/tests/Makefile, not stale docs; verify the manifest
/data/tools/m14l1b-source.sha256. Preserve both older stashes.
Modern native GCC 14.1.0 is /data/tools/gcc14-native/gcc: a compact compiler using
host startup/link libraries via explicit sysroot/-B paths, not C-source rewrites.
Clang 18.1.8 is /data/tools/clang18/bin/clang-18. Tools remain under 1 GiB.

The M23d2 null-conversion correctness fix passed complete normal/QBE regression,
both-host targeted ASan/UBSan and bounded sanitized fuzz: 10,946 lexer / 45,467
pipeline inputs in 26/26 seconds. No generated C or invalid curated program ran.
Clang 18.1.8 passed all 25 original null-conversion programs, 20 strict native
constraints and four actual C23 cross-object nullptr ABI arrangements, also with
a sanitized kcc. Expression queries passed 69 originals: 65 native agreements,
one exact array-unqualification gap and three exact explicit-nullptr-cast gaps,
plus 17 strict constraints. These gaps are not native agreements. The normative
assignment constraint, not stale N3096 footnote 127, admits integer/void-pointer
null pointer constants to nullptr_t. See m23-nullptr-assignment-conversions.md.
The implementation scripts were already applied; do not reapply them.

M14k2 is now integrated from /data/next-m14k2; its exact frozen source/test
SHA-256 manifest matched before and after transfer. Do NOT reapply implementation
scripts. Read m14-query-function-declarations.md.
M14k2 final validation: complete normal/QBE regression passed, as did a separate
complete normal regression using original-source native Clang 18.1.8 oracles.
Both GCC 11 / Clang 15 targeted ASan/UBSan lexer/sema, query/nullptr/control and
compound suites passed. Focused Clang 18: 34/34 original native agreements,
12/12 strict native constraints; all three hosts passed 24 mixed-stack primitive
ABI arrangements, declaration-only IL, immutable query/composite annotations and
256/257 function / 512/513 external-declaration boundaries. Legacy hosts lack
actual C23 keywords and are not counted as native query agreements. Sanitized
bounded fuzz passed 17,747 lexer / 76,739 pipeline inputs in 26/26 seconds.
No generated C or invalid curated source executed. SHA-256 verified exact frozen
source/test bytes before and after integration from /data/next-m14k2. Public CI
for this increment remains pending; no isolated full sanitizer-matrix claim.

Historical next design m14-file-typedef-foundation.md is now implemented above.
Preserve both older stashes. Compact Clang 18.1.8 is available under
/data/tools/clang18/bin/clang-18 (~247 MiB).


M14k1 sole query-derived void parameter normalization passed full normal/QBE
regression, both-host targeted ASan/UBSan and bounded sanitized fuzz (20,758 lexer /
61,639 pipeline inputs, 26/26 seconds). Focused: 38 original programs, 12 constraints,
24 zero-argument primitive-result ABI arrangements per host, syntax/subset/128/129
real-parameter boundaries and no marker ABI slot. GCC 11/Clang 15 provide three
ordinary baseline native agreements each; a subsequent Clang 18.1.8 exact-source run passed all 38 native programs and
12 strict native constraint rejections, plus QBE and all 24 ABI arrangements. No generated C or invalid curated source ran. Written ast_parameter nodes retain query
syntax/type/is_void_marker, but semantic signature and QBE ABI counts omit the
marker. Main checks the semantic signature count; header/spill traversals skip
markers before width or index calculation. Literal void/empty lists and real
unnamed parameters retain their old behavior. No fake parameter nodes/names.
Read m14-void-parameter-normalization.md. implement-m14k1.py is applied; do not
reapply. Next correctness design: m23-nullptr-assignment-conversions.md, before
m14-query-function-declarations.md (not implemented). M14k1 was stashed during that independent oracle fix; its interrupted full and
sanitizer runs are not passes. Those full runs were restarted from scratch and passed. Stash restoration
had documentation-only conflicts; both the complete correction history and M14k1
sections were preserved. No source conflicts occurred. The environment restart
removed installed Clang; clang/compiler-rt 15
were restored before repeating both-host focused validation. Keep older stashes.

M23d2 05097e6 expression queries are committed/pushed. Final local full normal/QBE,
both-host targeted ASan/UBSan and sanitized bounded fuzz passed (15,177 lexer /
39,321 pipeline, 26/26 seconds). Focused: 65 original programs, 17 constraints,
64/65 mixed-query boundaries, no operand call in IL and 24 primitive ABI cases
per host. GCC 11/Clang 15 lack actual C23 keywords, not native agreements.
Public CI 38918142442 failed both native reference jobs on the exact expression-
array b[1] read-only diagnostic; fuzz passed. Independent test-only correction
6893ce3 is committed/pushed after both-host normal/QBE and sanitized focused tests,
classifier units and bounded fuzz (16,211 lexer / 34,704 pipeline, 26/26 seconds).
Only the observed source/diagnostics is a native gap, not agreement. No compiler
source or semantic acceptance changed. Its CI 38919183328 passed fuzz but failed
GCC on the obsolete integer-zero-to-nullptr implicit rejection and Clang on valid
explicit null-constant-to-nullptr casts. The normative N3096 assignment constraint
admits null pointer constants; contradictory footnote 127 was stale (N3220 keeps
the normative rule and removes that footnote). Correct kcc implicit conversions
next, not GCC acceptance classification. Retain valid cast tests and classify
only exact Clang diagnostics/source separately from native agreement. Its isolated
matrix is running independently on an archived snapshot, not this working tree.
Scripts implement-m23d1.py / implement-m23d2.py are already applied.

M23d1 391fd01 and independent oracle fix e77cd0a are pushed. The original CI
38909406525 failed native nested-array unqualification oracles; corrected
e77cd0a CI 38911835030 passed all jobs. Only the exact original source/read-only
diagnostics is a native gap, never agreement; kcc follows N3096 unchanged.
M19f1 cff28ab public CI 38904988323 and isolated full GCC/Clang matrix passed;
M19f2 84797f7 public CI 38907237071 passed, isolated GCC passed/Clang incomplete.
Old process handles disappeared on provider restart: inspect logs and running
processes before treating old queues as active. User requests continuous tested
milestones, periodic commit/push, no arbitrary fuzz C execution, no subagents.

### Earlier foundation (chronological)

M18a implementation: fixed sizeof/alignof with checked unevaluated operands;
prior M19b conditional scalar/void values and immutable pointer composites;
prior M23a1 C23 bool/true/false typed constants and raw macro separation;
prior M14j2 const syntax/enforcement, immutable qualified types,
value/signature normalization and qualified pointer conversions; prior M19a sequenced comma values/discards with separate argument and
declaration separator floors; M14i explicit object/function-category pointer casts; prior object/void value conversions and mixed equality; prior real void types/functions, bare returns and effect-only
casts/discards; prior explicit function designators/decay, callback values and
indirect fixed calls; concrete fixed-function declarator syntax/array-pointer returns,
C23 unnamed definitions with positional ABI and no fake spills,
grouped local/for-header declarators,
incomplete array referent pointers and composite declarations,
single-pass parenthesized object/abstract declarators,
omitted outer array parameter bounds and effective adjustment,
adjacent ordinary static byte strings, fixed multidimensional arrays
and explicit decay/target layout, pointer
subscripts, scaled offsets, signed-long differences and compatible
comparisons, plus concrete address/indirection ASTs and general object lvalue
addresses, with pointer mutation, fixed calls/returns/casts
and scalar truth. Integer/pointer syntax resolves a separate semantic type graph.
All baseline primitive integers, ordinary byte characters, explicit conversions,
on-demand tokens, RDP/Pratt and single-file stages remain intact.
Branch: development. Public repository: https://github.com/0x6432/kcc
Commit identity: 0x42 <noreply@localhost> (repository-local).
Get the exact latest hash with git log -1; avoid a circular self-commit reference.

Latest confirmed exact-source CI: M19a 95a99d7 run 38861248497, M14i
1ed1cc8 run 38860337750 and M14h 274d966 run 38859812046 passed.
M14j1 6e7ff50 run 38861821792 passed. M14j2 b26ff3b run 38863255999
also passed. M23a1 fe26eb4 run 38864340577 and M19b 0c0ef33 run 38865164586
were still running; M18a remote/full isolated checks remain pending. M14g full GCC/Clang normal and
ASan/UBSan matrix passed; queued newer snapshots need actual log confirmation.
Logs/snapshots live in /data/tools and /data/validation-* outside the repo.

Next: M18b1 integer constant-evaluation foundation, designed in
m18-integer-constant-evaluation.md; then source-level requirements, null constants
and generalized constant bounds. Qualifier/typedef work remains separate.
Null constants, integer/pointer casts and full declarators,
general array bounds/initializers, string encodings and remaining
C23 features stay unfinished. &*null cancellation
is valid and tested using host-supplied null; actual invalid dereferences are
never executed. Read current limitations, not old checkpoint entries alone.

Working policy: continue across small milestones without asking for approval;
stop only for a real blocker or user interruption. Preserve rigorous regression,
QBE/reference/ABI, sanitizer/fuzz checks and commit/push each tested checkpoint.
Never execute arbitrary fuzz-generated C. Keep credentials ephemeral and outside
the repository. No subagents are authorized.

## Resume safely

1. Clone/fetch the public repository; reading requires no credentials.
2. Compare git rev-parse HEAD with git ls-remote origin refs/heads/development.
3. Preserve uncommitted/divergent work; fast-forward only a clean safe checkout.
4. Read architecture.md, milestones.md, limitations.md and component-contracts.md.
5. Run make clean && make test. If needed, build pinned QBE with
   sh scripts/build_qbe.sh tools, then run
   make test-codegen QBE="$PWD/tools/qbe-1.2/qbe".
6. Restore Clang/compiler-rt if missing; run make fuzz-lex fuzz-compile.
7. Obtain push authorization when needed. Do not put credentials in the repo,
   remote URLs, documentation or logs. Commit/push each tested checkpoint.

## Architecture and interactions

source_load/source_from_bytes still load raw bounded bytes. source_prepare
runs explicitly before pp_lexer_init and before any token spelling is borrowed.
It normalizes CRLF/lone CR, then deletes immediate backslash-newline pairs
while traversing original physical units. Do not rescan newly adjacent output.
This precedes comment recognition, so continued line comments and split comment
markers are intentional. No whitespace after backslash splice extension.

Prepared source.data/length and token spelling offsets/lengths are logical bytes.
Name lookup, types and QBE symbols keep using contiguous logical spelling.
Changed sources own optional physical_data/physical_length plus sparse offset
checkpoints; unchanged sources keep identity offsets without an extra buffer.
Lone CR changes bytes but needs no offset checkpoint. source_physical_offset
binary-searches the map; logical EOF maps to original EOF. Diagnostics use
physical lines/columns with eight-column tabs; --tokens prints physical starts.
Never use physical offsets to index logical spelling data.

Preparation is idempotent and transactional on allocation failure. Call it only
on an initialized source, before any borrowed spellings; destroy frees optional
buffers/maps too. Both fuzz harnesses and every lexer caller were updated.
Future callers must prepare explicitly; pp_lexer_init asserts this precondition.
No full-file token vector or new parser grammar/API was introduced.

M09b adds pp_token/pp_token_kind and pp_lexer in lex.h/lex.c. Raw numbers have
no value, keywords are identifiers, and punctuators use longest spelling first.
Raw quotes recognize ordinary/u8/u/U/L prefixes and escaped delimiters without
interpreting values. Invalid/partial tokens diagnose once and advance. Raw ASCII
other characters are preserved until conversion; UCN/Unicode/header-name context
is not complete. No per-token allocations or TU token vector.

pp_token carries leading_space, at_line_start and has_non_directive_space.
External newlines are explicit tokens and reset line-start state. A block
comment, including internal newlines, is one space; it does not end a directive.
Line comments stop before their newline. leading_space does not include an
already-emitted newline; a macro consumer must handle that explicit token.
VT/FF outside comments set has_non_directive_space; the preprocessor validates it only
in directive separators after # (not before #). EOF and repeat-peek flags are
stable, with no repeated diagnostics.

A stateless token_from_pp still converts raw tokens in lex.c; it must not receive
pp_newline and never rediagnoses pp_invalid. The temporary struct lexer adapter
has been removed. preprocess.c owns raw input and the sole parser-facing next/
peek cache. parse_translation_unit now takes struct preprocessor; every driver/
test/fuzz consumer migrated. No grammar/AST/sema/codegen changes. --tokens shows
language tokens after null removal; --pp-tokens remains raw inspection with its
unchanged physical_offset:kind:logical_length:leading_space:at_line_start:
non_directive_space format (one line, final three fields 0/1).

Only raw #/%: with at_line_start dispatches. Null directives accept space/tab/
comments up to external newline or the documented EOF extension. VT/FF before
# is allowed, after it outside comments fails. That diagnostic anchors the next
token/terminator; its returned error token marks the nonempty directive marker.
Unknown/unsupported/malformed/misplaced directives fail and drain their raw line,
without converting body numbers or keywords. Raw-invalid names retain lexical
locations/diagnostics; distinct lexical errors while draining may add errors.
Repeated peek/EOF never duplicates them. Debug inspection can continue next line;
compilation stops on errors and produces no IL. Null-only streams are accepted
here; the current parser still rejects an empty TU. M10a adds macro state below.

One implementation file per stage, concrete AST structs, on-demand lexer with
one cached token, recursive descent/BNF comments and Pratt expressions remain.
The TU contains an ordered external declaration list; prototypes and definitions
are distinct structs. Each definition references its declaration header. Sema
registers canonical functions in source order before checking definition bodies;
there is no forward hoisting. Prototypes share compatible name-independent types.
Calls resolve visible function symbols, respecting local ordinary-name shadowing.
Bare function values and indirect calls are unsupported.

Each parameter has a semantic local backlink. Parameters receive the first slots
and share the outermost body scope; nested blocks may shadow them. Scoped lookup
is separate from the all-local storage list. Scope/loop contexts restore on
failure and reset between functions. Call/loop/parameter semantic backlinks are
not ownership edges; do not recursively traverse them as AST children.
Sema runs once and inserts explicit lvalue loads, including in call arguments.
Source outlives AST/symbol spellings; destroy the arena before the source.

QBE codegen emits exported int functions with w parameters/results, entry alloc4
slots and stores for parameters. Local initialization stays at source positions.
All argument IL, including nested control flow, finishes before emitting a call
line. Argument lowering is left-to-right, not a C sequencing guarantee. Labels,
temporaries and loop frames reset per definition. Logical phi predecessors use
the actual current block label. A terminated block is not proof a loop returns.

## Supported subset and limits

Int literals/locals/parameters/returns; arithmetic, simple assignment, signed
comparisons, !/&&/||; scoped blocks, if/else, while/do/for, break/continue;
function prototypes/definitions, direct calls and direct/mutual recursion.
C23 () and (void) specify zero parameters. Prototype names optional; definition
names required until later C23 work. Main must take no parameters. Library units
need no main. Declared undefined functions are the host linker's responsibility.
Main fallthrough returns zero. Non-main ABI zero filler is not a promised C
implicit return value. No automatic local zeroing or missing-return warning.

Raw quoted literals and punctuators do not enable their C semantics. Only brace
digraphs are newly accepted language spelling; int-only conversion still applies.
Null/define/undef, object-like and fixed/variadic function macros are supported,
including __VA_ARGS__/__VA_OPT__, raw parameter #/%: and #__VA_OPT__. No token
pasting, C string expressions, other directives, other
types, pointers/function values, variadic functions, local
prototypes, globals/storage classes, comma/update/compound-assignment operators.
Partial phases only: no header-name context, encoding/UCNs/BOM,
#line presumed locations or full expansion-stack notes yet. Missing terminal newlines
remain an acceptance extension, not strict phase-2 validation. No synthetic
newline is appended. Allocation failures are handled but fault injection is
not yet tested. No full C23 conformance claim. Resource limits: 16 MiB source, expression and
statement nesting/typed depth 128, 512 external declarations, 256 functions,
128 parameters/arguments, 256 parameter/local slots and 4096 body items/function.
Runtime recursion has no added stack guard. Tests execute bounded defined C;
fuzzing compiles arbitrary inputs but never executes them.

## Tests and environment

GCC 11.5.0, Clang 15/compiler-rt and QBE 1.2 were used locally. Dependencies may
vanish after resets; keep artifacts small under the 4 GB sandbox budget. QBE
release/checksum are pinned in scripts/build_qbe.sh. Locally it is available at
/data/tools/qbe-1.2/qbe; do not assume that external path survives a reset.
GCC sanitizer SONAME lookup may need external /data/tools/sanitizer-runtime
links plus LD_LIBRARY_PATH, -fno-pie and -no-pie. CI needs no local workaround.

Tests cover syntax/constraints/AST, runtime/reference execution, source-order
visibility, signature compatibility, parameter/body scopes and resource bounds.
Separate-object ABI cases run both directions with 0/1/2/6/7/8/12/128 arguments,
signed boundaries and cross-compiler mutual recursion. CI selects GCC/Clang as
host compilers and runs executable/ABI tests with sanitized compiler builds too.
M09a adds source/oracle/physical-position regressions to make test and tests
phase-ordering executable behavior under LF/CRLF/CR. A binary corpus seed keeps
intentional NUL/high or CR bytes; ordinary source corpus files use LF. Existing
CI runs all source tests, compiler sanitizers, QBE/reference/ABI and both fuzz
paths. Final local/fuzz results and remote verification follow below.

## Next milestone

M11c: token pasting. Read m11-optional-stringizing.md and m11-stringizing.md.
Design #/## ordering, raw versus expanded operands, left/right empty arguments,
placemarker propagation/removal and optional-body interactions before coding.
Re-lex a synthesized spelling as exactly one pp token; do not source-prepare it
as physical input or accept concatenated multi-token results silently. Preserve
hide-set/provenance ownership and bound retained generated bytes/work. Decide
which small #/## subset to validate first; stringizing inside optional operands
must remain substitution-only until the appropriate operator phase completes.
Includes/conditions need separate bounded source/evaluation designs. No silent
GNU comma swallowing. M25 still owns predefined provenance and the audit gaps.

M10c uses concrete arena-owned macro_parameter, macro_argument and argument_token
records. Definition tokens have parameter_index or SIZE_MAX. Parameter name/order
is part of compatibility. Each invoked fixed macro owns an argument array;
arguments retain raw and lazy cached prescan lists. Empty () is zero arguments
for a zero-parameter macro, one empty argument if parameters exist. Only nested
parentheses protect commas; collect before expansion and check arity first.
Unused arguments are lexed/collected but not macro-expanded.

preprocessor.cursor is the main source cursor. A prescan cursor is temporary
heap storage, with isolated argument input and synthetic EOF: it cannot steal
following source. Prescan does not prematurely add the enclosing macro's hide
bit. Each substituted token unions its own cached hide set with the call base.
Cached tokens are immutable. Frames stream definition tokens or argument tokens;
parameter occurrences inject streams rather than flatten whole replacements.
A separate pending unexpanded token remains distinct from language lookahead.

Source directive LINES during invocation probing/collection still explicitly
fail; inline # is an ordinary argument token and can be discarded. Generated #
never dispatches. Prescan does not convert numbers/keywords to language tokens,
so a later unused parameter can discard unsupported literals. Raw-invalid input
retains lexer diagnostics. Errors/resources stop once then latch EOF; malformed
definitions retain line draining and preserve the old binding.

Ownership/init/destroy APIs are unchanged; destroy preprocessing after AST use
and before source. Diagnostics use the outermost macro call; spelling remains
original. Raw lexical errors retain physical input locations. Future __LINE__/
__FILE__ support must review richer argument provenance, not guess from these
outermost diagnostic offsets. Fixed argument metadata never reaches the C AST.

Limits: 1024 names, 1024 replacement tokens/definition, 65536 retained definition
tokens, 128 retained frames, 65536 work units. New: 128 fixed parameters, 128
argument parentheses, 64 nested prescans, 65536 auxiliary records across parameter
nodes, invocation array entries and raw/cached token copies (including abandoned
attempts). Work includes argument collection/input/copying and injected streams.
No arena reclamation before destroy; temporary cursor malloc/free is paired on
all paths. Fuzz checks main cursor/cache state, auxiliary bounds and prescan
unwind. The oracle now has 374 streams under GCC and Clang; old unit/runtime/ABI
regressions remain. Do not mistake host agreement for full C23 conformance.

Run normal GCC/Clang, stream/source/oracle/AST, QBE/reference/ABI, ASan/UBSan and
both fuzz paths. Clang/compiler-rt vanished on this resume and were restored with
sudo dnf install -y clang compiler-rt; do not assume dependencies persist. Commit/
push each tested checkpoint and update docs. Final M10c local/fuzz results are
recorded below; verify its remote CI independently after pushing.

Diagnostic performance note: line/column lookup rescans physical prefixes;
raw-line draining with many lexical errors can be superlinear. There is no
error-count cap yet. Preserve existing fuzz input/time limits and consider
line indexing/diagnostic caps with M10 resource design, rather than claiming a
large-hostile-input CPU bound from the byte limit alone.

M09c local verification passed: GCC/Clang, directive/cache/EOF/raw/conversion/CLI,
source/oracle/AST, QBE/reference executables, separate-object ABI and ASan/UBSan.
Final sanitized fuzzing: 69628 lexer/preprocessor and 126498 pipeline inputs in
26 seconds each; earlier runs passed (54419/127155 in 21 seconds each).
The null-directive fixture compiles/links and exits 7. Retained build artifacts
were under 10 MiB; external dependencies under 70 MiB. M09c remote CI was
verified successful on resuming M10a (link above).


M10a local verification passed: GCC 11.5 and Clang 15 strict normal builds and
ASan/UBSan builds; CLI/source/raw/token/cache/provenance/limit/AST regressions;
97 token/spelling oracle cases with each host compiler; QBE/reference execution
and separate-object integer ABI with both hosts. Final sanitized fuzzing passed
43915 lexer/preprocessor and 125308 full-pipeline inputs in 26 seconds each.
An earlier 26-second run passed 52672/136498 inputs. Both harnesses exercise the
real macro stage and never execute arbitrary generated code. A final normal
make test passed and --version reports m10a. Compiler build artifacts remain
under 10 MiB after cleanup; external tools/logs under 75 MiB. Remote CI is
verified separately after pushing; obtain the current hash from git log -1.


## M10b recovery verification checkpoint

Recovered files passed make test, 198 token/spelling oracle cases with GCC and
Clang, GCC-host QBE/reference runtime and separate-object ABI tests. Sanitized
libFuzzer runs passed 60392 lexer/preprocessor and 169562 pipeline inputs in
26 seconds each, with both new seed files in both harnesses. No arbitrary
generated programs were executed. The sandbox reset had destroyed uncommitted
work; this tested recovery checkpoint is pushed before the longer local matrix.
Normal/sanitized GCC/Clang full-matrix and exact pushed-commit CI verification
are still pending at this checkpoint. Do not infer those passes from fuzzing.


## M10b final verification

The pending validation above was completed after the recovery checkpoint.
GCC 11.5 and Clang 15 passed strict normal and ASan/UBSan builds, source/raw/
conversion/CLI/AST/cache/provenance/limit tests, the 198-case token/spelling
oracle, QBE/reference programs and separate-object integer ABI tests. Fuzzing
passed 60392 lexer/preprocessor and 169562 pipeline inputs in 26 seconds each,
without executing arbitrary generated code. Source commit c3ee142 also passed
GitHub CI: https://github.com/0x6432/kcc/actions/runs/38749074367

M10b is complete for its zero-parameter subset. Named arguments, argument
prescan/substitution and variadics remain unimplemented, as documented above.
The subsequent verification commit only records results; it changes no compiler
code. Verify its own remote CI separately after push. Future resumes must fetch
and compare the latest development hash before editing; the sandbox really did
lose uncommitted files and dependencies during this checkpoint.


## M10c tested implementation checkpoint

Local make test passed, including all argument/unit/resource/provenance tests.
The 374-case token/spelling oracle passed with GCC and Clang. GCC-host QBE/
reference execution and separate-object integer ABI passed. Sanitized fuzzing
passed 52567 lexer/preprocessor and 168281 full-pipeline inputs in 26 seconds
each, with new argument corpus seeds. Arbitrary generated code was not executed.
This checkpoint is pushed before the longer full GCC/Clang normal/ASan/UBSan
matrix to protect work from resets. That matrix and exact pushed-commit CI are
still pending here; do not infer them from fuzzing. Final evidence follows later.


## M10c final verification

The pending matrix above is complete. GCC 11.5 and Clang 15 each passed
strict normal and ASan/UBSan builds, all unit/rejection tests, the 374-case
macro token/spelling oracle, QBE/reference execution and separate-object
integer ABI tests. The full matrix was rerun after replacing the new limit-test
string generator with a bounds-checked vsnprintf builder: GCC 11 diagnosed
its previous unchecked sprintf construction under sanitizer optimization and
-Werror. No production code changed and no warning was suppressed.

Sanitized fuzzing passed 52567 lexer/preprocessor and 168281 pipeline inputs
(220848 total), without executing arbitrary generated code. Source checkpoint
8538ed4 passed GitHub CI:
https://github.com/0x6432/kcc/actions/runs/38755902384
The subsequent test/documentation verification commit must have its own remote
CI checked after push. M10c is complete only for the fixed-parameter subset;
M10d variadics and M11 macro operators/includes/conditions remain outstanding.


## M10d implementation checkpoint

Read m10-variadics.md for decisions recorded before coding. Variadic macros
allocate one final argument slot, retain internal raw commas and reuse isolated
lazy prescan. Optional regions are validated/annotated on the flat definition
list and stream through the current replacement frame when selected. Empty
expanded variable arguments suppress them. Definition validation and compatible
redefinition remain transactional. No parser/AST/sema/QBE API changed.

New tests cover omitted/empty/expanded-empty tails, callbacks and rescan across
optional boundaries, suppression, arity/definition/provenance errors and exact
limits. Both fuzz paths have variadic/optional seeds. Final validation evidence
will be recorded below; do not infer passes from this implementation record.


## M10d tested implementation checkpoint

make test passed with 564 token-kind/spelling oracle cases; the same oracle
passed with Clang. GCC-host QBE/reference programs and separate-object ABI
tests passed, including 16 new variadic runtime programs under LF/CRLF/CR.
Unit tests cover 128 named parameters plus a variable slot, exact 1024-token
optional definitions, 64/65 nested variadic prescans and bounded large tails.
Sanitized fuzzing completed 40473 lexer/preprocessor and 170004 pipeline inputs
(210477 total) in 26 seconds each, without executing arbitrary generated code.

The source checkpoint is pushed now to protect against sandbox resets. The
full GCC/Clang normal/ASan/UBSan matrix and exact-commit remote CI are pending;
these results must be checked separately before marking M10 complete. No new
parser, AST, sema or QBE interfaces; M11 operator/directive work remains deferred.


## M10d final verification

The pending validation above is complete. GCC 11.5 and Clang 15 each passed
strict normal and ASan/UBSan builds, all unit/CLI/AST/rejection tests, the
564-case token-kind/spelling oracle, QBE/reference execution and separate-object
integer ABI tests. The 16 new variadic runtime programs run with LF, CRLF and
lone CR endings. Both existing and new macro regressions remain covered.
Sanitized fuzzing completed 40473 lexer/preprocessor and 170004 pipeline inputs
(210477 total), without executing arbitrary generated code.

Source commit 34760ff passed GitHub CI:
https://github.com/0x6432/kcc/actions/runs/38759964506
This following documentation-only verification commit has its own exact-commit
CI checked after push. No production change followed the tested source commit.

M10a-M10d are complete for the documented object/function macro subset. M11
operators/includes/conditions, predefined macros, full preprocessing and the
remaining C23 language/ABI milestones are not complete. Next: design a small
M11a stringizing checkpoint, accounting for borrowed versus synthesized spelling,
raw arguments, whitespace/escaping and __VA_OPT__ semantics before coding.
Token pasting needs its own re-lex/placemarker design, not a shortcut extension.


## M11a implementation checkpoint

All production stringizing code is in preprocess.c. Arena-owned prepared source
views and byte buffers preserve existing token layouts while allowing non-input
spellings. Both parser language conversion and expanded-pp reads share one cursor;
choose a mode and never bypass pending language lookahead. See the stringizing
design, current limitations and latest component contract before changing this.

New tests cover raw/no-prescan behavior, escaping, empty/variadic arguments,
optional-body operators, transactional definition validation, generated lifetime,
original-call diagnostics, cache/EOF stability and exact single/cumulative 1 MiB
bounds. The expanded-pp fuzz path re-lexes generated strings and checks their
source ownership. Five explicit whitespace-policy groups distinguish host
disagreements from 564 language + 142 expanded-pp agreement streams. Follow-up
ISO interpretation audit is still needed; do not overstate host agreement.
Final local/fuzz and exact-commit remote results will be recorded below.


## M11a tested implementation checkpoint

make test passed, retaining 564 language-token oracle streams and adding 142
expanded-pp agreement streams. Both GCC and Clang passed the 706 agreement
cases and five separately recorded whitespace-policy groups. GCC-host QBE/
reference execution and separate-object ABI tests passed, including eight new
stringize-then-discard programs under LF/CRLF/CR. Single and cumulative 1 MiB
spelling boundaries, generated-source lifetime and cached conversion errors pass.
Sanitized fuzzing passed 19909 lexer/preprocessor and 114717 pipeline inputs
(134626 total) in 26 seconds each; arbitrary generated C was not executed.

This source checkpoint is pushed before the longer full normal/ASan/UBSan
GCC/Clang matrix to protect work from sandbox resets. That matrix and exact
pushed-commit CI are pending and must be checked separately. The subset excludes
#__VA_OPT__, ##, directives beyond define/undef/null and C string expressions.
The host whitespace differences remain a documented conformance-audit gap.


## M11a final verification

The pending validation above is complete. GCC 11.5 and Clang 15 each passed
strict normal and ASan/UBSan builds, all unit/CLI/AST/rejection tests, 564
language + 142 expanded-pp agreement streams and the five explicit whitespace
policy groups. QBE/reference execution and separate-object integer ABI tests
passed with both hosts and sanitizer builds. The eight new discard-path runtime
programs cover LF, CRLF and lone CR. Generated lifetime, original invocation
errors, cache/EOF stability and exact single/cumulative spelling caps passed.

Sanitized fuzzing passed 19909 lexer/preprocessor and 114717 pipeline inputs
(134626 total), without executing arbitrary generated code. Source commit
3640b6d passed GitHub CI:
https://github.com/0x6432/kcc/actions/runs/38763520175
The public API rate limit required authenticated CI reads using already authorized
GitHub access; temporary credentials were removed, never committed. This following
documentation-only commit has its own exact-commit CI checked after push.

M11a is complete for raw named/variadic parameter stringizing, not all # operator
forms or full C23 preprocessing. The five host whitespace disagreements remain
an explicit interpretation/conformance audit item, not counted as agreement.
M11b must implement #__VA_OPT__ with correct argument substitution and pre-rescan
boundaries. Token pasting, includes/conditions and C string semantics remain
separate future checkpoints. No production change followed the tested source.


## M11b implementation checkpoint

Read m11-optional-stringizing.md for pre-implementation decisions. The only new
production algorithm is in preprocess.c: selected optional bodies use exclusive
range cursors with parameter/inner-# substitution before ordinary rescan. Normal
frames have a NULL range end. Temporary body copies use existing arena records;
helper cursors are malloc/free pairs, limited to 32 active helpers and restored
to zero on all exits. No AST/parser/sema/QBE change. Empty operands generate "".

New tests preserve 706 previous agreements and add 134 expanded-pp cases, plus
one explicitly non-agreement inactive-argument diagnostic policy. Unit tests
check exact 32/33 nesting without exponential strings, failed-definition recovery,
original call locations, generated lifetime/caches and byte-limit cleanup.
Both fuzz seed paths include nested optional stringizing and discard programs.
Final validation evidence will be recorded below; do not infer it from this entry.


## M11b tested implementation checkpoint

make test passed, with 564 language + 276 expanded-pp agreement streams under
GCC and Clang. Five inherited whitespace policies and the additional inactive-
argument diagnostic policy are recorded separately, not counted as agreement.
GCC-host QBE/reference execution and separate-object ABI passed, including eight
new optional-stringize/discard programs under LF/CRLF/CR. Unit tests passed exact
32/33 helper nesting, byte-limit error cleanup, definition recovery and original
invocation diagnostics. Both active cursor counters return to zero on errors.
Sanitized fuzzing passed 26326 lexer/preprocessor and 151927 pipeline inputs
(178253 total) in 26 seconds each; arbitrary generated programs were not executed.

The source checkpoint is pushed before the longer full GCC/Clang normal and
ASan/UBSan matrix to protect against sandbox resets. That matrix and exact-
commit CI must be verified separately before marking M11b complete. Token pasting,
other directives and C string expressions remain outside this implementation.


## M11b final verification

The pending full matrix above is complete. GCC 11.5 and Clang 15 each passed
strict normal and ASan/UBSan builds, all unit/CLI/AST/rejection tests, 564 language
plus 276 expanded-pp agreement streams, five separate whitespace-policy groups
and one separate inactive-argument diagnostic policy. QBE/reference execution
and separate-object integer ABI tests passed with both hosts and sanitizer builds.
The eight new optional-stringizing discard programs cover LF/CRLF/lone CR.
Exact 32/33 helper nesting, failed-definition recovery, call-site diagnostics,
owned generated spellings and error-counter/cursor cleanup passed.

Sanitized fuzzing passed 26326 lexer/preprocessor and 151927 pipeline inputs
(178253 total), without executing arbitrary generated code. Source commit
c0928a7 passed GitHub CI:
https://github.com/0x6432/kcc/actions/runs/38766305589
This following documentation-only verification commit has its own exact-commit
CI checked after push. No production change followed the tested source commit.
Temporary push/API credentials were removed and never committed.

M11b is complete for optional stringizing without token pasting. The five
whitespace and one inactive-argument diagnostic disagreements remain explicit
interpretation/conformance audit gaps, not agreement claims. Next M11c needs a
small, reviewed token-pasting design covering raw operands, re-lex validation,
placemarkers and optional-region/operator interactions before implementation.
Includes/conditions, predefined macros, C string expressions and full C23 remain
unfinished. Preserve the exclusive substitution-only range contract when adding
operator phases; do not substitute a full ordinary macro rescan for it.

## M11c source checkpoint

Implemented ##/%:%: with definition validation, raw argument boundary pastes,
placemarkers, generated token re-lexing, optional-region and stringizing phases.
See m11-token-pasting.md for rationale. No parser/sema/codegen expansion needed;
generated keywords and names flow through existing language conversion.

Local make test, GCC-host QBE/reference execution and separate-object ABI passed.
GCC/Clang oracles each passed 564 language + 444 expanded-pp agreements; one
normative C23 H4 example (legacy GCC disagreement) and five whitespace plus one
inactive-argument diagnostic policy groups are counted separately. Sanitized
fuzzing passed 21801 lexer/preprocessor and 137656 pipeline inputs (159457 total),
26 seconds per target, without executing arbitrary generated code. Exact 32/33
paste nesting and shared 1 MiB spelling boundary tests passed, with counter
cleanup and failed-definition recovery. Full GCC/Clang normal + ASan/UBSan
matrix and source-commit CI are pending and must be recorded after completion.

The user's updated instruction is to continue across milestones without asking
for approval, stopping only for a real blocker or interruption. Next implement
small diagnostic directives, then continue the preprocessing roadmap. Keep
checkpoint pushes and handoff evidence current. Do not claim full C23 coverage.

## M11c final verification and M11d start

The full local GCC/Clang normal and ASan/UBSan matrix completed successfully
before the previous interruption (both MATRIX PASSED lines are in the saved
log). Source commit 66920ed passed remote GitHub CI:
https://github.com/0x6432/kcc/actions/runs/38773969266
No production changes followed that validation. M11c is complete within its
documented scope. M11d diagnostic directives are designed in
m11-diagnostic-directives.md before implementation; validation is not yet claimed.

## M11d tested source checkpoint

#error/#warning implementation, designated diagnostic initialization and separate
warning counts are implemented. GCC make test and QBE/reference/ABI execution
passed. The 1008 inherited macro agreement streams and separately counted policy
cases remain passing. New diagnostic tests cover 48 directive inputs across
three driver modes, LF/CRLF/CR and digraph markers, host preprocessing status,
24 warning-bearing QBE runs, two diagnostics in one compilation, and a long
adjoining-token message. Unit tests check warning/error counts, stable peek,
raw macro spelling, string/number messages, comments, empty/EOF bodies,
physical spliced locations and malformed bodies. Sanitized fuzzing passed 14547
lexer/preprocessor + 89800 pipeline inputs (104347 total), 21 seconds each.
No arbitrary fuzz-generated program was executed.

Full GCC/Clang normal/sanitizer matrix and source-commit CI are pending at this
checkpoint. Validation will use a committed isolated snapshot to avoid racing
continued M11e implementation. The Clang packages disappeared in the sandbox
reset and were restored. Source/documentation are the durable state, not tools.
M11e is designed in m11-macro-conditions.md; no implementation claimed yet.

## M11d final verification

The isolated fce649b snapshot passed the full GCC/Clang normal + ASan/UBSan
unit/CLI/oracle/QBE/reference/ABI matrix. Both MATRIX PASSED records are in
/data/tools/m11d-final-validation.log (the path is a local aid, not durable
source evidence). Exact-source remote CI passed:
https://github.com/0x6432/kcc/actions/runs/38803546331
M11d is complete within its documented scope. The diagnostic input count above
is corrected to 48 inputs, each checked in all three driver modes.

## M11e tested source checkpoint

Macro-existence conditionals and excluded-group filtering are implemented.
GCC make test and QBE/reference/ABI passed. New conditional streams cover 321
host agreements with each GCC/Clang; four explicit C23 alternative cases agree
with Clang but are separately counted as legacy GCC 11 nonagreements. Twelve
new LF/CRLF/CR QBE/reference programs passed. Units cover structural/operand
errors, 128/129 nesting, define/undef effects, excluded directives, EOF and
stable caches. Existing macro/diagnostic suites remain passing.

Initial pipeline fuzzing caught a real boundary bug: deferred EOF diagnostics
could coexist with a non-NULL parser AST. Fixed parse_translation_unit's final
success check, added a direct AST test and minimized conditional-eof corpus seed.
The corrected final sanitizer fuzz runs passed 25799 lexer/preprocessor and
141778 pipeline inputs (167577 total), 26 seconds per target; no generated code
was executed. Do not count the earlier failing run as successful validation.

Full isolated GCC/Clang normal/sanitizer matrix and exact-source CI are pending
at this checkpoint. M11f initial expression design is recorded before coding in
m11-conditional-expressions.md. Active expression #if/#elif remains unsupported
by M11e; includes and full C23 are unfinished. Preserve the EOF/parser contract.

## M11e final verification

Isolated committed snapshot de93224 passed the full GCC/Clang normal +
ASan/UBSan unit/CLI/oracle/QBE/reference/ABI matrix. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38805070048
M11e is complete within its macro-existence scope, including the fuzz-found EOF
parser-success fix and regression. No production changes were made to its
validation snapshot while later milestones were developed.

## M11f tested source checkpoint

Initial #if/#elif evaluation is implemented in preprocess.c, using signed-decimal
64-bit arithmetic and an isolated macro cursor. Literal defined operands are
handled before expansion; remaining identifiers become zero (C23 true/false
are 1/0). Arithmetic checks avoid host UB and logical short circuit suppresses
evaluation, not expansion or syntax checks. Raw reserved variadic identifiers
are rejected consistently, including inside defined operands.

GCC make test and QBE/reference/ABI passed; 540 new host/model agreements passed
with each GCC/Clang, plus eighteen LF/CRLF/CR QBE/reference expression programs.
Units cover precedence, defined/paste/function macros, signed min/max overflow,
zero division, inactive arithmetic, malformed syntax, explicit unsupported
literal/operator cases, and exact 128/129 recursion and 1024/1025 raw-token
limits. Existing tests remain passing. Final sanitized fuzz runs passed 21975
lexer/preprocessor and 96461 pipeline inputs (118436 total), 21 seconds each.
No arbitrary generated program was executed. Earlier exploratory runs are not
included in this final-source count.

Full isolated matrix and exact-source CI remain pending at this source
checkpoint. See m11-conditional-expressions.md for the supported subset and
m11-signed-operators.md for M11g's pre-recorded design. Do not claim unsigned,
nondecimal/character literal, remaining-operator or include support yet.

## M11g tested source checkpoint

Remaining signed preprocessing operators are implemented: ~, shifts, & ^ | and
right-associative ?: with arithmetic short circuit. Negative right shifts follow
the documented target policy using nonnegative host operations. Evaluated left
shifts and counts are checked; conditional branches still parse when unselected.
No runtime C expression/type expansion is implied.

GCC make test and QBE/reference/ABI passed. The expanded expression oracle passed
642 host/model streams with each GCC/Clang. Thirty LF/CRLF/CR expression programs
passed QBE/reference execution. Added exact 127/128 ternary-chain depth boundary
units; inherited arithmetic, raw-token, diagnostic and macro tests remain passing.
Sanitized fuzzing passed 25625 lexer/preprocessor and 123113 pipeline inputs
(148738 total), 26 seconds per target, without executing arbitrary generated C.

M11g full isolated matrix and exact-source remote CI are pending. M11f's longer
isolated matrix/CI also remain pending at this checkpoint; do not mark either
verified before their own results complete. M11h signed integer spellings are
designed in m11-integer-spellings.md before implementation. Unsigned arithmetic,
character constants and include handling remain later work.

## M11f final verification

Committed isolated c52dd27 passed both full GCC/Clang normal + ASan/UBSan
matrices, unit/CLI/oracle tests and QBE/reference/ABI execution. Exact-source CI:
https://github.com/0x6432/kcc/actions/runs/38806159321
M11f is complete within its signed-decimal subset. Later source work did not
modify the validation snapshot. M11g's separate full matrix/CI remains pending.

## M11h tested source checkpoint

Conditional signed integer scanning now separates prefix/base, digit/separator
and suffix validation. Supported bases include octal, hex and C23 binary; signed
L/LL forms and valid C23 separators are accepted up to INT64_MAX. Runtime C
conversion is unchanged. Valid unsigned forms/values still diagnose explicitly.

GCC make test and QBE/reference/ABI passed. Added 94 common literal host/model
agreements with each GCC/Clang and seven independently asserted C23 separator
cases (legacy GCC 11 rejects all seven; Clang agrees). Eighteen new LF/CRLF/CR
literal-selection programs passed QBE/reference execution. Malformed base digits,
prefixes, suffixes/separators and numeric overflow have regression tests. Existing
642 expression, 321 conditional and 1008 macro stream agreement cases remain
passing, with their separately counted normative/policy cases unchanged.
Sanitized fuzzing passed 27905 lexer/preprocessor and 114789 pipeline inputs
(142694 total), 26 seconds each, without executing arbitrary generated programs.

Full isolated matrix and exact-source CI for M11h remain pending; M11g's matrix
is queued/running separately after M11f. Do not call either completed until its
own results are checked. M11i unsigned-value semantics are designed in
m11-unsigned-conditions.md, not implemented at this checkpoint. Use an explicit
value type, retain unselected ternary branch types, and preserve signed checks.

## M11i tested source checkpoint

Preprocessing values now carry explicit uint64 bits and signedness. U suffixes,
large nondecimal constants, intmax/uintmax conversions and wrapping arithmetic
are implemented. Comparisons/logical results are signed; shifts preserve the
left type; ?: derives its common type from both parsed branches even when one
contains unselected arithmetic errors. No runtime C type/AST changes.

GCC make test and QBE/reference/ABI passed. New unsigned tests passed 302
host/model agreements with each GCC/Clang, including 250 modeled value-and-type
binary cases, boundary arithmetic, macro-pasted suffixes and nested ternary/
logical/shift result types. Fifteen LF/CRLF/CR unsigned-selection programs passed
QBE/reference execution. Inherited signed, literal, conditional, macro and
resource tests passed. Sanitizer fuzzing passed 26702 lexer/preprocessor and
106993 pipeline inputs (133695 total), 26 seconds per target, without executing
arbitrary C. A final brace-style-only cleanup was followed by passing unit tests;
full committed-snapshot sanitizer validation still needs separate confirmation.

M11i full isolated matrix and exact-source CI remain pending. M11g remote CI
passed run 38806781592, but its longer local matrix and M11h's full validation
still need final checks. M11j ordinary single-byte preprocessing characters are
designed in m11-character-conditions.md, not yet implemented. Keep signed target
character policy explicit; do not silently extend runtime types or Unicode.

## M11g final verification

Isolated a934115 passed the full GCC/Clang normal + ASan/UBSan unit/CLI/oracle
and QBE/reference/ABI matrix. Its exact-source remote CI also passed:
https://github.com/0x6432/kcc/actions/runs/38806781592
M11g is complete within its signed-operator scope. M11h/M11i later source
checkpoints retain their independent pending validation status until checked.

## M11j tested source checkpoint

Ordinary preprocessing characters now decode single ASCII bytes and standard
simple/octal/hex escapes. Numeric escapes are checked to 0..255 and mapped via
the chosen signed plain-char target policy. Empty/multicharacter, prefixes,
non-ASCII source bytes, universal names and unknown escapes remain explicit
rejections. No C runtime char type or general encoding support is implied.

GCC make test and QBE/reference/ABI passed. New character tests passed 126
chosen-target host/model agreements with each GCC/Clang, including printable
ASCII, all simple escapes, numeric boundaries/sign extension, unsigned/ternary
conversions and macro expansion/identity pasting. Twelve LF/CRLF/CR character
selection programs passed QBE/reference execution. Invalid/unsupported literal
forms diagnose even when unselected. Sanitizer fuzzing passed 26062 lexer/
preprocessor and 106415 pipeline inputs (132477 total), 26 seconds each, without
executing arbitrary generated code. All inherited suites remain passing.

M11j full isolated matrix and exact-source CI are pending. M11h source CI passed
run 38807421895; its local matrix and M11i full verification still need final
checks. M11g local/remote verification is complete as recorded above.
M11k direct quoted includes are designed in m11-quoted-includes.md before coding;
loader/source ownership and fuzz-safe memory-only loading are required. Do not
claim include support, header search paths or full C23 at this checkpoint.

## M11h/M11i final verification

Isolated snapshots 26e27e4 and 0e0a0db both passed full GCC/Clang normal +
ASan/UBSan unit/CLI/oracle and QBE/reference/ABI matrices. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38807421895
https://github.com/0x6432/kcc/actions/runs/38808207982
M11h/M11i are complete within their documented integer subsets. M11j remote CI
also passed run 38809079871, but its separate local matrix was still running
when this entry was written. Keep that distinction explicit.

## M11k tested source checkpoint

Direct quoted includes now use an explicit loader, resolve relative to the
including source or use an absolute path, retain child source buffers until
preprocessor destruction, and share macro state. Conditional bases prevent
cross-file groups. Raw directive readers and macro invocation lookahead see
file EOF; only ordinary expansion resumes the parent. A GCC/Clang audit found
and fixed the initial boundary mistake where header F acquired parent ().
The header EOF regression also rejects incomplete macro calls across files.

GCC make test and QBE/reference/ABI passed. Ten include pp streams agree with
each host, including all nine root/header newline combinations and the macro
EOF boundary. Nine nested-header programs passed QBE/reference execution;
absolute paths, missing final newlines, guards, skipped loads, malformed names,
load errors and original/spliced child diagnostics are covered. Unit memory
loaders check retained spellings, conditional isolation and stable root EOF,
32/33 active-depth and 128/129 attempt limits, 4095/4096 path bytes, plus actual
four 16 MiB child loads at the 64 MiB byte budget and a rejected fifth load.

Sanitizer fuzzing passed 27441 lexer/preprocessor and 107479 pipeline inputs
(134920 total), 26 seconds per target. Pipeline includes are memory-only: requested
paths never reach the filesystem, while arbitrary header bytes, loader failures,
recursion and successful prototype-only units exercise the new boundaries. No
arbitrary generated C is executed. The lexer fuzz preprocessor remains loader-
disabled, preserving its root/generated-spelling provenance assertions.

Full isolated M11k matrix and exact-source CI are pending. M11j source CI passed,
but its local matrix still needs its final result checked. M11l macro-computed
quoted operands are designed in m11-computed-includes.md before coding. Anchor
relative search to the directive source (not generated/header-definition spelling
sources) and never drain the next source line after isolated operand validation.
No angle/system/-I support or complete C23 claim is made yet.

## M11j final verification

Isolated 73b76f8 passed the complete GCC/Clang normal + ASan/UBSan matrix,
unit/CLI/oracle and QBE/reference/ABI execution. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38809079871
M11j is complete within its ordinary-character scope. M11k verification remains
independent and pending until its own matrix/CI results are checked.

## M11l tested source checkpoint

Macro-computed quoted operands now rescan one bounded isolated directive line.
Relative lookup uses the directive source, not the generated string spelling or
macro definition directory. Invalid expanded operands never consume the next
source line. Directive collectors retain each token's invocation location, so
computed include and conditional macro errors point to the call site.

GCC full tests and QBE/reference/ABI execution passed. Computed include tests
agree with both GCC and Clang on 24 streams each, covering object/function,
stringizing/pasting, empty replacements, all newline forms, source-directory
anchoring and malformed/missing operands. All 24 QBE/reference programs passed.
Sanitized fuzzing passed 22969 lexer/preprocessor and 89116 pipeline inputs
(112085 total), 26 seconds each, without executing arbitrary generated C.
Full isolated M11l normal/sanitizer matrix and exact-source CI remain pending.
M11k exact-source CI passed run 38810635063; its local GCC matrix passed, while
its local Clang matrix is still running. M11m bounded -I/angle search is designed
in m11-include-search.md before implementation. No full C23 claim is made.

## M11k final verification / M11l validation repair

326bcc3 passed both isolated GCC/Clang normal + ASan/UBSan matrices with all
unit/CLI/oracle and QBE/reference/ABI checks. Exact-source CI passed run
38810635063. M11k is complete within its documented scope.

M11l 0ffd06c normal/runtime and fuzz tests passed, but its isolated GCC sanitizer
build failed -Werror=format-overflow in test_computed_include_operands. CI run
38812216340 likewise failed the GCC sanitizer step (fuzz passed, Clang cancelled).
Repair 37857c4 replaces the fixture's sprintf loop with explicitly bounded byte
writes and is pushed. Its isolated full matrix and exact-source CI are pending;
do not claim the original source passed or conflate normal/fuzz with full CI.

## M11m tested source checkpoint

Bounded explicit include search and direct/computed basic angle names are
implemented. Direct angle identifiers never expand, while computed operands
retain isolated rescanning. One logical include can try 33 candidates; failed
candidate buffers are destroyed, and successful source ownership is unchanged.
The driver and oracle accept ordered attached/separate -I options in all modes.

Full normal GCC regressions, QBE/reference/ABI, targeted GCC ASan/UBSan units,
and 39 new header streams with each of GCC/Clang passed. All 39 new QBE/host
programs passed. Tests include quote/angle ordering, nested search, filename
spaces, direct-macro collisions, absolute and empty-directory behavior, 32/33
directories, actual 33-candidate cleanup, lexical subset errors and diagnostics.
Sanitized fuzzing passed 25488 lexer and 92079 memory-only pipeline inputs
(117567 total), 26 seconds each, without executing arbitrary generated programs.
Full isolated M11m host/sanitizer matrix and exact-source CI are pending.
M12a signed-int operators are designed in m12-integer-operators.md before coding.

## M12a tested source checkpoint

Runtime signed-int unary ~ and binary & ^ | << >> are implemented across token
conversion, Pratt parsing, concrete AST operators and QBE lowering. Sema retains
explicit lvalue loads and int-only depth checks; the word backend uses and/xor/
or/shl/sar. The parser's BNF and precedence table include the new operators.

GCC full normal regressions/QBE/reference/ABI and 102 full-value operator/model
programs passed; the 102 also passed Clang host/QBE execution. Comparisons inside
C check all 32 result bits, not only process status. Cases cover precedence,
associativity, arithmetic negative right shift, assignments, sequencing, loops,
calls, token paste, typed AST loads and rejection/depth constraints. Undefined
shift inputs are never executed. Sanitized fuzzing passed 25260 lexer and 83847
pipeline inputs (109107 total), 26 seconds each, with no arbitrary C execution.
Full isolated M12a host/sanitizer matrix and exact-source CI are pending.

M11l repair 37857c4 exact-source CI passed run 38812950255. Its isolated local
GCC matrix passed; the local Clang matrix remains in progress. M11m full local
matrix is queued after it and remote CI is still running. M12b shared integer
spelling decoding is designed in m12-integer-spellings.md before implementation.

## M11l repaired checkpoint final verification

37857c4 passed the full isolated GCC/Clang normal + ASan/UBSan matrix with
unit/CLI/oracle and QBE/reference/ABI execution. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38812950255
M11l is complete within its computed-quoted scope. The original 0ffd06c failure
is preserved above; this success belongs to its explicit fixture repair.
M11m and M12a validation remain separate and pending their own matrix/CI checks.

## M12b tested source checkpoint

The pure bounded decoder in lex.c now serves both preprocessing and language
conversion. Runtime unsuffixed decimal/octal/hex/binary/separator literals are
accepted within signed-int range. U/L/LL runtime suffixes and values requiring
wider types remain explicit errors, while preprocessing retains intmax/uintmax.
Its old signed-only integer grammar comment and context-specific spelling
messages were corrected alongside the refactoring.

GCC full normal regressions/QBE/reference/ABI and all shared-decoder units passed
(90 base/suffix combinations, malformed/overflow cases and exact byte slices).
Runtime spelling tests passed 50 GCC host programs plus six separately modeled
legacy separator gaps; Clang accepted all 56 originals. All 56 QBE/model programs
passed with each host, with macro-paste/newline and range-rejection regressions.
Sanitized fuzzing passed 24002 lexer/decoder and 92882 pipeline inputs (116884
total), 26 seconds each, including a pure-decoder uint64 decimal round-trip
invariant. Arbitrary generated C is never executed. Full isolated M12b host/
sanitizer matrix and exact-source CI are pending.

M11m remote CI passed run 38813251318; its local GCC normal/sanitizer matrix
passed, local Clang still running. M12a local GCC likewise passed; local Clang
and exact-source CI still need final verification. M12c unsigned-int types and
explicit AST conversions are designed in m12-unsigned-int.md before coding.

## M11m and M12a final verification

d33f7ae and b80ec53 each passed their full isolated GCC/Clang normal + ASan/UBSan
matrices, including unit/CLI/oracle and QBE/reference/ABI execution. Exact-source
CI passed for M11m run 38813251318 and M12a run 38813971204. Both are complete
within their documented scopes. M12b validation remains independent.

## M12c tested source checkpoint

Signed/unsigned 32-bit int now flows through declaration syntax, literal base/U
metadata, distinct semantic types, generic function signatures and explicit
integer conversion AST nodes. Sema implements usual arithmetic conversions and
destination contexts; shifts retain left type and logical/comparison results
remain int. QBE uses validated types to choose unsigned division, remainder,
comparisons/right shift, while low-word copies implement int/uint conversion.
Common AST headers remain first; type specifiers are separate from annotations.

GCC full normal regressions/QBE/reference/ABI passed. New typed AST tests cover
loads and conversion placement in initialization, assignment, arithmetic, calls
and returns; conversion-only depth overflow is rejected. Both GCC and Clang
passed 130 full-value model/QBE programs and separate-object mixed int/uint ABI
calls in both directions, including high bits and eight arguments. Malformed
specifier/signature/range cases and old diagnostic-provenance regressions pass.
Former U rejection fixtures now use still-unsupported L suffixes intentionally.
Sanitized fuzzing passed 24121 lexer and 85617 pipeline inputs (109738 total),
26 seconds each, with no arbitrary generated program execution. Full isolated
M12c normal/sanitizer matrix and exact-source CI are pending.

M12b exact-source CI passed run 38815061741; its isolated local full matrix is
still running and must be checked separately. M12d explicit int/unsigned casts
are pre-designed in m12-integer-casts.md. Other integer ranks remain absent.

## M12d tested source checkpoint

Explicit int/unsigned casts now have their own concrete AST nodes. Parser
consumes '(' before choosing type syntax or a grouped primary with the shared
postfix suffix helper; the public token cache remains one token. Sema loads and
types cast operands, preserves non-lvalue results and checks structural depth.
QBE copies target word bits; implicit conversion nodes remain distinct.

Full normal GCC regressions/QBE/reference/ABI passed. All 71 new full-value
model/host/QBE programs passed with GCC and Clang, including nested casts,
comparison/division/right-shift signedness, grouped named calls, macro type
specifiers and side effects. Typed cast/load AST checks, malformed casts,
non-lvalue assignments and exact parser/typed-depth boundaries pass. Sanitized
fuzzing passed 25342 lexer and 87518 pipeline inputs (112860 total), 26 seconds
each, without arbitrary generated C execution. Full isolated M12d normal/
sanitizer matrix and exact-source CI remain pending.

M12b/M12c full local verification remains pending independently; M12c remote CI
is still running. M12e LP64 long/unsigned long is designed before implementation
in m12-long-integers.md, including a successful curated QBE width/extension probe.
Do not claim compiler long support until that separate increment is implemented.

## M12b final verification

98b9a03 passed its isolated GCC/Clang normal + ASan/UBSan matrix, including all
unit/CLI/oracle and QBE/reference/ABI checks. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38815061741
M12b is complete within its recorded spelling scope. M12c/M12d verification
remains separate; do not substitute M12b evidence for those later sources.

## M12e tested source checkpoint

LP64 long/unsigned long now extends declarations, U/L literal candidate typing,
casts, semantic usual conversions and QBE word/long values, memory and calls.
Target width/rank/signedness lives in type.c. Widening uses source signedness;
narrowing preserves low words. Every branch/logical path normalizes the entire
value before jnz, and 64-bit shift counts narrow explicitly only after typing.
Long long and LL suffixes remain intentionally unsupported for the next step.

Full normal GCC regressions/QBE/reference/ABI passed. New type tests cover all
16 usual-conversion pairs, literal candidate identities and widening/narrowing
AST nodes. All 138 full-width model/host/QBE programs passed with GCC and Clang,
including high-only-bit truth in !/logical/if/while/do/for, mixed ranks, recursion,
unsigned wrap and signed division. Mixed word/long eight-argument separate-object
ABI calls, extensions and returns passed both directions with both hosts.
Old L/range rejection fixtures moved to still-unsupported floating numbers or
unrepresentable decimal values, preserving their diagnostic purpose explicitly.
Sanitized fuzzing passed 25253 lexer and 81809 pipeline inputs (107062 total),
26 seconds each, without executing arbitrary generated C. Full isolated M12e
host/sanitizer matrix and exact-source CI remain pending.

M12c exact-source CI passed run 38816221787; local GCC matrix passed, local
Clang remains pending. M12d local GCC likewise passed; Clang/remote still need
final verification. M12f distinct long-long rank and suffixes are designed in
m12-long-long.md before coding. Equal width must not imply compatible types.

## M12c final verification

37d33e9 passed the isolated GCC/Clang normal + ASan/UBSan matrix (including
all QBE/reference/ABI checks). Exact-source CI passed run 38816221787. M12d
exact-source CI also passed run 38817002032, with its local Clang leg still
running at this observation. These are separate source-specific results.

## M12f tested source checkpoint

Long long and unsigned long long now have distinct compatible-type identities
and rank above long, sharing its 64-bit representation. Full six-type conversion
matrix and literal candidates are covered by AST/type units. Same-width long
versus long-long prototypes conflict. LL/ULL runtime suffixes and valid two-long
specifier permutations are accepted; malformed suffixes and three-long remain
errors. Backend width-based lowering is unchanged.

Full normal GCC regressions/QBE/reference/ABI passed. All 93 new full-width
model/host/QBE programs passed with GCC and Clang; mixed-width eight-argument
long and long-long separate-object ABI tests passed both directions with both
hosts. Sanitized bounded lexer/pipeline fuzzing passed (counts below), without
executing arbitrary generated programs. Full isolated M12f GCC/Clang normal/
ASan/UBSan matrix and exact-source CI remain pending. M12g ordinary runtime
character constants are pre-designed in m12-character-constants.md.

M12f fuzz counts: lexer 23668, pipeline 86086 (109754 total), 26/26 seconds.

## M12d final verification / M12e remote verification

66e7c07 passed its isolated GCC/Clang normal + ASan/UBSan matrix, including
QBE/reference/ABI. Exact-source CI passed run 38817002032. 609164f (M12e)
exact-source CI passed run 38818409002; its isolated local matrix remains
pending independently. M12f CI is running at this observation.

## M12g tested source checkpoint

Ordinary character constants now have distinct language tokens and concrete AST
nodes, with int type/non-lvalue semantics. Preprocessing/runtime share a pure
explicit-slice character decoder. All 256 target byte values have octal/hex unit
coverage; 617 printable/escape checks in 44 full-value host/model/QBE programs
passed with GCC and Clang. Macro and pasted-prefix diagnostics retain invocation
locations; source splicing and three line-ending forms pass. Former valid 'x'
rejection became unsupported 'xy', preserving its original lexical boundary.

Full normal GCC regression/QBE/reference/ABI passed, including prior conditional
character oracles. Direct decoder and on-demand stream invariants are fuzzed.
ASan/UBSan bounded fuzzing passed 24619 lexer and 81387 pipeline
inputs (106006 total), 26/26 seconds,
without executing arbitrary generated C. Full isolated host/sanitizer matrix
and exact-source CI remain pending. M12h char types, promotions, canonical byte
values and QBE sub-word ABI are designed in m12-char-types.md before coding;
its curated QBE mechanics probe passed with both hosts, not compiler ABI yet.

## M12f remote verification

619ba96 passed exact-source CI run 38819398360 (GCC/Clang normal and sanitizer
jobs plus bounded fuzz). Its isolated local matrix is queued separately; do not
claim that queued run completed. M12g exact-source CI is still in progress.

## M12h tested source checkpoint

Three distinct byte types now flow through declarations, signatures, casts,
storage and calls. Sema explicitly promotes bytes to int for unary arithmetic
and binary/shift operands. Values remain canonical signed/unsigned words, with
byte ABI return normalization before any use. QBE base types, ABI names and
memory operations are separate helpers; byte locals use alloc4 1.

Full normal GCC regressions/QBE/reference/ABI passed. New 462 width/sign checks
in 69 full-value host/model/QBE programs passed with GCC and Clang. Typed AST
units cover identity, promotion nodes and usual-conversion combinations. Exact
typed-depth 128/129 boundaries, assignment narrowing, macro types, loops and
prototype conflicts pass. Both-direction mixed eight-argument byte ABI and
deliberately dirty upper-return bits passed with both hosts. The first depth
fixture accidentally formed ++ tokens; spacing unary + fixed the test, not the
compiler. No source workaround or relaxed depth bound was introduced.

ASan/UBSan bounded fuzzing passed 23257 lexer and 80030 pipeline
inputs (103287 total), 26/26 seconds,
without arbitrary generated program execution. Full isolated normal/sanitizer
matrix and exact-source CI remain pending. M12i short/unsigned short, inter-rank
conversions and halfword ABI are designed in m12-short-types.md before coding;
a curated QBE mechanics probe passed both hosts, not yet compiler short support.

## M12e final verification

609164f passed the isolated GCC/Clang normal + ASan/UBSan matrix, including
QBE/reference/ABI. Exact-source CI passed run 38818409002. M12f/M12g isolated
matrices are now running separately; M12h is queued behind them. M12g/M12h remote
CI remains pending at this observation.

## M12g remote verification

d4db0ef passed exact-source CI run 38820235372: GCC and Clang normal/sanitizer
jobs plus bounded fuzz all completed successfully. Its isolated local matrix
is still running. M12h remote normal/sanitizer steps remain in progress.

## M12i tested source checkpoint

Short/unsigned short now have 16-bit storage, rank between char and int,
independent promotion to int and canonical halfword values in QBE words.
Valid declaration permutations and short/signed-short identity are supported.
sh/uh ABI results normalize before any use, memory uses halfword operations,
and two-byte locals use stronger alloc4 alignment without changing C alignment.

Full normal GCC regressions/QBE/reference/ABI passed. 700 width/sign checks in
68 full-value host/model/QBE programs passed with GCC and Clang, including all
eleven current integer types, byte/halfword crossings, signed and unsigned
promotions, assignments, returns, shifts, macro types, loops and typed-depth
128/129 boundaries. Both-direction mixed-eight-argument halfword ABI and dirty
upper-return bits passed with both hosts. Existing byte and long tests still pass.
ASan/UBSan bounded fuzzing passed 24007 lexer and 76502 pipeline
inputs (100509 total), 26/26 seconds,
without arbitrary generated C execution. Full isolated host/sanitizer matrix
and exact-source CI remain pending. M12j _Bool is designed in m12-bool-type.md:
whole-value conversion is distinct from discarding unspecified ABI upper bits.
C23 bool/true/false remains planned M23a; _Bool is the next baseline type increment.

## M12h remote verification

76944c4 passed exact-source CI run 38821148738, including GCC/Clang normal and
sanitizer jobs plus bounded fuzz. Its isolated local full matrix remains queued
separately; M12i remote CI is still running.

## M12j tested source checkpoint

_Bool now has distinct type identity, rank below char, storage one byte and
canonical 0/1 values. Explicit value conversion compares the whole source width;
ABI return normalization independently drops unspecified upper bits. Unary/binary
promotions, assignment/init/fixed argument/return conversions and exact signature
compatibility follow the existing typed AST pipeline. C23 keyword/constants are
still planned M23a, not represented with fake int-valued macros.

Full normal GCC regressions/QBE/reference/ABI passed. 418 width/sign checks in
36 full-value host/model/QBE programs passed with GCC and Clang. Tests cover
high-only-bit long and even integers, narrowing-before-bool distinctions,
negative values, assignment normalization, once-only side effects, short-circuit
skips, typed-depth boundaries and invalid specifier/prototype combinations.
Both-direction mixed-eight-argument bool ABI and valid-low-byte/dirty-upper-bit
returns passed with both hosts. The first INT64_MIN fixture incorrectly used an
unrepresentable positive decimal magnitude after unary minus; it now uses the
standard (-MAX-1) expression, without relaxing compiler literal constraints.
ASan/UBSan bounded fuzzing passed 23090 lexer and 79394 pipeline
inputs (102484 total), 26/26 seconds,
without arbitrary generated C execution. Full isolated normal/sanitizer matrix
and exact-source CI remain pending. M13a pointer declarations and concrete type
syntax are pre-designed in m13-pointer-declarations.md; no pointers implemented
at this checkpoint. Local source syntax migration must retain every integer test.

## M12f/M12g final local verification / M12i remote verification

619ba96 and d4db0ef each passed their isolated GCC/Clang normal + ASan/UBSan
matrices, including QBE/reference/ABI. Their exact-source CI also passed runs
38819398360 and 38820235372 respectively. 81db52e (M12i) exact-source CI passed
run 38821949608. M12h/i/j isolated matrices are running independently at lower
CPU priority so foreground implementation/regressions can progress; no tests
were stopped or omitted. M12j exact-source CI remains pending.

## M13a tested source checkpoint

Declarations/parameters/returns/casts now use concrete integer/pointer syntax
nodes; sema caches separate semantic types, including parameter-local reuse.
Pointer compatibility recursively checks referents; scalar width is separate
from integer rank. Pointers use l/loadl/storel/alloc8 ABI/storage and full-width
truth. Unsupported pointer operations/conversions diagnose before integer helpers.

Full normal GCC regressions/QBE/reference/ABI passed, retaining all integer
literal, conversion and exact-depth behaviors after syntax migration. Pointer
AST/type-cache and compatibility units passed. Both GCC and Clang host-driven
live-object ABI tests passed both linkage arrangements, including eight mixed
pointer arguments, pointer-to-pointer identity, null-pointer truth supplied by
the host and compatible casts. All 19 rejection constraints and exact 64/65
pointer syntax bounds pass. No fabricated/dangling/uninitialized addresses were
executed. ASan/UBSan bounded fuzzing passed 21992 lexer and 69401
pipeline inputs (91393 total), 26/26
seconds, without arbitrary generated C execution. Full isolated host/sanitizer
matrix and exact-source CI remain pending. M13b is pre-designed; lvalue access
must become address-based rather than encoding indirection as a local slot.

New isolated matrix jobs use an external flock queue and lower CPU priority;
existing M12h/i/j snapshots finish independently. This scheduling changes no
validation coverage. Logs/snapshots remain outside the repo and may disappear
on a sandbox reset; remote exact-source CI is the persistent evidence.

## M12j remote verification

1735825 passed exact-source CI run 38822838501: GCC/Clang normal/sanitizer jobs
and bounded fuzz completed successfully. Its isolated local GCC normal/sanitizer
leg passed; Clang is running. M13a remote CI remains pending independently.

## M13b tested source checkpoint

Address-of and indirection now have concrete AST nodes, object-lvalue semantics
and general address lowering. Address computation is separate from value loads;
names copy their slot address and indirection evaluates its pointer operand once.
Every scalar object width/sign uses the existing typed memory helpers. &*E never
loads the pointee, preserving valid cancellation even for host-supplied null.

Full normal GCC regressions/QBE/reference/ABI passed. 53 new full-value host/model/
QBE programs passed with GCC and Clang, covering every primitive integer object,
pointer-to-pointer mutation, recursion, assignment conversion and once-only
address/load/store operand evaluation. Both-direction eight-argument host memory
mutation checks verify byte/halfword/word/long/bool/pointer writes, exact address
identity and &*null cancellation. Typed AST tests and exact 63/64 dereference
semantic-depth boundaries pass; syntax's separate 64-layer limit is unchanged.
No invalid/dangling/uninitialized pointer was executed. ASan/UBSan bounded fuzz
passed 20205 lexer and 59948 pipeline inputs (80153
total), 26/26 seconds, without arbitrary generated C execution.
Full isolated normal/sanitizer matrix and exact-source CI remain pending. M13c
pointer equality is pre-designed; existing integer comparison semantics must
remain unchanged and pointers must never enter integer signedness queries.

## M13c tested source checkpoint

Pointer ==/!= requires recursively compatible types and produces int without
integer promotions or pointer signedness queries. QBE compares full-width long
addresses. Full normal GCC regressions/QBE/reference/ABI and 15 new full-value
programs passed; the new suite also passed with Clang. Separate-object live/null
host tests cover both linkage directions, every primitive and deep referent,
once-only calls, assignment results and short circuit. Typed AST units pass.
The earlier now-valid p==p rejection is changed to p&p, a permanent pointer
operation constraint. No general integer-pointer/null-constant conversion added.
Sanitized bounded fuzz passed 22894 lexer + 73861 pipeline inputs (96755 total),
26 seconds each. Arbitrary generated C was not executed. Full isolated matrix
and exact-source CI remain pending; M13d is designed but not implemented yet.
M13a exact-source CI passed 38823808449; M13b run 38824691700 is in progress.

## M13d tested source checkpoint

Sema lowers parsed pointer arithmetic to concrete typed offset/difference nodes,
sharing already analyzed children and explicitly promoting only integer indices.
Object size is target storage size, not host sizeof or ultimate-pointee size.
QBE extends word indices by promoted signedness, scales and adds/subtracts;
pointer differences signed-divide bytes and return target long. Comparisons
use full-width pointer opcodes before any integer property query.

Full normal GCC regressions/QBE/reference/ABI passed. 14 new full-value scalar
programs and both-direction host-array ABI tests passed with GCC and Clang:
all twelve primitive referents plus pointer objects, all integer indices,
signed negative indices, promoted bytes/shorts/bool, signed differences, all six
comparisons, one-past addresses and once-only/short-circuit calls. Unit tests
assert replaced syntax nodes, integer promotion, exact target sizes, long
differences and depth; runtime tests check the 128/129 typed-depth boundary.
The initial unit fixture used a nonexistent ast_function_definition struct name;
it was corrected to the existing ast_function, without changing compiler code.
Earlier now-valid p+1 and p<p rejection fixtures became invalid p*2 and p/p;
no constraint coverage was silently discarded. No invalid pointer program or
arbitrary generated C was executed. Bounded sanitized fuzz passed
24192 lexer + 74272 pipeline inputs (98464 total),
26/26 seconds. Full isolated/remote matrix remains pending.
M12j 1735825 completed both local normal/sanitizer compiler legs, with previously
passed exact-source CI 38822838501. M13e pointer subscripts are pre-designed.

## M13e tested source checkpoint

Parsed subscript ASTs lower to shared typed pointer offsets plus indirection;
ordinary value completion inserts loads, address contexts do not. Factored
pointer-offset construction preserves prior arithmetic checks without fake
binary syntax or analyzing typed children twice. Postfix suffixes alternate
calls/indexing with normal binding, and language brackets include digraphs.

Full normal GCC regressions/QBE/reference/ABI passed. 15 new full-value programs
and both-direction read/write ABI passed with GCC and Clang, covering every
primitive/pointer referent and integer index, symmetric/negative/chained indexing,
assignment results, once-only calls, macros, digraphs and one-past address-only
uses. Typed units prove syntax replacement, explicit promotion, lvalue/load
separation and exact depth. 42/43 chained subscripts test typed 128/131 depth;
deep nested indices separately diagnose parser nesting. Earlier invalid arithmetic
fixtures remain invalid with more precise offset diagnostics; no rejection test
was silently dropped. No undefined pointer program or arbitrary generated C was
executed. Sanitized bounded fuzz passed 23753 lexer + 35805 pipeline
inputs (59558 total), 26/26 seconds.
Full isolated/remote verification remains pending. M13f fixed local arrays,
explicit decay and bounded target layout are designed before implementation.

M12h/M12i 76944c4/81db52e now passed both isolated compiler normal/sanitizer legs,
with prior exact-source CI 38821148738/38821949608. M13b 6f5e5ab exact-source CI
passed 38824691700. M13c/d and queued M13 local matrices remain pending separately.

## M13f tested source checkpoint

Local arrays have concrete literal-bound syntax and cached semantic element/count
identity. Scalar/pointer elements decay explicitly in ordinary value contexts;
address-of preserves pointer-to-array. Array assignment/initialization diagnose
before scalar conversion helpers. Complete-object addressing and independent
target size/alignment support entry storage without an array-as-scalar load.
The 1 MiB declared-object budget includes parameter spills/scopes and resets per
function; each count is division-checked before multiplication. Bounds remain
literal tokens, not a shortcut constant-expression evaluator.

Full normal GCC regressions/QBE/reference/ABI passed. 18 new full-value programs
and both-direction borrowed-array ABI passed with GCC and Clang: all primitive
and pointer elements, loops/scopes, explicit assignment conversions, macro bounds,
decay/calls, pointer-to-array strides, exact target alignment/size/compatibility
and 1 MiB/depth boundaries. Every executed array element was written first; large
limit sources and uninitialized AST fixtures were compile-only. The first runtime
test caught an old scalar-only named-address assertion: it now correctly requires
a complete object, retaining scalar-only ABI/memory-value helpers. GCC 11 lacks
C23 separators: only that known failing fixture uses an explicit 5U host reference
after original 0b1'01U passed kcc/QBE. Clang passed the original source, no gap.
The earlier a[2] rejection became unsupported incomplete a[]; no coverage dropped.
No undefined or arbitrary generated program was executed. Sanitized bounded fuzz
passed 22758 lexer + 72864 pipeline inputs (95622 total),
26/26 seconds. Full isolated/remote checks remain pending.
M13g multidimensional local arrays are pre-designed; all remaining bound,
initializer, parameter/full-declarator and string limitations are explicit.
M13c exact-source CI passed 38825345451; M13a local GCC leg passed independently.

## M13g tested source checkpoint

Parser accepts up to 64 literal-bound dimensions and wraps syntax right-to-left.
Recursive type compatibility/layout and single-level decay handle matrix shape
without new backend shortcuts. Equal byte counts do not imply compatible types;
selected row pointers are not int**. Literal-only bounds and all initializer/
parameter/full-declarator restrictions remain, as does the 1 MiB object budget.

Full normal GCC regressions/QBE/reference/ABI passed. 15 new full-value programs
and both-direction borrowed-row ABI passed with GCC and Clang: all primitive/
pointer leaves, nested loops, three-dimensional matrices, macro bounds, per-row
mutation, recursive decay and row/whole-array strides. Units check source-order
bounds, caches, equal-byte incompatible shapes and explicit two-level decay.
Exact 64/65 dimension, size-product and 42/43 fully indexed depth limits pass.
Large resource and uninitialized AST/depth fixtures are compile-only; executed
array elements are initialized and no cross-row flattened pointer arithmetic or
arbitrary generated C is executed. The earlier a[2][3] rejection became
incomplete a[2][], retaining the constraint test. Sanitized bounded fuzz passed
25173 lexer + 61850 pipeline inputs (87023 total),
26/26 seconds. Full isolated/remote checks remain pending.
M13h ordinary strings/static byte objects are designed; a curated QBE data/private
symbol probe passed both hosts, not yet compiler string support.
M13d 1435382 exact-source CI passed 38826152470. Baseline M12 integer subset
verification is complete; M13 queued local/source-specific checks remain separate.

## M13h tested source checkpoint

Ordinary byte strings now have arena-owned decoded bytes, explicit trailing NUL,
static array-of-char types and unit-ordered private data IDs. Shared bounded byte-
escape decoding retains character semantics; lexer validates/measures without
allocating decoded token buffers. Parser budgets before allocation; sema uses
ordinary array decay/address paths. QBE emits private align-1 byte data with
$.Lkcc.string.N symbols, safe across user identifiers and separate object files.

Full normal GCC regressions/QBE/reference/ABI passed. 12 new full-value programs
passed with GCC and Clang, including 512 all-byte octal/hex checks, empty/embedded/
trailing NUL, static-lifetime repeated calls, greedy escape boundaries, macro
stringizing and splicing. Both ABI directions and two separately compiled kcc
objects pass. Typed array/decay/list units and pure decoder slice/capacity units
pass. Exact 1 MiB/8 MiB/4096/depth limits compile-only; huge objects do not execute.
Four earlier stringizing errors now remain invalid pointer-to-int returns at the
same invocation anchors; lexer/preprocessor conversion tests now expect valid
strings and retain their provenance checks. No literal modification, unrelated
literal subtraction/order, undefined or arbitrary generated program executes.

After adding static object ID/type/size/alignment/NUL/budget invariants to pipeline
fuzzing, the final sanitized bounded run passed 25149 lexer + 74673
pipeline inputs (99822 total), 26/26 seconds.
An earlier additional bounded run also passed before these extra invariants.
Full isolated/remote checks remain pending. M13i adjacent ordinary string
concatenation is pre-designed; prefixes/encodings/initializers are still later.
M13e/f/g exact-source CI passed 38826762420/38827482501/38828318658. M13a b6ba02d
completed both isolated compiler normal/sanitizer legs; M13b GCC leg passed,
with later local legs/snapshots pending independently.

## M13i tested source checkpoint

String primaries collect at most a bounded adjacent sequence, decode fragments
independently into one final buffer and append one NUL. The constructor accepts
actual combined bytes/length plus first-fragment provenance, not a fake aggregate
token. Sema/static data/decay need no special concatenation path. Empty fragments
are explicitly bounded (4096 per sequence, 16384 per TU); result-object, decoded
and total object-byte budgets retain their earlier meanings.

Full normal GCC regressions/QBE/reference/ABI passed. 15 new full-value programs
and both-direction static-object ABI passed with GCC and Clang, covering greedy
hex/octal boundaries, embedded/final NUL, empty fragments, macro stringizing,
comments/directives/splicing, postfix binding and included literal tokens after
child EOF. Typed units assert one array/object and first-fragment source location.
Exact fragment/TU-fragment/decoded/storage limits pass compile-only, counting one
final NUL per result rather than per fragment. The earlier adjacency rejection
became an unsupported mixed ordinary/wide-prefixed sequence. No literal mutation,
unrelated-literal subtraction/order or arbitrary generated C executes. Sanitized
bounded fuzz passed 22880 lexer + 71927 pipeline inputs
(94807 total), 26/26 seconds.
Full isolated/remote checks remain pending. M13j array-parameter adjustment is
pre-designed; incomplete/qualified/general bounds and full declarators are later.
M13b 6f5e5ab completed both isolated compiler normal/sanitizer legs, with prior
exact-source CI 38824691700. M13h CI remains pending independently.

## M13j tested source checkpoint

Literal-bound parameter arrays retain their declared syntax/cache but signatures
and synthesized parameter locals use a separately adjusted element pointer.
Outer counts do not affect signature compatibility; inner row shapes do. Ordinary
scalar binding and codegen handle pointer spills, mutation, address-of and calls.

Full normal GCC regressions/QBE/reference/ABI passed. 27 new full-value programs
and both-direction eight-argument/row ABI checks passed with GCC and Clang; typed
units check declared/effective separation and pointer-sized storage accounting.
The initial full suite caught an old now-valid int p[2] negative fixture; it now
uses unsupported int p[static 2], retaining constraint coverage. Compiler behavior
was not weakened, and the full suite was restarted and passed. Sanitized bounded
fuzz passed 25039 lexer + 76541 pipeline inputs (101580 total), 26/26 seconds.
No uninitialized/out-of-bounds or arbitrary generated C program executes.
Full isolated/remote verification remains pending. M13k omitted outer bounds is
pre-designed; static/qualified/VLA/general bounds and full declarators remain later.

M13h 6b209a6 passed exact-source CI 38829878613. M13i 5699450 CI
38830826668 remains in progress; isolated matrices remain separate.

## M13k tested source checkpoint

Array syntax now distinguishes omitted bounds explicitly, and a separate
incomplete-array constructor preserves unknown cardinality in declared parameter
metadata. Complete object layout remains forbidden for unknown arrays; ordinary
one-level adjustment produces complete element pointers and existing spills.

Full normal GCC regression/QBE/reference/ABI passed. 27 new full-value programs
and both-direction stack/row ABI passed with GCC and Clang. Units verify declared
incomplete cache versus effective pointer, compatibility and complete-object
predicates. Zero/inner/local omissions and exact dimension/storage constraints
pass. Earlier now-valid [] parameter negatives now reject omitted inner bounds,
without removing local [] or static-form coverage. Sanitized bounded fuzz passed
25234 lexer + 70339 pipeline inputs (95573 total), 26/26 seconds. No arbitrary
fuzz C or invalid/uninitialized curated accesses execute. Full isolated/remote
verification remains pending. M14a single-pass object declarators are pre-designed.
M13c dfd9742 completed its isolated GCC/Clang normal + ASan/UBSan matrix; prior
exact-source CI 38825345451 passed. Later snapshots queue independently.

## M14a tested source checkpoint

Object declarations now separate integer specifiers from a single-pass derived
syntax builder. A parser-local unfilled base slot preserves parenthesis, suffix
and prefix precedence; complete concrete syntax is published once. Local/named/
abstract parameter and cast forms share it. Total 64-star/64-dimension counts
span groups, with a separate 64-group recursion bound. Codegen is unchanged.

Full normal GCC regression/QBE/reference/ABI passed. 20 new full-value programs,
both-direction all-primitive row ABI and mixed eight-argument shapes passed
with GCC and Clang. Typed units inspect exact alternating syntax/cache/size/
alignment and effective parameter graphs. A new invalid array-cast fixture first
exposed the scalar conversion helper's target precondition; sema now diagnoses
non-scalar targets before entering it. Targeted tests, units and the entire
regression suite passed after this fix. Sanitized bounded fuzz passed 25036 lexer
+ 73397 pipeline inputs (98433 total), 26/26 seconds. No arbitrary fuzz C or
undefined curated accesses execute. Full isolated/remote checks remain pending.
M14b incomplete object pointers/composite declarations are pre-designed; a
GCC/Clang pedantic probe confirmed unknown-array dereference and comparison
constraints, not yet compiler support. M13i 5699450 passed exact-source CI
38830826668. Later runs and isolated snapshots remain independent/pending.

## M14b tested source checkpoint

Unknown arrays are object but not complete object types. Their pointers are
complete scalar objects, with ordinary lvalue indirection/address/element decay.
No unknown object receives a fake size or stride; pointer offsets/subscripts
and both difference operands require complete referents before layout.
Compatible redeclarations form immutable recursive composite graphs retaining
known counts; definition parameter caches/locals keep their own declared shape.

Full normal GCC regression/QBE/reference/ABI passed. 19 new full-value programs,
all-primitive row and eight-mixed-pointer ABI in both directions passed with GCC
and Clang. Host-provided null cancellation remains non-dereferencing. Units
inspect unknown cache versus visible known composite and object/complete/layout
contracts. Three-way nested declaration conflicts, both subtraction orders and
zero-offset/subscript constraints pass. Earlier unknown-pointer negatives now
reject invalid nested incomplete arrays; local/inner omissions still reject,
with semantic completeness diagnostics. Sanitized bounded fuzz passed 24686
lexer + 72222 pipeline inputs (96908 total), 26/26 seconds. No arbitrary fuzz C
or undefined curated access executes. Full isolated/remote checks remain pending.
M14c grouped local/for-header declarations are pre-designed. M13j d0fc412 passed
exact-source CI 38831621684; later runs and isolated snapshots remain separate.

## M14c tested source checkpoint

Local groups parse specifiers once and construct each derived shape independently
around the immutable base. Existing declaration nodes form source-order lists.
Compound tails preserve all nodes; for statements explicitly own a header list.
Common list sema/codegen preserve scope, binding order and one-time initialization.
Each concrete local charges the function-wide item budget, including for headers.

Full normal GCC regression/QBE/reference/ABI passed. 23 new full-value programs
and both-direction all-primitive ABI tests passed with GCC and Clang, covering
mixed pointer/array/scalar groups, scope/shadowing, nested call commas, sequencing
and nested loop break/continue. Units check shared bases, independent chains,
source-order slots and header list ownership. Exact 256/257-local, 4096/4097-item
(including header locals) and storage limits pass compile-only. Earlier now-valid
ordinary/header comma-list negatives now reject repeated specifiers/incomplete
header arrays; accepted forms have positive coverage. Sanitized bounded fuzz
passed 24754 lexer + 68593 pipeline inputs (93347 total), 26/26 seconds.
No arbitrary fuzz C or undefined curated access executes. Full isolated/remote
checks remain pending. M14d C23 unnamed definition parameters are pre-designed;
both installed hosts accepted a simple syntax/runtime compilation probe, not a
claim of complete C23 support. M13k 7fa1cf3 passed exact-source CI 38832092805.
Later source-specific and isolated checks remain independent.

## M14d tested source checkpoint

Unnamed C23 definition parameters retain declared/effective types and positional
ABI arguments but create no fake name/binding/local spill. Codegen emits types
from parameter.type and advances %pN across unnamed entries; only named entries
are stored. Caller argument analysis/conversion/evaluation is unchanged.

Full normal GCC regression/QBE/reference/ABI passed. 17 new full-value programs,
both-direction all-primitive register/stack and mixed full-width ABI tests passed
with GCC and Clang. Units/IL checks verify NULL locals and stable argument indices,
including named positions 1/7. Exact 128/129 parameters and named-versus-unnamed
actual local/storage budgets pass; a 128-argument program runs through QBE.
The first full run found a second former unnamed-definition rejection not covered
by the diagnostic tuple update. Both now-valid negative occurrences became invalid
inner incomplete arrays, and a positive ordinary runtime regression was added.
The entire suite restarted and passed; compiler behavior was not weakened.
Sanitized bounded fuzz passed 22908 lexer + 73895 pipeline inputs (96803 total),
26/26 seconds. No arbitrary fuzz C or undefined curated access executes. Full
isolated/remote checks remain pending. M14e fixed function declarator syntax
is pre-designed; function pointer values/decay/indirect calls remain M14f.
M14a c10fa56 passed exact-source CI 38832685806. M13d 1435382 completed the
isolated GCC/Clang normal + ASan/UBSan matrix; prior CI 38826152470 passed.

## M14e tested source checkpoint

Function suffixes now share the single-pass derived parser, including abstract
function types and parenthesized external names. Concrete function syntax owns
return/parameter syntax and its cached semantic signature; declaration fields
are views. Shared recursion covers nested parameter types and flat function
layers have an independent 64 limit. Return/parameter category constraints run
before scalar ABI helpers. Function pointer values remain explicitly unsupported.

Full normal GCC regression/QBE/reference/ABI passed. 21 new full-value programs
and both-direction all-primitive row-return ABI passed with GCC and Clang.
Matrix/unknown array-pointer returns, static string-array addresses, recursive
borrowing and composite return signatures pass without backend shortcuts. Units
check syntax-owned signatures/views and original unknown versus visible known
composites. Exact function-layer/nested-type budgets pass compile-only. Earlier
function grouping/pointer negatives retain explicit semantic unsupported-feature
diagnostics. Sanitized bounded fuzz passed 23977 lexer + 71669 pipeline inputs
(95646 total), 26/26 seconds. No arbitrary fuzz C or undefined curated access
executes. Full isolated/remote checks remain pending. M14f function designators,
compatible pointer values and indirect fixed calls are pre-designed. M14b
1bfd4a9 passed exact-source CI 38833251538; later runs remain independent.

## M14f tested source checkpoint

Full GCC regression/QBE suites passed, with 22 targeted runtime programs under
both GCC and Clang. Callback/factory ABI checks cover both linkage directions
for all primitive/pointer leaves, mixed eight-argument stack ABI, six dirty
narrow-return assembly stubs, null &* cancellation and exact typed call depth.
Bounded sanitized fuzz passed 23,769 lexer and 68,371 pipeline runs (26 seconds
each); arbitrary fuzz programs were never executed. The existing integer-call
negative now expects the more precise not-a-function-pointer diagnostic.
Full isolated matrices and exact-source remote CI remain pending for this
checkpoint. Next M14g void types/functions/discards is designed in
m14-void-functions.md. Function pointer design is m14-function-pointer-values.md.

## M14g tested source checkpoint

Full GCC normal regression and QBE suites passed. Targeted GCC and Clang checks
cover 16 full-value programs, 28 primitive/pointer callback ABI combinations in
both linkage directions, mixed register/stack ABI, result-free QBE IL, host-null
&* cancellation, nonnull void-indirection effects, exact expression depth and
52 invalid constraints. Semantic units inspect void syntax/cache/category, no
void spills/loads, optional return AST values and indirect void calls.

Bounded sanitized fuzz completed 24,479 lexer and 70,044 pipeline inputs in
26 seconds per harness without reported failures; generated C was not executed.
The obsolete void-pointer-prototype rejection was replaced with an invalid named
void parameter. Test-only fixes use normalized bool expectations and the exact
64-bit mixed-argument sum. Full isolated and exact-source remote checks for this
checkpoint remain pending; do not infer them from older commits.

M13e's independent GCC/Clang normal + ASan/UBSan matrix passed. Later matrices
remain separately queued/running. M14h object/void conversions and mixed equality
are designed before implementation in m14-object-void-conversions.md.

## M14h tested source checkpoint

Full normal GCC regression and QBE suites passed. New GCC/Clang tests cover
21 full-value programs, all primitive object round trips, both cross-object ABI
directions, arrays/incomplete array shapes, pointer-to-pointer and function-
pointer objects, null conversions supplied by the host, once-only equality
effects, exact conversion-depth limits and 24 invalid constraints. Typed units
check explicit conversion nodes, mixed-equality normalization in both orders
and unchanged type compatibility. A strengthened mixed register/stack fixture
uses seven distinct live objects and an observable full-width tail; it passed
both hosts after the full suite, avoiding an unobservable same-pointer fallback.

Bounded ASan/UBSan fuzz completed 21,170 lexer and 63,070 pipeline inputs in
26 seconds per harness, without reported errors or execution of generated C.
Full isolated and exact-source remote checks for this checkpoint remain pending.
M14i explicit object/function pointer casts is designed before implementation.

The sandbox restart removed Clang and interrupted older isolated jobs. Clang
and compiler-rt were restored; unfinished immutable snapshot matrices were
requeued under the same external lock, preserving old logs and recording new
results in /data/tools/*-resumed-validation.log. The active M14g matrix is
independent. All remote checkpoints remain exact-source, not inferred.

## M14i tested source checkpoint

Full GCC normal regression and QBE suites passed. Targeted GCC and Clang checks
cover 31 full-value programs, every primitive object's character-pointer round
trip, defined byte-representation access, complete/incomplete arrays, nested
pointer objects, both primitive/function ABI linkage directions, mixed stack
callbacks, host-supplied object/function null pointers, once-only effects, exact
typed depth and 21 constraints. Function casts are restored to compatible
signatures before calls. Typed units preserve real cast syntax/cache/types,
incompatibility and depth rather than weakening implicit conversions.

Bounded ASan/UBSan fuzz completed 22,538 lexer and 69,788 pipeline inputs in
26 seconds each without reported failures; generated C was never executed.
Old explicit object-cast rejections were migrated to unchanged implicit
constraints; nested pointer implicit conversions still reject. Full isolated
and exact-source remote checks remain pending for this source. M19a comma
expressions are designed before implementation and brought forward because
they exercise M14g discard paths and declaration/call separator boundaries.
M14 qualifiers/typedefs and the rest of M19 remain incomplete.

## M19a tested source checkpoint

Full GCC normal regression and QBE suites passed. Targeted GCC and Clang checks
cover 35 full-value programs, scalar/void/pointer/function result sequencing,
short-circuit branch merges, loop/return/subscript full expressions, call and
declaration separator ownership, 28 primitive/pointer ABI combinations in both
linkage directions, exact typed-depth limits and 16 invalid constraints.
Typed units inspect concrete comma children, loads/decay, void/no-lvalue results,
left association and unchanged call argument count. Three obsolete now-valid
negative fixtures were migrated to real arity, missing-operand and void-scalar
constraints; their original valid shapes also have positive coverage.

Bounded ASan/UBSan fuzz completed 23,675 lexer and 71,371 pipeline inputs in
26 seconds per harness without reported failures; generated C was not executed.
Full isolated and exact-source remote checks for this source remain pending.
Exact-source M14g 592b551 CI run 38859101528 passed; M14h 274d966 run
38859812046 and M14i 1ed1cc8 run 38860337750 were still running when checked.
The immutable M14g GCC normal/ASan/UBSan matrix passed; its Clang half and other
queued matrices remain separate checks, not inferred successes.

Next M14j const is designed in m14-const-qualification.md. Implement immutable
qualification, strict versus root-unqualified compatibility and qualified
composites as M14j1, then parsing/value conversions and enforcement as M14j2.
No const syntax is claimed until the latter passes its language tests.

## M14j1 tested source checkpoint

Implemented immutable type qualification/unqualification, qualification-aware
strict/root-only compatibility and qualifier-preserving composites. All primitive
leaves and void, independent pointer levels, function referents, const pointer
arrays versus pointers to const elements, nested C23 arrays, unknown/known-bound
composites and 64-layer graphs have dedicated unit checks. Input graphs and
singletons remain unchanged; no-op operations share existing nodes. Layout/ABI
helpers retain their kind-based representation behavior.

Full normal GCC regression and QBE suites passed. The new type-unit executable
passed GCC and Clang ASan/UBSan directly and is part of make test and CI matrices.
Bounded sanitized fuzz completed 19,665 lexer and 54,466 pipeline inputs in
26 seconds each without reported errors; no generated C was executed. These
harnesses do not yet construct qualified types through source syntax: M14j2 is
next. Exact-source remote and full isolated checks for M14j1 remain pending.

The independent M14g full GCC/Clang normal + ASan/UBSan matrix now passed both
halves. Other queued matrices remain separate; do not infer newer-source results.

## M14j2 tested source checkpoint

Const builtin/star syntax uses a separate concrete qualified syntax node and
immutable semantic caches. Value loads, initializers, casts and function return/
parameter signatures unqualify only the required level; local parameter objects
retain const. Pointer conversions add only immediate qualifiers; comparison
common types preserve qualification, arrays and depth, while pointer differences
keep both completeness guards. QBE representation needs no qualifier shortcut.

Full normal GCC regression and QBE suites passed. Targeted GCC/Clang tests cover
39 original kcc full-value programs, 48 primitive/object ABI arrangements, mixed
register/stack, callbacks and native-null ABI in both directions, nested array
shapes, defined explicit qualification removal, once-only effects, 64/65 pointer
and exact typed conversion/promotion depth boundaries, and 40 constraints.
GCC gives 39 native runtime agreements. Clang 15 gives 36 and three narrowly
recorded C23 6.7.6.3p4 return-qualification diagnostic gaps; all 39 original kcc
programs still execute with QBE. Semantic units inspect concrete syntax/cache,
qualified parameter locals versus unqualified signatures, const pointee loads,
explicit conversions and unknown array parameter shapes. Both GCC and Clang
ASan/UBSan semantic-unit executables passed.

Bounded sanitized fuzz completed 23,480 lexer and 62,518 pipeline inputs in
26 seconds each without reported failures; generated C was never executed.
One old int *const function-prototype rejection is now a real const parameter
assignment constraint. Full regression restarted after that fixture migration.
A test-construction insertion/field-name mistake was corrected before the full
validation; it was not a compiler finding. Exact-source remote/full isolated
checks for this source remain pending.

Exact-source CI now passed M19a 95a99d7 run 38861248497, M14i 1ed1cc8 run
38860337750 and M14h 274d966 run 38859812046. M14j1 6e7ff50 run 38861821792
was still running at the latest check. M14g's full isolated GCC/Clang normal and
ASan/UBSan matrix passed. Do not infer other queued-source outcomes.

Next independent M23a1 bool/true/false keywords and typed boolean constants are
designed in m23-boolean-keywords.md, retaining the existing C23 pp true rule.
This does not finish M14 other qualifiers/typedefs or M23a's remaining keywords.

## M23a1 tested source checkpoint

C23 bool/true/false tokens, a separate concrete boolean constant AST and shared
_Bool semantics/codegen are implemented. Macro expansion stays before keyword
conversion and preprocessing true/false remains separate from language constants.
Full normal GCC regression and QBE suites passed. Both-host targeted checks
cover 32 original programs, 22 constraints, exact bool promotion depth, 26
cross-object ABI arrangements, mixed register/stack/callbacks and dirty narrow
returns. GCC 11 compatibility oracles are explicitly labelled; Clang 15 gives
native C23 keyword/type agreements. Three preprocessing defined/undef programs
are QBE-tested unchanged and only native hosts serve as their reference oracle.
Both GCC/Clang ASan/UBSan semantic units passed. Fuzz totals are recorded below;
no generated C was executed. Exact-source remote/full isolated checks are pending.

M14j1 6e7ff50 CI run 38861821792 passed. M14j2 b26ff3b CI run 38863255999
was still running at the latest check. Results are source-specific.
Next: M19b conditional expressions, with the design recorded before editing.
M14 remaining qualifiers/typedefs and M23a remaining keywords stay unfinished.

M23a1 bounded sanitized fuzz: 23,176 lexer and 68,839 pipeline inputs in
26 seconds each, without reported failures. Generated C was never executed.

## M19b tested source checkpoint

Concrete conditional AST/parser/sema/codegen now implement selected scalar/void
branches and qualified/composite pointer results. The Pratt table keeps comma,
assignment and conditional contexts distinct; the middle accepts full expressions
and the final operand associates right. All operands are checked semantically.
Known/unknown array bounds compose without changing parameter type snapshots.
Comparison and conditional common-pointer construction share one checked helper.

Full normal GCC regression and QBE suites passed. Targeted both-host tests cover
50 original programs, 288 pairwise sign/rank checks, typed units for all 144
integer pairs, 17 constraints, exact syntax and inserted-conversion depths,
24 primitive ABI arrangements, host-native null pointer conditions and dirty
narrow returns. GCC gives 50 native runtime agreements; Clang 15 gives 48 and
two exact C23 array-qualification diagnostic gaps. Every original kcc program
still executes with QBE. Both GCC/Clang ASan/UBSan semantic units passed.
A test expectation initially missed the existing explicit cast's depth; the
final exact typed boundary uses a real bool leaf and promotion. No compiler
failure was hidden by a host-source rewrite. Bounded sanitized fuzz totals follow;
no generated C was executed. Remote/full isolated checks remain pending.

Next independent M18a fixed sizeof/alignof is designed in m18-sizeof-alignment.md.
No VLA/constant evaluator, null constant or full M18/M19 conformance is implied.

M19b bounded sanitized fuzz: 23,373 lexer and 68,010 pipeline inputs in
26 seconds each without reported failures; generated C was never executed.

## M18a tested source checkpoint

Separate concrete sizeof-expression, sizeof-type and alignof ASTs preserve typed
operands/syntax. Parser disambiguates type versus expression with one on-demand
token and retains postfix binding inside sizeof operands. Sema suppresses only
root load/decay, checks complete object layout and emits unsigned-long constants.
Codegen never evaluates operands, including calls, writes and invalid-at-runtime
addresses. Unknown arrays/functions/void remain constraints, not GNU size extensions.

Full normal GCC regression and QBE suites passed. Both-host targeted tests cover
33 original full-value programs, 19 constraints, exact unevaluated structural
depths, all primitive/pointer/array/const layouts, adjusted parameters, embedded
NUL/concatenated strings, bool conditional promotion, unevaluated uninitialized
reads/calls/stores/out-of-range addresses and no unresolved-symbol references.
24 unsigned-long ABI arrangements and native-null unevaluated pointer operands
pass. GCC 11/Clang 15 alignof spelling checks use explicitly labelled _Alignof
compatibility macros; original kcc programs are unchanged. Both GCC/Clang
ASan/UBSan semantic units passed. Sanitized bounded fuzz totals follow; no
fuzz-generated C was executed. Exact-source remote/full isolated checks pending.

Next: M18b1 pure integer constant-evaluation foundation, designed in
m18-integer-constant-evaluation.md before implementation. Source-level constant
requirements, generalized array bounds and null conversions are later consumers.

M18a bounded sanitized fuzz: 23,465 lexer and 66,857 pipeline inputs in
26 seconds each without reported failures; generated C was never executed.
Exact-source M14j2 b26ff3b CI run 38863255999 passed. M23a1 fe26eb4 run
38864340577 and M19b 0c0ef33 run 38865164586 were still running.

## M18b1 tested source checkpoint

Added a pure consteval.c stage over checked bounded integer ASTs. Results preserve
canonical target bits/type/location or distinguish nonconstant forms from invalid
arithmetic. Portable checked operations never depend on signed host overflow,
negative signed shifts or large unsigned-to-signed casts. Short-circuit arms are
form-checked without arithmetic, and comma is allowed only when unevaluated.
sizeof/alignof are opaque typed leaves; queries do not emit diagnostics, mutate
ASTs, allocate or change runtime compilation acceptance.

Full normal GCC regression and QBE suites passed. Both GCC/Clang native oracles
agree on 958 curated strict ICE forms/values, with six C23 boolean queries,
34 nonexecuted invalid-arithmetic cases, 19 nonconstant forms and eight strict
native form rejections. Both-host ASan/UBSan evaluator oracles passed the same
checks. One exploratory predefined-macro test correctly exposed that __STDC__
is not yet provided; it was not disguised as a supported feature. Fuzz now queries
checked expression/initializer/return roots without executing generated C.
Bounded fuzz totals follow. Full isolated/remote exact-source checks are pending.

This is a shared foundation, not new declaration acceptance. Static assertions,
enums/constexpr, constant array bounds and null pointer constants are not yet
consumers. Next: M18b2 static assertions, designed in m18-static-assertions.md.

M18b1 bounded sanitized fuzz: 23,575 lexer and 64,254 pipeline inputs in
26 seconds each, without reported failures. Generated C was never executed.
Exact-source M23a1 fe26eb4 CI run 38864340577 passed; M19b/M18a were still running.

## M18b2 tested source checkpoint

static_assert and _Static_assert are on-demand post-pp keywords and concrete
assertion declarations with separate external/block wrappers. Parser accepts
conditional-expression and optional concatenated ordinary-string messages.
Sema checks all source-order scopes/unreachable items and consumes the pure ICE
query, preserving located invalid-arithmetic versus nonconstant diagnostics.
False values include quoted messages with all control/NUL/high bytes escaped,
never printf-interpreted. Messages allocate no local slots or QBE static objects;
successful assertions emit no runtime code, even in for initializers.

A standards audit corrected an initial design assumption: N3096 declarations
include static assertions in for clause-1. GCC 11 accepts them; Clang 15 rejects
with its exact identifier/parser diagnostic. Tests follow the draft and record
the host gap instead of rewriting the original source. Both hosts lack the C23
static_assert spelling and receive labelled _Static_assert oracle macros only.
Raw pp defined/undef behavior is checked on the original kcc program; legacy
host keyword-macro differences are not claimed as native agreements.

Full normal GCC regression and QBE suites passed. Targeted both-host tests cover
26 original QBE programs, 25 GCC and 24 Clang strict native runtime agreements,
39 constraints, four strict native ICE rejections, every diagnostic byte, message
concatenation/NUL/provenance, AST/scope/no-allocation invariants and exact syntax/
typed/item/external/message length/fragment limits. Both-host ASan/UBSan semantic
units and complete targeted assertion suites passed. Initial tests needed fixes
for the existing reverse local list, native diagnostic wording, unary '+' token
separation and trailing newlines in strict host feature probes; no compiler
failure was hidden. Bounded fuzz totals follow; no generated C was executed.
Full isolated/remote exact-source checks remain pending.

Next: M13l1 fixed ICE array bounds, designed in m13-constant-array-bounds.md.
Enums/constexpr/floating ICE casts, VLA, typedef/aggregates, null constants and
initializer/optimizer consumers remain unfinished.

M18b2 bounded sanitized fuzz: 21,256 lexer and 59,937 pipeline inputs in
26 seconds each, without reported failures. Generated C was never executed.
Exact-source M19b 0c0ef33 CI run 38865164586 and M18a ea59892 run
38865929894 passed. M18b1 5b71941 run 38866954105 remained in progress.

## M13l1 tested source checkpoint

Array syntax now retains an optional bound expression AST (NULL for unspecified)
instead of duplicate token/has_bound fields. On-demand Pratt assignment-expression
parsing feeds normal sema and the pure ICE query; signedness-aware positivity,
overflow-safe per-type bounds and aggregate local-storage limits are enforced.
No VLA/runtime bound or global folding is implied. Bounds emit no evaluations.

Function-type resolution now creates/restores ephemeral prototype scopes, resolves
parameters left-to-right and binds adjusted names only after their declarators.
Type-only name bindings consume no runtime slots/list entries; real definition
parameter locals remain separate. Nested callbacks, own-name outer lookup and
scope restoration are typed-tested. A pre-implementation host probe corrected a
return-scope assumption: parameters are not visible in trailing derived return
syntax, so return types continue resolving before entering the prototype scope.

Full normal GCC regression and QBE suites passed. Both-host targeted tests cover
31 original strict native/QBE programs, 34 constraints, 24 adjusted-array ABI
arrangements, exact syntax/typed/cross-type recursion and compile-only storage
boundaries. Both-host ASan/UBSan semantic units and targeted bound suites passed.
The cross-type recursion boundary is the existing 64 nested declarator edges,
not 128 independent expression nodes. Tests replace obsolete [true], [sizeof],
[1+2] rejections with variable-length/unparenthesized-comma cases; unsupported
static bracket diagnostic expectations now reflect expression parsing. No
rejection coverage was silently removed. Initial tests also corrected existing
local-object-storage wording. Bounded fuzz totals follow; generated C was never
executed. Full isolated/remote exact-source checks remain pending.

Next: M13m traditional null pointer constants, designed in
m13-null-pointer-constants.md. C23 nullptr/nullptr_t, VLA, typedef/qualifiers,
enums/constexpr and other constant consumers remain later work.

CI correction preceding this checkpoint: cade2cd's Clang CI run 38868636910
failed because the native host applies an unevaluated-string numeric-escape
restriction to a valid C23 assertion message. N3096 6.4.5/6.7.11 were rechecked;
kcc's acceptance and every diagnostic-byte test remain unchanged. Correction
5ce95d6 recognizes only that exact single-error host diagnostic for the original
numeric-message program, does not count it as a native agreement, and still
runs the original through kcc/QBE. Other native failures remain fatal. Both
local host assertion/QBE suites passed the correction. Remote CI is pending;
do not call the failed earlier checkpoint green. M18b1 5b71941 CI run
38866954105 did pass. A sandbox reset erased installed Clang and queued process
handles; Clang/compiler-rt were reinstalled. Old matrix source archives/logs
remain, but pending jobs are not claimed as successful.

M13l1 final post-reset full normal regression and QBE suites passed again;
bounded sanitized fuzz ran 22,845 lexer and 61,791 pipeline inputs in 26 seconds
each. Both-host focused ASan/
UBSan semantic, bound and assertion suites also passed with QBE runtime/ABI.
No fuzz-generated C was executed. Version-only driver change was rebuilt/smoke
checked after these suites. Remote/full isolated matrix status remains separate.
The first native-oracle correction's remote Clang job progressed to the separate
keyword-macro warning policy; a second exact-diagnostic/same-source warning
control fixes that test, documented in m18-static-assertions.md. Neither compiler
language acceptance nor warning policy for other tests was weakened.

## M13m traditional null pointer constants

Sema recognizes checked integer constant expressions with value zero, and
explicit casts of those expressions to unqualified void *. A zero-valued local,
assignment/comma result, arbitrary pointer, typed int * null value or pointer
conditional result does not gain null-constant status. Invalid constant arithmetic
is not proof of zero. C23 nullptr/nullptr_t remain a separate next milestone.

Assignment-like conversions (initialization/assignment/call/return), explicit
pointer casts, equality in both orders and conditional arms share the predicate.
Equality handles null constants before compatible/common pointer types; relational
comparisons still reject pointer/integer zero. Conditional arms select the exact
other pointer type before the object/void common-type rule, preserving qualified
objects, functions and incomplete-array pointers. Pointer+0 remains ordinary
pointer offset arithmetic, not a null conversion. Function/object bridges and
nonzero integer/pointer casts stay unsupported; the latter are implementation
limits, not claimed C constraints. Pointer-to-bool conversion remains available.

Existing concrete conversion/cast ASTs retain original operands, source locations,
resolved types and depth checks. No token vectors, synthetic literal rewrites,
extra local slots, global folding or runtime ABI adapters were added. Existing
QBE integer extension/copy lowering was audited: this amd64 LP64 target uses
all-zero 64-bit null pointers for implemented object/function pointer types.
That is an explicit target representation choice, not a portable C assumption.

Both-host focused tests cover 37 original curated programs, 36 strict GCC and 37
strict Clang native agreements, 25 compile-only constraints/implementation limits,
11 strict native constraint rejections, concrete AST/type/slot/depth invariants
and 24 mixed-register/stack/callback cross-object ABI arrangements. Once-only
non-null effects and selected conditional arms are checked without null calls,
dereferences, arithmetic or incompatible calls. Existing obsolete zero-rejection
fixtures were replaced with nonzero forms, not dropped. The ABI failure path uses
a live caller-owned sentinel, so an argument mismatch cannot accidentally return
null and pass. Both-host ASan/UBSan semantic/targeted results and full regression/
fuzz outcomes follow once complete; no generated fuzz C is ever executed.

A native-oracle audit found GCC 11 rejects a zero _Bool ICE in initialization,
assignment and return, despite C23 6.3.2.3/6.6 permitting it. Clang accepts the
same original program. Tests recognize only those three exact GCC errors, keep
the original kcc/QBE run, report the gap and do not count a native agreement.
An early test-generation failure was a missing parenthesis around interpolated
conditional zero forms; grouping was fixed, not compiler precedence. Strict
native rejection tests explicitly exclude legal-but-unimplemented cast forms.

M13m final validation: full normal regression and QBE suites passed. Both-host
ASan/UBSan semantic units and final targeted null suites passed, including the
extra original C23 false-leaf QBE program and its exact typed conversion unit.
Bounded sanitized fuzz ran 22,403 lexer and 63,128 pipeline inputs in
26/26 seconds without reported failures; generated C was never executed.
The full-suite audit found two additional obsolete zero/false rejections in void
function and boolean tests. Both were replaced with nonzero/true cases, retaining
constraint coverage, then the entire regression/QBE/fuzz chain was rerun.
No partial early run was called a full pass. Full isolated and remote exact-source
checks for this checkpoint are pending. Next: M23a2 nullptr constant with its own
scalar type, designed before implementation in m23-nullptr-constant.md.

## M23a2 work and next increment

See m23-nullptr-constant.md and the M23a2 ledger entry for implementation and
fixture decisions. Runtime/type correctness is tested on original nullptr source,
not a macro alias. Both local native hosts predate the keyword; modern CI must
run the original-source native differential branch. Keep remote CI and isolated
matrix results separate from targeted validation. M13l1 remote run 38877765103
passed all jobs; M13m run 38879492736 still running when last checked.
Next prewritten design: m19-prefix-updates.md. Keep postfix updates separate until
M19c2; integer bool updates require truth conversion rather than modulo-two
narrowing. Preserve once-only operand addresses and immutable qualified types.

M23a2 final local validation: full normal regression and QBE suites passed. Both-host
ASan/UBSan type/lexer/sema units and final targeted runtime/ABI passed. Bounded
sanitized fuzz ran 22,463 lexer and 54,705 pipeline inputs in
26/26 seconds with no reported failures. No generated C was executed.
Remote exact-source and full isolated matrix checks remain separate/pending.

## M23a2 native constant-form oracle correction

Exact-source addce68 CI run 38881054180 passed fuzz but failed the modern GCC
native rejection oracle for `int *p=nullptr?0:0;`. Clang was cancelled by matrix
fail-fast, not a compiler failure. N3096 6.6p8 only admits integer/arithmetic
constant operands in integer ICEs; nullptr_t is neither. Paragraph 14 allows
additional constant forms without making them integer ICEs. Preserve kcc's
form rejection and record host acceptance separately for exactly three named
nullptr-derived constant forms (that conditional and two static assertions).
All other native constraints must still reject; all 26 kcc rejections remain
mandatory. Do not change nullptr into arithmetic zero or relax general null
constant classification to match host folding. Extra host forms are never
counted as strict constraint agreements. Legacy hosts never run this branch.

M19c1 final local validation: complete normal regression and QBE suites passed.
Both-host ASan/UBSan lexer/sema units and targeted runtime/24 ABI arrangements
passed. Sanitized bounded fuzz ran 22,752 lexer and 58,812
pipeline inputs in 26/26 seconds with no reported failure.
No generated fuzz C or constraint-invalid/undefined curated source was executed.
CI now keeps both compiler matrix jobs running after either fails, so host
oracle/implementation failures do not hide the other compiler's evidence.
Prior M13l1 isolated GCC/Clang normal+ASan/UBSan full matrices passed. M13m
e06a497 remote run 38879492736 also passed every job. The nullptr oracle fix
f3df148 run 38881463571 is still running; GCC passed normal tests and reached QBE.
M19c1 isolated/remote checks are queued/pending, not claimed passed.
