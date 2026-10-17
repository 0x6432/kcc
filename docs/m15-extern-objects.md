# M15f1: declaration-only external scalar objects

Design recorded before implementation against fully validated and pushed M15e1
checkpoint 1b44e97f1677a9225bd1d5c5f0f8987b830f50e3. Local HEAD matches remote
development with a clean worktree. Prior M15d2 exact CI completed with all three
jobs green; new M15e1 CI is independently pending. No runtime data allocation or
definitions are implied merely by supporting an external reference.

## Proposed minimal language slice

File-scope explicit extern declarations of current complete scalar objects:
integers, object/function pointers and the existing nullptr type through typeof.
No initializer, no tentative definition, no static/global/local object definition,
no block extern, no arrays as externally declared objects, no inline/thread/VM.
Pointers to arrays remain ordinary scalar objects and preserve pointee composites.
External functions remain supported including mixed function/object prototype
lists under one extern specifier base, if the concrete-tail audit supports this
without a second parser or changing budgets. Source order remains authoritative.

A native TU owns each object's storage. kcc may read/write/address/pass/call an
external scalar object using the existing lvalue/load/conversion machinery. Const
objects stay nonmodifiable; function-pointer objects are object lvalues, not
function symbols. Unused extern declarations emit nothing. No data directive,
local spill, hidden implicit allocation or unresolved-reference validation is
introduced; linking a missing externally provided definition remains a linker job.

## Namespace and representation proposal

Keep separate concrete AST: ast_external_object_declaration for syntactically
object declarators, and ast_external_type_declaration for alias/query roots still
unresolved until sema. The latter must carry the written extern permission and
resolved object symbol separately from its existing function symbol; assert only
one is present. Do not repurpose local declarations or add a generic union AST.
Written storage flags belong only to concrete external declarations. Existing
function-only unresolved alias declarations continue classifying as before.

Canonical external_object_symbol records original name and current compatible
composite type; no storage slot/initializer/definition flag yet. A bounded pool
of at most 256 distinct objects, separate from the existing 256 functions, fits
inside 512 total concrete external declarations. Compatible redeclarations reuse
one symbol; differing qualifiers/types and object/function/typedef collisions in
the file ordinary namespace fail before mutation. File aliases/functions must
check prior object names too; block aliases/parameters/locals may hide them and
scope exit restores visibility. Objects do not turn into typedef syntax bindings.
Audit shared declaration-specifier caching: own complete declarator before name
publication; no initializer is permitted in this increment. Do not pollute a
nested function parameter scope or silently overwrite same-scope aliases.

At the existing expression_name entry: nearest local or nearer alias wins, else
external object wins before a file function. Replace the name with a distinct
ast_external_object_expression carrying canonical identity and a snapshot of its
visible type; set object lvalue. Do not make address-of/register checks dereference
a nonexistent local declaration. Existing bare-call precheck must recognize
external objects, so function pointers can be called and nonfunction scalar calls
get the proper constraint. Lowered-node switch and constant evaluator must list
new semantic nodes explicitly; no accidental expression_name assumptions.

QBE address emission copies the external symbol name into a temporary using the
same global address form as functions. All loads/stores/updates/subscripts then
reuse existing typed machinery, but extern scalar declarations emit no data.
Function and object lookup pools share ordinary-namespace conflict checks, not a
speculative generic symbol abstraction. Compatibility/composite types preserve
immutable source/query caches and previously captured expression identity/types.

## Required audit before finalizing

C23 6.2.2/6.7/6.9 constraints versus subset refusals, exact extern qualifier rules,
complete scalar/nullptr type handling, prototype-scope ordinary-name restoration,
point of declaration in later parameter queries, own-bound outer-name meanings,
and typedef same-scope versus nested scope precedence. Verify the actual
external-declarator parser and constructor shapes rather than guessing fields.
Every switch on expression kind must be audited; compilation with warnings/Werror
will expose incomplete switches but does not replace semantic review. No unbounded
symbol lists or data layout work hidden in this increment.

## Proposed focused evidence

Defined curated multi-TU host-owned globals: every full-width primitive, pointer
and function pointer, reads/writes/addresses/updates, const reads/refusals, block
and parameter/typedef shadowing, nested initializer capture and restored meanings,
query-only use with no referenced linker symbol, compatible composite pointer-to-
array declarations, exact captured object identity and immutable type caches.
All invalid conflicts, unsupported definitions/initializers/arrays/storage and
resource boundaries compile only. ABI arrangements must independently establish
native agreement; never execute unresolved or uninitialized external objects.

At least 24 both-direction object-reference arrangements: kcc accessing native
storage and native accessing a host-owned object through kcc wrappers; function-
pointer-object callbacks and row-pointer objects. nm U for referenced extern
objects, no allocation for unused/query-only declarations, unchanged local slots
and existing static t/export T behavior. Exact 512 declaration/256 object/256
function/mixed pools, plus existing parameters/locals/storage/depth limits.
Serial helpers before frozen full normal/QBE/sanitizer/fuzz matrix. Draft final
docs outside, apply only after every validator and manifest passes, commit/push,
verify clean local==remote, check exact CI independently. No full C23 claim.

## Read-only audit refinement while M15e1 validates

The current semantic ordinary-name chain resolves nearer typedef versus local
objects first; file-level object/function/typedef collisions can be checked in
separate pools without introducing another scope abstraction. File external
objects cannot legally hide a file typedef in the same scope, while block aliases
may hide outer objects. Existing parser_name_object masks suffice for completed
file object declarators too, restored by each function/parameter scope's saved
chain. Keep exact point of declaration AFTER the whole declarator; own bounds/
parameter queries still see prior entities. Publish aliases unresolved until sema
as ordinary names just like current aliases/query-derived functions (audit this
path; do not change earlier valid prototype typedef lookups accidentally).

