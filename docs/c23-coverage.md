# C23 coverage

Status vocabulary: absent, subset, implemented, validated. Implemented means
code exists, not that conformance has been established. Validated requires
recorded tests and a stated target. This is a coverage inventory, not a claim
of complete ISO conformance.

| Area | Current status | Owning milestones |
| --- | --- | --- |
| Source/translation phases | subset (newline policy, splicing, physical mappings; M09a) | M01, M09-M11, M25 |
| Tokens and literals | subset (raw pp boundary, shared spelling decoder, runtime ordinary byte characters and four-base/separator/U/L/LL integer literals; M12j) | M02, M12, M20, M23 |
| Declarations/types | subset (_Bool, plain/signed/unsigned char, signed/unsigned short/int/long/long long; M12j; object pointers, fixed multidimensional arrays, ordinary strings and adjusted array parameters M13k; parenthesized object/abstract declarators M14a and fixed function suffixes M14e) | M03, M08, M12-M18, M23-M24 |
| Expressions/statements | subset (integer arithmetic/conversions/casts; object-pointer lvalues, scaled arithmetic and comparisons; M13d) | M03-M08, M13, M19 |
| Constraint diagnostics | subset (M08c) | every semantic milestone |
| Preprocessing | subset (null/define/undef, object + fixed/variadic function macros, __VA_ARGS__/__VA_OPT__, raw parameter and optional-operand #/%:, ##/%:%: with placemarkers, #error/#warning, macro-existence groups and intmax/uintmax #if/#elif expressions, numeric spellings and narrow characters and direct/computed quoted/basic angle includes and explicit -I search subset; M11m) | M09-M11, M25 |
| Object layout and ABI | subset (byte/halfword/word/long integer calls, separate-object GCC/Clang and dirty-upper-bit tests; M12j) | M12-M17, M20-M22, M24 |
| C23 additions | subset (warning, elifdef/elifndef, optional macros; runtime binary/separator literals; unnamed definition parameters M14d); C23 keyword/type additions absent | M10-M11, M23a-M23h, M24a-M24g |
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
