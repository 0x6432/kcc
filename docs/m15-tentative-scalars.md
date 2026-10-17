# M15g1: tentative file-scope scalar definitions

## Pre-implementation design record

The plan below was drafted against f2 source before coding and selected after
f2 was validated/pushed as e0a3b24. Historical expected counts are not evidence;
observed final implementation and exact frozen validation follow at the end.

## Language slice and standards basis

Permit file-scope declarations of existing complete scalars without a storage
specifier or initializer: `int count;`, `const int limit;`, `int *p;`,
`int (*callback)(int);`, and current nullptr type through typeof. Support repeats,
mixed function/object lists, typedef/query roots, and compatible extern/tentative
interleavings. All new objects have external linkage and static storage duration.
Keep f2 extern scalar/array declarations unchanged.

No array **tentative definitions**, static objects, explicit initializers (even
`=0` or `={}`), ordinary array definitions, block extern, thread/VM, inferred
file objects, or new scalar kinds. Pointer-to-array objects remain scalars.
`int a[]; extern int a[3];` is still refused: do not defer the unsupported first
array tentative until a later declaration makes it complete.

Grounding: local `/data/tools/c23/n3096.txt`/PDF, official publication
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf:

- 6.9.2p2: file object declarations without initializer/extern/thread_local are
  tentative definitions. In the absence of an external definition, finalize as
  one declaration with the TU-end composite type and an empty initializer.
  Thus `extern int x; int x; extern int x; int x;` owns storage exactly once;
  all-extern declarations own none. Emit unused tentative objects too.
- 6.7.10p11: default initialization gives integers zero and pointers null, not
  automatic-storage indeterminacy. 7.21.2p2–3 separately supplies nullptr default
  initialization and its void-null-pointer representation/size/alignment.
- 6.2.2p4–5 supplies external linkage/interleavings; static/internal cases stay
  outside this increment. 6.2.1p7 supplies publication after the full declarator.
- 6.9p5 permits at most one external definition across the program (exactly one
  when used). Do not test two tentative-owner TUs by relying on common merging.
- Unknown-array size-one finalization in 6.9.2p2/example 2 is deliberately pending,
  not implemented implicitly. An extern-only unknown array is never completed.

## Smallest representation: written provenance + one canonical anchor

Reuse the existing concrete object and unresolved external-type nodes; no new
external kind, generic union/symbol abstraction or storage list.

1. Add `bool is_extern` to `ast_external_object_declaration` (ast.h around 642),
   set explicitly by the parser. The unresolved node already carries is_extern
   and is_static. This preserves written provenance rather than guessing from
   the symbol's history or from a resolved query type.
2. Add one nullable pointer to `external_object_symbol` (sema.h):
   `struct ast_external_declaration *tentative_definition;`.
   NULL means no ownership in this TU; otherwise it is the **first successful
   tentative declaration**, concrete or unresolved. It is both ownership fact
   and unique emission anchor; no extra has_definition/emitted boolean needed.
3. Keep each declaration's resolved source type and expression/query captures
   immutable. Only the canonical composite type and initially-NULL anchor change.
   An early extern must not become the anchor merely because a later tentative
   definition shares its symbol. Repeated tentatives preserve the first anchor.

### Parser and sema changes

`src/parse.c:2519–2571,2650–2720` currently admits direct object nodes only with
extern; otherwise alias/query roots remain unresolved. Permit a direct object
node when either explicit extern OR no storage class, but continue refusing
written static direct objects. Generalize helper/comment/initializer diagnostic
wording narrowly: a bare object initializer is still unsupported. The existing
sole-direct-function-body rule and declaration budgets remain unchanged.

Resolve unresolved roots before classification: `typeof(f) g;` can still be a
function prototype; `typeof(&f) fp;` is a tentative pointer object. Written static
query-derived functions stay supported; written static query-derived **objects**
still fail. Do not classify by absent extern alone.

