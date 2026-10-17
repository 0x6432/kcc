# M15f2: declaration-only external arrays

## Pre-implementation design record

The plan below was recorded before coding. Final observed validation follows at
the end; expected counts in this historical plan are not evidence.

## Minimal next slice

Extend explicit file-scope `extern` objects from the existing scalar slice to
arrays of currently supported complete object elements. Allow a known positive
outer bound or an unknown outer bound; inner elements/rows must remain complete.
Examples: `extern int a[3];`, `extern int a[];`, `extern int rows[][3];`, arrays of
object pointers, arrays of function pointers, and current nullptr scalar leaves
through `typeof`. Arrays of functions or void and unknown inner dimensions are
not admitted. Typedef/query roots resolve through the existing external-type
node and classify by their resolved type, not spelling.

No initializer, definition, tentative definition, data allocation, block extern,
static object, thread-local object, VLA, aggregate assignment, array return, or
new storage-duration mechanism is included. An unknown-bound declaration is not
completed to one element at translation-unit end: it is a declaration, not a
tentative definition. A native owner supplies the actual initialized object.
Missing referenced definitions remain the linker's responsibility.

Keep the M15f1 complete-scalar behavior unchanged, including nullptr. Do not
accept arbitrary new object kinds just because an array is now an object.

## Proposed implementation surface and audit

The likely minimal production change is the registration acceptance predicate:
accept existing scalar types OR `type_kind_array`, retaining all namespace,
compatibility/composite checks and limits. Do not require a complete outer array
in that predicate. Existing recursive type resolution already rejects incomplete
array elements and enforces positive bounds and bounded array-size products.
Audit this against the final f1 tree before editing; this is not a license to
skip semantic/codegen or standard-constraint review.

Keep the existing concrete `ast_external_object_declaration`, unresolved
`ast_external_type_declaration`, canonical `external_object_symbol`, and lowered
`ast_external_object_expression`. Do not add a generic declaration union, a
second array symbol pool, a separate expression-name lookup path, local slots,
initializer bookkeeping, or a storage emitter. Resolved alias/query nodes must
still populate only the appropriate object OR function symbol field.

Array expressions remain object lvalues; value contexts perform exactly one
existing array-to-pointer decay. `&array` is a pointer to the entire array, not
a pointer to its first element; `sizeof`/type queries suppress decay. Existing
codegen_address for an external object emits `$symbol`, and existing array-decay,
subscript/row addressing and element load/store/update machinery should suffice.
Do not load an entire external array as a scalar or load a nonexistent pointer
slot as if the array's first bytes held a base address. Callback elements are
indirect callees; taking an element address gives a pointer to the pointer object
and mutation changes that element, not a function symbol.

Audit every affected lowered-node switch, register-address exception, query
context, bare-call check and address path. The fact that scalar f1 already uses
a distinct lowered object node should prevent local-declaration dereferences,
but is not proof that every array path is covered. Preserve local alloc/slot
accounting and existing static-function `t` / exported-function `T` behavior.
Main integration should add direct AST/type-cache tests as well as this draft's
source-level tests; those unit edits are not part of this preparation.

## Source order, compatibility and immutable caches

- Unknown-bound and compatible known-bound redeclarations share exactly one
  external-object identity. The canonical composite becomes complete when a
  bound is supplied, and a later unknown declaration does not erase that bound.
- Different known bounds, different row shapes, incompatible pointer leaves,
  differing element qualifiers, or array-versus-scalar/pointer declarations
  reject before mutating the canonical symbol. Ordinary-name collisions with
  functions and typedefs remain symmetric.
- A previously captured expression/type query or typedef of an incomplete array
  must not acquire a later canonical bound retroactively. Earlier `sizeof a`
  remains invalid; `typedef typeof(a) Saved` before completion still denotes an
  unknown-bound array independently of the later canonical object type. Earlier
  functions returning `Saved *` preserve that referent while returning the exact
  same object's address. Valid decay/indexing can still address actual elements
  of the separately initialized owner.
