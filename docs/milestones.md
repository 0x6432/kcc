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
| M05 | Local int declarations, assignment, expression statements | Redeclaration/name/lvalue tests, read/write execution; shadowing deferred to M06 | complete |
| M06 | Blocks, if/else, comparison/logical expressions | Branch and short-circuit side effects, scope checks | complete |
| M07 | while/do/for/break/continue | Nested-loop execution, invalid control-flow diagnostics | complete |
| M08 | Integer functions/prototypes/parameters/calls | Recursion, declaration compatibility, ABI comparison | complete |
| M09 | Preprocessing tokens, phase ordering, directives | Splicing/comment ordering, locations, parser token contract unchanged | complete (stated subset) |
| M10 | Object/function macros and rescanning | Recursion suppression, arguments, nested expansion, fuzz limits | complete (M10a–M10d documented subset; operators/directives remain M11) |
| M11 | Includes, conditions, stringizing/token pasting | Include search/provenance, conditional evaluation, expansion tests | in progress (M11a/M11b stringizing complete; M11c token pasting next) |
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

## M05 completion record

Ordered block items, distinct local/name/assignment/load/expression/empty nodes,
one function-body scope, point-of-declaration binding and explicit lvalue loads
are implemented. Assignment binds below arithmetic and associates rightward.
Sema now receives the arena for conversion nodes and validates all items,
including unreachable code. QBE entry alloc4 slots and loadw/storew execute
initializers/statements in source order. No zero fill for uninitialized locals;
falling off main returns zero. Unsupported C keywords cannot become local names.

GCC/Clang builds, semantic-AST assertions, positive/negative/diagnostic tests,
ASan/UBSan and QBE executable/reference tests passed. Boundary tests cover
256/257 locals, 4096/4097 block items, right-associative assignment, explicit
conversion depth and malformed/unreachable items. Fuzzing completed 272,299
lexer and 425,201 pipeline inputs in 21 seconds per harness without failures.
Final diagnostic/self-assignment additions passed normal and ASan/UBSan
regressions before commit.

Scope is deliberately flat here: nested blocks/shadowing belong to M06. Limits
are resource policies, not C constraints. Uninitialized reads/self-initialization
are not executed in runtime tests; point-of-declaration is checked structurally.
Remote push and CI must be checked separately; M04 CI passed previously.

## M06A completion record

Nested blocks and shadowing. Nested compounds use scoped name bindings separate from the all-local slot list. Lookup walks parent scopes; redeclarations are checked only in the current scope. Combined statement nesting is bounded at 128 and block items are counted across the function.

Normal GCC, ASan/UBSan and QBE/reference executable regression tests passed.
Sanitized pipeline fuzzing: 376059 inputs in 11 seconds. Remote push and CI are checked separately.
Next: M06b: comparisons and if/else, nearest-if else binding and QBE branch/merge blocks.

## M06B completion record

Comparisons and if/else. A distinct if-statement AST node, nearest-if else binding, signed int comparisons, selection/substatement scopes and QBE branch/merge handling are implemented. Both branches are checked semantically. Termination propagates through nested blocks and conditionals; both-return paths have no dead merge block.

Normal GCC, ASan/UBSan and QBE/reference executable regression tests passed.
Sanitized fuzzing: lexer 242396 inputs in 13 seconds; pipeline 355675 inputs in 13 seconds. Remote push and CI are checked separately.
Next: M06c: distinct logical AST nodes and branch/phi short-circuit lowering; track actual predecessor labels for nested RHS expressions.

## M06C completion record

Short-circuit logical operators. Distinct logical-expression AST nodes lower &&/|| through conditional branches and phi values. Unary ! and all comparisons normalize int results to 0/1. The emitter records the current block label so nested RHS phi predecessors remain correct. Sema checks skipped operands too; codegen does not evaluate them at runtime.

Normal GCC, ASan/UBSan and QBE/reference executable regression tests passed.
Sanitized pipeline fuzzing: lexer: 339202 inputs in 21 seconds; pipeline: 622309 inputs in 21 seconds. Remote push and CI are checked separately.
Next: M07: while/do/for with distinct statement structs, loop scopes and bounded nesting, explicit break/continue targets, and correct QBE back edges. Do not skip ahead to functions.

