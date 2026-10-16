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
| M11 | Includes, conditions, stringizing/token pasting | Include search/provenance, conditional evaluation, expansion tests | complete within recorded M11a–M11m subsets; residual preprocessing audit/encodings/environment tracked in M23–M25 |
| M12 | Integer types/literals/conversions/casts/bitwise | Promotions, signedness, limits and target-model tests | complete within baseline M12a-j integer/character subset; recorded host/sanitizer matrices and exact-source CI passed |
| M13 | Pointers/strings/arrays/subscripts | Declarator/type checks, pointer arithmetic, executable cases | in progress (M13a-k pointers/arrays/subscripts/strings/parameter adjustment and M13l1 fixed ICE bounds and M13m traditional null constants implemented; later verification pending) |
| M14 | Full declarators, typedef scopes, qualifiers, function pointers | Declarator trees and typedef ambiguity cases | in progress (M14a-i and M14j1-j2 const qualification; declarators, lists, incomplete pointers/composites, unnamed definitions, callbacks and void functions; conversion/typedef/qualifier work remains) |
| M15 | Globals/storage/linkage/multiple translation units | Host-link integration, tentative definitions, compatibility | planned |
| M16 | Struct/union/member/layout | Size/alignment/member access, host ABI comparisons | planned |
| M17 | Initializers/designators/compound literals | Nested initialization, zero fill, storage duration | planned |
| M18 | Enums/constant evaluation/assertions/sizeof/alignment | Constraints and unevaluated-expression tests | in progress (M18a fixed sizeof/alignof, M18b1 integer constant evaluation and M18b2 static assertions implemented; enum/alignment work remains) |
| M19 | switch/labels/goto/remaining operators | Branch targets, duplicate labels/cases, sequencing | in progress (M19a comma, M19b conditional and M19c1/c2 prefix/postfix updates and M19d1/d2 all current integer compound assignments implemented; M19e1 named labels and M19e2 direct goto implemented; M19f1/f2 integer switch/case/default implemented; attributes/VLA interactions remain) |
| M20 | Floating arithmetic and ordinary floating types | Conversions/rounding/host ABI; do not fake long double | planned |
| M21 | Variadics and aggregate calls/returns | Mixed arguments, va_list behavior, host ABI interoperability | planned |
| M22 | Bit-fields/flexible arrays/baseline gap audit | Target layout, constraints, remaining C17 feature inventory | planned |
| M23a | C23 keyword changes and boolean constants | Token/declaration/expression constraints | in progress (M23a1 bool/true/false and M23a2 nullptr constant implemented; other changes planned) |
| M23b | C23 integer/literal spelling additions | Binary literals, separators, literal typing | planned |
| M23c | nullptr/nullptr_t | Conversions, comparisons, calls, header exposure | in progress (M23a2 constant/distinct type; source type naming/header exposure remain) |
| M23d | typeof/typeof_unqual | Declarators, qualifiers, evaluation rules | in progress (M23d1 type-name operands; expression operands and declarator normalization remain) |
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


## M11c planned implementation

Design recorded in m11-token-pasting.md before coding: bounded invocation-local
substitution/paste ranges, explicit placemarkers, quiet single-token re-lex and
owned generated spellings. Existing non-paste streaming remains unchanged.
User requested continuous milestone execution with tests/commits/pushes; do not
stop for routine milestone approval. No validation is claimed by this plan.

M11c implementation checkpoint: production token pasting and its bounded range
builder are implemented. Unit/CLI/oracle and GCC-host QBE/reference/ABI tests
passed; GCC and Clang each agree on 564 language + 444 expanded-pp streams.
One C23 normative example and six inherited policy groups are tested separately.
Sanitized fuzzing passed 21801 lexer/preprocessor + 137656 pipeline inputs.
The full four-build host/sanitizer matrix and exact-source remote CI are pending
at this checkpoint; do not confuse this local evidence with completed CI.

M11c final verification: GCC/Clang normal + ASan/UBSan unit/oracle/CLI and
QBE/reference/ABI matrix passed. Commit 66920ed passed GitHub CI run
38773969266. M11d diagnostic directives are next, per the separately recorded
design; subsequent conditionals remain unfinished.

M11d source checkpoint: diagnostic directives pass GCC unit/CLI/oracle and
QBE/reference/ABI tests, plus 104347 sanitized fuzz inputs. Full matrix and
source-commit CI pending. M11e macro-existence conditional design is recorded
before coding, with expression #if/#elif explicitly deferred.

M11d final verification: committed isolated snapshot fce649b passed GCC/Clang
normal and ASan/UBSan tests, QBE/reference execution and integer ABI. Remote CI
run 38803546331 passed. Diagnostic directives are complete for their documented
scope. No full conditional-expression or include support is implied.

M11e source checkpoint: macro-existence conditions and source exclusion pass
GCC tests/QBE/reference/ABI, 321 additional stream agreements with each host,
four independent C23 alternative cases and 167577 corrected sanitizer-fuzz
inputs. A fuzz-found deferred-EOF/parser-success bug is fixed and regressed.
Full isolated matrix and exact-source CI remain pending. M11f signed decimal
#if/#elif expression design is recorded, not yet implemented.

M11e final verification: de93224 passed isolated GCC/Clang normal + ASan/UBSan
matrix, QBE/reference/ABI and remote CI run 38805070048. M11f source checkpoint
passes GCC full tests/runtime/ABI, 540 additional host/model expression streams
with each GCC/Clang, boundary units and 118436 final sanitized fuzz inputs.
M11f full isolated matrix and exact-source CI are pending. M11g remaining signed
operators are designed before coding; unsigned/literal expansion remains later.

M11g source checkpoint: signed shift/bitwise/ternary operators pass GCC full
regressions/QBE/reference/ABI, 642 expression streams with each host, ternary
nesting units and 148738 sanitizer-fuzz inputs. M11f/M11g full isolated matrices
and exact-source CI still pending here. M11h signed literal spelling design is
recorded separately before implementation.

M11f final verification: isolated c52dd27 passed full GCC/Clang normal +
ASan/UBSan and QBE/reference/ABI matrix; remote CI run 38806159321 succeeded.
M11h source checkpoint: signed literal spellings pass GCC full tests/runtime,
94 common literal streams with each host, seven separate C23 separator cases,
and 142694 sanitizer-fuzz inputs. M11g/M11h full validation still pending here.
M11i explicit unsigned preprocessing values are designed before implementation.

M11i source checkpoint: explicit intmax/uintmax values pass GCC full regressions,
QBE/reference/ABI, 302 new host/model value/type checks with each host and
133695 sanitized fuzz inputs. Full isolated matrix/CI remain pending. M11g remote
CI run 38806781592 succeeded; local matrix still pending. M11j character subset
is designed before coding.

M11g final verification: a934115 passed the full isolated GCC/Clang normal and
ASan/UBSan matrix plus QBE/reference/ABI. Remote CI run 38806781592 passed.

M11j source checkpoint: ordinary single-byte preprocessing characters pass GCC
full regressions/QBE/reference/ABI, 126 target host/model checks with each host
and 132477 sanitizer-fuzz inputs. Full isolated matrix/CI pending. M11h source
CI run 38807421895 passed; local verification pending. M11k direct quoted include
design is recorded before coding, including ownership and memory-only fuzz I/O.

M11h/M11i final verification: 26e27e4 and 0e0a0db passed full isolated normal/
sanitizer host matrices plus QBE/reference/ABI. CI runs 38807421895 and
38808207982 passed. M11j source CI run 38809079871 passed; local matrix pending.

M11k source checkpoint: direct quoted includes pass GCC full tests/QBE/reference/
ABI, ten pp agreements with each host, actual byte/path/depth/attempt limits,
retained-source/conditional/EOF regressions and 134920 sanitizer-fuzz inputs.
Full isolated matrix/CI pending. M11l computed quoted operands are pre-designed,
including generated spelling provenance and isolated-line recovery contracts.

M11j final verification: 73b76f8 passed the isolated full normal/sanitizer host
matrix and QBE/reference/ABI. Remote CI run 38809079871 succeeded.

## M11l tested source checkpoint

Macro-computed quoted operands now rescan one bounded isolated directive line.
Relative lookup uses the directive source, not the generated string spelling or
macro definition directory. Invalid expanded operands never consume the next
source line. Directive collectors retain each token's invocation location, so
computed include and conditional macro errors point to the call site.