Both object semantic entry points should call one registration policy with an
optional tentative anchor (NULL for extern). Before registration/mutation, refuse
non-scalar tentative types and static objects; continue permitting existing arrays
on the extern path. Void is never admitted (`type_is_object` includes void).
Retain ordinary-namespace, compatibility/composite, and 256-object checks. After
successful registration set the anchor only if supplied and currently NULL.
Constructors must initialize provenance; do not accidentally turn old extern nodes
into tentative definitions via zero-initialized new fields.

Namespace: functions/objects/typedefs remain mutually exclusive at file scope;
locals, parameters and inner typedefs can hide a global. Own bounds/parameter
queries resolve before the new file name is registered; later list declarators
see earlier names. Local inference barriers still outrank global lookup.

## TU finalization and QBE emission

No new AST initializer or synthetic source declaration is needed. Sema already
walks the full ordered TU before any codegen; for this complete-scalar-only slice,
recording an anchor plus retaining the final canonical composite implements the
observable finalization. Add an explicit documented final invariant that every
anchored symbol is a complete scalar; no array completion and no initializers to
supersede the anchor are supported. Do not walk runtime expressions again.

The sema object's symbol-list head is private/transient, and
`ast_translation_unit` currently retains only declarations/strings. Avoid adding a
public canonical-symbol list solely for emission. During the existing codegen TU
walk (`src/codegen.c:1126–1146`), obtain the object symbol only from concrete object
nodes or resolved unresolved nodes; emit only when its anchor equals this exact
external node. Skip extern-only nodes, other repeats, typedefs and function-root
queries. Keep normal function emission and its error handling. Source-order data
and functions can interleave; forward `$symbol` addresses need no new lowering.

Use final canonical size/alignment, not the anchor's older source cache:

```text
export data $count = align 4 { z 4 }
export data $p = align 8 { z 8 }
```

QBE 1.2 `doc/il.txt` Linkage/Data sections specify export visibility, byte-count
`z`, and explicit object alignment. `parse.c:1080–1095` accepts data/align;
`emit.c:62–109` accumulates all-z bytes then selects BSS at DEnd; emitlnk applies
`.balign` and `.globl`. This is strong defined storage, not `.comm` merging.
No section flag, weak/common symbol, startup stores or allocation instruction.
Explicit align avoids relying on QBE's default 8 for char/short objects.

`type_object_size/alignment` already supply current 1/2/4/8-byte layouts.
All-zero bytes represent zero integers, object/function null pointers and nullptr
on kcc's existing amd64 SysV LP64 target. This is a target representation policy,
**not** a portable C rule that arbitrary null pointers are all-bits-zero. Backend
zero pointer/constants already assume this target; native interop must independently
confirm it. Const objects can use the same BSS allocation: C does not require
read-only placement. Keep const writes rejected and ordinary const loads non-ICE.

## Policy decisions / real source gaps

- Entry-point policy needs an explicit narrow decision: current main signature
  restrictions exist only in register_function. Recommend refusing a tentative
  object named main as a Linux hosted-entrypoint subset rather than emitting data
  at the startup entry symbol. Preserve current extern-only/local-name behavior;
  do not mislabel every declaration spelling main a C constraint. Object/function
  main collisions still fail through the ordinary namespace. Never run a program
  with object main as a supposed valid hosted entrypoint.
- Current symbol comments/diagnostics say extern/native-owned exclusively; revise
  affected descriptions, not all identifiers for cosmetic churn. Current codegen
  intentionally skips all object declarations; production emission is genuinely
  new and needs QBE/assembler/nm evidence. Source inspection is not that evidence.
- One anchor suffices only because explicit initialized definitions are forbidden.
  A later initializer milestone must redesign precedence/duplicate-definition
  bookkeeping; do not prebuild it now. Future static ownership/linkage also needs
  a separate design, not a type qualifier.

## Resource policy

