# M15g2: tentative fixed/unknown-outer array definitions

## Pre-implementation design record

The plan below was prepared before coding and selected after validated g1 was
pushed as 49aeb82. Historical proposed tests are not observed evidence. Final
implementation, audits and exact frozen validation are recorded below.

## Minimal slice and normative rule

Extend g1's unadorned file-scope tentative definitions from existing scalars to
existing arrays with complete elements: integers, pointers (including callbacks),
nullptr leaves and complete rows. Fixed positive or unknown OUTER bounds are
allowed. Keep static objects, explicit initializers (including empty/zero), block
extern, thread/VM, function/void elements, incomplete inner rows, array assignment/
copy/return and new storage mechanisms unsupported. Existing extern arrays and
scalar ownership remain unchanged.

N3096 6.9.2p2: if an identifier has tentative definitions and no external definition,
TU-end behavior is one empty-initialized definition with the final composite type;
only an unknown-sized outer array is changed to size one. Example 2 explicitly
shows `int i[];` becoming one zero element. Default element initialization follows
6.7.10p11, with nullptr supplied separately by 7.21.2p2–3. This is not a rule for
extern-only declarations or for arbitrary incomplete types nested within pointers.
Source: existing `/data/tools/c23/n3096.txt`/PDF; official publication:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

| Ordered declarations | Final canonical storage type / ownership |
| --- | --- |
| `extern int a[];` | unknown, unowned, no data |
| `int a[];` | int[1], one owner |
| `extern int a[]; int a[]; extern int a[];` | int[1], first tentative owns |
| `int a[]; extern int a[3]; int a[];` | int[3], first tentative owns |
| `extern int a[3]; int a[];` | int[3], first tentative owns |
| `int a[3]; int a[]; int a[3];` | int[3], one owner |
| `int a[2]; extern int a[]; int a[3];` | incompatible; no IL |
| `int rows[][3];` | int[1][3], one owner |

Unknown arrays are not provisionally size one during source analysis. Do not
finalize at each declaration, in resolve_type_syntax, in expression lookup, or
when first encountering the anchor in codegen.

## Smallest production changes

1. `register_external_object` (`src/sema.c:2234+`): remove/generalize only the
   tentative scalar-only refusal. Retain the shared scalar-or-array admission
   (not type_is_object, which includes void), main policy, compatibility/composite,
   namespace/budget checks and first-successful-anchor rule. Static refusal stays
   in existing parser/query classification paths. No new AST fields or pool.
2. Add a small semantic finalization helper over `sema.external_objects`.
   Call it after the **entire ordered TU** and successful existing internal-function
   checks, just before sema_translation_unit returns success (`:2527–2535`).
   The existing private list still exists then; no public unit storage list.
3. For each symbol: skip if no tentative_definition; leave complete scalars and
   known arrays alone. If the **top-level canonical type** is an array with count
   zero, create a fresh `type_new_array(arena, array->element, 1)` and replace only
   `symbol->type` after success. Never recurse into unknown pointees. For example
   `int (*p)[];` stays a scalar pointer to unknown array; `int (*a[])[];` becomes
   one pointer element whose array referent is still unknown.
4. If allocation fails, diagnose at `symbol->tentative_definition->location` and
   return false, leaving that symbol's type unchanged. Do not use an earlier
   extern's name location as the default finalization anchor. An exact identifier
   location can be recovered from the existing concrete/unresolved anchor if
   needed; no new generic source wrapper. Driver sema failure must emit no IL.
   Previously finalized canonical symbols need no rollback: the failed unit is
   discarded and never code-generated. Fault-injection can verify this contract.
5. `src/codegen.c:1151`: broaden the owned-type assertion to complete scalar OR
   complete array (and retain completeness). Existing exactly-once anchor emission
   already uses final canonical type_object_size/alignment and `export data ...
   { z bytes }`. Keep vfprintf/fflush failure handling unchanged. No array load,
   local alloc, startup stores or array-copy implementation.
6. Update only now-obsolete scalar-only/comment/refusal text and focused tests.
   Parser suffixes/concrete/unresolved nodes already preserve unknown-bound syntax;
   do not add a second declaration path. Explicit initialized definitions remain
   refused, so no initialized-definition precedence logic is needed yet.

## Immutable source snapshots and scope

Expression lowering copies the visible `object->type` into a concrete global
lvalue (`src/sema.c:1048–1060`). Type/query caches and declaration types are also
immutable. Finalization must replace the canonical pointer, never write an old
array->count or rewrite AST/typedef/function-return caches.

- `int a[]; sizeof a` is invalid at that source point, even if a later declaration
  supplies [3], or finalization would make [1]. Analysis fails before finalization.