GCC full tests and QBE/reference/ABI execution passed. Computed include tests
agree with both GCC and Clang on 24 streams each, covering object/function,
stringizing/pasting, empty replacements, all newline forms, source-directory
anchoring and malformed/missing operands. All 24 QBE/reference programs passed.
Sanitized fuzzing passed 22969 lexer/preprocessor and 89116 pipeline inputs
(112085 total), 26 seconds each, without executing arbitrary generated C.
Full isolated M11l normal/sanitizer matrix and exact-source CI remain pending.
M11k exact-source CI passed run 38810635063; its local GCC matrix passed, while
its local Clang matrix is still running. M11m bounded -I/angle search is designed
in m11-include-search.md before implementation. No full C23 claim is made.

## M11k final verification / M11l validation repair

326bcc3 passed both isolated GCC/Clang normal + ASan/UBSan matrices with all
unit/CLI/oracle and QBE/reference/ABI checks. Exact-source CI passed run
38810635063. M11k is complete within its documented scope.

M11l 0ffd06c normal/runtime and fuzz tests passed, but its isolated GCC sanitizer
build failed -Werror=format-overflow in test_computed_include_operands. CI run
38812216340 likewise failed the GCC sanitizer step (fuzz passed, Clang cancelled).
Repair 37857c4 replaces the fixture's sprintf loop with explicitly bounded byte
writes and is pushed. Its isolated full matrix and exact-source CI are pending;
do not claim the original source passed or conflate normal/fuzz with full CI.

M11m source checkpoint: bounded -I/basic angle search passed normal GCC full
regressions/QBE/reference/ABI, GCC ASan/UBSan units, 39 new pp agreements with
each host and 117567 sanitizer-fuzz inputs. Full isolated/remote validation is
pending. M12a signed-int operators are pre-designed; other types remain absent.

M12a source checkpoint: signed-int bitwise/shifts pass full normal GCC
regressions/QBE/reference/ABI, 102 full-value model/host programs with each host,
AST/token/constraint tests and 109107 sanitizer-fuzz inputs. Full isolated/remote
verification remains pending. M11l repair 37857c4 remote CI passed 38812950255;
local GCC passed, local Clang pending. M11m validation remains independent.
M12b shared integer spelling decoding is pre-designed.

## M11l repaired checkpoint final verification

37857c4 passed the full isolated GCC/Clang normal + ASan/UBSan matrix with
unit/CLI/oracle and QBE/reference/ABI execution. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38812950255
M11l is complete within its computed-quoted scope. The original 0ffd06c failure
is preserved above; this success belongs to its explicit fixture repair.
M11m and M12a validation remain separate and pending their own matrix/CI checks.

M12b source checkpoint: shared decoder and runtime four-base/separator subset
passed full normal GCC regressions/QBE/reference/ABI, 90 decoder combinations,
50 GCC host + six legacy model cases, all 56 Clang host/QBE cases and 116884
sanitizer-fuzz inputs. Full isolated/remote checks pending. M11m CI 38813251318
passed; M11m/M12a isolated GCC passed, their Clang verification remains pending.
M12c unsigned int and explicit conversions are pre-designed.

## M11m and M12a final verification

d33f7ae and b80ec53 each passed their full isolated GCC/Clang normal + ASan/UBSan
matrices, including unit/CLI/oracle and QBE/reference/ABI execution. Exact-source
CI passed for M11m run 38813251318 and M12a run 38813971204. Both are complete
within their documented scopes. M12b validation remains independent.

M12c source checkpoint: signed/unsigned int, generic signatures and explicit
conversions passed full normal GCC regressions/QBE/reference/ABI, 130 full-value
model/runtime programs with each host, both separate-object ABI directions,
AST/constraint/depth tests and 109738 sanitizer-fuzz inputs. Full isolated/remote
checks pending. M12b CI 38815061741 passed; local full matrix still running.
M12d explicit casts are pre-designed.

M12d source checkpoint: explicit casts and one-token cast/group disambiguation
passed full normal GCC regressions/QBE/reference/ABI, 71 full-value host/model/
QBE programs with each host, typed AST/depth/constraint tests and 112860
sanitizer-fuzz inputs. Full isolated/remote verification remains pending.
M12e LP64 long/ulong is pre-designed with a successful QBE mechanics probe.

## M12b final verification

98b9a03 passed its isolated GCC/Clang normal + ASan/UBSan matrix, including all
unit/CLI/oracle and QBE/reference/ABI checks. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38815061741
M12b is complete within its recorded spelling scope. M12c/M12d verification
remains separate; do not substitute M12b evidence for those later sources.

M12e source checkpoint: LP64 long/ulong passed full normal GCC regressions/QBE/
reference/ABI, 16 rank pairs/literal/AST tests, 138 full-width host/QBE programs
with each host, both mixed-width separate-object ABI directions and 107062
sanitizer-fuzz inputs. Full isolated/remote validation pending. M12c CI
38816221787 passed; M12c/M12d local GCC passed, remaining verification pending.
M12f distinct long long rank is pre-designed.

M12c final verification: 37d33e9 passed the isolated GCC/Clang normal and
ASan/UBSan matrix plus exact-source CI 38816221787. M12d remote CI passed
38817002032; its local Clang matrix remains pending independently.

M12f source checkpoint: distinct long-long rank and LL/ULL literals passed full
normal GCC regressions/QBE/reference/ABI, 93 new full-value programs with both
hosts, both-direction extended ABI checks and bounded sanitized fuzzing. Full
isolated matrix/exact-source CI remain pending; M12g is pre-designed.

M12d final verification: 66e7c07 passed isolated GCC/Clang normal + ASan/UBSan
and CI 38817002032. M12e CI passed 38818409002; local matrix remains pending.

M12g source checkpoint: ordinary int-valued character constants, shared decoder,
617 byte/escape checks across 44 both-host/QBE programs, full normal GCC suites
and bounded sanitized fuzz passed. Full matrix/exact-source CI remain pending.
M12h distinct char types and promotion/ABI contracts are pre-designed.

M12f exact-source CI passed run 38819398360; its isolated local full matrix
remains queued behind M12e. M12g remote verification remains pending.

M12h source checkpoint: char identities, explicit integer promotions and QBE byte
memory/ABI passed full normal GCC suites, 462 conversion checks across 69 both-
host/QBE programs, cross-host ABI/dirty-return checks and bounded sanitized fuzz.
Full isolated matrix/CI remain pending. M12i short types are pre-designed.

M12e final verification: 609164f passed isolated GCC/Clang normal + ASan/UBSan
plus exact-source CI 38818409002. Later snapshots remain independently pending.

M12g exact-source CI passed run 38820235372; its isolated local verification
remains in progress separately. M12h CI is still running.

M12i source checkpoint: short ranks, promotions and canonical halfword storage/ABI
passed full normal GCC suites, 700 conversion checks across 68 both-host/QBE
programs, separate-object ABI/dirty-return tests and bounded sanitized fuzz.
Full isolated/remote matrix remains pending. M12j _Bool is pre-designed with
a successful both-host QBE mechanics probe; C23 bool/constants remain M23a.

M12h exact-source CI passed run 38821148738. The isolated local matrix is queued
separately, not yet complete. M12i remote verification remains pending.

M12j source checkpoint: _Bool identity, promotions and full-value conversion passed
full normal GCC suites, 418 conversion checks across 36 both-host/QBE programs,
separate-object ABI/dirty-return tests and bounded sanitized fuzz. Full isolated
and exact-source CI remain pending. M12's baseline primitive integer scope is
implemented, not full language conformance. M13a pointer/type syntax is designed.

M12f/M12g final verification: 619ba96/d4db0ef passed isolated GCC/Clang normal +
ASan/UBSan matrices and exact-source CI 38819398360/38820235372. M12i CI passed
38821949608; its isolated local matrix remains in progress separately.

M13a source checkpoint: concrete type syntax and object-pointer declaration
values passed full normal GCC suites, AST/cache/compatibility checks, both-host
live-object ABI/stack arguments, exact 64/65 type bounds, 19 rejection constraints
and bounded sanitized fuzz. Full isolated/remote verification remains pending.
M13b address/indirection and general lvalue-address lowering is pre-designed.

M12j exact-source CI passed run 38822838501. Its isolated local GCC leg passed;
Clang remains in progress. M13a verification remains separate and pending.