M06c final verification also passed with Clang as compiler/reference compiler,
ASan/UBSan executable tests, and 24 deterministic random logical trees.

## M07A completion record

While, break and continue. While has a distinct AST node. Jump nodes record the nearest enclosing loop during sema. Scope and loop contexts are independent and restore their parents on failure too. QBE while continue targets the condition; break targets the exit. Only an unterminated body gets an implicit back edge.

Normal GCC, semantic-AST, ASan/UBSan and QBE/reference executable tests passed.
Sanitized fuzzing: pipeline: 262257 inputs in 13 seconds. Remote push and CI are verified separately.
Next: M07b: distinct do/while AST, body-first execution, continue-to-condition and break/return bypass of condition.

## M07B completion record

Do/while loops. A distinct do-statement node executes its body before the condition. Continue targets the condition; break and return bypass it. Body scopes do not leak into the condition. Sema still validates unreachable conditions. QBE emits well-formed condition/exit blocks conservatively without claiming whole-loop reachability inference.

Normal GCC, semantic-AST, ASan/UBSan and QBE/reference executable tests passed.
Sanitized fuzzing: pipeline: 395480 inputs in 13 seconds. Remote push and CI are verified separately.
Next: M07c: for headers with optional declaration/expression initialization, optional condition and step; scope the initializer across the loop only and send continue through the step.

## M07C completion record

For loops and complete M07 iteration subset. A distinct for-statement node records optional initializer declaration/expression, condition and step. Initializer declarations are visible in condition/body/step but not after the loop. Continue executes the step before the condition; missing condition means unconditional iteration. All loop kinds preserve scoped local initialization, short-circuit conditions and nearest-loop jump targets.

Normal GCC, semantic-AST, ASan/UBSan and QBE/reference executable tests passed.
Sanitized fuzzing: lexer: 316096 inputs in 21 seconds; pipeline: 533342 inputs in 21 seconds. Remote push and CI are verified separately.
Next: M08: integer functions, declarations/prototypes, parameters, calls and recursion. Specify translation-unit function lists, signature compatibility, separate function/local scopes, entry parameter slots and QBE call ABI before implementation.

M07c final verification passed with Clang as compiler/reference and GCC
ASan/UBSan, including QBE executable tests. Twelve deterministic generated
for-loop cases exercise continue/step sequencing. Structural tests assert
header-vs-body-vs-outer bindings and nearest-loop jump targets.

## M08A completion record

Ordered external declarations, compatible zero-argument prototypes and multiple int function definitions are supported. Sema installs canonical symbols in source order; calls resolve visible functions, respect local shadowing and reject duplicate definitions. QBE emits each definition independently and direct w-result calls; prototypes emit no IL.

Normal GCC, semantic-AST and QBE/reference runtime regressions passed.
ASan/UBSan and sanitized pipeline fuzzing are run before the commit; exact
results follow below. Push and remote CI are verified separately.
Next: M08b parameter/argument lists and name-independent signature compatibility.

M08a sanitizer verification passed with ASan/UBSan, including QBE runtime
tests. Sanitized pipeline fuzzing completed 349498 inputs in 13 seconds.

M08a remote CI passed: https://github.com/0x6432/kcc/actions/runs/38714173006

## M08B completion record

Integer parameter and argument lists are implemented with name-independent function signatures, source-order prototype visibility and argument-count checks. Parameters receive the first local slots and share scope with the outermost body declarations. QBE w entry values are stored into those slots; nested call arguments finish emitting before the call line.

Acceptance covers argument order/arity, prototype names/compatibility,
parameter mutation/shadowing/redeclaration, nested call/short-circuit operands,
128 arguments/parameters and 256 total parameter/local slots.
Tests and fuzz counts are recorded after verification. Next: M08c direct/mutual
recursion and bidirectional host-compiler ABI testing.

M08b verification passed: GCC/Clang, semantic-AST, QBE/runtime/reference
and ASan/UBSan. Sanitized fuzzing: lexer 280937 and pipeline 450116 inputs
in 16 seconds per harness. Remote push/CI are verified separately.