- Mixed function/scalar/array declaration lists share one immutable specifier
  base; each completed declarator becomes visible to subsequent members.
- Resolve an own declarator bound before publishing its local name. The draft's
  `extern int items[3]; ... long items[sizeof items];` uses the outer 12-byte
  array in the bound, creates twelve local longs, then checks the local size.
  Conversely a scalar `int items=sizeof items` initializer sees the newly
  published local int, not the external array. Neither case reads an
  uninitialized local value.
- Later parameter queries must see a current adjusted array parameter (`int *`),
  not an outer file array. Preserve all established prototype-scope restoration
  rules and inferred-name reservation: an unavailable inferred local must not
  fall back to an outer array, even inside sizeof/typeof or a dead branch.

## Existing bounds to preserve, not raise

1. Exactly 256 canonical external OBJECTS shared by scalars and arrays, separate
   from the 256 canonical functions. Do not allocate 256 new array symbols.
2. Exactly 512 concrete external declarations, including repeats and mixed lists.
   The draft fills 128 scalars + 128 arrays + 256 functions together, then checks
   the next declaration fails, and tests the object pool independently.
3. Existing 1 MiB maximum known array type size/product, including nested rows
   and bound refinement. A single `char[1048576]` passes, one extra byte fails;
   the corresponding int and row-product boundaries remain checked. An unknown
   outer bound can have a complete 1 MiB row, but completing it with two such
   rows exceeds the existing limit. This is a subset/resource policy, not a C
   constraint or a statement that external storage is allocated by kcc.
4. No cumulative external-storage budget: two separately declared 1 MiB arrays
   remain legal declarations. An external 1 MiB declaration consumes none of a
   function's separate existing 1 MiB local storage allowance.
5. Existing 64 dimensions per concrete declarator, checked at 64/65 for both
   complete and unknown-outer forms. Do not imply a new global dimension counter
   or silently alter expanded-type/expression-depth limits for typedef chains.
   Retain the existing expanded-depth checks and f1 regression suite unchanged.

## Draft test inventory

`/data/tools/test_extern_arrays-draft.py` is structured for its eventual path
`tests/test_extern_arrays.py`. Its root intentionally resolves relative to that
future path. Do not run it in /data/tools against f1 and mistake resulting
rejections for regressions. Integration and removal of obsolete array refusals
belong to the main agent after f1 is pushed; this preparation does not edit the
frozen f1 suite or any repository file.

Proposed inventory, not execution results:

- **72 initialized paired native-owner arrangements**: 48 primitive arrangements
  (12 integer leaves x fixed/unknown outer x both caller directions), plus 24
  interactions. Both directions compare full-width values and exact addresses
  of owner storage; wrapper returns distinguish whole-array address from decay.
- Interactions cover fixed/unknown row strides, three-dimensional layout,
  pointer-array slot writes, function-pointer-array slot writes, native-driven
  callback replacement, void callbacks, pointer-returning callbacks, const leaves
  and const pointer elements, mixed function/scalar/array/callback lists, canonical
  composites, local own-bound publication, aliases and typeof snapshots, and
  current nullptr leaf arrays.
- **34 compile-only native-constraint originals**: 30 baseline + four typeof
  originals. Each is submitted unchanged to kcc and strict native syntax checks
  (when the exact required keyword probe succeeds). Includes bound/shape/type/
  qualifier/name conflicts, invalid elements, VM file declarations, incomplete
  sizeof/whole-array arithmetic, array assignment/update/call, invalid pointer
  conversions, const writes, non-ICE loads, and immutable earlier query types.
- **Nine compile-only subset/storage refusals**, with no native-rejection claim.
  Existing unrelated inline syntax refusals remain covered by the frozen f1 suite.
- **Six kcc-only inferred-name barriers** over an outer external array. Do not
  require native rejection, count them as agreements, or execute them.
