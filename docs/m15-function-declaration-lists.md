# M15d2: single-specifier file-scope function declaration lists

Design recorded before implementation against fully validated, documented and
pushed M15d1 checkpoint 0b5fcb4d13634ae3a0a4b6681678a7e954d9f0e8. Local HEAD
matched remote development and the worktree was clean. M15c1 Clang CI and the
new M15d1 exact-commit CI are independently pending at design time.

## Scope and invariants

Support `int f(int), g(void);` and explicit extern versions, including distinct
return pointer/function declarators, typedef bases, typedef/query-derived function
prototypes (`typedef int F(int); extern F f,g;`) and repeated compatible names.
One shared declaration-specifier syntax is scanned once; each declarator gets its
own derived chain and concrete existing external declaration node. No public
AST/semantic/type/backend interface addition. Every concrete name contributes
one external declaration to the existing 512 budget, and distinct symbols still
contribute to the independent 256 function limit. Initializers/objects, local
function declarations, internal linkage, inferred extern objects and function
definitions inside comma lists remain unsupported/invalid as appropriate.

Preserve single direct function definitions and all old single-declaration
behavior/diagnostics. Alias/query-derived function definitions remain the existing
explicit subset refusal; a function body is only accepted for a single direct
outer function declarator with no preceding comma list. Native constrained invalid
list definitions are never executed. This does not add global object declarations.
Existing typedef lists must stay on their dedicated parser path unchanged.

## Parser lifetimes and stage interaction

Introduce a private ordinary external-declarator-list tail that receives the
already-scanned base, beginning token and remaining concrete external budget.
Move existing direct-function construction/body path into this tail, retaining
one view of each outer function syntax and actual parameter list (no reparse).
At each declarator: check remaining item budget BEFORE allocation/parsing,
parse_derived_type with external context around the SAME shared base, classify
the syntax and construct the existing direct or alias/query external node.

The current query/alias external helper must no longer consume the final ';'.
Rename it to reflect construction if needed; accept either comma or semicolon as
a prototype delimiter without consuming either. Preserve its old exact
"query-derived external declarations require ';'" diagnostics for body/initializer
or other unsupported tails, and its file-object classification rules. The shared
tail consumes comma/semicolon. Link each concrete external node in source order,
return the head, and let translation-unit append/count the returned list just
as it already does for typedef groups. Update that explanatory count comment.

For a direct function, a sole first declarator with neither comma nor semicolon
continues through the old function-body path (including its existing unexpected-
token error). Once any comma is seen, only prototypes and a final semicolon are
allowed; no body can sneak into a later list member or be silently discarded.
No expression initializer parser, token vector, backtracking or duplicate storage.
Per-function parser parameter suffix scopes already restore names; assert that
an earlier parameter T does not mask outer typedef T in a sibling declarator.

Sema already visits concrete external nodes in order. The first function symbol
is registered before resolving later declarators, so later parameter typeof or
sizeof queries may refer to it. Shared base caches resolve once and keep exact
captured identity; declarator-specific parameters/callbacks stay separate.
Aliases/query-derived types, canonical/composite signatures and source unknown
array bounds must not be overwritten while later compatible declarations add
known bounds. Prototypes emit no storage/IL, and real function definitions keep
only their own adjusted named spills/register provenance. No alias/function name
is an object local; QBE emits one definition per canonical symbol as before.

## Validation

Four-host unchanged standard originals for list cardinality, shared typedef and
builtin bases, primitive full-width results, distinct return pointers/function
pointers, explicit/implicit extern prototypes and later definitions, repeated
compatible names and both-direction mixed-stack ABI. Alias-defined function
prototypes, pointer-to-row composite bounds, nested callback/parameter name
restoration, later declarations seeing earlier function names, and body captures
retain identities. Modern-only typeof/bool/nullptr originals use independent exact
legacy absence probes; no rewriting source or counting syntax absence as agreement.

AST invariants: distinct concrete nodes in correct external order, one shared
specifier base with separate derived graphs, isolated parameter syntax/scopes,
shared immutable alias/query caches, source-order function captures and symbol
composites, own definition spills/register flags and no prototype runtime storage.
Plain/extern declaration-only IL empty, actual definitions emitted exactly once.