M13b source checkpoint: concrete address/indirection and general lvalue-address
lowering passed full normal GCC suites, 53 both-host/QBE full-value programs,
both-direction memory ABI/null cancellation, typed AST/depth checks and bounded
sanitized fuzz. Full isolated/remote checks remain pending. M13c is pre-designed.

M13a exact-source CI b6ba02d passed run 38823808449. M13b 6f5e5ab remains
in progress on run 38824691700; isolated snapshot validation is separate.

M13c source checkpoint: compatible pointer equality passed full normal GCC suites,
15 both-host/QBE full-value programs, both-direction live/null ABI, typed AST,
once-only/short-circuit checks and bounded sanitized fuzz. Full isolated/remote
verification remains pending. M13d scaled arithmetic/ordering is pre-designed.

M12j final verification: 1735825 passed isolated GCC/Clang normal + ASan/UBSan
matrix and exact-source CI 38822838501. Older h/i and later snapshots remain
independently pending; source-specific CI evidence is not interchangeable.

M13d source checkpoint: scaled pointer offsets, signed-long differences and
compatible ordering passed full normal GCC suites, 14 both-host/QBE programs,
13 referent sizes x all integer indices in both ABI directions, typed-tree/depth
and bounded sanitized fuzz checks. Full isolated/remote verification remains
pending. M13e pointer subscripts are designed before implementation.

M12h/M12i final verification: 76944c4/81db52e passed isolated GCC/Clang normal +
ASan/UBSan matrices and exact-source CI 38821148738/38821949608. M13b 6f5e5ab
passed exact-source CI 38824691700. Later snapshots remain independent/pending.

M13e source checkpoint: pointer subscripts passed full normal GCC suites,
15 both-host/QBE full-value programs, all referent/index types in both read/write
ABI directions, chained/postfix/digraph/once-only and typed-depth checks plus
bounded sanitized fuzz. Full isolated/remote checks remain pending. M13f fixed
local arrays and explicit decay/layout contracts are pre-designed.

M13c dfd9742 passed exact-source CI 38825345451. Later snapshots and isolated
matrices remain separate; M13a's local GCC leg passed, Clang remains in progress.

M13f source checkpoint: fixed local arrays and explicit decay passed full normal
GCC suites, 18 both-host/QBE full-value programs, primitive/pointer storage,
both-direction borrowed-array ABI, target layout/compatibility/cache, exact
storage/depth and bounded sanitized fuzz checks. Full isolated/remote verification
remains pending. M13g multidimensional shape composition is pre-designed.

M13d 1435382 passed exact-source CI 38826152470 (both compiler normal/sanitizer
legs and fuzz). Its isolated local matrix remains queued independently. M12a-j
baseline integer subset verification is complete; remaining language areas stay
in their owning milestones, not implied by the M12 status update.

M13g source checkpoint: multidimensional local arrays passed full normal GCC
suites, 15 both-host/QBE full-value programs, primitive/pointer leaves, both ABI
row directions, shape/stride/decay and exact dimension/product/depth checks plus
bounded sanitized fuzz. Full isolated/remote verification remains pending.
M13h ordinary byte strings and static data are pre-designed, with a passed QBE probe.

M13e/f/g 941fad7/fae54eb/e472687 passed exact-source CI 38826762420/38827482501/
38828318658 respectively. M13a b6ba02d passed its complete isolated GCC/Clang
normal/sanitizer matrix plus prior CI 38823808449; later local snapshots queue.

M13h source checkpoint: ordinary static byte strings passed full normal GCC
suites, 12 both-host/QBE programs with 512 byte checks, both-direction/static
multi-object ABI, pure decoder/typed tree/resource checks and bounded sanitizer
fuzz with static object invariants. Full isolated/remote verification remains
pending. M13i adjacent ordinary string concatenation is pre-designed.

M13b 6f5e5ab completed the isolated GCC/Clang normal + ASan/UBSan matrix, with
prior exact-source CI 38824691700. Later local snapshots remain independently queued.

M13i source checkpoint: adjacent ordinary strings passed full normal GCC suites,
15 both-host/QBE programs, both static ABI directions, include/macro provenance,
escape boundaries, typed object and exact resource checks plus bounded sanitized
fuzz. Full isolated/remote verification remains pending. M13j literal-bound
array parameter adjustment is pre-designed with separate declared/effective types.

M13j source checkpoint: literal-bound array parameter adjustment passed full
normal GCC suites, 27 both-host/QBE full-value programs, both eight-argument/row
ABI directions, declared/effective cache and resource units, and bounded sanitized
fuzz. Full isolated/remote verification remains pending. M13k omitted outer
parameter bounds is designed with explicit incomplete declared-type metadata.

M13k source checkpoint: omitted outer parameter bounds passed full normal GCC
suites, 27 both-host/QBE programs, both stack/row ABI directions, incomplete
declared versus effective pointer units, exact budgets and bounded sanitized
fuzz. Full isolated/remote checks remain pending. M14a parenthesized object
declarators are designed; this does not mark remaining M13 null/void/general
bound support complete. M13c dfd9742 completed its isolated GCC/Clang normal +
ASan/UBSan matrix, with prior exact-source CI 38825345451.

M14a source checkpoint: single-pass parenthesized object/abstract declarators
passed full normal GCC suites, 20 both-host/QBE programs, all primitive row ABI
directions, mixed eight-argument ABI, exact syntax/cache/shape and global
declarator resource checks plus bounded sanitized fuzz. Full isolated/remote
checks remain pending. M14b incomplete object pointers and recursive composite
function redeclarations are designed before implementation. M13i 5699450 passed
exact-source CI 38830826668; later source runs remain independent.

M14b source checkpoint: incomplete array pointers and recursive composite
redeclarations passed full normal GCC suites, 19 both-host/QBE programs, all-
primitive row/eight-argument ABI directions, null address cancellation and typed
cache/composite/complete-object units plus bounded sanitized fuzz. Full isolated/
remote checks remain pending. M14c local declaration lists are pre-designed.
M13j d0fc412 passed exact-source CI 38831621684; later source runs are separate.

M14c source checkpoint: comma-separated local/for declarations passed full normal
GCC suites, 23 both-host/QBE programs, both all-primitive ABI directions, shared-
base/independent-chain and scope units, exact item/local/storage budgets and
bounded sanitizer fuzz. Full isolated/remote checks remain pending. M14d C23
unnamed definition parameters are designed with unchanged positional ABI.
M13k 7fa1cf3 passed exact-source CI 38832092805; later runs remain separate.

M14d source checkpoint: C23 unnamed definition parameters passed full normal GCC
suites, 17 both-host/QBE programs, both all-primitive register/stack and mixed
full-width ABI directions, caller side effects, no-fake-binding/spill units and
exact parameter/storage budgets plus bounded sanitizer fuzz. Full isolated/
remote checks remain pending. M14e fixed-function declarator syntax is designed.
M14a c10fa56 passed exact-source CI 38832685806. M13d 1435382 completed its
isolated GCC/Clang normal + ASan/UBSan matrix, with prior CI 38826152470.

M14e source checkpoint: concrete fixed-function declarators passed full normal
GCC suites, 21 both-host/QBE programs, both all-primitive row-return ABI directions,
syntax/cache/composite/view units, exact function/nested-type budgets and bounded
sanitizer fuzz. Full isolated/remote checks remain pending. M14f function
designators/pointers and indirect fixed calls are designed. M14b 1bfd4a9 passed
exact-source CI 38833251538; later source runs remain separate.

## M14f tested source checkpoint

Full GCC regression/QBE suites passed, with 22 targeted runtime programs under
both GCC and Clang. Callback/factory ABI checks cover both linkage directions
for all primitive/pointer leaves, mixed eight-argument stack ABI, six dirty
narrow-return assembly stubs, null &* cancellation and exact typed call depth.
Bounded sanitized fuzz passed 23,769 lexer and 68,371 pipeline runs (26 seconds
each); arbitrary fuzz programs were never executed. The existing integer-call
negative now expects the more precise not-a-function-pointer diagnostic.
Full isolated matrices and exact-source remote CI remain pending for this
checkpoint. Next M14g void types/functions/discards is designed in
m14-void-functions.md. Function pointer design is m14-function-pointer-values.md.

## M14g tested source checkpoint

