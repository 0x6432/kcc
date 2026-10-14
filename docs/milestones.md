# Milestone ledger

Each milestone ends in a dedicated tested commit and push. Completion records
must state tests, limitations, component changes and remote checkpoint status.
Do not implement a later milestone just to hide a failure in an earlier one.

| ID | Deliverable | Acceptance evidence | Status |
| --- | --- | --- | --- |
| M00 | Build/driver, style, CI, architecture and handoff | Normal/sanitizer CLI tests, invalid input rejected | complete |
| M01 | Owned source buffers, byte locations, diagnostics, arenas | Empty/NUL/large input, bounds/alignment/overflow/lifetime tests | complete |
| M02 | On-demand initial lexer | Keywords, decimal integers, punctuators, comments, bad bytes; EOF/progress tests; libFuzzer CI | complete |
| M03 | `int main(void) { return 0; }` through AST, sema and QBE | Valid program emits IL, QBE builds executable, negative syntax/type tests | complete |
| M04 | Integer/unary/arithmetic expressions; Pratt table | Precedence/associativity/runtime tests, bounded parser fuzzing | complete |
| M05 | Local int declarations, assignment, expression statements | Shadowing/redeclaration/name tests, read/write execution | planned |
| M06 | Blocks, if/else, comparison/logical expressions | Branch and short-circuit side effects, scope checks | planned |
| M07 | while/do/for/break/continue | Nested-loop execution, invalid control-flow diagnostics | planned |
| M08 | Integer functions/prototypes/parameters/calls | Recursion, declaration compatibility, ABI comparison | planned |
| M09 | Preprocessing tokens, phase ordering, directives | Splicing/comment ordering, locations, parser token contract unchanged | planned |
| M10 | Object/function macros and rescanning | Recursion suppression, arguments, nested expansion, fuzz limits | planned |
| M11 | Includes, conditions, stringizing/token pasting | Include search/provenance, conditional evaluation, expansion tests | planned |
| M12 | Integer types/literals/conversions/casts/bitwise | Promotions, signedness, limits and target-model tests | planned |
| M13 | Pointers/strings/arrays/subscripts | Declarator/type checks, pointer arithmetic, executable cases | planned |
| M14 | Full declarators, typedef scopes, qualifiers, function pointers | Declarator trees and typedef ambiguity cases | planned |
| M15 | Globals/storage/linkage/multiple translation units | Host-link integration, tentative definitions, compatibility | planned |
| M16 | Struct/union/member/layout | Size/alignment/member access, host ABI comparisons | planned |
| M17 | Initializers/designators/compound literals | Nested initialization, zero fill, storage duration | planned |
| M18 | Enums/constant evaluation/assertions/sizeof/alignment | Constraints and unevaluated-expression tests | planned |
| M19 | switch/labels/goto/remaining operators | Branch targets, duplicate labels/cases, sequencing | planned |
| M20 | Floating arithmetic and ordinary floating types | Conversions/rounding/host ABI; do not fake long double | planned |
| M21 | Variadics and aggregate calls/returns | Mixed arguments, va_list behavior, host ABI interoperability | planned |
| M22 | Bit-fields/flexible arrays/baseline gap audit | Target layout, constraints, remaining C17 feature inventory | planned |
| M23a | C23 keyword changes and boolean constants | Token/declaration/expression constraints | planned |
| M23b | C23 integer/literal spelling additions | Binary literals, separators, literal typing | planned |
| M23c | nullptr/nullptr_t | Conversions, comparisons, calls, header exposure | planned |
| M23d | typeof/typeof_unqual | Declarators, qualifiers, evaluation rules | planned |
| M23e | auto inference | Valid initializers and forbidden declarations | planned |
| M23f | C23 enum underlying types and enumeration rules | Range, compatibility and ABI tests | planned |
| M23g | Attributes | Placement, supported effects and unknown-attribute policy | planned |
| M23h | constexpr objects and residual C23 declaration/preprocessor changes | Constant evaluation and clause-mapped gap tests | planned |
| M24a | _BitInt types and representation | Width/signedness/layout/constraint tests; documented limits | planned |
| M24b | _BitInt arithmetic/conversions/ABI | Wide lowering/runtime tests and host interoperability where supported | planned |
| M24c | Atomic types/load/store | Memory model, alignment, target code inspection | planned |
| M24d | Atomic RMW/fences/library interface | Ordering constraints and multithreaded stress tests | planned |
| M24e | Complex types/arithmetic | Representation, operations and ABI; explicit runtime dependencies | planned |
| M24f | VLA/variably modified types | Lifetime, evaluation, stack bounds, goto constraints | planned |
| M24g | long double, floating environment and remaining backend gaps | Correct target representation and runtime/ABI tests | planned |
| M25a | Predefined macros and translation/environment audit | Standard clause matrix and implementation-defined docs | planned |
| M25b | Compiler-provided headers and runtime helpers | Header compile tests and link resolution | planned |
| M25c | Hosted system-libc compatibility | Declare supported libc/version; verify C23 gaps explicitly | planned |
| M25d | Language/library conformance audit | Published unsupported/validated list; no premature full-C23 claim | planned |
| M26 | Self-host and bootstrap | Compile compiler with itself, compare bootstrap stages | planned |