## M08C completion record

Bounded factorial, Fibonacci, accumulator, local-preservation and mutual
recursion are tested against host-compiled reference programs. Separate-object
ABI tests cover both call directions with 0, 1, 2, 6, 7, 8, 12 and 128 int
arguments, signed boundary values and cross-compiler mutual recursion. Missing
external definitions compile successfully and are rejected by the host linker.
The 128-argument weighted sum is balanced to respect the expression-depth bound.

CI now selects the matrix host compiler for runtime/reference tests and also
runs generated-executable/ABI tests with the sanitized compiler build. Exact
local verification/fuzz counts follow below. Remote CI is checked after push.

M08 is complete for its stated int-only subset, not for all C23 function
features. Next is M09: plan preprocessing-token/translation-phase contracts
before adding line splicing/directives. Macro expansion remains M10/M11.

M08b remote CI passed: https://github.com/0x6432/kcc/actions/runs/38714953000
M08c verification passed: GCC/Clang reference/runtime and separate-object ABI
tests, semantic-AST and ASan/UBSan. Sanitized fuzzing: lexer 336767 and
pipeline 472930 inputs in 21 seconds each. README factorial example exits 120.

M08c remote CI passed: https://github.com/0x6432/kcc/actions/runs/38715578290

## M09 checkpoint plan

- M09a: input newline policy, phase-2 splicing, logical spelling/physical location
  mapping, source unit/oracle tests and both fuzz paths.
- M09b: distinct preprocessing tokens, maximal-munch pp numbers, newline/spacing
  state and deferred language-token classification. Specify APIs before coding.
- M09c: on-demand preprocessor facade and initial directive dispatch/null
  directives. Do not silently accept unsupported directives or implement macros.
  Macro expansion/rescanning is M10; includes/conditions/stringizing/pasting M11.

## M09A completion record

CRLF and lone CR normalize to LF; immediate backslash-newline pairs disappear
before comments/tokens. Splicing can join names/keywords/operators/comments and
extend line comments. Output is not rescanned into a second splice. Logical
spellings remain contiguous for parser/sema/codegen. Physical byte offsets and
diagnostic lines/columns use retained original bytes and sparse checkpoints.
Preparation is explicit, idempotent and transactional on allocation failure.
The existing lexer/parser token API remains; no whole-file token materialization.

Acceptance includes an independent two-phase oracle on 1024 deterministic
binary inputs, embedded NUL/high bytes, mapping/EOF/idempotence checks, 8192 map
checkpoints, exact 16 MiB source acceptance and one-byte oversize rejection.
Executable/reference tests cover 11 phase-ordering cases under LF, CRLF and CR;
negative tests cover no-rescan, whitespace after backslash and comment separation.
Diagnostics and token-debug offsets refer to physical positions across splices.
Both fuzz harnesses prepare sources; lexer fuzzing asserts spelling/mapping
bounds, monotonicity, stable EOF and progress. Fuzz never executes source C.

Still unsupported: preprocessing tokens as a separate stream, directives/macros,
encodings/UCNs and full translation phases. Missing-final-newline acceptance
remains an extension; no synthetic newline is added. Allocation-failure paths
are checked in implementation but not yet covered by allocator fault injection.
Final local verification/fuzz results follow below; remote CI is checked after
push. Next: M09b, not macro expansion.

M09a local verification passed with GCC and Clang, source/oracle/AST tests,
QBE/reference executables, separate-object integer ABI tests and ASan/UBSan.
Final sanitized fuzzing: lexer 244776 inputs; compiler pipeline 500452 inputs;
21 seconds per harness. Earlier 21-second runs also passed (257740/510224).
Remote CI is verified after push, independently of local passes.

M09a remote CI passed: https://github.com/0x6432/kcc/actions/runs/38717250245

## M09B completion record

Raw preprocessing tokens and language tokens are separate structs/enums.
pp_lexer scans identifiers, ASCII pp numbers, quoted/prefixed literals, all C23
punctuator spellings, other ASCII characters and explicit external newlines.
No raw numeric values/keywords are assigned. Spacing/line-start flags and VT/FF
metadata survive scanning. Block-comment newlines do not become directive ends.
A stateless converter and temporary language adapter preserve parser interfaces
and rejection of unsupported language constructs/directives. --pp-tokens exposes
the raw stream; --tokens keeps converted behavior. Raw brace digraphs convert to
existing brace kinds without changing parser productions.