Full GCC normal regression and QBE suites passed. Targeted GCC and Clang checks
cover 16 full-value programs, 28 primitive/pointer callback ABI combinations in
both linkage directions, mixed register/stack ABI, result-free QBE IL, host-null
&* cancellation, nonnull void-indirection effects, exact expression depth and
52 invalid constraints. Semantic units inspect void syntax/cache/category, no
void spills/loads, optional return AST values and indirect void calls.

Bounded sanitized fuzz completed 24,479 lexer and 70,044 pipeline inputs in
26 seconds per harness without reported failures; generated C was not executed.
The obsolete void-pointer-prototype rejection was replaced with an invalid named
void parameter. Test-only fixes use normalized bool expectations and the exact
64-bit mixed-argument sum. Full isolated and exact-source remote checks for this
checkpoint remain pending; do not infer them from older commits.

M13e's independent GCC/Clang normal + ASan/UBSan matrix passed. Later matrices
remain separately queued/running. M14h object/void conversions and mixed equality
are designed before implementation in m14-object-void-conversions.md.

## M14h tested source checkpoint

Full normal GCC regression and QBE suites passed. New GCC/Clang tests cover
21 full-value programs, all primitive object round trips, both cross-object ABI
directions, arrays/incomplete array shapes, pointer-to-pointer and function-
pointer objects, null conversions supplied by the host, once-only equality
effects, exact conversion-depth limits and 24 invalid constraints. Typed units
check explicit conversion nodes, mixed-equality normalization in both orders
and unchanged type compatibility. A strengthened mixed register/stack fixture
uses seven distinct live objects and an observable full-width tail; it passed
both hosts after the full suite, avoiding an unobservable same-pointer fallback.

Bounded ASan/UBSan fuzz completed 21,170 lexer and 63,070 pipeline inputs in
26 seconds per harness, without reported errors or execution of generated C.
Full isolated and exact-source remote checks for this checkpoint remain pending.
M14i explicit object/function pointer casts is designed before implementation.