- Generated compile-only 256-object/512-declaration/1-MiB/64-dimension boundaries,
  no data or extra local alloc, query-only absence of linker symbols, and nm
  `U` array/callback references alongside normal private/public function symbols.

## Native oracle, safety and deliberate assumptions

Reuse the frozen f1 helper approach: a fresh temporary directory; compile the
unchanged kcc TU and its initialized native storage owner into separate objects;
run the native pair independently and, when QBE is selected, the kcc/native pair.
Every owner object and callback slot is explicitly initialized. All pointer
arithmetic stays within an actual array or one-past it; every dereferenced index
is backed by the owner. No unresolved, uninitialized, dangling, invalid or fuzz
source is executed. No source is rewritten to manufacture agreement.

Probe typeof, typeof_unqual and nullptr independently with the frozen f1 exact
source/status/full error-warning-note-record classifier and negative controls.
Unsupported keywords gate only relevant native originals. They do not suppress
kcc compilation. A plain-C owner still enables kcc/QBE execution of query-derived
programs on legacy hosts; only the nullptr owner needs keyword support itself.
No broad native failure waiver or inferred-typedef gap classifier is added.

The one-dimensional `typeof_unqual(source)` case deliberately exercises array
unqualification without the known multidimensional const-array host issue.
Its untouched modern-native source MUST pass or receive a standards/source audit
before integration. There is no speculative fallback, qualifier rewrite, or
waiver in this draft. Diagnostic fragments likewise follow current code and
must be verified against the actual f2 implementation; only Python syntax has
been checked. ABI expectations retain the existing amd64 SysV LP64 target
(int 4, long/pointer 8; existing char policy), not a portable host claim.

If all assumptions hold, modern hosts should produce 72 unchanged native
agreements and 72 QBE pairs, with 34 native rejections. Hosts lacking all three
keywords should produce 66 native agreements, six gated native pairs, 30 native
rejections, 71 QBE pairs and one nullptr-owner keyword gap. These are EXPECTED
counts, not observed validation. The retained f1 suite separately continues its
24 simple-object and 24 mixed-stack primitive ABI arrangements; the 48 array
arrangements here are a third, distinct category, not a relabeling of f1 evidence.

## Later validation and integration gate

After f1 is pushed and f2 is implemented, promote the draft, review exact error
paths and run all four focused host configurations with and without QBE as
appropriate. Keep native agreements, exact keyword gaps, constraints, subset
refusals and kcc-only barriers separate in results. Add targeted semantic AST
checks and only then retire obsolete array refusals with positive replacements;
retain extern initializers/definitions, void objects, block extern and other
existing refusal coverage. Main owns Makefile registration and full exact-frozen
normal/QBE/sanitizer/fuzz validation. No full C23 claim follows from this slice.


## Current checkpoint and implementation decision

Design recorded before coding against validated/pushed M15f1 checkpoint
b64e0f9c464db044143dcc1b2c5e43a87058dbd8. Local HEAD and origin/development
match with no pre-existing worktree changes or discarded stashes. M15f1 passed
all local frozen checks; its new remote CI is pending independent completion.

Proceed with the scalar-or-array registration predicate only, and update the
array-suffix grammar comment to distinguish incomplete extern declarations from
complete local storage. Do not use type_is_object, which currently includes void.
No AST/type/codegen/storage algorithm change is planned. Current resolver retains
its 1 MiB per-array-type ceiling even without runtime allocation. Existing scalar
extern tests retain all other scope/storage refusals; replace exactly the two
obsolete array refusals with focused positives, updating the void subset message.

## Pre-implementation array-unqualification audit

## Finding

**Native implementation/feature gap relative to N3096, not a kcc
array-unqualification bug.** The original one-dimensional test is valid under
that draft. Keep it unchanged; do not make kcc retain element const to match the
native failures. This conclusion is scoped to the inspected N3096 semantics and
recorded GCC14/Clang18 results, not a claim about every compiler release or final
standard revision.