M23-M25 are now split into independently testable batches. Their exact grammar,
runtime and ABI designs are reviewed before their implementation, not guessed
in early code. Any newly discovered standard feature is assigned a milestone
before the audit can be considered complete.

## Test policy

Every feature adds positive, negative and integration tests. Tests distinguish
compilation rejection from executable failure. Use GCC/Clang only as references
for defined programs with matching target choices. Minimize fuzz crashes and
commit regressions. No arbitrary user-provided C is executed by fuzz harnesses.
M02 fuzzes lexing; parsing, sema and IL emission are added as they become usable.
Pull requests run short, resource-bounded fuzzing; scheduled runs are longer and
save failures even when the fuzz command exits unsuccessfully.

## M00 completion record

Normal GCC build and all CLI tests passed. ASan/UBSan build and the same tests
passed after correcting the sandbox's missing runtime-library search path.
No compiler features yet. Push/remote CI are verified separately.

## M01 completion record

Normal and ASan/UBSan support/CLI tests passed. Source byte buffers preserve
embedded NUL, use an explicit 16 MiB limit and own filenames. Locations count
bytes, with tabs at eight-column stops. Diagnostics count errors and write to
a supplied stream. Arena allocation checks overflow and returns max_align_t
alignment. Parser/AST consumers do not exist yet. No translation normalization.

## M02 completion record

GCC/Clang regression tests and GCC ASan/UBSan tests passed. Local Clang
libFuzzer + ASan/UBSan completed 197,465 inputs in 11 seconds without failures.
The lexer generates tokens on demand and caches one lookahead token; repeated
peek and EOF are stable. Decimal unsigned values up to UINT64_MAX are lexed;
semantic int-range checking comes in M03. Unsupported compound operators and
nondecimal/suffixed literals are rejected rather than reinterpreted. Driver
adds `--tokens file.c`; CI adds bounded and scheduled fuzzing with artifacts.

## M03 completion record

Separate AST structs/constructors, BNF-documented recursive descent, explicit
int type, independent sema and QBE emission are implemented. This milestone
accepts one int main(void) with exactly one return of a decimal int literal.
Literals 0 through INT32_MAX are supported, expanding the initial zero-only
example without introducing another language feature. Validation completes
before any IL emission. GCC/Clang and ASan/UBSan tests passed, including QBE
assembly/link/runtime results. Full pipeline fuzzing completed 585,480 inputs
in 11 seconds without failures. CI adds pinned QBE build and pipeline fuzzing.

## M04 completion record

Pratt parsing handles parentheses, prefix +/- and binary + - * / %. Concrete
unary/binary AST structs have structural depth annotations. Sema recursively
types operands; codegen emits QBE integer instructions with explicit SSA
temporaries. Nesting and tree depth are separately bounded at 128, preventing
flat left-associative chains from bypassing recursion limits downstream.
GCC/Clang, sanitizer and QBE/runtime tests passed. Defined arithmetic cases
(including deterministic random cases) agree with host compiler executables.
The first final fuzz run covered 271,175 lexer and 697,473 pipeline inputs in
16 seconds per harness without failures. Deep/flat seeds and output-I/O failure
regressions were then added before final verification. An additional pipeline
fuzz run with those seeds completed 347,705 inputs in 11 seconds. Final
regressions and output-failure tests passed under ASan/UBSan as well.

Remote CI for M00, M01, M02 and M03 was observed completed successfully. The
M04 run is verified separately after push, not inferred from those successes.