- `int a[]; typedef typeof(a) Saved; extern int a[3];` leaves Saved incomplete.
  A separate `Saved b;` gets its own canonical [1] at TU end, but neither Saved's
  type nor b's written declaration type changes. `sizeof b` before TU end still
  rejects. `extern Saved c;` alone remains incomplete/unowned.
- A function returning `typeof(&a)` before completion retains pointer-to-unknown
  return type. `sizeof *earlier()` still rejects; element decay/indexing can work
  because its element is complete. Do not re-run sema over lowered functions.
- A same-name query tentative repeat shares identity/anchor; a different named
  query object owns separate storage. Typedefs create no owner by themselves.
- Own bounds/parameter queries resolve before name publication. Later members
  see completed earlier declarators, not future definitions. Preserve local/
  parameter/typedef shadowing, restored visibility and inferred-name barriers.

Typing `int a[]; int read(void) { return a[2]; }` can succeed without a known bound,
but executing it after only [1] finalization is out of bounds. A later compatible
[3] declaration makes that particular index runtime-valid. Keep such unresolved-
size/out-of-bounds candidates compile-only unless final allocated extent is
independently established. For fallback [1] runtime tests access only element 0;
for rows[][3], only row 0 and valid columns. One-past pointers may be formed but
never dereferenced. A zero callback element is never called until assigned.

## Bounds and finalization invariants

`src/sema.c:356–398` already resolves complete elements, ICE bounds and the 1 MiB
per-complete-array type/product limit, independently of allocation. Keep it intact.
Unknown outer arrays can have a complete 1 MiB row; defaulting to one row is at the
limit, while an explicit later two-row declaration must fail in the resolver.

The finalizer's direct constructor call bypasses that resolver policy: explicitly
check/assert complete elements, and enforce element_size <= ast_max_local_storage
before building the one-element array. Known canonical arrays have already passed
the resolver/composite invariants; retain a final complete-owned-type/size invariant.
Do not just rely on type_new_array: its guards are completeness/uint64 overflow,
not the 1 MiB policy. No multiplication overflow for count 1; no recursive
completion of incomplete inner arrays. Existing type_composite selects known
outer bounds and preserves compatible element layouts without mutating caches.

No new total-global-byte cap: use the existing 256 canonical objects shared across
extern/owned scalar/array symbols, separate 256 functions, and 512 concrete
ordered declarations including repeats. At most 256 MiB of owned arrays under the
existing per-type/count limits; exercise maximal combinations compile-only rather
than executing huge fixtures. Local 1 MiB/slots, query/declarator/typed-depth and
expanded typedef budgets stay separate and unchanged.

## Required evidence after selection (not performed here)

- AST: untouched written empty bound/count-zero type/cache and earlier global
  expressions; canonical [1] after TU finalization only; same anchor through early
  extern/repeats; later known bound wins; distinct query objects finalize
  independently; unowned unknown externs remain count zero. Confirm function
  signatures, whole-array address captures and typedefs do not acquire later
  bounds. Scalars and pointers-to-unknown arrays do not get recursively completed.
- Acceptance/refusal: table above, aliases/typeof/typeof_unqual, const rows,
  callback/pointer/nullptr arrays; incompatible bounds/shapes/qualifiers/name
  collisions; incomplete inner/function/void elements, non-ICE/VM/bad bounds,
  initializer/static/block/thread/main policies and array-copy/return refusals.
  Earlier sizeof unknown and whole-array arithmetic reject despite later bounds.
  All invalid candidates compile only; never execute them as native or kcc C.
- IL/nm: one exported z datum at the existing first-tentative anchor, with final
  bytes/alignment for fixed/completed/default-one arrays, including unused or
  query-only **owned** arrays. Unowned query-only externs have no data/U; evaluated
  extern-only references are U. Owned all-z storage is B, not U/common C; track
  B/D/U separately. No extra local alloc or scalar load of an entire array.
  Preserve output-error handling and f1/f2/g1 symbol/linkage regressions.
- Native/QBE: unchanged zero-owning TU + extern-only companion, separately
  compiled with `-std=c2x -pedantic-errors -fno-common -c`; never define the same
  object in both. Both driver directions, all primitive widths, exact owner
  addresses, zero/read/write, default-one and later-known arrays, row strides,
  pointer/callback element mutation, const reads and keyword-gated nullptr leaves.
  Check g1 all-zero representation assumptions independently. Retain native-owned
  extern-reference coverage as a distinct category, not duplicate ownership.
- TU-end unknown-array diagnostics: first capture actual original-source native
  `-c` results, compiler versions/flags, statuses and full normalized error/warning/
  note records. Syntax-only may omit finalization checks. A permitted warning is
  not a rejection or feature gap; do not assume clean stderr, turn it into an
  error, or add a broad warning waiver. Any allowed warning classifier needs
  exact unchanged source/status/sequence plus changed-source/status and extra/
  missing-record negative controls. No exact native warning strings are asserted
  by this unprobed draft; audit before integrating. kcc need not invent a warning
  just to match a native implementation's optional diagnostic.