Native compile-only constraints: duplicate incompatible signatures in a list,
ordinary/typedef conflicts, invalid mixed definition/declaration lists, bad argument
uses, query register-address constraints and parameter storage. Subset refusals:
any global object in a list, alias-derived bodies, local extern/function lists,
static/inline and inferred extern. Keep a list containing unsupported members from
emitting partial IL. Replace only two known old list exclusions with new positive
coverage: extern-functions `extern int f(void),g(void);` and queried-function
`typeof(int(void)) f,g;`; retain alias/query body/initializer errors unchanged.
Search other current tests/corpus before modifying expectations.

Exact 512/513 concrete items in ONE list and combined with prior declarations,
256/257 unique symbols in lists vs 512 repeated prototypes, 128/129 parameters,
256/257 locals/spills, 1 MiB storage, 4096 block items, 64 combined declarator and
128 expanded-type depths. Generated boundaries compile only. At least 24
both-direction mixed-stack primitive ABI and row/callback arrangements per host.

Add focused suite/compile+lex corpus/Makefile recipes and both-host targeted
sanitizer matrix. Build helpers serially, freeze exact source/tests/Makefile, run
full normal/GCC11-GCC14-Clang18 native oracles and modern QBE, both-host ASan/UBSan,
bounded compile-only lexer/pipeline fuzz, and unaffected old corpus comparison.
Draft completion docs outside while frozen; apply after all passes and manifest
matching. Commit/push promptly and inspect exact-commit CI separately. Not full C23.

## Pre-freeze review

Final focused list suite passed on all four hosts: 43 baseline + 8 C23-keyword
unchanged originals; GCC14 51 agreements, Clang18 46 agreements plus five exact
return-qualifier gaps; GCC11 43 and Clang15 38 plus five such gaps. Twelve modern
and nine applicable legacy constraints reject. Seven subset forms compile only.
The qualifier cases are VALID under N3096 6.7.6.3p4's unqualified return rule,
not invalid curated programs. Clang's exact two conflict errors plus notes are
classified only for those five source strings/status 1; negative controls reject
wrong source/status/signal, extra warning/note/fatal/duplicate records. Original
sources were retained, not rewritten to fake native agreement. This is the same
independently documented return-qualifier rule as the existing const suite.

All hosts passed 24 both-direction mixed-width/full-value primitive ABI and two
row/callback arrangements. Existing extern/query/typedef-foundation/typedef-
placement/register-parameter suites reran on all four hosts; prior exact gaps
remain separate. Removed two obsolete list subset exclusions only with new
positive coverage: extern 12 -> 11 and queried-function 13 -> 12. Alias/query
body/initializer diagnostics remain tested unchanged.

AST verifies 13 source-ordered concrete declarations, shared specifier base with
distinct function parameter graphs, pointer wrapping the same base, restored
outer typedef in sibling parameter lists, shared alias/query cache with distinct
symbols, later query capture of an earlier symbol, own definition register spill,
and no prototype runtime storage. Only parse.c and main.c implementation change;
no public AST/semantic/type/QBE source change. Exact generated limits and invalid
probes compile only. Final completion evidence is added after one frozen full
normal/QBE/both-host sanitizer/bounded fuzz run and source-manifest verification.

The pre-freeze semantic gate caught a new AST TEST assertion incorrectly equating
a previously resolved typeof cache with the canonical composite after a later
definition. Those caches must remain immutable; the symbol identity stays the
same, but register_function can replace its compatible composite type. The test
now asserts exact original declaration/captured-expression cache identity and
compatibility with the later canonical type, not mutable pointer equality. No
compiler source fix was needed. The earlier focused AST command's trailing log
print obscured its failure status; that result is NOT a semantic pass. The
serial pre-freeze gate stopped before any manifest/isolated tree/final validator
was created. The corrected AST suite passed as a standalone checked command;
final frozen validation is still required for the whole snapshot.

## Completion evidence

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

M15c1 exact-commit CI run 39009008993 and M15d1 run 39010665350 both completed
successfully with all three jobs green. New M15d2 exact-commit CI is pending until
checked after push; local passes never imply remote success.
