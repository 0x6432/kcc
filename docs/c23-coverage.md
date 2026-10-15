# C23 coverage

Status vocabulary: absent, subset, implemented, validated. Implemented means
code exists, not that conformance has been established. Validated requires
recorded tests and a stated target. This is a coverage inventory, not a claim
of complete ISO conformance.

| Area | Current status | Owning milestones |
| --- | --- | --- |
| Source/translation phases | subset (newline policy, splicing, physical mappings; M09a) | M01, M09-M11, M25 |
| Tokens and literals | subset (raw pp boundary, shared spelling decoder, runtime int/uint/long/ulong four-base/separator subset; M12e) | M02, M12, M20, M23 |
| Declarations/types | subset (int/uint/long/ulong; M12e) | M03, M08, M12-M18, M23-M24 |
| Expressions/statements | subset (implemented integer arithmetic, mixed-width conversions and casts; M12e) | M03-M08, M13, M19 |
| Constraint diagnostics | subset (M08c) | every semantic milestone |
| Preprocessing | subset (null/define/undef, object + fixed/variadic function macros, __VA_ARGS__/__VA_OPT__, raw parameter and optional-operand #/%:, ##/%:%: with placemarkers, #error/#warning, macro-existence groups and intmax/uintmax #if/#elif expressions, numeric spellings and narrow characters and direct/computed quoted/basic angle includes and explicit -I search subset; M11m) | M09-M11, M25 |
| Object layout and ABI | subset (word/long integer calls, separate-object GCC/Clang tests, M12e) | M12-M17, M20-M22, M24 |
| C23 additions | preprocessing subset (warning, elifdef/elifndef, optional macros, binary/separator literals); runtime keyword/type additions absent | M10-M11, M23a-M23h, M24a-M24g |
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