The sandbox restart removed Clang and interrupted older isolated jobs. Clang
and compiler-rt were restored; unfinished immutable snapshot matrices were
requeued under the same external lock, preserving old logs and recording new
results in /data/tools/*-resumed-validation.log. The active M14g matrix is
independent. All remote checkpoints remain exact-source, not inferred.

## M14i tested source checkpoint

Full GCC normal regression and QBE suites passed. Targeted GCC and Clang checks
cover 31 full-value programs, every primitive object's character-pointer round
trip, defined byte-representation access, complete/incomplete arrays, nested
pointer objects, both primitive/function ABI linkage directions, mixed stack
callbacks, host-supplied object/function null pointers, once-only effects, exact
typed depth and 21 constraints. Function casts are restored to compatible
signatures before calls. Typed units preserve real cast syntax/cache/types,
incompatibility and depth rather than weakening implicit conversions.

Bounded ASan/UBSan fuzz completed 22,538 lexer and 69,788 pipeline inputs in
26 seconds each without reported failures; generated C was never executed.
Old explicit object-cast rejections were migrated to unchanged implicit
constraints; nested pointer implicit conversions still reject. Full isolated
and exact-source remote checks remain pending for this source. M19a comma
expressions are designed before implementation and brought forward because
they exercise M14g discard paths and declaration/call separator boundaries.
M14 qualifiers/typedefs and the rest of M19 remain incomplete.

## M19a tested source checkpoint

Full GCC normal regression and QBE suites passed. Targeted GCC and Clang checks
cover 35 full-value programs, scalar/void/pointer/function result sequencing,
short-circuit branch merges, loop/return/subscript full expressions, call and
declaration separator ownership, 28 primitive/pointer ABI combinations in both
linkage directions, exact typed-depth limits and 16 invalid constraints.
Typed units inspect concrete comma children, loads/decay, void/no-lvalue results,
left association and unchanged call argument count. Three obsolete now-valid
negative fixtures were migrated to real arity, missing-operand and void-scalar
constraints; their original valid shapes also have positive coverage.

Bounded ASan/UBSan fuzz completed 23,675 lexer and 71,371 pipeline inputs in
26 seconds per harness without reported failures; generated C was not executed.
Full isolated and exact-source remote checks for this source remain pending.
Exact-source M14g 592b551 CI run 38859101528 passed; M14h 274d966 run
38859812046 and M14i 1ed1cc8 run 38860337750 were still running when checked.
The immutable M14g GCC normal/ASan/UBSan matrix passed; its Clang half and other
queued matrices remain separate checks, not inferred successes.

Next M14j const is designed in m14-const-qualification.md. Implement immutable
qualification, strict versus root-unqualified compatibility and qualified
composites as M14j1, then parsing/value conversions and enforcement as M14j2.
No const syntax is claimed until the latter passes its language tests.

## M14j1 tested source checkpoint

Implemented immutable type qualification/unqualification, qualification-aware
strict/root-only compatibility and qualifier-preserving composites. All primitive
leaves and void, independent pointer levels, function referents, const pointer
arrays versus pointers to const elements, nested C23 arrays, unknown/known-bound
composites and 64-layer graphs have dedicated unit checks. Input graphs and
singletons remain unchanged; no-op operations share existing nodes. Layout/ABI
helpers retain their kind-based representation behavior.

Full normal GCC regression and QBE suites passed. The new type-unit executable
passed GCC and Clang ASan/UBSan directly and is part of make test and CI matrices.
Bounded sanitized fuzz completed 19,665 lexer and 54,466 pipeline inputs in
26 seconds each without reported errors; no generated C was executed. These
harnesses do not yet construct qualified types through source syntax: M14j2 is
next. Exact-source remote and full isolated checks for M14j1 remain pending.

The independent M14g full GCC/Clang normal + ASan/UBSan matrix now passed both
halves. Other queued matrices remain separate; do not infer newer-source results.

## M14j2 tested source checkpoint

Const builtin/star syntax uses a separate concrete qualified syntax node and
immutable semantic caches. Value loads, initializers, casts and function return/
parameter signatures unqualify only the required level; local parameter objects
retain const. Pointer conversions add only immediate qualifiers; comparison
common types preserve qualification, arrays and depth, while pointer differences
keep both completeness guards. QBE representation needs no qualifier shortcut.

Full normal GCC regression and QBE suites passed. Targeted GCC/Clang tests cover
39 original kcc full-value programs, 48 primitive/object ABI arrangements, mixed
register/stack, callbacks and native-null ABI in both directions, nested array
shapes, defined explicit qualification removal, once-only effects, 64/65 pointer
and exact typed conversion/promotion depth boundaries, and 40 constraints.
GCC gives 39 native runtime agreements. Clang 15 gives 36 and three narrowly
recorded C23 6.7.6.3p4 return-qualification diagnostic gaps; all 39 original kcc
programs still execute with QBE. Semantic units inspect concrete syntax/cache,
qualified parameter locals versus unqualified signatures, const pointee loads,
explicit conversions and unknown array parameter shapes. Both GCC and Clang
ASan/UBSan semantic-unit executables passed.

Bounded sanitized fuzz completed 23,480 lexer and 62,518 pipeline inputs in
26 seconds each without reported failures; generated C was never executed.
One old int *const function-prototype rejection is now a real const parameter
assignment constraint. Full regression restarted after that fixture migration.
A test-construction insertion/field-name mistake was corrected before the full
validation; it was not a compiler finding. Exact-source remote/full isolated
checks for this source remain pending.

Exact-source CI now passed M19a 95a99d7 run 38861248497, M14i 1ed1cc8 run
38860337750 and M14h 274d966 run 38859812046. M14j1 6e7ff50 run 38861821792
was still running at the latest check. M14g's full isolated GCC/Clang normal and
ASan/UBSan matrix passed. Do not infer other queued-source outcomes.

Next independent M23a1 bool/true/false keywords and typed boolean constants are
designed in m23-boolean-keywords.md, retaining the existing C23 pp true rule.
This does not finish M14 other qualifiers/typedefs or M23a's remaining keywords.

## M23a1 tested source checkpoint

C23 bool/true/false tokens, a separate concrete boolean constant AST and shared
_Bool semantics/codegen are implemented. Macro expansion stays before keyword
conversion and preprocessing true/false remains separate from language constants.
Full normal GCC regression and QBE suites passed. Both-host targeted checks
cover 32 original programs, 22 constraints, exact bool promotion depth, 26
cross-object ABI arrangements, mixed register/stack/callbacks and dirty narrow
returns. GCC 11 compatibility oracles are explicitly labelled; Clang 15 gives
native C23 keyword/type agreements. Three preprocessing defined/undef programs
are QBE-tested unchanged and only native hosts serve as their reference oracle.
Both GCC/Clang ASan/UBSan semantic units passed. Fuzz totals are recorded below;
no generated C was executed. Exact-source remote/full isolated checks are pending.

M14j1 6e7ff50 CI run 38861821792 passed. M14j2 b26ff3b CI run 38863255999
was still running at the latest check. Results are source-specific.
Next: M19b conditional expressions, with the design recorded before editing.
M14 remaining qualifiers/typedefs and M23a remaining keywords stay unfinished.

M23a1 bounded sanitized fuzz: 23,176 lexer and 68,839 pipeline inputs in
26 seconds each, without reported failures. Generated C was never executed.

## M19b tested source checkpoint

Concrete conditional AST/parser/sema/codegen now implement selected scalar/void
branches and qualified/composite pointer results. The Pratt table keeps comma,
assignment and conditional contexts distinct; the middle accepts full expressions
and the final operand associates right. All operands are checked semantically.
Known/unknown array bounds compose without changing parameter type snapshots.
Comparison and conditional common-pointer construction share one checked helper.

Full normal GCC regression and QBE suites passed. Targeted both-host tests cover
50 original programs, 288 pairwise sign/rank checks, typed units for all 144
integer pairs, 17 constraints, exact syntax and inserted-conversion depths,
24 primitive ABI arrangements, host-native null pointer conditions and dirty
narrow returns. GCC gives 50 native runtime agreements; Clang 15 gives 48 and
two exact C23 array-qualification diagnostic gaps. Every original kcc program
still executes with QBE. Both GCC/Clang ASan/UBSan semantic units passed.
A test expectation initially missed the existing explicit cast's depth; the
final exact typed boundary uses a real bool leaf and promotion. No compiler
failure was hidden by a host-source rewrite. Bounded sanitized fuzz totals follow;
no generated C was executed. Remote/full isolated checks remain pending.

Next independent M18a fixed sizeof/alignof is designed in m18-sizeof-alignment.md.
No VLA/constant evaluator, null constant or full M18/M19 conformance is implied.

M19b bounded sanitized fuzz: 23,373 lexer and 68,010 pipeline inputs in
26 seconds each without reported failures; generated C was never executed.

## M18a tested source checkpoint

Separate concrete sizeof-expression, sizeof-type and alignof ASTs preserve typed
operands/syntax. Parser disambiguates type versus expression with one on-demand
token and retains postfix binding inside sizeof operands. Sema suppresses only
root load/decay, checks complete object layout and emits unsigned-long constants.
Codegen never evaluates operands, including calls, writes and invalid-at-runtime
addresses. Unknown arrays/functions/void remain constraints, not GNU size extensions.

Full normal GCC regression and QBE suites passed. Both-host targeted tests cover
33 original full-value programs, 19 constraints, exact unevaluated structural
depths, all primitive/pointer/array/const layouts, adjusted parameters, embedded
NUL/concatenated strings, bool conditional promotion, unevaluated uninitialized
reads/calls/stores/out-of-range addresses and no unresolved-symbol references.
24 unsigned-long ABI arrangements and native-null unevaluated pointer operands
pass. GCC 11/Clang 15 alignof spelling checks use explicitly labelled _Alignof
compatibility macros; original kcc programs are unchanged. Both GCC/Clang
ASan/UBSan semantic units passed. Sanitized bounded fuzz totals follow; no
fuzz-generated C was executed. Exact-source remote/full isolated checks pending.

Next: M18b1 pure integer constant-evaluation foundation, designed in
m18-integer-constant-evaluation.md before implementation. Source-level constant
requirements, generalized array bounds and null conversions are later consumers.

M18a bounded sanitized fuzz: 23,465 lexer and 66,857 pipeline inputs in
26 seconds each without reported failures; generated C was never executed.
Exact-source M14j2 b26ff3b CI run 38863255999 passed. M23a1 fe26eb4 run
38864340577 and M19b 0c0ef33 run 38865164586 were still running.

## M18b1 tested source checkpoint

Added a pure consteval.c stage over checked bounded integer ASTs. Results preserve
canonical target bits/type/location or distinguish nonconstant forms from invalid
arithmetic. Portable checked operations never depend on signed host overflow,
negative signed shifts or large unsigned-to-signed casts. Short-circuit arms are
form-checked without arithmetic, and comma is allowed only when unevaluated.
sizeof/alignof are opaque typed leaves; queries do not emit diagnostics, mutate
ASTs, allocate or change runtime compilation acceptance.

Full normal GCC regression and QBE suites passed. Both GCC/Clang native oracles
agree on 958 curated strict ICE forms/values, with six C23 boolean queries,
34 nonexecuted invalid-arithmetic cases, 19 nonconstant forms and eight strict
native form rejections. Both-host ASan/UBSan evaluator oracles passed the same
checks. One exploratory predefined-macro test correctly exposed that __STDC__
is not yet provided; it was not disguised as a supported feature. Fuzz now queries
checked expression/initializer/return roots without executing generated C.
Bounded fuzz totals follow. Full isolated/remote exact-source checks are pending.

This is a shared foundation, not new declaration acceptance. Static assertions,
enums/constexpr, constant array bounds and null pointer constants are not yet
consumers. Next: M18b2 static assertions, designed in m18-static-assertions.md.

M18b1 bounded sanitized fuzz: 23,575 lexer and 64,254 pipeline inputs in
26 seconds each, without reported failures. Generated C was never executed.
Exact-source M23a1 fe26eb4 CI run 38864340577 passed; M19b/M18a were still running.

## M18b2 tested source checkpoint

static_assert and _Static_assert are on-demand post-pp keywords and concrete
assertion declarations with separate external/block wrappers. Parser accepts
conditional-expression and optional concatenated ordinary-string messages.
Sema checks all source-order scopes/unreachable items and consumes the pure ICE
query, preserving located invalid-arithmetic versus nonconstant diagnostics.
False values include quoted messages with all control/NUL/high bytes escaped,
never printf-interpreted. Messages allocate no local slots or QBE static objects;
successful assertions emit no runtime code, even in for initializers.

A standards audit corrected an initial design assumption: N3096 declarations
include static assertions in for clause-1. GCC 11 accepts them; Clang 15 rejects
with its exact identifier/parser diagnostic. Tests follow the draft and record
the host gap instead of rewriting the original source. Both hosts lack the C23
static_assert spelling and receive labelled _Static_assert oracle macros only.
Raw pp defined/undef behavior is checked on the original kcc program; legacy
host keyword-macro differences are not claimed as native agreements.

Full normal GCC regression and QBE suites passed. Targeted both-host tests cover
26 original QBE programs, 25 GCC and 24 Clang strict native runtime agreements,
39 constraints, four strict native ICE rejections, every diagnostic byte, message
concatenation/NUL/provenance, AST/scope/no-allocation invariants and exact syntax/
typed/item/external/message length/fragment limits. Both-host ASan/UBSan semantic
units and complete targeted assertion suites passed. Initial tests needed fixes
for the existing reverse local list, native diagnostic wording, unary '+' token
separation and trailing newlines in strict host feature probes; no compiler
failure was hidden. Bounded fuzz totals follow; no generated C was executed.
Full isolated/remote exact-source checks remain pending.

Next: M13l1 fixed ICE array bounds, designed in m13-constant-array-bounds.md.
Enums/constexpr/floating ICE casts, VLA, typedef/aggregates, null constants and
initializer/optimizer consumers remain unfinished.

M18b2 bounded sanitized fuzz: 21,256 lexer and 59,937 pipeline inputs in
26 seconds each, without reported failures. Generated C was never executed.
Exact-source M19b 0c0ef33 CI run 38865164586 and M18a ea59892 run
38865929894 passed. M18b1 5b71941 run 38866954105 remained in progress.

## M13l1 tested source checkpoint

Array syntax now retains an optional bound expression AST (NULL for unspecified)
instead of duplicate token/has_bound fields. On-demand Pratt assignment-expression
parsing feeds normal sema and the pure ICE query; signedness-aware positivity,
overflow-safe per-type bounds and aggregate local-storage limits are enforced.
No VLA/runtime bound or global folding is implied. Bounds emit no evaluations.

Function-type resolution now creates/restores ephemeral prototype scopes, resolves
parameters left-to-right and binds adjusted names only after their declarators.
Type-only name bindings consume no runtime slots/list entries; real definition
parameter locals remain separate. Nested callbacks, own-name outer lookup and
scope restoration are typed-tested. A pre-implementation host probe corrected a
return-scope assumption: parameters are not visible in trailing derived return
syntax, so return types continue resolving before entering the prototype scope.

Full normal GCC regression and QBE suites passed. Both-host targeted tests cover
31 original strict native/QBE programs, 34 constraints, 24 adjusted-array ABI
arrangements, exact syntax/typed/cross-type recursion and compile-only storage
boundaries. Both-host ASan/UBSan semantic units and targeted bound suites passed.
The cross-type recursion boundary is the existing 64 nested declarator edges,
not 128 independent expression nodes. Tests replace obsolete [true], [sizeof],
[1+2] rejections with variable-length/unparenthesized-comma cases; unsupported
static bracket diagnostic expectations now reflect expression parsing. No
rejection coverage was silently removed. Initial tests also corrected existing
local-object-storage wording. Bounded fuzz totals follow; generated C was never
executed. Full isolated/remote exact-source checks remain pending.

Next: M13m traditional null pointer constants, designed in
m13-null-pointer-constants.md. C23 nullptr/nullptr_t, VLA, typedef/qualifiers,
enums/constexpr and other constant consumers remain later work.

CI correction preceding this checkpoint: cade2cd's Clang CI run 38868636910
failed because the native host applies an unevaluated-string numeric-escape
restriction to a valid C23 assertion message. N3096 6.4.5/6.7.11 were rechecked;
kcc's acceptance and every diagnostic-byte test remain unchanged. Correction
5ce95d6 recognizes only that exact single-error host diagnostic for the original
numeric-message program, does not count it as a native agreement, and still
runs the original through kcc/QBE. Other native failures remain fatal. Both
local host assertion/QBE suites passed the correction. Remote CI is pending;
do not call the failed earlier checkpoint green. M18b1 5b71941 CI run
38866954105 did pass. A sandbox reset erased installed Clang and queued process
handles; Clang/compiler-rt were reinstalled. Old matrix source archives/logs
remain, but pending jobs are not claimed as successful.

M13l1 final post-reset full normal regression and QBE suites passed again;
bounded sanitized fuzz ran 22,845 lexer and 61,791 pipeline inputs in 26 seconds
each. Both-host focused ASan/
UBSan semantic, bound and assertion suites also passed with QBE runtime/ABI.
No fuzz-generated C was executed. Version-only driver change was rebuilt/smoke
checked after these suites. Remote/full isolated matrix status remains separate.
The first native-oracle correction's remote Clang job progressed to the separate
keyword-macro warning policy; a second exact-diagnostic/same-source warning
control fixes that test, documented in m18-static-assertions.md. Neither compiler
language acceptance nor warning policy for other tests was weakened.

## M13m traditional null pointer constants

Sema recognizes checked integer constant expressions with value zero, and
explicit casts of those expressions to unqualified void *. A zero-valued local,
assignment/comma result, arbitrary pointer, typed int * null value or pointer
conditional result does not gain null-constant status. Invalid constant arithmetic
is not proof of zero. C23 nullptr/nullptr_t remain a separate next milestone.

Assignment-like conversions (initialization/assignment/call/return), explicit
pointer casts, equality in both orders and conditional arms share the predicate.
Equality handles null constants before compatible/common pointer types; relational
comparisons still reject pointer/integer zero. Conditional arms select the exact
other pointer type before the object/void common-type rule, preserving qualified
objects, functions and incomplete-array pointers. Pointer+0 remains ordinary
pointer offset arithmetic, not a null conversion. Function/object bridges and
nonzero integer/pointer casts stay unsupported; the latter are implementation
limits, not claimed C constraints. Pointer-to-bool conversion remains available.

Existing concrete conversion/cast ASTs retain original operands, source locations,
resolved types and depth checks. No token vectors, synthetic literal rewrites,
extra local slots, global folding or runtime ABI adapters were added. Existing
QBE integer extension/copy lowering was audited: this amd64 LP64 target uses
all-zero 64-bit null pointers for implemented object/function pointer types.
That is an explicit target representation choice, not a portable C assumption.

Both-host focused tests cover 37 original curated programs, 36 strict GCC and 37
strict Clang native agreements, 25 compile-only constraints/implementation limits,
11 strict native constraint rejections, concrete AST/type/slot/depth invariants
and 24 mixed-register/stack/callback cross-object ABI arrangements. Once-only
non-null effects and selected conditional arms are checked without null calls,
dereferences, arithmetic or incompatible calls. Existing obsolete zero-rejection
fixtures were replaced with nonzero forms, not dropped. The ABI failure path uses
a live caller-owned sentinel, so an argument mismatch cannot accidentally return
null and pass. Both-host ASan/UBSan semantic/targeted results and full regression/
fuzz outcomes follow once complete; no generated fuzz C is ever executed.

A native-oracle audit found GCC 11 rejects a zero _Bool ICE in initialization,
assignment and return, despite C23 6.3.2.3/6.6 permitting it. Clang accepts the
same original program. Tests recognize only those three exact GCC errors, keep
the original kcc/QBE run, report the gap and do not count a native agreement.
An early test-generation failure was a missing parenthesis around interpolated
conditional zero forms; grouping was fixed, not compiler precedence. Strict
native rejection tests explicitly exclude legal-but-unimplemented cast forms.

M13m final validation: full normal regression and QBE suites passed. Both-host
ASan/UBSan semantic units and final targeted null suites passed, including the
extra original C23 false-leaf QBE program and its exact typed conversion unit.
Bounded sanitized fuzz ran 22,403 lexer and 63,128 pipeline inputs in
26/26 seconds without reported failures; generated C was never executed.
The full-suite audit found two additional obsolete zero/false rejections in void
function and boolean tests. Both were replaced with nonzero/true cases, retaining
constraint coverage, then the entire regression/QBE/fuzz chain was rerun.
No partial early run was called a full pass. Full isolated and remote exact-source
checks for this checkpoint are pending. Next: M23a2 nullptr constant with its own
scalar type, designed before implementation in m23-nullptr-constant.md.

## M23a2 distinct nullptr constant

Implemented the prewritten m23-nullptr-constant.md design with a concrete leaf
AST, post-pp keyword and distinct complete scalar type. Sema separates constants
from arbitrary nullptr_t values, inserts explicit pointer/bool conversions and
normalizes equality without changing original typed operands. Pointer/nullptr
conditional arms preserve the exact pointer type; two nullptr_t arms retain that
type. nullptr versus integer zero is invalid in conditional arms even though
equality permits it. Arithmetic/relational/non-bool integer conversions reject it.
QBE emits a 64-bit zero leaf; sizeof is an opaque unsigned-long ICE of value 8.
No nullptr_t keyword, typedef, header or declaration inference was invented.

Both local hosts pass 35 original programs through QBE, 26 compile-only
constraints, three raw-pp programs, 26 both-direction stack/callback pointer ABI
arrangements and exact typed depths. Native GCC 11/Clang 15 lack nullptr: probes
report this explicitly and never macro-rewrite original source as type evidence.
Native helpers alone use separately written traditional zero forms. Type, lexer
and sema units preserve qualifications, operand identities, depth and local slots.
Both-host ASan/UBSan targeted units/runtime/ABI passed. Full regression/fuzz and
remote results are recorded below only when complete.

Test construction corrections: a reserved-name diagnostic is "expected local
name"; right-nested parenthesized comma fixtures hit parser nesting rather than
typed depth, so flat left-associated commas isolate the conversion boundary.
Traditional native ABI helpers require (void *)0, not a non-ICE (0,0) argument.
None of these fixture corrections changed compiler semantics or native evidence.

Next: M19c1 prefix updates, designed before implementation in
m19-prefix-updates.md; M19c2 postfix follows separately. Full C23 remains incomplete.

Exact-source prior remote CI: M13l1 6ce8f52 run 38877765103 passed GCC, Clang,
normal/QBE/ASan/UBSan and fuzz jobs. M13m e06a497 run 38879492736 is still running.

M23a2 final local validation: full normal regression and QBE suites passed. Both-host
ASan/UBSan type/lexer/sema units and final targeted runtime/ABI passed. Bounded
sanitized fuzz ran 22,463 lexer and 54,705 pipeline inputs in
26/26 seconds with no reported failures. No generated C was executed.
Remote exact-source and full isolated matrix checks remain separate/pending.

## M23a2 native constant-form oracle correction

Exact-source addce68 CI run 38881054180 passed fuzz but failed the modern GCC
native rejection oracle for `int *p=nullptr?0:0;`. Clang was cancelled by matrix
fail-fast, not a compiler failure. N3096 6.6p8 only admits integer/arithmetic
constant operands in integer ICEs; nullptr_t is neither. Paragraph 14 allows
additional constant forms without making them integer ICEs. Preserve kcc's
form rejection and record host acceptance separately for exactly three named
nullptr-derived constant forms (that conditional and two static assertions).
All other native constraints must still reject; all 26 kcc rejections remain
mandatory. Do not change nullptr into arithmetic zero or relax general null
constant classification to match host folding. Extra host forms are never
counted as strict constraint agreements. Legacy hosts never run this branch.

## M19c1 prefix update expressions

Concrete prefix update ASTs retain one lvalue subtree plus operation, promoted
calculation type and pointer stride. Sema suppresses the operand root load,
requires modifiable integer/complete-object pointer lvalues, preserves referent
const and rejects const objects, arrays, functions and nullptr_t. Result types
are unqualified stored types, not promoted arithmetic types; results are not
lvalues. QBE computes the address once, loads, updates, converts back and stores
once. Boolean conversion tests the whole promoted result (not its low bit).
sizeof checks constraints but emits no update; consteval rejects update forms.

Both hosts pass 36 strict native original programs through QBE, 15 strict native
constraint rejections, the nullptr constraint and explicit VLA subset limit,
exact depth and 24 both-direction mixed-stack/narrow-result ABI arrangements.
Units retain operand identity, root lvalue, source location, qualifiers, stride,
calculation/result types and depth. Longest-match ++/-- token tests distinguish
spaced unary operators and token-pasting without changing raw preprocessing.
The first test run misclassified a legal VLA bound as a native constraint; it is
now separately labelled as kcc's runtime-bound implementation limit. No compiler
rule changed to force native rejection. Full regression/fuzz results follow.
Next: M19c2 postfix updates, predesigned in m19-postfix-updates.md.

M19c1 final local validation: complete normal regression and QBE suites passed.
Both-host ASan/UBSan lexer/sema units and targeted runtime/24 ABI arrangements
passed. Sanitized bounded fuzz ran 22,752 lexer and 58,812
pipeline inputs in 26/26 seconds with no reported failure.
No generated fuzz C or constraint-invalid/undefined curated source was executed.
CI now keeps both compiler matrix jobs running after either fails, so host
oracle/implementation failures do not hide the other compiler's evidence.
Prior M13l1 isolated GCC/Clang normal+ASan/UBSan full matrices passed. M13m
e06a497 remote run 38879492736 also passed every job. The nullptr oracle fix
f3df148 run 38881463571 is still running; GCC passed normal tests and reached QBE.
M19c1 isolated/remote checks are queued/pending, not claimed passed.

## M19c2 postfix update expressions

Separate concrete postfix nodes use the existing ++/-- tokens and iterative
call/subscript suffix parser. Shared semantic checking retains one operand
lvalue, calculation type and complete-pointer stride; both result types are
unqualified/non-lvalue. A backend-only previous/current pair shares the single
address/load/arithmetic/back-conversion/store path: prefix selects current and
postfix selects previous. No generic AST payload or assignment duplication was
introduced. Existing prefix tests are rerun after this factoring.

Both hosts pass 39 strict-native original postfix programs, 18 native constraint
rejections, explicit nullptr/VLA-subset/compile-only-null-update checks, exact
depth and 48 both-direction narrow/pointer-return/mixed-stack ABI arrangements.
Tests distinguish *p++/(*p)++/p++[0]/a[i++]++, verify bool/narrow/unsigned wrap,
short-circuit/conditional/comma/sizeof and loops. No unsequenced conflicting
read/write or out-of-array/null update is executed. Concrete AST units retain
operand identity, types, qualifiers, location, operation and depth. Both-host
ASan/UBSan semantic units and prefix/postfix runtime/ABI passed. Full regression
and fuzz results follow once complete. The obsolete i++ for-header negative is
now an undefined-name j++ case, retaining loop diagnostic coverage.
Next: M19d1 +=/-=, predesigned in m19-additive-assignment.md.

M19c2 final local validation: complete normal regression and QBE suites passed.
Both-host ASan/UBSan semantic units and prefix/postfix runtime/ABI passed.
Sanitized bounded fuzz completed 23,138 lexer and 50,219 pipeline inputs in
26 seconds each without reported failure. No generated C was executed.
Full isolated matrix and remote CI are queued separately, not claimed passed.

## M19d1 additive compound assignment

Implemented +=/-= with demand post-pp tokens, right-associative assignment Pratt
powers and a concrete compound AST, never assignment expansion. Sema preserves
the modifiable left lvalue, explicitly converts RHS, records usual calculation
type/complete-object pointer stride, and yields the unqualified stored type.
Backend value conversions are factored from expression conversions so the old
load and result share ordinary extension/narrow/bool semantics without repeated
addresses. Pointer offsets reuse signedness-aware scaling. Unevaluated sizeof
still validates constraints; consteval rejects evaluated updates.

The first conditional fixture omitted required parentheses around an assignment
in the last arm; corrected the fixture, not compiler precedence or constraints.
Target/full/sanitizer/fuzz results follow once validated.

An obsolete += rejection in the broad compiler suite is now an undefined-RHS
name rejection; the semantic positive suite covers the newly valid syntax.
The compound static-assert negative is parenthesized to satisfy its conditional
expression grammar before testing the ICE restriction. Both were test-fixture
repairs, not relaxed compiler semantics. Next: M19d2, predesigned in
m19-integer-compound-assignment.md.

M19d1 targeted evidence: both hosts passed 59 strict-native original programs,
19 strict-native constraint rejections and 48 both-direction narrow/pointer-return
mixed-stack ABI arrangements. Separate nullptr constraints, VLA subset limit,
compile-only null-pointer update and exact typed-depth boundary passed. Semantic
units preserve original left/right identity, location, stored/calculation types,
referent const, explicit bool-index promotion and pointer stride. Both-host
ASan/UBSan lexer/sema plus additive/prefix/postfix runtime/ABI suites passed.
An initial sanitizer orchestration attempted Clang before its binaries existed;
after building them its complete stage passed; no compiler source change was
needed. Full normal/QBE/fuzz remain pending until final markers.

M19d1 final local validation: complete normal regression and QBE suites passed.
Both-host targeted ASan/UBSan lexer/sema and additive/prefix/postfix runtime/ABI
passed. Bounded sanitized fuzz completed 22,986 lexer and 60,623 pipeline inputs
in 26 seconds each without reported failure. No generated C or curated runtime
invalid arithmetic/pointer source was executed. Remote/isolated full matrices
are queued separately. Prior f3df148 CI run 38881463571 passed every job.

## M19d2 remaining integer compound assignment

Added demand post-pp tokens/Pratt assignment operators and extended the concrete
compound node, preserving one left lvalue and one RHS. Integer shifts promote
operands independently; other operators use usual arithmetic calculation types.
Only +=/-= permit pointer left operands. Shared signedness-aware integer
instruction selection and QBE word shift-count normalization avoid duplicated
lowering rules. Stored result back-conversion and checked/unevaluated sizeof
reuse M19d1 semantics. No generic AST, assignment expansion or folding shortcut.

Both native hosts pass 127 strict-native original programs, 43 native constraint
rejections, separate nullptr/VLA-subset checks, exact typed-depth boundaries,
compile-only invalid arithmetic and 48 both-direction mixed-stack narrow-result/
wide-count ABI arrangements. Concrete AST units retain original left/right
identity, operator/location, calculation/result types and independent RHS shift
promotions. Full/sanitizer/fuzz results follow once validated.

M19d2 final local validation: complete normal regression and QBE suites passed.
Both-host ASan/UBSan lexer/sema units and integer/additive/prefix/postfix update
runtime/ABI suites passed. Bounded sanitized fuzz completed 21,351 lexer and
54,832 pipeline inputs in 26 seconds each without reported failure. No generated
C or curated invalid runtime arithmetic was executed. Isolated full matrix and
remote CI require their own final markers. Next: M19e1 named labels, designed
in m19-named-labels.md before goto target/control-flow changes.

## M19e1 named-label foundation

Implemented distinct concrete label/block-label/labeled-statement representations
and subset BNF parsing. Identifier-leading items/statements consume one name and
inspect the colon with one demand peek; ordinary names continue through shared
postfix/Pratt suffix parsing with unchanged recursion accounting and precedence.
No token vector, rewind or new lookahead buffer. Function-local label bindings
are separate from objects/functions, check duplicates even in skipped/unreachable
syntax and reset per function. Explicit 512-label resource bound complements
statement nesting/block-item limits. Labels add no runtime storage; standalone
ones are ignored and labeled statements propagate child termination. Goto and
its needed unreachable-label traversal remain a separate increment.

Both native hosts pass 15 strict original ordinary-label programs, five duplicate
label constraint rejections, syntax/nesting/512-label boundaries and 24 both-
direction mixed-stack primitive-result ABI arrangements. GCC also strictly
accepts both original C23 declaration/end-block placement programs; Clang 15
rejects them with exactly expected-expression/expected-statement grammar errors.
These are labelled host gaps, not rewritten comparisons; kcc/QBE executes both
originals. AST units retain all three concrete node forms, source positions,
ordinary binding through labels and exactly two preexisting parameter/local
objects with no label-created static objects. Full/sanitizer/fuzz follow.

M19e1 targeted sanitizer evidence: both-host ASan/UBSan lexer/sema units and
named-label/integer-compound/additive/prefix/postfix runtime/ABI suites passed.
Full normal suite passed; QBE/fuzz remain running. Next M19e2 goto is designed
in m19-goto.md. A standalone QBE probe confirmed predecessor-free dead blocks
using entry allocations are accepted; no generated C was executed by the probe.

M19e1 final local validation: complete normal regression and QBE suites passed.
Both-host ASan/UBSan lexer/sema and named-label/integer/additive/prefix/postfix
runtime/ABI suites passed. Bounded sanitized fuzz completed 22,997 lexer and
58,129 pipeline inputs in 26 seconds each without reported failure. No generated
C was executed. Full isolated/remote matrices are tracked separately. Next:
M19e2 goto resolution/target lowering per the prewritten m19-goto.md design.

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

Focused validation passed on both hosts: lexer/sema units, 22 strict original
native programs, six native missing-target constraints, syntax and 4096/4097
reference boundaries, and 24 both-direction mixed-stack primitive-result ABI
arrangements. Both original C23 placement programs run through kcc/QBE; GCC
agrees, while Clang 15 has two exact labelled grammar gaps, not agreements.
Named-label regression also passed both hosts. Full normal/QBE, sanitizer and
bounded fuzz validation follow; only final markers count as completed runs.

The first full run exposed an obsolete raw-IL test expecting post-terminator
syntax to disappear. With goto it must remain in predecessor-free blocks until
QBE reachability removal. Updated only that exact return-count expectation
(two to three), retaining the no-false-merge-jump assertion; rerun the complete
chain. No compiler semantics were relaxed to satisfy the old fixture.

M19e2 final local validation: complete normal regression and QBE suites passed.
Both GCC/Clang ASan/UBSan lexer/sema units and goto/named-label/integer-compound/
additive/prefix/postfix runtime/ABI suites passed. Bounded sanitized fuzz completed
22,770 lexer and 54,016 pipeline inputs in 26 seconds each with no reported
failure. No generated fuzz C or constraint-invalid/runtime-UB source was executed.
M19d1 e1e5eb3 remote CI 38884494636 passed every job. Later remote and full
isolated matrices remain separately tracked, not claimed as completed.
User requested a stop after this milestone; no next milestone was started.

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

M19f1 initial full/sanitizer runs exposed the old lexer fixture still classifying
switch as unsupported. Kept unsupported-keyword coverage with struct and retained
the new direct/macro switch-token assertions. No compiler change was needed.
Both complete validation chains are rerun after the fixture correction.

M19f1 final validation: complete normal and QBE regression passed. GCC/Clang
ASan/UBSan lexer/sema and switch-foundation/goto/named-label/integer-compound
runtime/ABI suites passed. Sanitized bounded fuzz ran 14,107 lexer and 49,285
pipeline inputs in 26 seconds each without reported failures; generated C was
never executed. Remote exact-source and isolated full matrices remain separate.
Next: M19f2, designed before implementation in m19-switch-cases.md.

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

The initial generated parser patch matched a forward declaration instead of the
block-item definition, putting block wrappers into parse_statement. Strict build
detected incompatible pointer returns; moved that exact block before testing the
new compiler. No partial build was treated as validation. Native tests also
exposed exact Clang 15 case/default end-label diagnostics and host folding of
overflowing ICE arithmetic. Three invalid-arithmetic cases remain mandatory
compile-only kcc rejections, not strict native-rejection claims. The remaining
19 native constraint rejections stay strict. No compiler acceptance was relaxed.

M19f2 final local validation: complete normal and QBE regression passed. Both
GCC/Clang ASan/UBSan lexer/sema and switch-case/foundation/goto/named-label/
integer-compound runtime/ABI suites passed. Focused coverage: 75 strict original
native programs, 19 strict native constraint rejections, three compile-only
checked-arithmetic ICE failures, and 24 both-direction mixed-stack ABI arrangements
per host. All three original C23 declaration/end-label programs run via kcc/QBE;
GCC agrees, Clang 15 has three exact labelled grammar gaps, not agreements.
1024/1025 switch and 4096/4097 function-label boundaries pass through QBE when
valid, never execute. No generated fuzz C was executed.
Sanitized bounded fuzz: 14,777 lexer and 52,498 pipeline inputs in 26/26 seconds, no reported failure.

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

M23d1 focused validation: 48 original curated C23 programs and 24 both-direction
mixed-stack primitive-result ABI arrangements passed through kcc/QBE with GCC
and Clang linkers. The installed GCC 11/Clang 15 lack the actual C23 typeof
keywords, confirmed by exact diagnostics; zero original native agreements or
native constraint rejections are claimed on these hosts. Modern CI uses the same
original sources when keyword probes pass. Ten kcc constraints, syntax/subset
rejections and 64/65 nesting boundaries passed. VLA rejection is a subset gap,
not a native C constraint; function qualification is also excluded from the
strict native oracle. Initial fixtures were corrected for GCC's typographic
quotes and existing complete-object/file-scope-object/variable-length diagnostics;
no acceptance checks or compiler constraints were relaxed.

M23d1 final local validation: full normal and QBE regression passed. GCC/Clang
ASan/UBSan lexer/sema units and typeof-type-name, switch-case/foundation, goto,
named-label and integer-compound runtime/ABI suites passed. Bounded sanitized
fuzz ran 15,037 lexer / 52,225 pipeline inputs in 26/26 seconds without reported
failure; generated C was never executed. M19f1 cff28ab public CI 38904988323
completed success; M19f2 84797f7 run 38907237071 remains in progress at this
checkpoint. Isolated full matrices and this commit's CI are separately pending.
Next expression-operand design is m23-typeof-expressions.md.

### M23d1 native array-qualification oracle correction

Exact-source CI 391fd01 run 38909406525 failed both Build and test jobs while
fuzz passed. The original typeof_unqual(const int[2][3]) program was rejected
as a read-only assignment by GCC and Clang. N3096 6.2.5p31 says array and element
are identically qualified; 6.7.2.5p5/example 2 shows typeof_unqual removing array
element qualification. Keep kcc's immutable unqualification and typed-AST checks.
Classify only this exact original source with either exact observed read-only
diagnostic as a native gap, not agreement. Unexpected sources/diagnostics still
fail. All original sources still compile/run with kcc/QBE; no macro/type rewrite
is used. Zero gaps are also valid when a native compiler implements the rule.
M23d2 uncommitted work was stashed while this independent correction is tested;
its interrupted full regression is not a pass. Its both-host targeted sanitizer
run finished before interruption, but full validation will be restarted after
restoring the increment. Preserve the older reset stashes.

M23d1 oracle correction local validation: full normal/QBE regression and the
corrected suite with both unchanged GCC/Clang ASan/UBSan compiler binaries passed.
Bounded sanitized fuzz ran 14,800 lexer / 48,621 pipeline inputs in
26/26 seconds without reported failure. Exact-gap classifier units accept only
the observed source/diagnostics, rejecting unrelated source or extra errors.
No compiler source or constraint changed. M19f1 cff28ab isolated full GCC/Clang
normal and ASan/UBSan matrix now completed; later matrices/CI remain separate.