Proposed external tail classification: direct function syntax stays on existing
function path. A non-query syntactic object with written extern gets the new
object node (arrays later rejected explicitly in sema); otherwise preserve old
file-object refusal. Alias/query roots retain the unresolved node, recording
written extern permission, then sema selects a scalar object or function. A
function-pointer declarator has outer pointer syntax: it is an object, never a
function declaration. Written static object forms remain a refusal. Every member
counts exactly once and shares the same immutable specifier base. Bodies still
require the sole direct function declarator; object initializers are refused
before publication/type binding and produce no partial IL.

Current codegen_address assumes expression_name always denotes a real local and
emits %vslot. The new concrete lowered object expression must instead emit $name.
Current sema address-of and array-decay register checks also assume expression_name
has a local declaration, so keep that invariant by replacing global names rather
than overloading ast_name_expression. Bare-call diagnostic precheck must include
find_external_object. ast_call.function stays NULL for function-pointer objects;
only actual direct function-designator calls get the canonical direct target.
Constant evaluator already returns nonconstant in its default case; audit whether
an explicit external-object case improves readability without altering old ICE
limitations. Both pointer-composite and expression snapshot types stay immutable
when later compatible declarations refine canonical types.

Native compile-only audit retained in /data/tools/m15f1-native-object-probes.json:
all four hosts accept six exact scalar/repeated/qualified/composite/mixed-list/
shadowing forms and reject seven object/function/typedef/qualifier/pointee-bound/
const-write constraints. Probes were compiled to objects only, never executed.
For new runtime tests every native-owned object must be explicitly initialized
before any read. Keep initializers/definitions native-owned and distinct from
kcc's declaration-only slice. Preserve the existing 24 mixed-stack function ABI
arrangements as well as the new 24 primitive object-reference directions; do not
relabel one arrangement as another merely to keep a historical count.

Focused interactions to retain in the final design: extern typeof(&private_fn)
fp is an external pointer OBJECT even when private_fn has internal linkage and
no definition (its only use is the non-VM type query). Native storage can hold a
compatible different function pointer; do not accidentally emit/reference the
private function or turn fp into a direct function target. Conversely extern
typeof(private_fn) another declares a FUNCTION, not an object. The unresolved
alias/query node's resolved kind, not the extern spelling, selects the branch.

Capture a pointer-to-incomplete-array object in an earlier function body/type
query, then redeclare the external object's pointee bound as known. Canonical
composite may refine, but the earlier expression/query snapshot must retain its
original compatible type and exact symbol identity. Address/load width remains
pointer-sized; never retroactively type-check earlier source against a later
composite. Actual object arrays remain an explicit deferred slice.

## Final audited decisions before implementation

Support mixed explicit-extern function/scalar-object lists with one immutable
specifier base. Add concrete ast_external_object_declaration, semantic
external_object_symbol and lowered ast_external_object_expression; use
external_object_declaration / expression_external_object enum tags. Keep one C
implementation per existing stage. No generic declaration union or symbol table.
Add ast_max_external_objects=256, independent of existing 256 function symbols and
512 total concrete declarations. Current type_is_scalar includes nullptr, so
explicit typeof(nullptr) object declarations use the existing complete scalar
representation; no ad-hoc exclusion. Object arrays and void/incomplete objects
remain clear subset refusals, not fabricated native constraints.

The unresolved alias/query node retains is_static and gains written is_extern
permission plus an object-symbol pointer separate from the function-symbol pointer.
Only one resolved symbol may be populated. Sema selects function versus scalar
object from the resolved type; extern typeof(f) is not automatically an object.
Syntactically object-shaped extern declarators use the concrete object node.
Initializers remain unsupported definitions, not native constraint claims.

Audit correction to the exploratory parser-binding proposal above: completed
file ordinary names need NO new syntax bindings. Like current file functions,
file object names cannot legally hide a file typedef in the same scope; same-scope
collisions are rejected semantically before any later declaration is analyzed.
Absence of a typedef binding already classifies an ordinary identifier correctly.
Retain existing parameter/block/for syntax-mask lifetimes unchanged, rather than
adding an asymmetric file-only mask for a distinction the parser does not need.
Semantic registration after complete type/declarator resolution supplies the exact
point of declaration for later members and queries. Do not broaden block extern.

register_external_object performs file namespace/type compatibility/composite
checks before mutation and retains canonical identity without runtime storage.
Function registration and file typedef declaration check prior external objects;
block aliases/locals/parameters may hide them. expression_name resolves the nearer
alias/local first, then external object, then file function. Lower only global
object names into the new concrete lvalue expression. Leave local-only register
checks and %vslot address assumptions intact. The existing bare-call precheck must
recognize objects, and function-pointer-object calls stay indirect (call.function
NULL). QBE global addresses use $name; declarations never emit data. Constant
expression checks must still reject ordinary object loads, including const objects.

Remove only three obsolete extern-object refusals and one mixed-list refusal with
positive replacements. Keep extern initializer probes as explicit subset refusals
with updated diagnostic, plus every plain/static object restriction. Add required
name/type/const constraints, unchanged originals/native-owned runtime globals,
source snapshots/canonical composites/prototype scopes and budget/IL/nm tests.
Validate all final source changes, grammar comments and tests in one exact frozen
matrix; archive retired candidates rather than mixing their evidence. Full
normal/QBE/ASan/UBSan/fuzz and original-source ABI workflow remains mandatory.

## Final implementation and verification

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