Dedicated unit tests cover all punctuators, overlapping maximal munch, numeric
boundaries/exponent signs/apostrophes/overflow spellings, prefixes/escaped quotes,
comment/line/VT/FF flags, splice spellings, deferred conversion and stable EOF.
CLI tests cover the raw format, physical positions, raw partial-error output,
output failure and separation from compiler acceptance. Both lexer paths are
fuzzed independently, with progress/bounds/flags/repeat-peek/error-count checks.
Existing syntax/AST/source, QBE/reference and separate-object ABI tests remain.

Limitations: no header-name context, Unicode/UCN recognition, interpretation of
non-int literals, directives, expansion/concatenation or macro provenance yet.
Exact verification/fuzz counts follow below; check remote CI after push.
Next: M09c, with explicit preprocessor ownership and directive whitespace/null
rules before implementation. Macro expansion stays M10.

M09b local verification passed: GCC/Clang strict builds, raw/conversion unit
and CLI tests, source/oracle/AST checks, QBE/reference executables, separate-object
ABI and ASan/UBSan. Final sanitized fuzzing completed 106643 lexer inputs
(each exercises raw and converted streams) and 466292 pipeline inputs in
26 seconds per harness. Earlier 21-second runs passed (58630/320824).
README factorial example exits 120; raw fixture inspection succeeds without
numeric conversion. Verify remote CI separately after pushing.

M09b remote CI passed: https://github.com/0x6432/kcc/actions/runs/38719725392

## M09C completion record

preprocess.c now owns raw input and parser-visible one-token lookahead. Parser,
driver, semantic tests and fuzz paths migrated together; the temporary language
lexer wrapper was removed. Null #/%: directives disappear anywhere between C
tokens before conversion. Directive start/whitespace/comment/splice/EOF behavior
is explicit. Known-but-unsupported, unknown, malformed and misplaced directives
reject without converting their bodies. Raw lexical errors remain distinct and
are not rediagnosed. Error tokens stay nonempty even for bad separators at EOF.

Dedicated tests cover 16 standard directive names, null-only streams, digraphs,
VT/FF before/after markers and inside comments, block-comment logical lines,
physical spliced locations, draining errors, no eager future-line diagnostics,
stable peek/EOF and nonempty error progress. CLI tests distinguish raw inspection,
processed language tokens and empty-TU rejection. Thirty LF/CRLF/CR runtime/
reference cases place null directives before/within/after supported C constructs;
late invalid directives still prevent all compiler IL. Existing source/oracle/
AST/ABI coverage remains. Both fuzz harnesses use the production preprocessor.

M09 is complete for its stated subset, not full C23 preprocessing. Non-null
directives, macro expansion, headers, conditions, complete encoding/literals and
macro provenance remain deferred. Clang/compiler-rt had disappeared from the
sandbox and were restored; dependencies may vanish again. Exact final local
verification/fuzz counts follow below. Remote CI is checked separately after
push. Next: specify a small M10 object-like macro slice before implementation.

M09c local verification passed: GCC/Clang strict builds; directive/cache/EOF,
raw/conversion, CLI, source/oracle/AST tests; QBE/reference execution,
separate-object integer ABI and ASan/UBSan. Final sanitized fuzzing completed
69628 lexer/preprocessor inputs and 126498 full-pipeline inputs in 26 seconds
each. Earlier 21-second runs passed too (54419/127155). The null-directive
fixture compiles/links and exits 7. Remote CI is verified separately after push.


## M10A completion record

Design was recorded in m10-object-macros.md before implementation. Object-like
#define/#undef use arena-owned linked replacement tokens and stable macro
identities, then an explicit bounded rescan stack. Empty macros, aliases, keyword
names, direct/mutual recursion, final-token suppression, source-order definition
changes and spacing-sensitive compatible redefinitions are tested. Rejected
lines preserve prior bindings. Adjacent function-like definitions, token pasting
and protected names reject explicitly; replacement # never starts a directive.

