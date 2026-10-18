# C23 coverage

Current storage checkpoint: M15i2 adds explicit pointer definitions initialized
by proved null constant expressions. M15i1 integer ICE definitions and M15h1–h2
internal tentative scalars/fixed arrays remain supported. Explicit-over-tentative
ownership, immutable captures and internal/exported storage are shared. Symbolic
addresses, pointer arithmetic/conditionals, nullptr_t targets, array/braced
initializers and block storage remain absent. See m15-null-initializers.md,
m15-integer-initializers.md and m15-static-objects.md.
This is still a subset, not ISO conformance.

Status vocabulary: absent, subset, implemented, validated. Implemented means
code exists, not that conformance has been established. Validated requires
recorded tests and a stated target. This is a coverage inventory, not a claim
of complete ISO conformance.

| Area | Current status | Owning milestones |
| --- | --- | --- |
| Source/translation phases | subset (newline policy, splicing, physical mappings; M09a) | M01, M09-M11, M25 |
| Tokens and literals | subset (raw pp boundary, shared spelling decoder, runtime ordinary byte characters and four-base/separator/U/L/LL integer literals; M12j) | M02, M12, M20, M23 |
| Declarations/types | subset (_Bool, plain/signed/unsigned char, signed/unsigned short/int/long/long long; M12j; object pointers, fixed multidimensional arrays, ordinary strings and adjusted array parameters M13k; parenthesized object/abstract declarators M14a and fixed function suffixes M14e, callbacks/void M14f-g and const qualification M14j2; query-derived types and scoped typedef lists through C23 for initializers M14l2b and ordinary-name shadowing through parameter/prototype scopes M14l3b and typedef specifier placement M14l4 and scalar block/for register objects M15a1 and non-decaying fixed register arrays M15b1 and explicit-type auto objects M15a2) | M03, M08, M12-M18, M23-M24 |
| Expressions/statements | subset (integer arithmetic/conversions/casts; object-pointer lvalues, scaled arithmetic and comparisons; M13d; sequenced comma/conditional expressions, integer compound assignments and updates; direct goto and integer switch/case/default through M19f2) | M03-M08, M13, M19 |
| Constraint diagnostics | subset (M08c) | every semantic milestone |
| Preprocessing | subset (null/define/undef, object + fixed/variadic function macros, __VA_ARGS__/__VA_OPT__, raw parameter and optional-operand #/%:, ##/%:%: with placemarkers, #error/#warning, macro-existence groups and intmax/uintmax #if/#elif expressions, numeric spellings and narrow characters and direct/computed quoted/basic angle includes and explicit -I search subset; M11m) | M09-M11, M25 |
| Object layout and ABI | subset (byte/halfword/word/long integer calls, separate-object GCC/Clang and dirty-upper-bit tests; M12j) | M12-M17, M20-M22, M24 |
| C23 additions | subset (warning, elifdef/elifndef, optional macros; runtime binary/separator literals; unnamed definition parameters M14d); bool/true/false, alignof/static_assert and distinct nullptr constant/type implemented; typeof/typeof_unqual type and expression operands, C23 for-typedefs and bounded block/for auto inference (including register and outer typedef hiding) implemented; standard header support incomplete | M10-M11, M23a-M23h, M24a-M24g |
| Required library/header environment | absent | M25a-M25d |
| Self-hosting | absent | M26 |

Implementation-defined target choices: Linux x86-64 System V ABI; LP64;
little endian; eight-bit bytes; signed plain char. Other choices remain
unresolved until their milestone. Unsupported constructs must produce a clear
error, not a guessed meaning.

Before the final audit, map this inventory to the chosen public C23 draft or
licensed standard clause by clause. Differential tests exclude undefined,
unspecified and incompatible implementation-defined behavior. Standard-library
coverage and compiler-language coverage are reported separately.

### M12f long long increment

Declarations, casts, literals and conversions include signed/unsigned long long
with rank distinct from long on LP64. LL/ULL suffixes and candidate ordering are
implemented within uint64 magnitudes. Complete six-type usual-conversion matrix,
same-width incompatible prototypes, full-width host/model comparisons and both-
direction mixed-width separate-object ABI tests cover this increment. This is
not full integer/C23 support: character constants and char/short types are next.

### M12g ordinary runtime characters

One ASCII source character or simple/octal/hex byte escape is an int expression.
617 printable/escape checks cover all 256 target bytes in both octal and hex;
pure decoder units and direct arbitrary-slice fuzzing share preprocessing tests.
Prefixes/Unicode/multicharacter/string literals remain explicit later work. Char
declaration types and integer promotions are designed for M12h, not implemented
by character constants.

### M12h byte types and promotions

Plain/signed/unsigned char declarations, casts, exact signature identity and
integer promotions are implemented. 462 width/sign conversion checks, promoted
arithmetic, assignment narrowing and typed-depth boundaries have both-host/QBE
coverage. Byte memory and SysV ABI use correct signed/unsigned QBE sub-word
annotations and canonicalization. Short/bool and other types remain separate.

### M12i short types

Signed/unsigned short add 16-bit object types, declarations, casts and promoted
arithmetic. 700 width/sign checks cover conversions between all eleven current
integer types; both-host/QBE programs and cross-object dirty-return ABI tests
exercise halfword storage and sh/uh calls. Bool and other remaining language
features remain separately tracked.

### M12j baseline boolean type

_Bool declarations, casts, exact compatibility and whole-integer conversion to
0/1 are implemented, with integer promotion to int. 418 width/sign checks include
even and high-only-bit values; side-effect and dirty-upper-bit ABI tests distinguish
value conversion from register normalization. C23 bool/true/false spellings and
constants remain M23a, not silently represented as int macros in the language.

### M13a object-pointer declaration values

Restricted prefix pointer type syntax, compatible object-pointer values, fixed
parameters/returns/casts and truth are implemented. Host-driven live-object and
null-pointer ABI tests cover both linkage arrangements and eight mixed pointer
arguments; type graphs/AST caches and exact 64/65 syntax bounds are tested.
Address/dereference, arithmetic/comparison, null constants and full declarators
remain later work. This is not complete pointer semantics or full C23.

### M13b pointer lvalues

Concrete address/indirection ASTs, general object lvalue addresses and referent
loads/stores cover all implemented integer and pointer object types. 53 curated
full-value programs cover mutation/recursion/once-only evaluation; both-direction
eight-argument host ABI tests verify every memory width, address identity and
valid null cancellation. Pointer arithmetic/comparison and null constants remain
later increments; invalid pointer dereferences are never executed by tests.

### M13c pointer equality

Compatible object pointers support ==/!= with full-width values and int results.
15 both-host/QBE full-value programs, both-direction live/null ABI, typed AST and
once-only/short-circuit tests cover this increment. The M13a rejection of p==p is
replaced by permanently invalid p&p; its pointer-operation constraint purpose is
retained. Pointer ordering/arithmetic and source null constants are not implied.

### M13d scaled pointer arithmetic and ordering

14 both-host/QBE full-value scalar programs, host-created arrays for all twelve
primitive referents plus pointer objects, every integer index type and both ABI
linkage directions cover signed/unsigned promotion, offsets, distances, ordering,
one-past/scalar cases and once-only calls. Large word-index extension is asserted
in IL, not exercised through impossible out-of-bounds arrays. Typed tree units
assert replacement, target sizes, explicit index promotion and signed-long
differences; exact 128/129 typed-depth cases pass. Previously rejected p+1 and
p<p fixtures now use permanently invalid p*2 and p/p, preserving their pointer
operation constraint purpose. Arrays/subscripts/null constants are not implied.

### M13e pointer subscripts

15 both-host/QBE full-value programs plus both-direction read/write array ABI
cover all thirteen current referent categories and all twelve integer indices.
Separate chained-pointer host arrays, parser/postfix/digraph/macro tests, once-
only/address-without-load cases, typed AST replacement/promotion and exact 42/43
chain-depth limits pass. Array declarations/decay/string literals are not yet
implemented, so live array storage is supplied by the host in ABI tests.
The arithmetic suite's invalid pointer+pointer/integer-pointer cases remain;
the factored builder now diagnoses their more specific offset constraint.

### M13f fixed local arrays

18 both-host/QBE full-value programs, all primitive borrowed-array ABI directions,
pointer elements, loops/scopes and pointer-to-array address/stride checks cover
literal-bound local storage and explicit decay. Size/alignment/compatibility/cache
units and exact storage/depth limits pass. Executed elements are initialized;
large resource fixtures are not executed. The earlier now-valid a[2] rejection
became incomplete a[], retaining array-declaration constraint coverage. GCC 11's
known C23 separator gap uses an explicit equal-valued host oracle only after the
original spelling passes kcc/QBE; Clang validates the original source directly.
General constant-expression bounds, multidimensional/parameter arrays, aggregate
initializers and strings are not implied by this subset.

### M13g fixed multidimensional arrays

15 both-host/QBE full-value programs and both-direction borrowed-row ABI cover
all primitive/pointer leaves, unequal dimensions, nested loops, recursive decays,
row/whole-array strides and lifetime-safe row mutation. Typed syntax/cache/shape
units distinguish equal-byte incompatible arrays. Exact 64/65 dimensions, product
budget and 42/43 indexed-depth limits pass. The prior a[2][3] rejection now uses
unsupported a[2][], retaining incomplete-bound constraint coverage. No flattened
cross-row element-pointer arithmetic is executed. Other bound/declarator and
initializer limitations remain explicit.

### M13h ordinary byte strings

12 both-host/QBE full-value programs include all 256 octal and hexadecimal byte
escapes (512 runtime checks), empty/embedded/final NUL, greedy escape boundaries,
macro stringizing and static-lifetime returns. Both ABI linkage directions and
two separately compiled kcc objects verify private static data symbols. Typed
units and pure decoder slice/capacity tests, direct fuzz roundtrips/static-list
invariants and exact length/storage/count/depth limits cover this increment.
Four former stringizing rejection fixtures now reject invalid pointer-to-int
returns at the same invocation anchors; lexer/pp conversion fixtures now expect
valid string tokens rather than dropping provenance checks. Concatenation,
encodings and initializers remain later work.

### M13i adjacent ordinary strings

15 both-host/QBE full-value programs cover independent greedy escape boundaries,
embedded NUL and empty fragments, macro/stringizing/comment/directive/splice and
include-separated adjacency. Both static ABI directions, one resulting data
object, typed first-fragment provenance and exact fragment/decoded/storage budgets
pass. The prior now-valid adjacency rejection became an unsupported ordinary+
wide-prefixed sequence; mixed/prefixed encoding constraints remain tested. This
is ordinary byte concatenation, not general C23 encoded string support.

### M13j literal-bound array parameters

27 both-host/QBE full-value programs, both linkage directions with eight mixed
pointer arguments and borrowed rows, and typed declared/effective cache units
cover named/unnamed prototypes, outer-count compatibility, inner-row mismatch,
rebinding and address-of-pointer storage. Exact dimension/type/local budgets
remain checked. Full regression initially caught an old now-valid int p[2]
parameter rejection; it now rejects unsupported int p[static 2], preserving a
real constraint check rather than weakening compiler acceptance. Other omitted-
bound rejection fixtures remain until the next increment.

### M13k omitted outer parameter bounds

27 both-host/QBE programs exercise every primitive/pointer leaf, mixed named/
unnamed []/[literal] prototypes, row shapes, rebinding, strings and recursion.
Both linkage directions cover eight mixed pointer arguments and matrix rows.
Units distinguish incomplete declared cache metadata from complete effective
pointer storage and verify unknown/known compatibility. Explicit zero, omitted
inner/local bounds, exact 64/65 dimensions and pointer-spill storage limits pass.
Earlier now-valid parameter [] negatives became omitted inner dimensions, while
local [] and unsupported static-bound rejections remain.

### M14a parenthesized object declarators

20 both-host/QBE full-value programs cover all primitive leaves, named/abstract
row pointers, arrays of row pointers, alternating shapes, one-level parameter
adjustment, recursive/once-only access and compatible abstract casts. Both row
ABI directions for all leaves and mixed eight-argument shapes pass. Units inspect
syntax/cache graphs and target layouts, distinguishing equal-byte incompatible
shapes. Exact grouped 64/65 nesting/star/dimension budgets pass compile-only.
A new invalid array-cast fixture exposed a scalar-helper precondition; explicit
target constraint checking now rejects it before that helper. The entire suite
and sanitizer fuzz were then run on the corrected source. Function declarators,
qualifiers, typedef names and incomplete object pointers remain future work.

### M14b incomplete object pointers and composites

19 both-host/QBE full-value programs cover all primitive/pointer leaves, unknown
array lvalue decay, compatible casts, arrays of unknown-row pointers and defined
comparisons. Both host directions cover all leaves and eight mixed pointer
arguments; a host-provided null verifies &* cancellation without invalid access.
Typed units distinguish original unknown caches from known visible composites.
Three-way unknown/known/conflicting redeclarations, nested pointer shapes and
both mixed-completeness subtraction orders are checked. Zero-offset/subscript
constraints and incomplete local/element diagnostics precede layout queries.
Former now-valid unknown-pointer negatives became incomplete nested-array cases;
local/inner omissions remain invalid with semantic completeness diagnostics.

### M14c grouped local declarators

23 both-host/QBE full-value programs cover all primitive leaves, mixed shapes,
initializer order, shadowing, nested calls/short-circuit expressions and for-list
scopes with nested break/continue. Both-direction ABI tests use grouped locals
for each primitive leaf. Units verify independent derived chains around a shared
base, ordered binding slots and complete loop-header list ownership. Exact
256/257 locals, 4096/4097 items including header locals, and storage limits pass
compile-only. Former now-valid ordinary/header comma-list rejections became
repeated-specifier and incomplete-header-array constraints, preserving negative
coverage while new positive tests cover the accepted syntax.

### M14d C23 unnamed definition parameters

17 both-host/QBE full-value programs cover every primitive and adjusted array
form, recursion, caller side effects and partial/all-unnamed definitions. Both
ABI directions cover all primitive register/stack positions and mixed full-width
returns. IL/unit checks preserve original argument indices and omit only unused
spills/bindings. Exact 128/129-parameter and named-versus-unnamed local/storage
budgets pass; a 128-argument program executes with QBE. The ordinary regression
now includes an unnamed definition. Both former now-valid rejection occurrences
became invalid incomplete-inner-array declarators; duplicate/count/conversion
constraints remain. Full regression was restarted after finding the second old
negative fixture. Host runtime agreement is not an ISO conformance claim.

### M14e fixed function declarators

21 both-host/QBE full-value programs cover parenthesized external names, all
primitive row-pointer returns, matrix/unknown array pointers, static string-array
address returns, recursion and composite return signatures. Both host directions
exercise every primitive row-return ABI. Units inspect one syntax-owned signature,
shared declaration views, original unknown caches and visible known composites.
Exact 64/65 flat function layers and shared nested-parameter recursion limits
pass compile-only. Earlier function grouping/pointer negatives remain invalid
under explicit semantic unsupported-feature diagnostics instead of parser-only
errors. Function pointer values/decay/indirect calls remain the next increment.

### M14f function pointers and indirect calls

Concrete designators/decay, compatible function pointers, function-parameter
adjustment, callbacks/factories and direct/indirect fixed calls are implemented.
No object/function conversions, function pointer arithmetic/ordering, variadics
or null integer constants are implied. Void remains next.

### M14g void types/functions

Void syntax/types, fixed void callbacks, bare returns, void casts and discarded
expressions are implemented with no scalar representation. Conditions/conversions
reject void values. Object/void pointer conversions and mixed equality are next;
this does not imply full declarator, qualifier or C23 conformance.

### M14h object/void pointer conversion

Assignment-like and explicit object/void pointer conversion and mixed equality
are implemented with explicit typed conversions. This is not recursive pointer
compatibility; function bridges, integer null constants and other incompatible
pointer casts remain unsupported.

### M14i explicit pointer casts

Object/object and function/function explicit pointer casts are supported,
separately from implicit conversion. Runtime alignment, effective type and
compatible indirect target requirements remain C program obligations. No
object/function bridges or integer/pointer conversions are implied.

### M19a comma operator (brought forward)

Sequenced, left-associative comma expressions, including void and pointer
results, are implemented independently of list separators. Full expressions
and assignment-expressions have distinct Pratt entry floors. Switch/labels/goto,
conditional and other remaining operators are still later work. Const remains
a designed next increment, not an implemented syntax feature at this checkpoint.

### M14j1 qualification type-model foundation

Immutable qualifier operations, strict/root-only compatibility and C23 matching
array/element qualification are unit-tested. Const language syntax, qualification
conversions and modification constraints are not implemented until M14j2. No
source-level const support or general qualifier conformance is claimed here.

### M14j2 const language integration

Concrete qualified syntax, immutable type graphs, const modification constraints,
ordinary value/cast normalization, function return/parameter signature rules,
qualified pointer/void conversions and array qualification are implemented within
the current declarator/type subset. Dedicated typed units and 39 QBE programs
cover this increment. Clang 15 has three exact C23 return-qualification diagnostic
gaps (not claimed as native agreements). Other qualifiers, typedefs and full C23
remain later work. bool/true/false source spellings are the next independent step.

### M23a1 C23 boolean subset

bool is an alternate spelling of _Bool; true/false have bool type and concrete
boolean ASTs. Raw macros and preprocessing conditions keep their phase-specific
rules. Runtime/type/ABI/boundary tests cover this subset; other keyword changes,
nullptr, standard headers and full integer constant evaluation remain later work.

### M19b conditional operator

Integer, qualified compatible/composite pointer, object/void pointer and void
arms implement C23 conditional constraints/type rules and selected evaluation.
Result is not an lvalue. Null pointer constant, nullptr_t, floating and aggregate
cases await their own type/evaluation milestones. Two exact legacy Clang 15 C23
array-qualification diagnostic gaps are tracked, not counted as native passes.

### M18a fixed size/alignment queries

sizeof expression/type and alignof/_Alignof type queries support complete fixed
object types with LP64 unsigned-long results and genuinely unevaluated operands.
No void/function size extensions, VLAs, bit-fields, standard headers or general
constant requirements are claimed. Literal array bounds remain a separate gap.

### M18b1 integer constant-evaluation foundation

Pure typed AST query for the current integer subset: checked portable arithmetic,
conversions, comparisons, short-circuit conditions, unevaluated comma and fixed
layout leaves. GCC/Clang strict native form/value oracles and both-host sanitizer
runs pass. This stage is queried by tests/fuzz only, not yet a source-level
constant requirement, optimizer, null conversion or full C23 ICE implementation.

### M18b2 static assertions

Both static_assert/_Static_assert spellings and optional ordinary-string messages
are supported in the available declaration contexts, including for initializers.
Checked integer constant expressions must be nonzero. Messages are diagnostic
bytes, not emitted static objects. Both-host strict native, original QBE and
sanitizer tests cover the subset; exact Clang 15 for-initializer parser and legacy
keyword-spelling gaps are recorded. Aggregate-member assertions await aggregates.

### M13l1 fixed integer constant array bounds

Assignment-expression bound ASTs are checked with ordinary sema, then the shared
integer constant evaluator. Positive counts respect per-type/aggregate storage
limits before layout. Incomplete bounds remain NULL, not zero-length arrays.
Prototype parameter names have point-of-declaration, nesting and restoration
rules; names in sizeof consume no runtime locals. Runtime VLA bounds, [*],
static/qualified brackets, enums/constexpr and general constant consumers remain
unsupported. Tests cover both-host strict forms, concrete typed ASTs, QBE/ABI,
storage/recursion boundaries and sanitizer/fuzz paths.

### M13m traditional null pointer constants

Checked integer ICE zero and explicit void * casts of such expressions implement
traditional null conversions. Equality accepts either order; conditionals keep
the other pointer's exact type. Typed pointer null values are not integer/void *
null constant forms. This LP64 target uses all-zero 64-bit null representations.
Both-host originals/strict rejection, QBE runtime/ABI and typed limits are tested;
one exact GCC 11 _Bool-zero oracle gap is labelled. C23 nullptr/nullptr_t, general
integer/pointer casts, headers and other constant-expression consumers remain.

### M23a2 nullptr constant and unnamed type

C23 6.2.5, 6.3.1.2, 6.3.2.3/.4, 6.5.9/.15 and 7.21.2 subset: a distinct complete
scalar nullptr type, keyword expression, pointer/bool conversions, equality,
conditional/null control and sizeof behavior. LP64 size/alignment 8 and all-zero
void-pointer null representation are explicit target choices. Source nullptr_t
names/headers and conversions to that named type are not exposed yet. Tests run
original source via QBE; legacy host keyword absence is not native agreement.

### M19c1 prefix ++/--

N3096 6.5.3.1 subset: integer and complete-object pointer modifiable lvalues,
result type/no-lvalue behavior, promoted/back-converted narrow and boolean values
and once-only operand addressing. Prefix updates are not constant expressions.
Postfix, compound assignment, floating and atomic cases remain separate work.

### M19c2 postfix ++/--

N3096 6.5.2.4 subset adds the old-value result with stored new value for current
integer and complete-object pointer types. Postfix precedence/loops/once-only
addresses and both ABI directions are tested; no atomic/float semantics claimed.

### M19d1 additive compound assignment

N3096 6.5.16.2 subset: +=/-= integer usual arithmetic/back conversion, boolean
truth conversion, complete-object pointer/integer offsets and once-only lvalue
evaluation. Concrete nodes retain calculation/result types and pointer strides.
All remaining compound operators, floating and atomic operations are separate.

### M19d2 remaining integer compound operators

N3096 6.5.16.2 adds integer *= /= %= &= ^= |= <<= >>= to the additive subset.
Usual arithmetic conversions and independent shift promotions remain distinct;
the result is the stored unqualified type, not an lvalue. Tests cover original
source, pointer/non-lvalue/const constraints and both-direction narrow ABI. No
floating or atomic operation support or runtime UB diagnosis is claimed.

### M19e1 identifier labels

N3096 6.8.1 and 6.8.2 subset: named labels are function-scoped and unique, in a
separate namespace. C23 standalone block-item labels act as null statements and
may precede declarations or block end; secondary labels retain a child statement.
No goto/case/default/switch/attribute support is claimed in this foundation.

## M19e2 direct goto

Concrete goto nodes keep identifier locations and resolve original label pointers
after the whole function body is checked, including dead syntax. Labels receive
source-order indices; functions retain their checked label count. References are
bounded to 4096 per function, independently of 512 labels and block-item limits.
Codegen reserves target IDs, tracks the current numeric block for phi nodes and
continues after terminators using predecessor-free blocks, preserving nested
targets without inventing fallthrough. Initializers execute only when reached.
Computed goto, switch/case/default, attributes and VLA jump-scope rules remain
unsupported; this does not claim full C23 control-flow support.

## M19f1 switch foundation

Case-free switches evaluate an integer control exactly once with explicit integer
promotion, then skip the body. Full body checking and predecessor-free backend
traversal preserve named goto targets; goto entry bypasses control evaluation.
One enclosing-control context stack binds break to the closest loop/switch and
continue to the closest loop across switches. AST jumps retain exact target
identity and backend target lookup follows it. Scope and context parents restore
on failure. Case/default dispatch, attributes and VLA jump-scope constraints
remain unsupported and are not implied by this foundation. Existing loops and
function/ABI contracts are unchanged; no new runtime storage is introduced.

## M19f2 case/default labels and dispatch

Separate concrete case/default labels have block-item and secondary-statement
wrappers. C23 block labels can precede declarations or end a block; secondary
labels require a child statement. Case conditional expressions stop at the outer
colon with Pratt floor 2. Sema assigns the nearest switch across nested loops,
checks integer ICEs after explicit conversion to promoted control type, detects
duplicate converted bits and rejects multiple defaults. Nested switches have
independent collections. Cases never emit runtime operand evaluation.

Named goto indices/counts remain unchanged; function switch-label indices reserve
a separate QBE target range after named targets. Bounds: 1024 labels per switch
and 4096 per function, each including default. Linear equality dispatch evaluates
control once; ordered label emission gives fallthrough without false edges after
terminators. Current block IDs still track phi predecessors. Attributes, GNU case
ranges, VLA jump constraints and jump-table optimization remain unsupported.

## M23d1 typeof type-name operands

Demand keyword conversion recognizes typeof/typeof_unqual only after macro
expansion. A concrete ast_typeof_type_syntax owns its type-name operand; RDP
parses the documented subset BNF with a separate restored 64-query nesting guard.
Sema caches immutable resolved types: typeof preserves the operand identity,
typeof_unqual removes root qualification (including C23 array element qualifiers
until a pointer) without stripping referent qualifiers. Function qualification
is diagnosed before the old qualifier-helper assertion. Declarations, casts,
sizeof/alignof, static assertions, fixed bounds, adjusted parameters and callbacks
reuse their existing checks and backend; queries introduce no runtime operation.

Expression operands, GNU aliases, typedef/atomic/VLA/bit-field cases and
alias-derived bare function declarations remain unsupported. A sole typeof(void)
parameter is not yet normalized to an empty signature; existing literal void
syntax remains supported. These are documented subset gaps, not C constraints.
The current file-scope bare-function alias path reports the existing unsupported
file-scope-object diagnostic; it does not guess a function AST.

M23d1 native oracle: the published GCC/Clang jobs rejected the original nested
const-array typeof_unqual write, unlike N3096 6.2.5p31 / 6.7.2.5p5 example 2.
Only that original source plus exact observed read-only diagnostics is labelled
a native qualification gap, not an agreement. kcc runtime and immutable qualifier
tests remain mandatory; unexpected native failures still fail the suite.

## M23d2 typeof expression operands

A distinct ast_typeof_expression_syntax keeps one Pratt floor-zero expression
operand, source location and unqualification flag. One demand peek selects the
existing type-name path; both forms share the restored 64-query bound. Sema checks
the operand in its lexical/prototype scope with only root load/array/function
decay suppressed. Child conversions and constraints remain checked. typeof
shares its actual immutable type; typeof_unqual uses root unqualification.
Previous prototype names remain type-only bindings; query operands allocate no
extra runtime locals. The backend never visits query syntax, so calls, updates,
assignments and comma/conditional effects in non-VM operands do not execute.
Existing string registration may retain static data for an unevaluated literal.

Query expressions now name the existing nullptr type, including objects, pointers,
parameters and results. N3096 6.3.2.4 / 6.5.4 explicit casts to that type accept
only null pointer constants or nullptr values. The later M23d2 null-conversion
correction also admits checked null constants in initialization/assignment/
argument/return, as required by the normative 6.5.16.1 constraint. Its contradictory
footnote 127 was stale; N3220 retains the normative rule and removes that footnote.
Nonconstant integer/pointer zero values and non-ICE zero forms remain rejected.

Typedef ambiguity, atomic/bit-field/variably modified operands, required VM
evaluation, GNU aliases, alias-derived bare function declarations and sole
query-derived void-parameter normalization remain separate work. sizeof(void)
and void objects are still invalid; typeof of a void expression itself is valid.
No stddef.h exposure or full C23 conformance is implied.

### M23d2 expression-array native oracle correction

Exact-source CI 05097e6 run 38918142442 passed fuzz but both reference jobs failed
at the original const int a[2]; typeof_unqual(a) b write, reporting read-only b[1].
This is the expression form of the already documented host array-unqualification
gap (N3096 6.2.5p31, 6.7.2.5p5/example 2). Keep kcc semantic behavior and all
original kcc/QBE programs unchanged. Classify only that exact original source
and the exact GCC/Clang read-only diagnostic as a native gap, not an agreement.
Classifier units reject unrelated sources and extra/unexpected errors. Do not
broaden skips to arbitrary arrays, rewrites or errors.

M14k1 source/tests/docs are stashed during this independent correction. Its
interrupted full/sanitizer runs are not passes and must restart after restoration.
Compiler source is unchanged by this oracle fix; full prior local M23d2 regression
remains recorded separately, not a fresh full-run claim for this test-only change.

## M14k1 query-derived void parameter normalization

A sole unnamed unqualified resolved void parameter is annotated is_void_marker,
retaining its written query syntax and checked type. It contributes no semantic
function parameter, prototype binding, local spill or ABI operand. Parsed counts
still describe written AST nodes (literal void keeps the existing zero-node
parser fast path); semantic function_type counts describe the actual ABI. Named,
qualified or mixed void parameters remain errors. Main's supported zero-parameter
check now uses the resolved signature instead of the written node count.

Backend definition-header and spill traversals skip the checked marker before
querying its width or incrementing ABI indices. Real unnamed C23 parameters keep
their ABI positions; no synthetic parameters or names are introduced. Direct/
indirect calls, nested signatures, prototypes and definition compatibility reuse
the existing semantic function types. Root query non-evaluation still applies in
local callback declarators. This adds no new runtime storage or resource bound.

Bare query-derived function declarations, block-scope function declarations,
typedef/storage/variadic/VM work remain unsupported. Qualified void is not an
empty-list marker unless typeof_unqual first removes its qualification. No full
C23 declaration-normalization claim is made.

## M14k2 query-derived file-scope function declarations

A separate concrete ast_external_type_declaration retains a query-root type
syntax, its source name and checked type/symbol annotations. Parsing only accepts
a semicolon-terminated declaration and does not resolve the query or manufacture
function syntax, parameter lists, names or a definition. Sema resolves the query
in source order and currently accepts only a function type. Query-derived object,
pointer, array and void declarations retain the explicit file-scope-object subset
diagnostic; query-derived bare definitions, comma lists and initializers remain
unsupported. Block function declarations, typedef/storage/variadic/VM work remain
separate. This does not make typeof a symbol-alias facility.

Both ordinary function declarators and query-root declarations use one shared
registration helper for main checks, symbol bounds, compatibility, immutable
composite types and redefinition checks. Query caches remain immutable snapshots:
a later prototype can strengthen a symbol's incomplete array bound without
rewriting an earlier query's cached type. Definition parameter nodes/bindings and
recursion installation retain their existing path. Queried declarations add no
parameters, locals, data, function definitions, runtime query operations or QBE
alias instructions. Calls/addresses use the existing shared symbol and ABI.
The existing 256 unique-function / 512 external-declaration bounds still apply;
repeated compatible queries do not consume additional function-symbol slots.

## M14l1 unshadowed file-scope typedef foundation

A language typedef keyword is converted only at token demand; raw preprocessing
identifiers/macros retain their old behavior. Concrete ast_typedef_declaration,
ast_external_typedef_declaration and ast_typedef_name_type_syntax retain each
written declaration/name. Parser aliases are bounded syntax-only name bindings;
sema independently resolves earlier aliases in source order and shares immutable
types, never a new nominal type or synthetic runtime declaration.

Aliases participate in all existing declaration/type-name ambiguities: local and
for declarations, qualifiers, pointers, arrays, adjusted parameters, signatures,
casts, sizeof/alignof and type queries. Alias-derived bare function declarations
reuse M14k2 registration. Identifier-plus-colon is classified before alias local
declarations, preserving the label namespace. Alias-named labels still consume
one block item; consumed alias declarations reuse a shared specifier/declarator
tail without token replay, vectors or semantic resolution during parsing.

This increment supports one unique file-scope alias per typedef declaration.
Block typedefs, typedef redeclarations, comma typedef lists, shadowing visible
aliases, bare alias-derived function definitions and remaining storage classes
are explicit subset limits, not newly invented C constraints. Actual ordinary
file-scope function/typedef namespace collisions are rejected by sema. Existing
VM, aggregate, floating, atomic and other unsupported types remain unsupported.

Aliases share DAGs that could encode exponentially expanded function signatures.
Sema caches shape metrics by immutable type identity before publishing an alias,
with explicit expanded-node 4096 and depth 128 limits (each leaf counts as one).
These bounded valid-C subsets protect existing recursive type operations; they
are not incompatibility diagnostics. The existing 512 external declarations,
256 function symbols and 4096 block items remain independently enforced. Alias
names do not emit storage, data, functions, QBE aliases or runtime query effects.

## M14l1b same-type file-scope typedef redeclarations

Already-visible aliases may be redeclared for the same non-VM type. The type
stage exposes type_same separately from compatibility: array counts must match,
including unknown versus known bounds, recursively through pointers and normalized
function signatures. Existing compatibility and immutable composite construction
are unchanged. Typedef equality never strengthens an unknown-bound array.

The parser reuses its syntax-only name binding. Sema checks the expanded alias
shape before comparison, annotates a valid redeclaration with the first canonical
immutable alias type, and leaves each separately written syntax cache intact.
A different type is a genuine constraint; function/typedef ordinary-namespace
collisions remain errors. No additional alias binding, storage, QBE alias,
parameter or emitted function is introduced by a same-type redeclaration.

Block typedefs, shadowing, comma typedef lists, VM/aggregate types and bare
alias-derived definitions remain deferred at this checkpoint. The existing 512
external items, 256 function symbols, 4096 block items and 4096-node/128-level
expanded alias limits are unchanged. Each repeated declaration still consumes an
external item; canonical type reuse does not bypass resource accounting.

## M14l1c file-scope typedef declaration lists

A file-scope typedef declaration may contain comma-separated declarators. One
written specifier base is shared by distinct derived syntax chains; each alias
retains a concrete typedef declaration and external wrapper in source order. The
parser publishes each syntax-only name after its complete declarator, so later
names in the same group can use it in bounds, parameters, casts and type queries.
Sema still resolves the external chain independently; no new backend path exists.

Each concrete alias, including a repeated name, consumes one external item. The
parser checks the remaining 512-item budget before constructing another declarator,
not merely once per group. Mixed ordinary function/static-assert/typedef groups
therefore cannot bypass the bound. Existing function-symbol, block-item and alias
expanded shape limits are unchanged. Typedef initializers receive an explicit
constraint diagnostic. Alias-only translation units emit no function or data.

Block scope, alias shadowing, storage-specifier permutations, VM/aggregate types
and bare alias-derived function definitions remain deferred at this checkpoint.

## M14l2 block-scope typedef foundation

Compound blocks now accept typedef declaration lists through a concrete
ast_block_typedef_declaration wrapper. Every alias charges one block item; shared
written specifiers and distinct derived declarators retain source order. The
complete-declarator syntax-name publication helper is shared with external
aliases, without making either representation an automatic object.

Parser compound scopes restore their syntax-only alias-list head on success and
failure. Sema independently restores its bindings around nested compounds and the
outer function body, tagging each binding with its semantic scope. Same-scope
same-type redeclarations preserve canonical immutable types. Names cannot leak
into sibling blocks, later functions or subsequent external declarations.

Codegen skips the new item kind. Aliases create no locals, stack slots, strings,
runtime initialization or QBE data/function aliases. Expanded type limits remain
4096 nodes / 128 levels; each alias still counts toward 4096 function block items,
independently of the 512 external items and 256 function symbols.

Typedef/typedef, typedef/object and typedef/function shadowing remain explicit
subset restrictions at this checkpoint; same-scope object/parameter conflicts
and different-type typedef redeclarations are genuine constraints. C23 permits
for-initializer typedefs: those are deferred to M14l2b, not labelled invalid C.
Storage-class permutations, VM/aggregate types and general ordinary-namespace
hiding remain unsupported. Read m14-block-typedef-foundation.md, including its
normative draft correction, before changing scoped lookup or parser classification.

M14l2 validation: complete normal/QBE regression, complete normal regressions with
original-source GCC 14.1.0 and Clang 18.1.8 native oracles, both GCC 11 / Clang 15
targeted ASan/UBSan lexer/sema/typedef/query/nullptr/local-list/assertion/control
suites and bounded sanitized fuzz passed. Fuzz executed 4,845 lexer / 14,954
pipeline inputs in 26/26 seconds; no generated or invalid curated C ran. Focused
suite: 36 standard + 4 C23 originals, 6 strict native constraints, 24 mixed-stack
primitive ABI arrangements per host, concrete AST scope/wrapper/type identity,
no alias locals and exact block/external/expanded-depth boundaries. Legacy hosts
agree on 36 originals, modern hosts on all 40 without rewriting. Frozen manifest
/data/tools/m14l2-source.sha256 matched before and after integration. Remote CI
is separate from these local passes.

## M14l2b C23 for-initializer typedefs

For clause-1 accepts the existing block typedef declaration group, preserving its
concrete AST wrappers, per-declarator source order and single-semicolon parser
contract. Each alias consumes one function block item, independently of the
containing for statement. A bare return loop body is not a compound block item.

The guarded parser for wrapper restores syntax-only alias names on success and
failure. Sema_for independently restores semantic aliases around its existing
loop scope. Aliases are visible after their complete declarator through the
remaining initializer, condition, step and body, but not after the loop. Compound
bodies retain their own nested scopes. No new AST representation or backend path
is required: initializer item emission already skips compile-time-only aliases.

N3096 6.8.5 / 6.8.5.3 and N3220 6.8.6.4 permit these declarations; do not revive
C17's removed object/storage constraint. GCC 14 accepts original C23 sources.
GCC 11, Clang 15 and Clang 18 reject an exact minimal for-typedef probe; tests
recognize only those specific sole diagnostics, report a feature gap separately
and still execute original defined kcc/QBE programs and primitive ABI comparisons.
They never rewrite aliases into objects or move declarations to fake agreements.

Shadowing, storage-class permutations, VM/aggregate types and prototype scopes
remain outside this increment. Existing item/alias-expanded budgets and semantic
same-scope constraints remain unchanged. Read m14-for-typedefs.md.

M14l2b validation: complete normal/QBE regression, complete normal regressions
with original-source GCC 14.1.0 and Clang 18.1.8 native oracles, both GCC 11 /
Clang 15 targeted ASan/UBSan lexer/sema/typedef/query/nullptr/control suites and
bounded sanitized fuzz passed. Fuzz executed 3,394 lexer / 9,630 pipeline inputs
in 26/26 seconds; no generated or invalid curated C ran. Focused suite: 34
base-type + 4 query originals, all 38 strict native agreements / 4 constraints
with GCC 14; exact for-typedef grammar gaps, not agreements, on GCC 11 / Clang 15 /
Clang 18. All four hosts passed original kcc/QBE runs and 24 mixed-stack primitive
ABI arrangements each. AST tests verify scoped aliases, canonical repeats and
independent post-loop names with no alias locals. Exact 4096-item and alias-only
IL checks passed. Frozen manifest /data/tools/m14l2b-source.sha256 matched before
and after integration. Earlier interrupted helper-build-race runs are not passes;
all final normal helpers were built serially before parallel tests. Remote CI
remains separate from these local results.

## M14l2c nested typedef-to-typedef shadowing

An inner typedef can hide an outer typedef with either the same or a different
type. Sema applies same-type redeclaration checking only when the nearest alias
binding belongs to the current scope; otherwise it prepends an independent
binding after resolving the written type. Thus typedef T *T uses the outer T in
its specifiers, not its own unfinished declaration. A repeated name within the
new scope must still name the same non-VM type, not merely a compatible type.

No parser/lexer classification change is needed: both visible meanings are type
names. Existing compound/function/for save-and-restore contracts reveal the outer
alias after inner scope exit. Syntax caches and canonical types remain immutable;
typedefs still create no runtime locals, slots or data. Item and expanded-type
limits are unchanged. Typedef/object/function hiding in either direction,
prototype scopes, storage-class permutations, VM and aggregate types remain
unsupported. Read m14-typedef-shadowing.md before broadening ordinary-name lookup.


M14L2C validation: complete normal/QBE regressions, complete normal
regressions with original-source GCC 14.1.0 and Clang 18.1.8 oracles, and both
GCC 11 / Clang 15 targeted ASan/UBSan lexer/sema/typedef/query/nullptr/control
suites passed. Bounded sanitized fuzz executed 3,927 lexer /
6,164 pipeline inputs in 26/26 seconds. No invalid or generated C
was executed. Four-host focused checks: 46 standard + 4 C23 originals, 6 native constraint rejections, and 24 both-direction
mixed-stack primitive ABI arrangements per host passed. Expanded for suite: 39+4
originals; GCC 14 agrees on all 43 / 4 constraints; other hosts report exact grammar
gaps separately. AST tests verify canonical same-scope repeats, independent nested
bindings, scope restoration and no alias storage.
Frozen manifest /data/tools/m14l2c-source.sha256 matched before and after
integration. Normal test helpers were built serially before parallel validation.
Remote GitHub CI is tracked separately; local passes do not prove remote success.

## M14l2d block typedefs hiding file-scope functions

Block and loop typedef bindings may hide a file-scope function, including their
own containing function. Sema keeps the original function symbol unchanged and
rejects visible typedef names in expressions before trying local/function lookup.
Bare calls bypass the undeclared-function shortcut for visible typedefs, giving
the same not-an-expression diagnostic. This closes the otherwise incorrect path
that could call or take the address of a hidden outer function.

Type-name uses refer to the alias. Captured function pointers remain valid and
scope exit restores subsequent calls/designators to the original function.
File-scope function/typedef collisions and same-scope differing aliases remain
constraints. Typedef/object hiding is still explicitly unsupported in both
directions: the typedef-first value-name guard relies on this invariant, and must
not be broadened to object shadowing without scope-aware namespace lookup.

No new type, AST form, parser classification, local slot or backend operation is
introduced. Existing expanded-type and declaration/item budgets remain. Storage
specifier permutations, prototype scopes, block function declarations, VM and
aggregate types are not implemented here. Read m14-typedef-function-shadowing.md.


M14L2D validation: complete normal/QBE regressions, complete normal
regressions with original-source GCC 14.1.0 and Clang 18.1.8 oracles, and both
GCC 11 / Clang 15 targeted ASan/UBSan lexer/sema/typedef/query/nullptr/control
suites passed. Bounded sanitized fuzz executed 3,408 lexer /
8,153 pipeline inputs in 26/26 seconds. No invalid or generated C
was executed. Four-host focused checks: 35 standard + 4 C23 originals, 11 native constraint rejections, and 24 both-direction
mixed-stack primitive ABI arrangements per host passed. Expanded for suite: 41+4
originals; GCC 14 agrees on all 45 / 4 constraints; other hosts report exact grammar
gaps separately. AST tests preserve captured/restored function-symbol identity and
verify no alias locals.
Frozen manifest /data/tools/m14l2d-source.sha256 matched before and after
integration. Normal test helpers were built serially before parallel validation.
Remote GitHub CI is tracked separately; local passes do not prove remote success.

## M14l2e typedefs hiding outer automatic objects and parameters

A block or for typedef may hide an automatic object or parameter from an outer
scope. Sema rejects only same-scope object/parameter collisions, resolves written
types before alias publication, and otherwise prepends the scoped alias binding.
The outermost function body still shares parameter scope; nested blocks do not.

The visible-typedef expression guard prevents calls, addresses, loads and
unevaluated value uses from falling through to the hidden outer object. Captured
addresses and earlier AST names retain their exact object declarations and slots;
restoring scope reveals subsequent object uses again. No object is removed from
the function-local storage list and no alias slot is created. Type queries in a
typedef's own specifiers may inspect the still-visible outer object.

Objects or parameters hiding visible typedefs in the opposite direction remain
explicitly unsupported. The typedef-first value-name guard relies on that parser
restriction; scope-aware unified ordinary-name lookup is required before removing
it. File globals, block function declarations, storage-class permutations, VM,
aggregate types and prototype-scope changes remain unsupported. Type-shape/item
budgets are unchanged. Read m14-typedef-object-shadowing.md.


M14L2E validation: complete normal/QBE regressions, complete normal
regressions with original-source GCC 14.1.0 and Clang 18.1.8 oracles, and both
GCC 11 / Clang 15 targeted ASan/UBSan lexer/sema/typedef/query/nullptr/control
suites passed. Bounded sanitized fuzz executed 6,665 lexer /
36,413 pipeline inputs in 26/26 seconds. No invalid or generated C
was executed. Four-host focused checks: 33 standard + 4 C23 originals, 8 native constraint rejections, and 24 both-direction
mixed-stack primitive ABI arrangements per host passed. Expanded for suite: 43+4
originals; GCC 14 agrees on all 47 / 4 constraints; other hosts report exact grammar
gaps separately. AST tests preserve captured parameter addresses, restored object
identity and original object slots; aliases allocate no local storage.
Frozen manifest /data/tools/m14l2e-source.sha256 matched before and after
integration. Normal test helpers were built serially before parallel validation.
Remote GitHub CI is tracked separately; local passes do not prove remote success.

## M14l3a automatic objects hiding typedef names

The parser maintains one syntax-only ordinary-name chain, recording typedef or
object kind. Nearest matching names control type/expression disambiguation. An
object publishes after its complete declarator and before its initializer; each
comma declarator publishes independently. Compound/for scope restoration handles
both kinds. No token buffering, backtracking, lexer change or new AST kind occurs.

Semantic typedef lookup honors nearer object scopes rather than falling through
to a hidden alias. Same-scope alias/object declarations remain constraints. Type
resolution precedes object binding, which precedes initializer analysis. Shared
specifier caches preserve the written base in T T=40,*P=&T while later value uses
bind to the object T. Existing typed conversion/load nodes and storage slots keep
their provenance. Alias/object nesting in both directions restores prior meanings.

Tests cover initializers, own-declarator array bounds, comma lists, parentheses
versus casts, sizeof/typeof, for lifetimes, labels, captured addresses, same-scope
constraints and no alias storage. Named parameters hiding visible aliases remain
explicitly unsupported pending a separate prototype-scope design. Globals,
block function declarations, VM/aggregate types and storage-class permutations
are not added. Existing item/local/storage/expanded-type budgets remain unchanged.
Read m14-object-typedef-shadowing.md before broadening prototype name lifetimes.


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

## M14l3b parameter names hiding outer typedefs

Implemented and locally validated for the stated Linux amd64 LP64 subset:
parameter point of declaration, later parameter/type-query disambiguation,
nested prototype restoration, trailing return syntax and definition-body names.
No VM types, globals, new storage classes or full-C23 conformance is implied.

Focused originals: 48 standard + 6 C23, all kcc/QBE-valid; GCC 14.2.1 agrees on
54, Clang 18.1.8 on 53 with one exact C23 for-typedef grammar gap. Legacy GCC
11.5/Clang 15.0.7 agree on all 48 standard originals; keyword gaps are not
agreements. Ten kcc constraints remain errors; GCC has nine strict rejections
plus one exact named-void warning, Clang ten strict rejections. No source is
rewritten to obtain native agreement. Both-direction ABI, AST identities,
128/129 parameter and 256/257 local boundaries, complete regression/QBE,
both-host targeted sanitizers and bounded compile-only fuzz passed. Read the
M14l3b ledger for exact counts/tools and separate pending exact-commit CI status.

## M14l3b native-oracle diagnostic follow-up

The valid parameter/for-typedef restoration original remains accepted by kcc.
Its exact GCC and Clang for-typedef grammar-gap diagnostics are classified
separately from native agreements; only exact source, status 1 and a single
observed error match. This test-only CI correction changes no language scope,
resource budget or ABI. Read m14-parameter-native-diagnostics.md and the latest
ledger entry for the failed predecessor CI and frozen local validation evidence.

## M14l4 typedef storage-class placement

Implemented and locally validated within the recorded subset: typedef anywhere
among supported declaration specifiers at file/block/C23 for scope; duplicate
storage and type-name/parameter placement diagnosed. This adds no other storage
classes, VM types, globals or full-C23 claim. All 55 focused original programs
pass kcc/QBE; GCC 14 agrees on 55, Clang 18 on 51 plus four exact for-typedef gaps.
Legacy keyword/parser gaps are not agreements, and no source was rewritten.
Full regression/QBE, both-host targeted sanitizers, bounded compile-only fuzz,
ABI/AST/storage/resource boundaries passed; see the M14l4 ledger for exact counts,
fixture corrections, predecessor CI evidence and pending new-commit CI status.

## M15a1 register scalar storage (N3096 6.7.1 / 6.5.3.2)

Validated target subset: implemented scalar block/for objects accept register in
any specifier position, share ordinary storage/ABI and reject address-taking of
the declared object, including unevaluated queries. Pointee addresses remain
valid; qualifiers/types and typeof do not carry storage. Raw keyword-named macros
still expand before language classification. Register array objects and register
parameters are explicitly unsupported, even when their C usage is valid. Other
storage/linkage, globals and complete C23 remain absent. Read the ledger for
frozen full/QBE/sanitizer/fuzz evidence; Clang's exact strict keyword-macro
warning-as-error is separately counted, never a native agreement.

## M15b1 fixed register-array queries (N3096 6.3.2.1 / 6.7.1)

Validated target subset: complete fixed register arrays at block/for scope accept
direct sizeof and typeof/typeof_unqual queries without decay. Type copies retain
array structure, not storage class; ordinary copies remain usable/addressable.
Direct address-taking is a constraint; register-array-to-pointer conversion is
refused before decay-node insertion, including inside otherwise unevaluated
queries. Evaluated conversion has undefined behavior and is never executed or
presented as a native constraint test. Register parameters, VM/incomplete arrays
and array initializers remain unsupported. No parser/type/QBE interface changes
or full C23 claim; exact original/native/ABI and frozen validation in the ledger.

## M15a2 explicit auto storage (N3096 6.7.1)

Validated subset: explicit-type block/for auto objects retain ordinary storage,
addressability, scope, shared bases and ABI for implemented object types. No
inferred type or storage propagation through typeof. Type-name/parameter auto is
rejected; inferred C23 auto, file scope and auto/register combinations remain
explicit subset limits requiring a separate 6.7.9 design. Exact native Clang 18
C23 grammar gaps and unchanged-source C11 corroborations are separately counted,
never conflated with strict C23 agreement. Register parameters, other storage/
linkage/globals, VM types and full C23 remain absent. Read the ledger for frozen
full/QBE/sanitizer/fuzz/boundary evidence and independent CI state.

## M23e0 inference preparation, not implemented inference

Semantic local binding is split into explicit name/storage/initializer phases
without changing language coverage or interfaces. Ordinary explicit declarations
and adjusted parameter spills retain their former behavior and limits. C23
inferred auto remains absent: its unavailable-name interval, concrete syntax,
qualifier/inference policy and single-identifier/underspecified-UB cases need a
separate final design. No native acceptance of UB is counted as a missing
constraint diagnostic. Read the research notes and ledger; not full C23.

## M23e1 single-identifier auto inference (N3096 6.2.1 / 6.7 / 6.7.9)

Validated block/for subset: one bare/grouped identifier, assignment initializer,
optional written const; infer its complete scalar type AFTER ordinary value
conversions without integer-promotion shortcuts. Fixed ordinary arrays, strings
and functions decay to pointers; nullptr retains its distinct type. Inferred
names are unavailable during initialization while hiding outer namesakes;
sizeof/typeof/dead branches do not escape the rule. Subsequent uses see the
completed ordinary local. Explicit auto/register paths remain distinct.

Only bare/parenthesized identifiers without a visible typedef ambiguity are
supported. Visible typedef T in auto T=42 or auto (T)=42 remains explicitly
outside this first subset; explicit auto T x is unchanged. Inferred derived
declarators, braced initializers, register combinations, globals, attributes,
constexpr and VM types remain unsupported. Multiple underspecified identifiers
and prior same-scope declarations have UB under N3096 6.7p12: refusal probes
compile only and are NOT required native diagnostics. Register parameters remain
unsupported. This is not full C23 conformance.

Modern native original-source comparisons and independent legacy feature probes,
24 both-direction cross-object arrangements per host, AST identity/storage and
exact boundaries are recorded in the ledger. Legacy linkage is not inference
syntax support. No UB probe or generated boundary is executed. Full frozen
normal/QBE/sanitizer/fuzz evidence and remote CI are recorded separately.

## M23e2 auto/register inferred objects (N3096 6.7.1 / 6.7.9)

Validated block/for extension: auto and register may appear in either order,
with existing const positions, for a single supported initialized inferred
identifier. Source object identity carries register's address restriction;
ordinary copies carry only types. Existing complete scalar inference, normal
array/function decay, unavailable-name interval and one-pass initialization
remain. No new backend/type feature or claim of inferred array object storage.

C23 6.7.1p4 requires inference when auto accompanies another storage class:
auto register int x=42 is a CONSTRAINT violation, not valid traditional explicit
auto. Those explicit primitive/alias/query/void forms remain rejected. Register
alone without a type does not silently infer or default to int. Duplicate/typedef
mixtures still reject. Register parameters, globals, other storage classes,
attributes/constexpr/VM, visible-typedef ambiguities and inferred derived/braced
forms remain unsupported. Multiple underspecified identifiers and prior same-
scope declarations are UB refusal probes, not native constraint requirements;
none execute. This is still an incomplete C23 subset.

Modern original-source agreement, independently probed legacy absence, exact
AST/budget tests and both-direction ABI arrangements are recorded in the ledger.
Native acceptance of UB never proves a missing constraint. Frozen full normal/
QBE/both-host sanitizers/fuzz evidence and remote CI are independently recorded.

## M23e3 inferred identifiers hiding typedefs (N3096 6.2.1 / 6.7 / 6.7.9)

Validated block/for extension: bare/grouped inferred identifiers can hide outer
typedef names, including ordinary/register auto and written const. The '=' lookahead
forces an initialized identifier, not an unnamed explicit type. The parameter-
list ambiguity rule is not applied to these object definitions. Existing one-
pass complete-scalar inference and unavailable-name semantics apply; initializer
queries cannot expose the alias, completed queries bind the object, and scope
exit restores the type. Explicit auto/type aliases and shared caches remain.

Only initialized single identifiers, optionally grouped, and implemented complete
scalar inference are supported. Derived/braced/incomplete/nonobject inference,
register parameters, globals/other storage, constexpr/attributes/VM/aggregates
remain unsupported. Same-scope prior aliases/objects and multiple underspecified
identifiers are UB refusal probes under N3096 6.7p12, NOT required native
constraint diagnostics; none execute. Combined auto/register with explicit types
is still a 6.7.1p4 constraint. Existing register-array conversion refusal, ordinary
own-bound/initializer rules and all resource/ABI limits remain. Not full C23.

Original Clang 18 agreement and exact GCC 14 typedef-inference grammar absence
are recorded separately, as are legacy basic-inference absence and cross-object
ABI linkage. No syntax-gap rejection is counted as semantic constraint agreement;
no UB acceptance is called a missing diagnostic. Read the ledger for exact
classifier/AST/boundary/full frozen local validation and independent remote CI.

## M15c1 register parameters (N3096 6.7.6.3p2/p12, 6.5.3.2p1)

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

Register void (direct/query/alias) markers remain conservatively unsupported;
plain and unregistered query-derived void markers retain zero-ABI normalization.
Only supported complete scalar adjusted parameters are implemented: no K&R,
variadics, VM/static/restrict array forms, aggregates or other parameter storage.
Globals, static/extern/thread storage and real linkage expansion remain deferred.
Existing register-array conversion refusal and inferred-auto limitations remain.
Not full C23 conformance.

The storage hint ignored for non-definition function type compatibility is not a
permission to take the address of a prototype object declared register. Native
query comparisons, AST identity, cross-object ABI and shared resource budgets
are recorded in the ledger, separately from grammar absence and remote CI.

## M15d1 explicit extern functions (6.2.2p4/p5; 6.7.1p2/p4)

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

Only single file-scope function declarations/definitions are added. Global or
local extern objects, tentative definitions, block-scope function declarations,
static/internal linkage, inline/thread storage, multiple function declarators
and inferred extern objects remain unsupported. No function storage/type flag is
needed while explicit/implicit declarations have identical external semantics;
future linkage work must separately design provenance and visibility. Existing
register-void, scalar inference, qualifier/VM/aggregate and resource restrictions
remain. Not full C23 conformance.

## M15d2 file-scope function prototype lists (6.7; 6.7.6.3; 6.9)

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

Only function prototypes form ordinary comma lists. No global objects/tentative
definitions, mixed object/function lists, function bodies in lists, alias/query-
derived function bodies, block function declarations, static/internal linkage,
inline/thread storage or inferred extern objects. Existing register-void,
qualifier/VM/aggregate/inference/resource restrictions remain. Shared bases are
immutable; no token vector/replay or second semantic/cache owner. Not full C23.

Clause 6.7.6.3p4 removes top-level return qualifiers in C23 function typing; exact
native diagnostic gaps are separate from original-source agreements. See the
ledger for shared-cache/scope/ABI/resource evidence and independent CI status.

## M15e1 static functions (6.2.2; 6.7.1; 6.9p3)

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

See the milestone ledger for exact source, diagnostic, ABI, AST and resource
evidence. Both evaluated and non-VM unevaluated function-use contexts are tested.

## M15f1 external scalar declarations (6.2.2; 6.7; 6.9)

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

Only explicit file-scope extern scalar declarations are added. Object definitions,
initializers, tentative/plain/static object declarations, externally declared object
arrays, block extern/function declarations, inferred extern, thread/inline storage,
VM/aggregate/remaining qualifier support and full C23 remain unsupported. Pointers
to incomplete arrays are scalar objects and retain existing composite rules.
Ordinary const objects are not constant expressions. Missing external storage is
a linker error, not an invented per-TU definition requirement. No full C23 claim.
Earlier global-object exclusions are superseded only for this documented slice.

## M15f2 external array declarations (6.2.2; 6.7.6.2; 6.9)

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

Only explicit extern declarations gain arrays. All definitions, initializers,
tentative/plain/static objects, block extern/functions, inferred extern, VM/VLA,
aggregate additions, thread storage/inline and remaining qualifiers stay deferred.
Unknown INNER rows, void/function elements and invalid constant bounds remain
errors. Unknown outer arrays are not tentative definitions and are not completed
to one element at TU end. Referenced native storage must exist at link time; every
executed index in curated tests is backed by initialized owner storage. No full
C23 conformance claim. Earlier array exclusions are superseded only for this slice.

The typeof_unqual expression-array native gap is separate from kcc support and
native original-source agreement. See the exact classifier/standards audit.

## M15g1 tentative scalar definitions (6.9.2; 6.7.10)

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

## M15g2 tentative arrays (6.9.2; 6.7.6.2; 6.7.10)

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

The exact Clang native storage bugs and permitted-warning agreement categories
are separate from kcc support; see the retained standards/layout audit.