## Authoritative grounding

Read the existing `/data/tools/c23/n3096.txt` (April 1, 2023 working draft; PDF
beside it). Official publication: https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

- **6.3.2.1p3** explicitly exempts typeof operands from array-to-pointer conversion.
  Thus `typeof(source)` describes the const-int array, not a pointer.
- **6.7.2.5p5**: typeof_unqual yields the non-atomic unqualified type that typeof
  would yield; typeof preserves all qualifiers.
- **6.2.5p31**: an array and its element type are always considered identically
  qualified. The exception is _Atomic, not const (footnote 54). **6.7.6.2 footnote
  173** reiterates the array/element rule.
- **6.7.2.5p7, example 2** makes the intended operation explicit:
  `const char* const animals[]` becomes `const char* animals2_array[3]` under
  `typeof_unqual(animals)`. Element-pointer const is removed; the pointed-to char
  const remains. Consequently a const-int array becomes an int array. For nested
  arrays the identical-qualification rule applies through each array layer;
  it does not recursively strip const through a pointer referent.

## Exact original and recorded evidence

`/data/tools/test_extern_arrays-draft.py:161–165` contains:

```c
extern const int source[3]; extern typeof_unqual(source) target;
int main(void) { typeof_unqual(source[0]) value=source[1]; value+=2;
    target[1]=value; int *p=target; return p[1]; }
```

Native owner, unchanged: `const int source[3]={0,40,0}; int target[3]={0,0,0};`.
Under N3096, target has type int[3]; the element assignment and decay to int* are
both valid, and the initialized pair would return 42. No execution was performed
for this audit.

The recorded compile-only JSON has two host records. Each reports 143 accepted
positive fragments of 144, all 34 constraint rejections, and this sole original
failure with status 1. GCC14 diagnoses read-only `target[1]` plus discarded const
in pointer initialization. Clang18 diagnoses read-only assignment plus a pointer
initializer whose source is explicitly printed as `typeof_unqual (source)` aka
`const int[3]`. Both errors are manifestations of retaining array qualification,
not evidence that the original needs rewriting. Do not suppress errors and run
these native translations: their retained target type also disagrees with the
owner's intended mutable definition.

## Existing kcc path and precedent

`src/sema.c:300–320` resolves type-name and expression typeof_unqual via the same
unqualified_type helper. Expression queries use unevaluated analysis with no root
load/decay (`:238–247`). `src/type.c:263–307` unqualifies by copying array layers
and their elements, preserving counts; at a pointer it clears only that pointer's
qualifiers and retains the referent. Constructors (`:97–125`) mirror element
qualifiers on arrays. This matches the clauses/example and leaves source caches
immutable. No correction to these paths is indicated by the native evidence.

`tests/test_typeof_types.py:26,66–80,123–127` already covers the multidimensional
type-name form `typeof_unqual(const int[2][3])`, with an exact-source/read-only-
assignment native-gap classifier citing the same rules. It is precedent, not
an existing exemption for this different one-dimensional expression original.
The new original has two diagnostics per host, so the old single-error matcher
must not be reused unchanged or widened to a generic const-error waiver.

## Recommendation / limits

No waiver or repository change made. If the main implementation later records a
native-gap classification, gate it on this exact unchanged original, host family,
nonzero status and the complete expected normalized diagnostic sequence (both
errors; reject unexpected warnings/notes/errors). Add classifier negative controls
for changed source/status and extra/missing diagnostics. Count it separately as
a native feature gap, never native agreement. Retain strict compilation of its
owner and independent keyword probes; retain kcc AST/IL/runtime checks of the
valid original only after f2 implementation and native-owned storage validation.
No new compiler invocation, build output, C execution or public fetch was needed;
this audit used local authoritative text, source inspection and existing JSON.

## Final implementation and verification

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