Share the existing 256 canonical objects across extern scalars/arrays and scalar
tentatives; 512 concrete declarations count every repeat/list member; retain 256
functions independently. No new global-count or aggregate-byte budget. Current
scalar definitions are at most 8 bytes each (at most 2048 bytes for 256 symbols).
The existing 1 MiB bound is a per-array-type resolver policy, even for pointer
referents/extern arrays; per-function local storage/slot budgets remain separate.
Tentative globals consume no local slot/spill. Preserve all depth/query/parameter
limits and immutable composite checks; do not broaden array sizes.

## Required focused tests after selection

- Compile/native-oracle originals: bare, extern-before/after, repeated tentative,
  mixed lists, same-name alias/query redeclarations; different-name typeof creates
  a different object, typedef creates none, extern typeof creates no ownership.
  Functions through bare query roots stay functions. Scalars with array-pointer
  referent refinement preserve old expression/query caches and canonical identity.
- AST: written is_extern flags; first-tentative anchor stable across repeated
  concrete/unresolved declarations, never early extern; canonical identity and
  final type; captured types unchanged; no locals/slots/synthetic initializers.
- IL/nm: exactly one exported `z size`/align datum per owned canonical object,
  including unused/query-only owned objects; extern-only unused/query-only objects
  still emit none. Referenced extern-only objects are U, owned zero objects B (not
  U or C); inspect sizes/alignment. Track B/D/U distinctly: all-z QBE currently
  yields B, not D; future initialized D storage is not this milestone. One datum
  remains even when a function use precedes the tentative declaration.
- ABI/zero: all 12 integer leaves/full-width writes, bool, object/void pointers,
  function pointers and nullptr where native keywords are supported. Read startup
  zero/null before writes, compare exact addresses, mutate through native/kcc
  wrappers, verify in both caller directions. Test kcc-owned storage with native
  extern declarations, and retain native-owned storage with kcc extern declarations
  as distinct arrangements. Each executable has exactly one object owner, never
  a native tentative definition plus kcc tentative definition of the same name.
  A zero-initialized callback is only compared to null; assign a valid function
  before calling. Never dereference a zero pointer. Const owners are read only.
- Scope/constraints/subsets: namespace collisions both orders, local/parameter/
  typedef hiding and restoration, own-bound meanings and inference barriers;
  incompatible redeclarations/qualifiers; void, main-object policy, all initializers,
  static/block/thread/VM and array tentatives (complete/unknown/query/alias) refused.
  Keep f2 extern arrays positive. Invalid sources compile only, never execute.
- Exact 256/257 objects, 512/513 declarations, mixed object/function pools and
  repeated-list limits; unchanged locals/storage/depth boundaries. Then frozen
  normal/QBE/sanitizer/fuzz and native comparison matrix. No validation claims or
  implementation authorization are implied by this preparation.


## Current checkpoint and selected implementation

Design recorded before coding against validated/pushed M15f2 checkpoint
e0a3b24e63f7ec612982340749d6edbc5c6e12ad. Local HEAD and origin/development
match cleanly, with no reset/discard/stash deletion. Prior M15f1 CI run
39052481142 completed successfully with all three jobs green. New M15f2 CI is
pending independent verification, not implied by its local frozen passes.

Select written is_extern on concrete object declarations and one canonical
tentative_definition pointer to the first successful concrete/unresolved node.
No extra runtime storage list, symbol kind, generic AST union or initializer
interpreter. Sema accepts only current complete scalar tentative definitions;
pure extern arrays retain existing support but no ownership. Preserve static
object refusals and all function-root alias/query behavior. Canonical final type
supplies QBE export data alignment and zero-byte count; exact anchor identity
selects one emission, including unused definitions. Backend asserts complete
scalar ownership at TU-final emission. Hosted main objects remain an explicit
Linux subset refusal, not a fabricated native constraint.

Every compiler/source/test change must precede the final frozen validation.
Probe native tentative-finalization constraints with real compile-to-object
where syntax-only mode omits TU-end storage checks; no invalid C may execute.

## Final implementation and verification

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