Raw tokens now distinguish spelling and expansion locations; language tokens
distinguish diagnostic and spelling locations. Numeric conversion, semantic name
matching and QBE symbol emission were migrated together. Every preprocessor
consumer releases its storage. Parser grammar and typed AST variants are unchanged.

Tests cover cache/EOF/provenance, macro identity reuse, all five resource limits,
a countable expansion-work boundary and exponential expansion rejection. A new
97-case deterministic kind/spelling oracle includes cyclic macro graphs against
HOST_CC; CI selects GCC and Clang. Ten macro runtime/reference cases run under
LF/CRLF/CR. Compiler diagnostics use invocation locations. Both existing fuzz
paths have macro corpus seeds and expansion-aware progress/spelling assertions.

M10 is NOT complete: next checkpoint is M10b function-like definitions and
arguments, with explicit unavailability/hide-set and argument-lifetime design
before coding. Stringizing, pasting, includes and conditions remain M11.
Final local results/fuzz counts follow below; remote CI is checked after push.


M10a local verification passed: GCC 11.5 and Clang 15 strict normal builds and
ASan/UBSan builds; CLI/source/raw/token/cache/provenance/limit/AST regressions;
97 token/spelling oracle cases with each host compiler; QBE/reference execution
and separate-object integer ABI with both hosts. Final sanitized fuzzing passed
43915 lexer/preprocessor and 125308 full-pipeline inputs in 26 seconds each.
An earlier 26-second run passed 52672/136498 inputs. Both harnesses exercise the
real macro stage and never execute arbitrary generated code. A final normal
make test passed and --version reports m10a. Compiler build artifacts remain
under 10 MiB after cleanup; external tools/logs under 75 MiB. Remote CI is
verified separately after pushing; obtain the current hash from git log -1.


## M10B completion record

The tentative full function/argument batch was split before implementation:
M10b zero-parameter functions, M10c fixed arguments/substitution, and optionally
M10d variadics. m10-zero-parameter-macros.md records design and subset policy.
An unexpanded-token cursor/pending token crosses replacement/source boundaries;
fixed token-carried hide sets replace active-frame disabling. Object expansion
inherits name bits; function expansion intersects name/closing-delimiter bits,
then adds itself. Storage/provenance, parser/AST/sema/QBE APIs and deferred
conversion remain unchanged. No re-lexing or whole-TU token vector.

Tests cover empty lists/bodies, whitespace/comments/splices, non-invoked names,
keywords, aliases, partial delimiters, non-retroactive invocation, recursive
suppression and all hide-set word boundaries. Form-changing redefinitions reject
transactionally; undef allows a fresh form. Unsupported parameters/operators,
nonempty/unterminated calls and the directive-boundary policy diagnose. Cache/
cursor counters and fatal EOF are tested. Exponential function expansion hits
the work bound; 201 successive source-delimited calls need not retain 201 frames.

The host oracle now compares 198 kind/spelling streams, retaining all 97 object
cases. New QBE/reference cases include macros falling through to actual C
functions, plus LF/CRLF/CR variants. Both sanitizer fuzz paths have function and
boundary seeds. Sandbox reset lost uncommitted work during validation; the
reviewed implementation/tests/docs were reconstructed and validated afresh.
Clang/compiler-rt and pinned QBE were restored; dependencies may disappear again.
Final local evidence follows below; verify exact pushed-commit CI separately.

Next: M10c fixed parameters, balanced raw argument collection, zero/empty argument
rules, argument prescan ownership, substitution and per-token availability.
Stringizing/pasting/includes/conditions remain M11. Full M10 is not complete.


## M10b recovery verification checkpoint

Recovered files passed make test, 198 token/spelling oracle cases with GCC and
Clang, GCC-host QBE/reference runtime and separate-object ABI tests. Sanitized
libFuzzer runs passed 60392 lexer/preprocessor and 169562 pipeline inputs in
26 seconds each, with both new seed files in both harnesses. No arbitrary
generated programs were executed. The sandbox reset had destroyed uncommitted
work; this tested recovery checkpoint is pushed before the longer local matrix.
Normal/sanitized GCC/Clang full-matrix and exact pushed-commit CI verification
are still pending at this checkpoint. Do not infer those passes from fuzzing.


