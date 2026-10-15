# C23 coverage

Status vocabulary: absent, subset, implemented, validated. Implemented means
code exists, not that conformance has been established. Validated requires
recorded tests and a stated target. This is a coverage inventory, not a claim
of complete ISO conformance.

| Area | Current status | Owning milestones |
| --- | --- | --- |
| Source/translation phases | subset (newline policy, splicing, physical mappings; M09a) | M01, M09-M11, M25 |
| Tokens and literals | subset (raw pp boundary, shared spelling decoder, runtime ordinary byte characters and four-base/separator/U/L/LL integer literals; M12j) | M02, M12, M20, M23 |
| Declarations/types | subset (_Bool, plain/signed/unsigned char, signed/unsigned short/int/long/long long; M12j; restricted integer-object pointers M13a) | M03, M08, M12-M18, M23-M24 |
| Expressions/statements | subset (implemented integer arithmetic, promotions, mixed-width/boolean conversions and casts; M12j) | M03-M08, M13, M19 |
| Constraint diagnostics | subset (M08c) | every semantic milestone |
| Preprocessing | subset (null/define/undef, object + fixed/variadic function macros, __VA_ARGS__/__VA_OPT__, raw parameter and optional-operand #/%:, ##/%:%: with placemarkers, #error/#warning, macro-existence groups and intmax/uintmax #if/#elif expressions, numeric spellings and narrow characters and direct/computed quoted/basic angle includes and explicit -I search subset; M11m) | M09-M11, M25 |
| Object layout and ABI | subset (byte/halfword/word/long integer calls, separate-object GCC/Clang and dirty-upper-bit tests; M12j) | M12-M17, M20-M22, M24 |
| C23 additions | subset (warning, elifdef/elifndef, optional macros; runtime binary/separator literals); C23 keyword/type additions absent | M10-M11, M23a-M23h, M24a-M24g |
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