- Limits: 1 MiB exact/one-element-over complete arrays, one 1 MiB row fallback,
  oversized later completion; 256/257 shared objects, 512/513 declarations,
  mixed function pools, repeats, 64/65 dimensions and unchanged depth/local limits.
  Finalization allocates one array node per owned still-unknown canonical object,
  not per declaration. Inject allocation failure if infrastructure permits; check
  source location, false semantic result and no partial IL. Then run the full
  exact frozen matrix on the eventual selected candidate.

## Remaining uncertainty / gate

No new backend operation or generic abstraction is needed by source inspection.
The new semantic finalization pass is real work: immutable pointer replacement,
outer-only completion, resource guards and allocation failure must be validated.
Native warning behavior is deliberately unresolved until real -c probes. Future
initialized definitions would supersede tentative-only finalization and require
new bookkeeping; keep them unsupported here. Nothing in this draft modifies or
claims results for g1's running frozen validation.


## Native implementation audit before selection

The outside compile-only audit m15g2-native-warning-audit.md and saved JSON
preserve all 74 original owner/companion pairs. GCC14/GCC11 allocate expected
storage. Clang18 underallocates four later-known-completion originals, Clang15
two applicable non-keyword originals. These native objects must never link/run
or count as agreements. Final-one warnings on correctly allocated objects are
optional diagnostics on valid C, not feature gaps. Every native runtime needs
source/diagnostic validation AND exact strong owned symbol sizes before linking.
Original sources must remain unchanged. Correct kcc/QBE ownership validation is
independent. Exact classifier portability across CI vendor versions is reviewed
before integration; no pending waiver is treated as observed agreement.

A finalizer allocation-failure probe can build an isolated compiler without LTO
and --wrap=type_new_array: int items[]; reaches that constructor only at TU-end.
Require unwrapped exact-size success; wrapped failure at the tentative anchor
with empty stdout. Wrapped extern-only unknown arrays and scalar tentatives
are no-finalizer-call controls. Fixed arrays are NOT such controls. No public
allocator API or broad infrastructure change is needed.


## Selected checkpoint and implementation decisions

Selected BEFORE coding against validated/pushed M15g1 commit
49aeb8241f55c21c3f34a40231811ebfdc08c376, clean local/remote equality.
M15f2 CI run 39056814296 has all three jobs green. New g1 CI is independently
checked after push and remains pending until completion, never inferred locally.

Admit tentative arrays with the same scalar-or-array registration policy as
extern declarations. Use neutral file-scope-object diagnostic wording for void
and other unsupported kinds; retain main/static/initializer refusals. Add one
private TU-end finalization helper over the existing canonical object list. It
checks complete elements and the retained per-type 1 MiB policy, then allocates
a fresh one-element array only for anchored still-unknown OUTER arrays. Allocation
failure reports at that tentative anchor and prevents IL. Never mutate source
types/caches; known composites win, extern-only and pointer referents stay intact.
Codegen requires a complete object and reuses anchor-selected zero data emission.

Portable native audit policy: independently probe compiler family and the exact
Linux amd64 LP64 little-endian/signed-char target macros; log exact version.
Match only frozen original sources, flags, full diagnostic sequences and exact
owned symbol layouts. No AWS vendor-version/executable-name assumption. Correct
layout optional warnings are separate agreement candidates only after safe runtime
success. Exact Clang undersized outcomes never link/run or count as agreement.
Corrected layouts cannot match the old bug category. Unknown messages/layouts fail
closed. All ownership paths require mutable B/D; R only for exact const ownership
records. Clear previous output files before compilation. Actual Ubuntu CI remains
pending until the new run: the policy is not a claim of observed CI acceptance.

Only obsolete tentative-array refusals are updated; original positive fixtures
are not rewritten to manufacture native agreement. Build helpers serially before
focused parallel validation. Freeze source/tests/Makefile only after integration
and preflight; stop all validators before fixes, retire and rerun full snapshots.

## Native storage audit retained before final validation

See m15-tentative-arrays-native-audit.md for exact unchanged originals, compiler
versions, emitted zero reservations and actual ELF section extents. This confirms
the Clang outcomes are genuine underallocation, not symbol-size metadata alone.
The affected native objects were never linked or executed. The focused harness
separately proves QBE allocation using directives, symbol offsets and BSS extent
because QBE1.2 intentionally omits ELF data .size metadata; native nm-S guards
remain mandatory and are not replaced by that QBE-specific proof.

## Final implementation and verification

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