## M10b final verification

The pending validation above was completed after the recovery checkpoint.
GCC 11.5 and Clang 15 passed strict normal and ASan/UBSan builds, source/raw/
conversion/CLI/AST/cache/provenance/limit tests, the 198-case token/spelling
oracle, QBE/reference programs and separate-object integer ABI tests. Fuzzing
passed 60392 lexer/preprocessor and 169562 pipeline inputs in 26 seconds each,
without executing arbitrary generated code. Source commit c3ee142 also passed
GitHub CI: https://github.com/0x6432/kcc/actions/runs/38749074367

M10b is complete for its zero-parameter subset. Named arguments, argument
prescan/substitution and variadics remain unimplemented, as documented above.
The subsequent verification commit only records results; it changes no compiler
code. Verify its own remote CI separately after push. Future resumes must fetch
and compare the latest development hash before editing; the sandbox really did
lose uncommitted files and dependencies during this checkpoint.


## M10c completed implementation

Design was recorded in m10-fixed-arguments.md before coding. Fixed parameter
lists are validated and indexed on replacement tokens; redefinitions compare
names/order and preserve old bindings on failure. Raw balanced collection
preserves empty arguments and checks arity before expansion. Isolated lazy
prescan cannot consume following source or hide the enclosing macro too early.
Substitution retains per-token suppression and original spelling, with the
outermost invocation used for diagnostics. Unused arguments are not expanded.

Cursor state was separated from global source/table/arena/work ownership.
Concrete arena records cover parameters, invocation arrays and raw/cached tokens;
heap prescan cursors are freed on all returns. Parser/AST/sema/QBE interfaces
are unchanged. New parameter, parentheses, prescan and auxiliary storage bounds
join existing source/definition/frame/work caps, with argument work charged too.

Tests retain all 198 previous oracle cases and extend to 374 GCC/Clang streams,
including recursive fixed-parameter graphs, callbacks, empty and unused arguments,
comma protection and parameter shadowing. Unit boundaries test 128 parameters,
64 nested prescans, 128 nested parentheses and auxiliary retention across repeated
definitions. New QBE/reference cases cover macro-generated declarations/calls,
sequenced side effects, source locations and LF/CRLF/CR variants. Both fuzz paths
have fixed-argument/rescan seeds and cursor/auxiliary invariants.

The sandbox resumed with a stale uncommitted M10b snapshot. It was preserved in
a local stash before fast-forwarding to the pushed M10b checkpoint. Dependencies
were restored again. Final validation evidence follows; remote CI is checked
separately. Full M10 is not complete: M10d is variadics/__VA_ARGS__/__VA_OPT__;
M11 owns macro operators/includes/conditions and directive integration.


## M10c tested implementation checkpoint

Local make test passed, including all argument/unit/resource/provenance tests.
The 374-case token/spelling oracle passed with GCC and Clang. GCC-host QBE/
reference execution and separate-object integer ABI passed. Sanitized fuzzing
passed 52567 lexer/preprocessor and 168281 full-pipeline inputs in 26 seconds
each, with new argument corpus seeds. Arbitrary generated code was not executed.
This checkpoint is pushed before the longer full GCC/Clang normal/ASan/UBSan
matrix to protect work from resets. That matrix and exact pushed-commit CI are
still pending here; do not infer them from fuzzing. Final evidence follows later.


## M10c final verification

The pending matrix above is complete. GCC 11.5 and Clang 15 each passed
strict normal and ASan/UBSan builds, all unit/rejection tests, the 374-case
macro token/spelling oracle, QBE/reference execution and separate-object
integer ABI tests. The full matrix was rerun after replacing the new limit-test
string generator with a bounds-checked vsnprintf builder: GCC 11 diagnosed
its previous unchecked sprintf construction under sanitizer optimization and
-Werror. No production code changed and no warning was suppressed.

Sanitized fuzzing passed 52567 lexer/preprocessor and 168281 pipeline inputs
(220848 total), without executing arbitrary generated code. Source checkpoint
8538ed4 passed GitHub CI:
https://github.com/0x6432/kcc/actions/runs/38755902384
The subsequent test/documentation verification commit must have its own remote
CI checked after push. M10c is complete only for the fixed-parameter subset;
M10d variadics and M11 macro operators/includes/conditions remain outstanding.


## M10d planned implementation

Design decisions and acceptance criteria are recorded in m10-variadics.md before
coding. Extend fixed parameters with a trailing variadic slot, preserve raw
separator commas, reuse isolated lazy prescan, and stream validated optional
replacement regions without isolating rescan boundaries. M11 operators and
directive integration remain deferred. No implementation or validation is
claimed by this planning checkpoint.


## M10d tested implementation checkpoint

make test passed with 564 token-kind/spelling oracle cases; the same oracle
passed with Clang. GCC-host QBE/reference programs and separate-object ABI
tests passed, including 16 new variadic runtime programs under LF/CRLF/CR.
Unit tests cover 128 named parameters plus a variable slot, exact 1024-token
optional definitions, 64/65 nested variadic prescans and bounded large tails.
Sanitized fuzzing completed 40473 lexer/preprocessor and 170004 pipeline inputs
(210477 total) in 26 seconds each, without executing arbitrary generated code.

The source checkpoint is pushed now to protect against sandbox resets. The
full GCC/Clang normal/ASan/UBSan matrix and exact-commit remote CI are pending;
these results must be checked separately before marking M10 complete. No new
parser, AST, sema or QBE interfaces; M11 operator/directive work remains deferred.


## M10d final verification

The pending validation above is complete. GCC 11.5 and Clang 15 each passed
strict normal and ASan/UBSan builds, all unit/CLI/AST/rejection tests, the
564-case token-kind/spelling oracle, QBE/reference execution and separate-object
integer ABI tests. The 16 new variadic runtime programs run with LF, CRLF and
lone CR endings. Both existing and new macro regressions remain covered.
Sanitized fuzzing completed 40473 lexer/preprocessor and 170004 pipeline inputs
(210477 total), without executing arbitrary generated code.

Source commit 34760ff passed GitHub CI:
https://github.com/0x6432/kcc/actions/runs/38759964506
This following documentation-only verification commit has its own exact-commit
CI checked after push. No production change followed the tested source commit.

M10a-M10d are complete for the documented object/function macro subset. M11
operators/includes/conditions, predefined macros, full preprocessing and the
remaining C23 language/ABI milestones are not complete. Next: design a small
M11a stringizing checkpoint, accounting for borrowed versus synthesized spelling,
raw arguments, whitespace/escaping and __VA_OPT__ semantics before coding.
Token pasting needs its own re-lex/placemarker design, not a shortcut extension.


## M11a planned implementation

Decisions are recorded in m11-stringizing.md before coding: raw named/variadic
argument stringizing, owned synthesized spellings, bounded bytes, expanded-pp
inspection and observable whitespace contracts. #__VA_OPT__ interactions are a
separate M11b checkpoint; token pasting and directives remain later M11 slices.
This planning entry makes no implementation or validation claim.


## M11a tested implementation checkpoint

make test passed, retaining 564 language-token oracle streams and adding 142
expanded-pp agreement streams. Both GCC and Clang passed the 706 agreement
cases and five separately recorded whitespace-policy groups. GCC-host QBE/
reference execution and separate-object ABI tests passed, including eight new
stringize-then-discard programs under LF/CRLF/CR. Single and cumulative 1 MiB
spelling boundaries, generated-source lifetime and cached conversion errors pass.
Sanitized fuzzing passed 19909 lexer/preprocessor and 114717 pipeline inputs
(134626 total) in 26 seconds each; arbitrary generated C was not executed.

This source checkpoint is pushed before the longer full normal/ASan/UBSan
GCC/Clang matrix to protect work from sandbox resets. That matrix and exact
pushed-commit CI are pending and must be checked separately. The subset excludes
#__VA_OPT__, ##, directives beyond define/undef/null and C string expressions.
The host whitespace differences remain a documented conformance-audit gap.


## M11a final verification

The pending validation above is complete. GCC 11.5 and Clang 15 each passed
strict normal and ASan/UBSan builds, all unit/CLI/AST/rejection tests, 564
language + 142 expanded-pp agreement streams and the five explicit whitespace
policy groups. QBE/reference execution and separate-object integer ABI tests
passed with both hosts and sanitizer builds. The eight new discard-path runtime
programs cover LF, CRLF and lone CR. Generated lifetime, original invocation
errors, cache/EOF stability and exact single/cumulative spelling caps passed.

Sanitized fuzzing passed 19909 lexer/preprocessor and 114717 pipeline inputs
(134626 total), without executing arbitrary generated code. Source commit
3640b6d passed GitHub CI:
https://github.com/0x6432/kcc/actions/runs/38763520175
The public API rate limit required authenticated CI reads using already authorized
GitHub access; temporary credentials were removed, never committed. This following
documentation-only commit has its own exact-commit CI checked after push.

M11a is complete for raw named/variadic parameter stringizing, not all # operator
forms or full C23 preprocessing. The five host whitespace disagreements remain
an explicit interpretation/conformance audit item, not counted as agreement.
M11b must implement #__VA_OPT__ with correct argument substitution and pre-rescan
boundaries. Token pasting, includes/conditions and C string semantics remain
separate future checkpoints. No production change followed the tested source.


## M11b planned implementation

Design decisions are recorded in m11-optional-stringizing.md before coding.
Stringized optional operands use presence testing, bounded substitution-only
range cursors and the existing spelling builder, not premature ordinary rescan.
Token pasting remains M11c; no implementation or validation is claimed here.


## M11b tested implementation checkpoint

make test passed, with 564 language + 276 expanded-pp agreement streams under
GCC and Clang. Five inherited whitespace policies and the additional inactive-
argument diagnostic policy are recorded separately, not counted as agreement.
GCC-host QBE/reference execution and separate-object ABI passed, including eight
new optional-stringize/discard programs under LF/CRLF/CR. Unit tests passed exact
32/33 helper nesting, byte-limit error cleanup, definition recovery and original
invocation diagnostics. Both active cursor counters return to zero on errors.
Sanitized fuzzing passed 26326 lexer/preprocessor and 151927 pipeline inputs
(178253 total) in 26 seconds each; arbitrary generated programs were not executed.

The source checkpoint is pushed before the longer full GCC/Clang normal and
ASan/UBSan matrix to protect against sandbox resets. That matrix and exact-
commit CI must be verified separately before marking M11b complete. Token pasting,
other directives and C string expressions remain outside this implementation.


## M11b final verification

The pending full matrix above is complete. GCC 11.5 and Clang 15 each passed
strict normal and ASan/UBSan builds, all unit/CLI/AST/rejection tests, 564 language
plus 276 expanded-pp agreement streams, five separate whitespace-policy groups
and one separate inactive-argument diagnostic policy. QBE/reference execution
and separate-object integer ABI tests passed with both hosts and sanitizer builds.
The eight new optional-stringizing discard programs cover LF/CRLF/lone CR.
Exact 32/33 helper nesting, failed-definition recovery, call-site diagnostics,
owned generated spellings and error-counter/cursor cleanup passed.

Sanitized fuzzing passed 26326 lexer/preprocessor and 151927 pipeline inputs
(178253 total), without executing arbitrary generated code. Source commit
c0928a7 passed GitHub CI:
https://github.com/0x6432/kcc/actions/runs/38766305589
This following documentation-only verification commit has its own exact-commit
CI checked after push. No production change followed the tested source commit.
Temporary push/API credentials were removed and never committed.

M11b is complete for optional stringizing without token pasting. The five
whitespace and one inactive-argument diagnostic disagreements remain explicit
interpretation/conformance audit gaps, not agreement claims. Next M11c needs a
small, reviewed token-pasting design covering raw operands, re-lex validation,
placemarkers and optional-region/operator interactions before implementation.
Includes/conditions, predefined macros, C string expressions and full C23 remain
unfinished. Preserve the exclusive substitution-only range contract when adding
operator phases; do not substitute a full ordinary macro rescan for it.
