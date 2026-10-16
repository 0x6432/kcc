# Component contracts

Interfaces are introduced with their implementing milestone, not speculative
empty headers. Any incompatible contract change must identify affected stages
and update their tests in the same checkpoint.

| Producer | Consumer | Contract |
| --- | --- | --- |
| source | lexer/diagnostics | Prepare raw bytes before borrowing; immutable logical spelling slices, explicit length and physical diagnostic mappings; EOF is not an input sentinel |
| lexer | preprocessor | Distinct pp_token on demand, borrowed logical spelling, newline/spacing state, no keyword/value classification; conversion is separate |
| preprocessor | parser | One cached language token, null/define/undef consumed and object/fixed/variadic macros rescanned before conversion; separate spelling/invocation locations; errors prevent IL |
| parser | sema | Distinct concrete AST structs, source locations, no inferred semantics |
| sema | codegen | Validated typed AST, explicit conversions, resolved declarations; failure prevents codegen |
| codegen | QBE | Well-formed IL for the pinned target; no source-language validation here |
| arena | AST/stages | Compilation-lifetime ownership; alignment and overflow checked; destruction releases all chunks |
| driver | stages | Explicit initialization/destruction order; diagnostics on stderr, successful output on stdout |

Errors initially stop the affected compilation. Error recovery is a separate
milestone, not an accidental result of uninitialized nodes. Fuzz harnesses must
use the same public interfaces as the driver and release every compilation.

M00 interaction: driver has only argument handling; there are no compiler
stages to invoke yet. It rejects source input rather than pretending to compile.

M01 contracts: source_from_bytes/source_load initialize fresh structs and leave failures
empty; destroy is idempotent. Line/column clamps invalid offsets to EOF.
Diagnostic stream lifetime is caller-owned. arena_alloc(0) allocates one byte;
failed allocation leaves existing chunks intact. No support for over-aligned
types. All support stages have one implementation file.

M02: lexer_next/lexer_peek return borrowed spelling via source slices. Tokens
contain a byte location, length, kind and integer value when applicable. Peek
may advance the internal byte cursor but does not consume the cached token.
Both APIs can produce diagnostics. An invalid token consumes at least one
byte. EOF is zero-length at source length. Source and diagnostics outlive the
lexer. Parser will use the same API in M03; preprocessing will wrap it later.

M03: AST constructors return NULL on allocation failure. Common headers are
the first member of concrete node structs; kind-based casts preserve identity.
Parser failure returns NULL and reports an error (or preserves the lexer error).
Sema success supplies type_int annotations throughout the supported tree.
Only then may codegen emit. Codegen's bool is an I/O result, not semantic
validation. Destroy the arena before its referenced source.

M04: parser computes AST expression depths and rejects a node deeper than 128,
as well as bounding Pratt recursion. Constructors initialize depth but expect
parser-validated operands. Recursive sema/codegen rely on that invariant.
Every supported unary/binary expression has int operands and int result;
future type conversions belong in sema. Codegen emits operands before result
temporaries. Invalid source is rejected before output; output I/O failure
returns failure but cannot undo already-written bytes.

## M05 design (before implementation)

- Compound bodies become ordered linked block items. Declarations and statement
  wrappers are separate concrete structs; no all-purpose AST union.
- One local declaration introduces one int object, with an optional initializer.
  Parser stores names only; sema owns the one function-body scope. Nested blocks
  and shadowing remain M06. A name becomes visible before its initializer.
- Name expressions resolve to declaration nodes and are modifiable lvalues.
  Sema inserts a distinct load-expression node for lvalue-to-rvalue conversion.
  Assignment is its own expression type, binds below arithmetic and associates
  right-to-left. Its result is an rvalue. Sema receives the arena to allocate
  conversion nodes; driver and fuzz harness must pass it explicitly.
- Every local gets a sema-assigned slot ID. QBE alloc4/loadw/storew implement
  storage. Allocation happens at entry; initialization follows source order.
  Uninitialized automatic objects are not silently zero-filled. Reading one is
  not turned into a false C constraint error; runtime tests exclude such UB.
- Sema validates even unreachable items. Codegen stops after a return. Falling
  off this main returns zero, as C requires, not an arbitrary missing-return
  error. Empty and expression statements have distinct structs.
- Keep expression nesting/tree limits at 128, including inserted conversions.
  Limit a function body to 4096 items and 256 locals, with explicit diagnostics.
  These resource policies are not C language constraints.

M05 integration record: compound->body was replaced by compound->items. Block
items retain source order through item->next; function->locals is a separate
reverse binding/allocation list. Slots are assigned in declaration order.
Name nodes reference declarations, not their initializer expressions: passes
must not recursively follow declaration backlinks (self-initializers can make
the reference graph cyclic). Conversion nodes are arena-owned. Sema is run
once on a fresh parsed tree; typed depth is recomputed after conversions.
Driver and pipeline fuzz harness pass the arena to the new sema interface.
Codegen uses binding IDs, never performs name lookup, and never initializes
an object solely because its storage was allocated. Empty bodies are valid.

## M06 checkpoint design

M06a adds compound statements and scoped bindings. Each block gets a separate
scope; duplicate checking is current-scope only and lookup walks parents.
Bindings are arena-owned, while scope frames are stack-local to sema. The
function-wide locals list still retains every declaration for QBE slot allocation.
Parser counts all block items across the function (4096), not per nested block,
and bounds combined compound/if nesting at 128 before recursion.

M06b adds a distinct if-statement struct and comparison operators. Recursive
descent attaches else to the nearest unmatched if. QBE tracks labels and whether
a statement's paths terminate; it must not emit instructions after a terminator
or emit a merge block when both branches return. Selection-statement scope is
explicit, including the C scope of its substatements.

M06c adds distinct logical-expression nodes rather than eager binary nodes.
&& and || have C precedence, produce normalized int 0/1, and emit branches plus
phi values. The emitter records the current block label so a nested RHS supplies
the actual predecessor to a phi. Skipped RHS operands are still checked by sema,
but are never evaluated at runtime. ! is an ordinary prefix operation.

M06 implementation notes: scope frames restore parents on success or failure.
If substatements have their own scope frames. Function-wide block-item counting
reserves an item before descending into it, so nesting cannot bypass the cap.
Labels/temporaries have independent monotonic counters. Each logical merge
starts with its phi; predecessor IDs are captured after operand emission, not
before nested control flow. No eager binary opcode represents && or ||.

## M07 design before implementation

M07a: distinct while/break/continue structs. Sema records the enclosing loop on
jump nodes, rejecting jumps outside loops even in unreachable source. Its loop
context is separate from its scope stack. QBE loop contexts carry explicit break
and continue labels and assert the sema-selected target. While continue returns
to the condition, never the first body instruction. Only an unterminated body
gets an implicit back edge. Loop exit labels remain conservatively reachable;
this checkpoint does not infer nontermination from constant conditions.

M07b: a distinct do-statement struct. Execute body before condition; continue
jumps to the condition and break bypasses it. Unreachable condition blocks must
still be well-formed QBE and semantically checked; don't evaluate a condition on
paths that already broke or returned.

M07c: a distinct for-statement struct with explicit optional init declaration,
init expression, condition and step. A declaration in the initializer is visible
through condition/body/step, not after the loop. The body has its own C scope.
Missing condition means unconditional iteration; missing step means no work.
For continue executes the step before rechecking the condition. Header parsing
uses an explicit semicolon contract, not special whole-file token buffering.

All composites share the 128 statement nesting limit. Loop declarations count
toward 256 locals per function; nested block items remain globally capped at
4096. Sema validates all syntax, including skipped paths. Fuzzing compiles but
never runs arbitrary loop inputs; executable tests use bounded, defined cases.

M07 integration notes: jump target pointers are semantic backlinks, not owned
syntax children. Never recursively traverse target->body from a jump; this
would create cycles. Loop codegen contexts store labels, not source-name
bindings. For initializer declarations use the same local-initializer helper
as block declarations; sema analyzes step in the header scope before body
locals exist. Header declarations count toward the global local limit but are
not C block items. All loop forms preserve explicit load nodes and nested
logical-expression predecessor tracking. Unreachable condition/step blocks
are intentionally well-formed and may be removed by QBE, not source sema.

## M08 design before implementation

M08a replaces the single-function translation unit with an ordered list of
external declarations. Function declarations and definitions have separate AST
structs; definitions refer to their header declaration. Sema registers each
function before its body (so self-reference works) but does not hoist later
headers. Compatible prototypes share one arena-owned symbol; duplicate
definitions and incompatible signatures are errors. Direct calls have their own
AST kind and resolve through ordinary-name shadowing rules. Bare function
values/indirect calls remain later work.

M08b adds distinct int parameter and argument-list nodes. Function types record
int return and parameter types, independent of parameter names. Definition
parameter names must exist and be unique; prototype names are optional. Parameters
and the outermost body declarations share a scope, and parameters receive entry
slots before ordinary locals. Calls check counts and insert normal value
conversions. QBE emits w parameters, entry stores, and w call arguments.
C23 empty () means zero parameters; no variadics or unspecified argument lists.

M08c verifies direct/mutual recursion and ABI interoperability with GCC/Clang,
including arguments beyond the six x86-64 integer registers. Argument evaluation
uses the compiler's chosen left-to-right order; tests do not rely on unspecified
order or execute undefined programs. Local, scope, loop, label and temporary
contexts reset per function. Main remains int main(void) until pointer/argv work.

Limits: 512 external declarations, 256 distinct functions, 128 parameters/call
arguments, existing per-function locals/block limits and expression depth bounds.
Library translation units without main are allowed. Only definitions emit IL;
prototype-only units emit no definitions. Undefined declared functions are left
for the host linker. Non-main fallthrough is not diagnosed yet: a zero filler
satisfies QBE's int return ABI, but using a missing C return value is still UB,
not a promised implicit-zero C result. Main fallthrough is the defined C zero.

### M08a implemented contract

Ordered external declarations, compatible zero-argument prototypes and multiple int function definitions are supported. Sema installs canonical symbols in source order; calls resolve visible functions, respect local shadowing and reject duplicate definitions. QBE emits each definition independently and direct w-result calls; prototypes emit no IL.

The TU owns an ordered external list with distinct declaration/definition
structs. Definitions reference their own declaration header. Call expressions
carry a canonical symbol; their callee has a function type, while the call has
int type. Sema runs once and checks unreachable calls too. No forward hoisting.

### M08b implemented contract

Integer parameter and argument lists are implemented with name-independent function signatures, source-order prototype visibility and argument-count checks. Parameters receive the first local slots and share scope with the outermost body declarations. QBE w entry values are stored into those slots; nested call arguments finish emitting before the call line.

Distinct ast_parameter and ast_argument lists preserve source order. Parameter
syntax names are separate from function_parameter_type entries. A canonical
symbol carries compatible type information; type_compatible compares return
and each parameter type/count, never names. Sema resolves callees against local
shadowing and visible functions, then inserts value conversions in arguments.
Parameters have semantic local backlinks; these are not AST ownership edges.
The root scope is explicit so a same-body redeclaration fails. Nested blocks
may shadow parameters. All scopes/loop contexts reset between definitions.

### M08c acceptance boundary

Recursion needs no special codegen path: a function's canonical symbol exists
before its own body is checked, and a prototype makes a later mutual callee
visible. The semantic/compiler traversal never follows call-symbol backlinks
recursively. Runtime recursion uses the ABI's ordinary call frames.

The ABI harness compiles kcc IL and host C to separate objects and links them,
so neither compiler can inline across the boundary. It checks full int results
through comparisons rather than relying only on process exit truncation. The
128-parameter weighted sum uses a balanced expression to stay within depth 128.
CI matrix host selection applies to executable/reference and ABI tests; these
also run after rebuilding the compiler with ASan/UBSan. Fuzzing never executes
source programs and retains its source-size/time/memory limits.

## M09 design before implementation

Reference: WG14 N3096, 5.1.1.2 and 6.10:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf
This public C23 draft guides the checkpoint, not a complete conformance claim.

M09a prepares source bytes before any token is borrowed. Phase-1 input policy
maps CRLF and lone CR end-of-line indicators to LF. Phase 2 deletes only a
backslash immediately followed by a normalized newline. Perform this in one
forward traversal of physical units; never rescan newly adjacent output bytes.
Only the last backslash on a physical line is eligible. This precedes comment
recognition, so splicing can join identifiers, operators or comment delimiters,
and can extend a line comment. Comments still separate tokens, not concatenate
identifiers. Whitespace between backslash and newline is not accepted as a
splice extension. C23 does not require trigraph replacement; none is added.

source_load/source_from_bytes continue to own raw bytes. New explicit
source_prepare is fallible, idempotent and transactional: on failure the source
remains raw, valid and destroyable. Call before lexer_init; never transform a
source after token spellings have been borrowed. Prepared source.data/length
are logical bytes; token location.offset and length index those bytes. If
changed, retain the original bytes and sparse logical-to-physical offset
checkpoints. Diagnostics use original physical lines/columns; token debug
output continues reporting physical byte offsets. Semantics/codegen continue
using contiguous logical spelling slices; they must not use physical offsets
to index source.data. Source preparation is byte normalization, not eager token
materialization. Lexer lookahead remains one token.

Keep empty input and the current missing-final-newline acceptance extension;
do not synthesize a newline or silently introduce a second splice. These
extensions do not claim strict phase-2 final-line constraint validation. Source
encoding/UCNs, BOM policy and complete translation phases remain later work.
Memory stays bounded by the 16 MiB raw-source limit: optional logical bytes plus
one sparse checkpoint per transformation event at most. No per-token allocation.
Both fuzz harnesses must call the same preparation API and test logical bounds,
physical mapping bounds/monotonicity, EOF and progress. Fuzz never executes C.

M09b separates raw preprocessing tokens from language-token conversion. Retain
newlines, leading whitespace and line-start state for directives/macros; do not
classify keywords or validate int values prematurely. Preserve maximal munch
for preprocessing numbers even when the eventual C token is unsupported.
Keep distinct pp and parser token types, spelling ownership and provenance
explicit. No whole-file token vectors or pretend macro expansion.

M09c inserts an on-demand preprocessor facade between lexer and parser, with
one parser-visible cached token, null directives and explicit unsupported or
malformed directive diagnostics. Reuse language token conversion here; normal
subset behavior must stay unchanged. Design the exact APIs and newline/comment
rules before this slice. Macro definitions/rescanning are M10; include search,
conditionals, stringizing/pasting are M11. Do not add empty speculative stages.
EOF remains stable, all failures prevent compiler IL, and each tested checkpoint
gets its own commit/push and handoff/limitations update.

### M09a implemented contract

source_prepare is explicit before lexer_init, including in both fuzz harnesses.
It leaves unchanged bytes in place when no transformation is needed. Changed
sources keep original physical bytes, a logical spelling buffer and sparse
checkpoints only where offsets diverge (CRLF or splice); lone CR needs no map
entry. Consecutive deletions at one logical offset share the last checkpoint.
source_physical_offset clamps to logical EOF and binary-searches checkpoints;
EOF maps to original EOF. source_line_column walks physical bytes with CRLF/CR
newline policy and eight-column tabs. The --tokens command reports physical
start offsets; token.length still describes logical spelling bytes.

Two-pass preparation first counts allocation capacity, then transforms original
physical units once; it never rescans generated output. No token vector is
introduced. source_destroy releases all optional buffers and resets preparation.
Parser, AST, type, sema and codegen implementation interfaces are unchanged.
All lexer callers were updated; adding another caller requires preparation.

## M09b design before implementation

Keep raw lexing and language-token conversion in lex.c (one implementation file
for the lexing stage). Introduce distinct pp_token/pp_token_kind and pp_lexer
structures. pp_lexer_next/peek produce identifiers (including keyword spellings),
pp numbers without values, quoted string/character preprocessing tokens,
maximal-munch punctuators, other ASCII non-whitespace bytes, newline, invalid
and stable EOF. No header-name context, Unicode/UCN recognition or expansion
provenance is claimed yet. Token locations/spellings remain borrowed prepared
logical slices; physical diagnostics still go through source mappings.

Raw tokens carry leading_space and at_line_start. Horizontal whitespace and
comments set leading_space. A block comment is one separating space, including
its internal newlines; it does not reset directive line-start state or emit
newline tokens. A line comment stops before its terminating newline. Only
newlines outside comments emit pp_newline and start a new logical directive
line. Source preparation already removes splices before these rules. Raw
lookahead caches one token; repeated peek and EOF never duplicate diagnostics.

Recognize ASCII pp-number maximal munch, including leading .digit, exponent
signs, identifier continuations and C23 apostrophe-digit/nondigit sequences.
Do not validate values, bases or suffixes while scanning. Recognize all C23
punctuator spellings, including :: and digraphs, longest first. Quote scanning
recognizes ordinary/u8/u/U/L prefixes, escaped delimiters and comment-like
contents; interpretation, supported literal types and concatenation come later.
Unterminated quotes/comments and invalid binary bytes diagnose and advance.
Other ASCII pp characters remain raw until conversion, rather than diagnosing
before preprocessing can consume them. Encoding/UCN/header-name support remains
explicitly incomplete.

A stateless token_from_pp converts one non-newline preprocessing token to the
existing parser token: keyword classification, supported decimal int checking,
and supported punctuator conversion happen here, not in raw scanning. Raw
invalid tokens carry their existing diagnostic and are not diagnosed twice.
The existing struct lexer/lexer_next/peek API temporarily wraps a pp_lexer,
ignores newlines and converts lazily. Parser/AST/sema/codegen signatures do not
change in M09b. This wrapper still rejects every # directive; it is not macro
expansion. M09c will move parser-facing dispatch onto the real preprocessor
facade. Never mix raw and converted reads on the same owned stream.

Add --pp-tokens to inspect raw kind, physical start, logical length and the
spacing flags without integer/keyword conversion; preserve --tokens behavior.
Test the raw stream independently and fuzz raw plus converted paths with bounded
progress, stable EOF, repeat-peek and no extra-diagnostic assertions. Preserve
all executable/reference/ABI checks and source preparation invariants. Commit
and push only after normal/Clang/sanitizer/fuzz verification, then check CI.

### M09b implemented contract

pp_lexer produces raw tokens with one cached lookahead. pp_token has no integer
value: keywords remain identifiers and unsupported numeric spellings remain pp
numbers until token_from_pp. The language adapter still uses lexer_next/peek,
skips newlines and converts exactly one token on demand. Parser/AST/sema/codegen
signatures and supported int behavior are unchanged; brace digraphs map to the
existing brace kinds. Every # or %: still fails language conversion.

Raw newline tokens carry the spacing/line-start state before the newline; the
following token starts a new line. leading_space means horizontal whitespace
or comments since the previous raw token, not an already-emitted newline.
has_non_directive_space records VT/FF in that leading trivia, not characters
inside a comment. M09c must check it after an introducing #, not before #.
Block comments replace one space without changing at_line_start; line comments
stop before a real newline. EOF retains stable flags, including trailing trivia.
Repeated raw/language peek never repeats diagnostics. token_from_pp propagates
pp_invalid without diagnosing it a second time; callers skip pp_newline.

Raw numbers implement ASCII pp-number maximal munch, including e/E/p/P signs,
leading .digit and apostrophe-digit/nondigit continuations. Literal prefixes and
escaped delimiters are recognized, but escape values, encoding validity and
concatenation are deferred. Source NUL/high bytes outside comments/literals
are diagnosed; NUL inside a quoted token is diagnosed too. Other single ASCII
non-white-space characters are pp_other until language conversion. Partial
quotes/comments yield one invalid token and make progress; no input vector.
Header-name context, UCN identifiers and macro source/expansion provenance remain
unimplemented, not silently converted through the host preprocessor.

## M09c design before implementation

preprocess.c becomes the sole parser-facing input stage. struct preprocessor
owns a pp_lexer and one cached language token; preprocess_next/peek dispatch
raw directives before calling token_from_pp. Remove M09b's temporary struct
lexer/lexer_next/peek adapter rather than maintain two compiler frontends.
Change parser input to struct preprocessor and update driver, semantic tests,
language-token tests and both fuzz build paths in the same checkpoint. Raw
pp_lexer APIs and --pp-tokens remain unchanged; --tokens now shows language
tokens after directive dispatch. AST/sema/codegen interfaces do not change.
No macro tables, arena allocations, full-file buffers or speculative expansion
state are introduced in this slice.

Only raw pp_punctuator # or %: with at_line_start introduces a directive.
Before #, horizontal whitespace/comments (including VT/FF) are allowed. After
#, has_non_directive_space on the next token records forbidden VT/FF separators;
check it even when that token is newline or EOF. VT/FF inside a comment count
only as the comment's one replacement space. Anchor a bad-separator diagnostic
at the following token/terminator, whose location is available. Real newlines
outside comments terminate directives; block-comment internal newlines do not.
Splices have already disappeared. Null directives are discarded, including an
EOF terminator under the existing missing-final-newline extension. A null
stream is valid at this stage; the current parser still rejects an empty TU.

An identifier after # is dispatched as known-but-unsupported (all standard
non-null directives) or unknown. Other token kinds are malformed directive
names. No numeric/keyword conversion occurs inside rejected directives. A raw
invalid token preserves its lexical diagnostic without a duplicate. Failed or
misplaced directives are drained through their logical line using raw tokens,
then return one nonempty invalid language token at the directive marker; the
diagnostic still points to the offending token. Raw-invalid tokens retain their
lexical location. This also guarantees progress when bad trivia is at EOF.
Distinct raw lexical errors encountered while draining remain diagnostics.
This is bounded line-level cleanup for debug inspection, not general parser
error recovery. The compiler stops on failure and emits no IL. Repeated peek
and EOF remain stable with no extra diagnostics; every read advances or yields
EOF. Unsupported #pragma/#error/#warning are not silently executed or ignored.
Standalone ##/%:%: remain unsupported operators, not directive introducers.

Test null directives before/within/after code, digraph markers, comments,
physical splices/locations, VT/FF before versus after #, EOF, malformed/unknown/
unsupported/misplaced directives and lexical failures during draining. Fuzz the
actual facade's cached-token/progress/error invariants and the full compiler;
keep raw lexer fuzzing too. Run existing source/oracle/AST, GCC/Clang,
QBE/reference/ABI, ASan/UBSan and CI. M09 completes only the stated phase/token/
null-directive subset; macro expansion stays M10 and includes/conditions M11.
M10 must never reinterpret macro-generated # tokens as new directives.

### M09c implemented contract

The temporary lexer language adapter was removed. Parser input is now struct
preprocessor with preprocess_next/peek; raw pp_lexer and token_from_pp remain in
lex.c. Driver --tokens, semantic tests, language-token tests and lexer/pipeline
fuzz consumers all use the same real facade. --pp-tokens still bypasses dispatch
for raw inspection. PREPROCESS_SOURCES in Makefile wires the stage consistently.
There is no new allocation, per-token ownership or grammar/AST/codegen change.

Only #/%: at raw line start dispatches. Null directives allow space/tab/comments
through external newline or the existing EOF extension. VT/FF before a marker
is ordinary whitespace; after it, outside comments, the following raw token's
flag triggers a diagnostic (including newline/EOF). Block comments do not end
a directive internally; line comments stop before newline. Unsupported known,
unknown, malformed and misplaced directives are rejected, with raw line draining
and no premature numeric/keyword conversion of their bodies. Diagnostic anchor
is the offending token; the returned invalid token marks the nonempty directive
introducer. Raw-invalid tokens propagate their original location/diagnostic.
EOF and repeated peek remain stable. A null-only stream is allowed here but
still rejected as an empty translation unit by the current parser.

M09's phase/token/null-directive foundation is complete, not all preprocessing.
M10 must design macro storage, expansion contexts, recursion suppression and
limits before implementation; never treat expanded # as a new directive.


## M10a object-like macro contract

The preprocessor owns arena-backed macro identities/replacement lists, borrowed
source spellings and a fixed expansion-frame stack. preprocess_init initializes
all state; preprocess_destroy frees it and clears state. All driver, test and
fuzz callers destroy after AST use and before source destruction. Raw lexer and
parser entry APIs are otherwise unchanged. Arena is linked into PREPROCESS_SOURCES.

Raw pp_token.location is spelling; expansion_location initially matches it.
Copied expansion tokens retain spelling but carry the outermost invocation.
Converted token.location is the diagnostic location; spelling_location plus
length is the only spelling slice. Diagnostics/AST nodes keep using location;
sema equality, numeric conversion and emitted function symbols use spelling.
There is no full expansion-chain note API yet. EOF has both locations at source
length. Error lengths describe spelling, not invocation width. Expanded output
need not have increasing spelling offsets or fit within the invocation name.

Definition/undefinition parsing never expands operands or converts replacement
literals. Completed valid lines bind atomically; failures preserve old bindings.
Redefinitions compare kind/spelling and inter-token spacing. All attempted stored
replacements count against retained storage, even duplicates/rejected definitions;
undefinition does not reclaim identities or arena memory. Macro identity is
stable across undef/redefine; later definitions affect subsequent rescans only.

Frame push and replacement-token visits consume the translation-unit work budget.
An exhausted frame stays active until its last token is fully rescanned; direct
and mutual object recursion terminate. No C parser grammar or typed AST variant
was added. Function-like argument expansion must revisit unavailability/hide sets.
Raw-source markers alone dispatch directives; replacement markers reach language
conversion and fail without starting a directive. Deferred numeric/string errors
point at invocation sites. A limit/allocation failure returns one nonempty invalid
token then permanent EOF, with no repeated diagnostics from peek. Source/raw
scanning and diagnostics retain their earlier limits/performance caveats.

Fuzz invariants now bound language steps by source length + expansion work + one
terminal error. Diagnostic offsets are nondecreasing (equal for one invocation);
spelling offsets may go backward, but spelling slices must remain source-bounded.
No arbitrary generated program is executed. The test-only pp_oracle compares
actual kind/spelling pairs with host -E -P output; CI uses both GCC and Clang.


## M10b zero-parameter function-like contract

M10a's active-frame suppression is superseded. macro has a stable identity index
and function_like flag; redefinitions must agree on form and body/spacing.
Definition '(' must be adjacent to the name; whitespace after ')' is optional.
Empty parameter lists are parsed without storing delimiters. Named/variadic
parameters reject explicitly. Function bodies reject #/%: and ##/%:%:; object
bodies retain the earlier literal-marker behavior. Errors preserve old bindings.

rescan_token contains pp spelling/invocation information, source-origin flag and
an inline macro_hide_set (1024 bits in 64-bit words). Source sets are empty.
Each replacement frame copies its set onto emitted tokens. Object expansion
adds itself to the name set; function expansion adds itself to the intersection
of name/closing-delimiter sets. Availability survives frame popping. This policy
matches the tested GCC/Clang subset; full arguments need per-token set unions
and prescan. Some C23 rescan corner cases have unspecified behavior; no unique
ISO result is asserted for every case. Bit boundaries through ID 1023 are tested.
Undef/redefine retains identity, including object/function form changes.

The cursor has one pending UNEXPANDED token separate from language lookahead.
Probing '(' skips raw newlines and crosses streams, but does not expand macros;
a later object producing '(' cannot retroactively invoke an emitted name.
Pending visits are not charged twice. Bare function-like names convert normally.
Invoked macros consume only a raw-empty '(' ')' sequence; nonempty arguments
reject without expansion. Source directives during probing/delimiters explicitly
fail instead of changing bindings speculatively. Raw-invalid input retains its
existing lexical diagnostic. Invocation errors latch EOF; definition errors
still drain lines. Generated # cannot dispatch, including through lookahead.

Ownership/provenance and all five macro limits are unchanged. Depth counts
retained streams, not completed logical calls: 201 successive source-delimited
calls need not occupy 201 frames. Work still counts pushes/replacement visits
and bounds long/exponential expansion. Fixed hide sets need no heap hide nodes.
Fuzzing also checks cache reads leave cursor offset/pending/frame/work state
unchanged. The 97-case object oracle plus 101 new cases make 198 streams tested
under both host compilers in normal/sanitized CI. No arbitrary generated code
is executed by fuzzing.


## M10c fixed-argument contract

Each definition has ordered macro_parameter records and a count (maximum 128).
Replacement nodes carry a parameter_index or SIZE_MAX. Parameter names are raw
identifiers, including keyword spellings; their namespace shadows macro names
inside the replacement. Duplicate parameters, malformed lists and variadics
reject transactionally. Redefinition also compares parameter names/order.
__VA_ARGS__/__VA_OPT__ are not accepted as fixed parameter names in this slice.

Expansion state is now expansion_cursor: main source cursor versus isolated
argument input. A frame streams definition or argument tokens and borrows an
arena-owned invocation argument array. Collection uses raw unexpanded pp tokens;
parentheses alone protect commas, preserving empty leading/trailing arguments.
An empty () supplies zero arguments to a zero-parameter definition and one empty
argument when parameters exist. Check arity before expansion. Source directive
LINES encountered while probing/collecting remain unsupported; inline # tokens
are ordinary argument tokens and can be discarded by unused parameters.

Used arguments get a lazy cached prescan. Isolated cursors cannot read following
source, and the enclosing macro's hide bit is not added early. A cached token's
hide bits are unioned with the call base on each substitution; cached nodes are
never mutated. Prescan is pp-only: a later unused parameter can discard literals
unsupported by language conversion. Raw-invalid tokens still diagnose during
collection. Unused arguments never undergo macro expansion/arity validation of
nested calls. Injected argument streams may meet replacement/source tokens.
Only source-origin tokens dispatch directives; copied arguments are not source.

Macro records and raw/cached argument nodes belong to the preprocessing arena.
Temporary prescan cursors are malloc/free pairs on every success/error path.
Caller init/destroy APIs are unchanged. The main pending/frame state moved into
preprocessor.cursor; fuzz assertions follow it and check auxiliary bounds and
zero active prescans after each public read. No parser/AST/sema/codegen changes.

New limits: 128 fixed parameters, 128 nested argument parentheses, 64 prescans,
65536 cumulative auxiliary records (parameter nodes, argument array elements,
raw/cached argument-token copies, including abandoned attempts). Definition token
storage retains its separate 65536 cap. Work also counts argument collection,
prescan input, record copies and injected frame pushes/visits. Source/object-only
accounting stays unchanged. These bounds cover retained memory, not just output.
Limit/allocation failure stops once then latches EOF; definitions keep line-level
recovery except fatal resource errors. Allocation fault injection remains absent.

Spelling slices stay original; substituted diagnostics use the outermost call.
Raw lexical errors keep their original lexer locations. No full expansion chain
is retained. M25 predefined-location macros need additional provenance review:
outermost diagnostic position alone is not the semantic __LINE__ expansion site.
The host oracle now has 374 streams, retaining all 198 prior cases, under both
hosts; it includes cyclic fixed-parameter graphs, callbacks and unused arguments.


## M10d variadic contract

Supersedes the M10c variadic exclusions only. macro.parameter_count still counts
named parameters, bounded at 128; macro.variadic records the trailing ellipsis.
The invocation array has named_count + 1 slots for variadic macros, even when
all variable arguments are omitted. At least the named arguments must exist;
an empty () supplies one empty argument when needed. Once collection reaches
the variable slot, top-level commas are copied rather than consumed as slot
separators. The separator introducing that slot is not part of its contents.

__VA_ARGS__ and __VA_OPT__ definition tokens carry the variable slot index.
Optional markers also point at their matching closing definition token, which
is tagged as a structural non-emitting boundary. All raw spelling/spacing stays
available to compatible-redefinition checks, which now compare variadic form.
Validation is iterative, bounded by replacement-token limits and transactional.
It rejects nested/malformed optional regions, GNU named ellipses and either
special identifier outside a variadic function-like replacement list. Special
source identifiers are rejected even in otherwise unused arguments.

Optional substitution requests the variable slot's lazy cached prescan. Empty
expanded output skips the whole region; nonempty output streams the region in
the same frame, without its operator delimiters. Parameter injection retains
the existing token hide-set union and outermost-call provenance. Crossing an
optional boundary must not isolate following replacement or source tokens.
Inactive regions do not expand their parameters. No synthetic spelling or
placemarker is needed without #/##; M11 must add real operator/placemarker
semantics rather than treating this subset as a complete operator implementation.

Arena ownership, public APIs, cursor/cache invariants and budgets are unchanged.
The extra variable slot and raw/cached commas consume auxiliary records; optional
selection and closing-boundary visits consume work. The full oracle has 564
streams under GCC and Clang, retaining all 374 prior cases. Fuzz cache checks
also require that repeated peeks do not allocate additional auxiliary records.
Variadic macros do not change the parser's fixed-arity function signatures or ABI.


## M11a stringizing contract

#/%: in a function replacement must precede a named parameter or __VA_ARGS__.
Validation annotates the operator with the raw argument index and skips its
operand during substitution. __VA_OPT__(#parameter) works; #__VA_OPT__(...) is
explicitly deferred. Object-like # stays ordinary punctuation. Failed validation
keeps old definitions; compatible redefinition still compares raw tokens/spacing.

Stringizing never requests argument prescan. It visits raw token spellings,
trims outside trivia, emits one space for each intertoken separation and escapes
quotes/backslashes within quoted literal tokens only. Empty input yields "".
A standalone nonliteral backslash rejects under the current no-UCN subset.
Two checked passes measure then fill a fixed arena buffer. Source views count
as auxiliary records; all bytes including NULs share a new cumulative 1 MiB cap.
Failure yields invalid then stable EOF for resource/allocation errors.

A generated token's spelling source is a prepared arena view with offset zero;
its diagnostic expansion location remains the outermost original call. The view
and NUL-terminated data live until preprocess_destroy, not source_destroy. Never
assume token.spelling_location.source or pp_token.location.source equals the
translation-unit input. Source/lexer APIs and AST/sema/QBE interfaces are unchanged.
Future synthesized identifiers/numbers must obey the same ownership contract.

preprocess_next_pp shares the main cursor and returns expanded pp tokens before
language conversion. It normalizes EOF and maps existing preprocessing errors
to pp_invalid without diagnosing again. Clients must not mix it with a pending
language peek. Parser language caching remains unchanged; string tokens still
reject during language conversion, unless discarded by an outer macro first.
The test-only oracle has a --pp mode rather than weakening string conversion.

Spacing now preserves source newlines, invocation first-token separation, empty
streams and internally created prescan separation. Strip only original leading
argument trivia; keep separation created when internal macros disappear. Cached
arguments retain trailing separation, applied when their injected frame ends.
Optional marker delimiters do not emit spacing; an empty region preserves the
following token's own separation. Repeated peeks cannot allocate spellings or
change deferred spacing/byte counters. Both language and expanded-pp fuzz paths
check ownership, bounds, diagnostics and EOF; generated strings must re-lex as
exactly one pp_string. Source view lifetime is tested across subsequent reads.

Agreement coverage: 564 language + 142 expanded-pp streams with GCC and Clang.
Five separate two-level whitespace policy groups record host disagreement:
kcc follows GCC 11.5 for removed internal macros/optional delimiter spacing;
Clang 15 differs. They are explicit local policy regressions, not agreements
or claims that ISO makes all such differences implementation-defined. Review
these interpretation gaps during the conformance audit before broader claims.


## M11b optional stringizing contract

A stringizing operator may now precede a validated __VA_OPT__ operand. It keeps
its variable-slot index and matching closing definition node. Redefinition still
compares raw tokens/spacing; failed validation remains transactional. A nested
__VA_OPT__ in a single definition remains invalid, even if stringized.

The variable argument's existing cached prescan decides presence. An inactive
body contributes no tokens and yields ""; no named body parameter is prescanned.
A selected body gets ordinary parameter prescan/substitution and inner raw #,
but not ordinary macro rescan. Thus a body macro name remains text, while a
parameter spelling that names the same macro can expand through its argument
cache. Inner generated strings are escaped again by the existing outer builder.

expansion_frame.replacement_end is an exclusive borrowed definition pointer;
NULL means the ordinary complete list. A temporary heap cursor reads only that
range via read_rescan_token, never read_expanded_token. Its argument array,
hide set and invocation come from the caller. Injected streams retain existing
spacing/hide behavior; the parent skips the whole optional operand afterwards.
Neither suffix tokens nor following source can be consumed by the body cursor.

Substitution output uses existing arena argument_token records, charged to the
auxiliary and work budgets. Generated buffers share the existing cumulative
1 MiB cap. At most 32 optional cursors may be active; optional_depth restores
to zero on every public return, including nested argument/resource failures.
Heap cleanup is shared for all pushed-cursor exits. Normal/init/destroy APIs
and source/AST/sema/QBE interfaces are unchanged. No real placemarker nodes are
needed without ##; token pasting must add them under its own reviewed contract.

Oracle agreement coverage is now 564 language + 276 expanded-pp streams under
both hosts. The five M11a whitespace policies remain separate. One additional
inactive-argument diagnostic policy explicitly checks kcc's lazy result and
allows the observed GCC diagnostic versus Clang acceptance; it is not agreement
or a settled standards ruling. Unit limits cover 32/33 active helper nesting
without exponential string growth, using prescan-then-discard forwarding macros.
Fuzzers check zero active helper depth, owned spellings and stable cache/EOF.

## M11c token-pasting contract

See m11-token-pasting.md for the phase and ownership design. Paste-bearing
invocations build a bounded per-invocation list, not a translation-unit vector.
Definition-origin operators are distinct from argument/generated ## tokens.
Raw boundary operands are substituted, paste pairs are re-lexed as exactly one
pp token, placemarkers are removed only after enclosing operator phases, then
ordinary rescanning applies the invocation hide set. Real concatenations use
operand hide-set intersection. The substitution-only optional stringizer may
paste but must not perform an ordinary macro rescan.

All synthesized token kinds may borrow arena-owned generated source views.
Consumers must not assume only strings have generated spellings. The shared
spelling-byte budget includes each NUL terminator. A NULL diagnostic stream
counts errors without resolving/outputting locations, allowing speculative
re-lexing to report one final user-call-site diagnostic instead. All active paste,
prescan and optional-range counters unwind on both success and failure.

## M11d diagnostic-directive contract

Diagnostics count warnings separately from errors. NULL-stream mode counts both
without resolving source locations. Warnings do not invalidate AST/sema/codegen;
errors still suppress all compiler IL. Existing initializers use designated
stream fields. Diagnostic directive bodies bypass macro expansion and language
conversion. Temporary text is freed before returning; cache peeks do not repeat
diagnostics. The raw --pp-tokens driver mode remains directive-agnostic.

## M11e conditional-source contract

A fixed 128-entry preprocessor stack owns conditional branch state and opening
locations; it is independent of macro rescan frames and parser ASTs. Evaluated
macro-existence operands are raw identifiers. Excluded source tokens never enter
macro expansion or language conversion, but still pass through the raw lexer.
Only source line-start controls can affect the stack. Unknown/excluded directives
have no define/undef/diagnostic side effects. Evaluated #if/#elif expressions are
not supported in this increment; skipped nested expressions are balanced only.

M11e EOF integration: the parser must not return a successful translation unit
when deferred preprocessing errors arrive with EOF. parse_translation_unit now
checks diagnostics before constructing its success node. Fuzzing found the old
assumption that EOF always implied no new errors; the minimized conditional-eof
seed and a direct AST regression preserve this boundary. Warning counts do not
invalidate parser success.

## M11f conditional-expression contract

#if/#elif collect only one raw directive, replacing literal defined operands
before isolated macro rescanning. No whole-source token vector or C AST nodes
are introduced. The evaluator reads expanded pp tokens on demand, uses a Pratt
binding table and a 128-level recursion bound; raw directives are limited to
1024 tokens, with macro expansion also subject to existing shared budgets.
Generated defined results use owned views and the shared spelling-byte budget.

This first expression subset uses signed 64-bit decimal values. Arithmetic
checks precede host operations; short-circuited operands still parse and expand
but do not evaluate arithmetic. Diagnostics retain expansion locations. Parser,
sema and QBE contracts are unchanged except the earlier EOF error-success fix.

## M11g signed operator contract

The preprocessing Pratt table now includes shifts/bitwise operators. ?: binds
below logical-or and recurses right-associatively; its middle operand parses a
full supported expression. Short circuit extends to ternary arithmetic, not
syntax or macro expansion. Shift checks precede host operations; negative right
shifts are explicitly sign-extending via nonnegative arithmetic. Both ternary
branches are signed-intmax in this subset; later unsigned support must compute
the common type from both branches even when one is not evaluated.

## M11h preprocessing literal contract

Conditional numeric scanning is separate from both pp lexing and runtime token
conversion. Prefix/base, digits/separators and suffix are distinct validation
steps; accumulation is bounded before host arithmetic. Accepted values are still
signed-intmax only, with absent or signed l/L/ll/LL suffixes. Valid unsigned forms
and nondecimal values requiring uintmax_t diagnose as unsupported, not as signed
negative values. Digit-separator grammar is checked even in unevaluated operands.
No change to parser AST types, C expression conversion or QBE IL types.

## M11i explicit integer-value contract

Each preprocessing expression value carries uint64 bits plus signedness; this
private struct does not change AST or runtime types. One mathematical decoder
maps signed bit patterns without large unsigned-to-signed casts. Arithmetic and
bitwise operators apply intmax/uintmax usual conversion; comparisons/logical
operators produce signed 0/1. Shifts preserve the left type independently of the
right operand. Unsigned arithmetic wraps in uint64; signed arithmetic is checked.

Unselected operands still produce correct types without evaluated arithmetic.
Ternary signedness depends on both branches, not only the selected one, and the
chosen bits are converted to that common type. This invariant also applies to
unselected unary, binary and nested conditional expressions. Macro-generated
numeric spellings follow the same literal scanner and ownership contracts.

## M11j conditional character contract

A private decoder maps ordinary single-byte character tokens to signed-intmax
values using target ASCII/signed-char rules, independently of host char type.
Simple/octal/hex escapes are checked before conversion. Literal validation and
result typing apply even to unselected operands. Prefixes, multicharacter forms,
non-ASCII source bytes and universal names remain explicitly unsupported.
No runtime char type, C character-expression conversion or Unicode claim.

## M11k direct quoted include contract

Source loading is an explicit callback, disabled by default. Driver/oracle opt
into file loading; pipeline fuzzing supplies only owned memory sources and never
opens requested paths. Successful child buffers remain alive through AST/sema/
codegen use and are destroyed before the preprocessor arena. Parent lexer states
and conditional bases form a bounded stack; macros are shared across sources.

Only ordinary expansion pops a header at EOF. Macro invocation probing sees
that file's EOF so F at header end cannot acquire () from its parent. Directive
readers similarly cannot consume parent lines. A child cannot close a parent's
conditional group. Unclosed child conditionals diagnose then return stable root
EOF; parser must reject its deferred diagnostic. Include filenames/physical
locations remain the child's own, not the root's or a generated spelling view.

## M11l computed include contract

Quoted operands rescan one bounded isolated raw line, using normal macro
operators and no defined-expression handling. Require exactly one resulting
unprefixed quoted token. Relative paths always use the directive source, not
macro spelling/definition sources; generated views never become search roots.
Raw directive token collection preserves individual invocation locations (also
corrected for conditional expression collection). Expanded format recovery must
not drain input again: the next source line is already available for normal
conditional/lexical processing. Raw lexical failures take precedence over
emitting an additional expanded-header format diagnostic.

M11m: preprocess_set_include_directories borrows up to 32 strings/list entries,
configured before input; overflow returns false without changing configuration.
Driver argv owns these strings through compilation. Quote resolution tries the
directive source directory then -I; angle resolution only -I, unless absolute.
Each failed loader candidate is destroyed before retry, and all successful
sources retain existing compilation lifetime. Direct angles bypass expansion;
computed operands remain isolated. Parser/sema/codegen are unchanged. Pipeline
fuzz search uses only memory-backed missing/fallback directories, never disk.

M12a: language token conversion accepts ~ & ^ | << >> (raw pp scanning already
recognized them). Parser maps the Pratt table to existing concrete unary/binary
structs with new operator kinds. Sema loads object operands and validates depth;
only int exists, so integer promotions are identity. Codegen word and/xor/or/shl/
sar follows that typed contract. Undefined C shift inputs are not made defined
by backend masking; the differential suite never executes them.

M12b: parse_integer_spelling in lex.c takes an explicit byte slice and fills
integer_spelling metadata, returning NULL or a static diagnostic message. It
performs no source I/O, allocation, diagnostics or target type selection. Empty
slices need no readable byte. Callers must not use partial output after error.
preprocess.c applies its intmax model; token_from_pp currently rejects suffixes,
and sema retains the signed-int literal bound. AST/ABI interfaces stay unchanged.

M12c: tokens/AST integer leaves retain base/U spelling facts, not inferred types.
Parser stores integer specifier enums separately from semantic type annotations;
common AST headers remain first members. type_new_function copies a return type
and parameter-type array into arena-owned signature records. Sema inserts
concrete conversion nodes, annotates all int/uint expressions and recomputes
depths. Codegen selects signedness only from validated types. int/uint have
identical word storage/call ABI; conversion copies preserve low 32 bits.

M12d: parser disambiguates casts/groups with only the current token after '('.
AST cast specifiers record syntax separately from sema result annotations.
Grouped expressions reuse their existing nodes and shared postfix suffixes;
cast nodes always value-convert operands and are non-lvalues. Their structural
depth includes operand loads. Codegen copies the validated int/uint word; no
parser heuristic or requested-type inference is deferred to the backend.

M12e: primitive integer properties and literal candidate selection are owned by
type.c. Tokens/AST retain L count; parser records long specifiers, sema selects
int/uint/long/ulong and inserts all widening/narrowing conversions explicitly.
Codegen derives w/l from validated types at every value/storage/ABI boundary.
32-to-64 extension follows source signedness, even for an unsigned destination;
all control contexts compare the whole value to zero before word jnz. QBE
shift counts explicitly narrow only after source typing; C-invalid counts remain
undefined, not a guaranteed masked-count extension.

## M12f rank versus representation

Primitive properties distinguish long long/unsigned long long rank 3 from
long/unsigned long rank 2 even though both widths are 64. Compatibility compares
kind; usual conversions compare rank, width and signedness. LL plus unsigned long
therefore converts both operands to unsigned long long, not unsigned long. The
shared literal candidate helper returns these distinct types; the lexer only
decodes base, magnitude and suffix metadata. Existing QBE lowering dispatches on
width/signedness rather than spelling or rank, so no backend change is needed.

## M12g shared character spelling

parse_character_spelling(text,length,&value) consumes only the explicit byte
slice, allocates nothing and returns NULL/static error string. It guards empty/
truncated inputs and yields the target signed-byte value in int64_t, not an
unsigned literal magnitude. Preprocessing selects intmax_t; language tokens carry
a separate character field and ast_character_expression has int type in sema.
The parser still caches one token, and spelling/invocation ownership is unchanged.
QBE emits a signed word constant; existing explicit conversions handle wider use.

## M12h promotions and canonical byte values

type_integer_promotion maps each byte type to int and preserves other currently
implemented types. Sema inserts explicit conversions after lvalue loads and
before usual arithmetic conversion, including each shift operand independently.
Unary ! and logical operands only require scalar truth. Assignment/initialization/
fixed calls/returns convert directly to their exact declared target type. All
inserted nodes contribute to the checked typed-expression depth.

QBE base types (w/l), ABI names (sb/ub/w/l), memory loads and stores are separate
helpers. Every integer temporary is canonical for its semantic type; call results
are normalized at the ABI boundary, even for immediate truth or same-type uses.
Narrow conversions use extsb/extub; widening canonical byte values to long uses
extsw/extuw by source signedness. Byte locals allocate one byte with alloc4
(stronger local alignment); future target layout must not infer type alignment
from that allocation instruction. Plain/signed char compatibility stays distinct.

## M12i halfword extension

Short/ushort have width 16 and rank strictly between byte types and int. Both fit
int and use the same explicit promotion path. QBE ABI, load/store and normalization
helpers cover sh/uh, loadsh/loaduh, storeh and extsh/extuh independently of base
word types. The canonical-value invariant applies across every byte/halfword/word/
long conversion, including call results and assignment expression values. Local
alloc4 2 is stronger than target short alignment 2, not a type-layout API.

## M12j boolean range versus storage

Bool's property width is storage width 8, not a promise that every byte value is
valid. Semantic values are exactly 0/1, and promotion is int. codegen_truth_value
normalizes an already evaluated temporary using its complete source width; casts/
implicit conversions to bool use it without reevaluating operands. Conversely,
codegen_canonicalize discards unspecified upper ABI bits using extub for an ub
result whose valid low byte is 0/1. Never replace either operation with the other.
Exact compatibility distinguishes _Bool from unsigned char; integer literal
candidate selection remains unchanged. C23 boolean literal ASTs are future work.

## M13a type syntax, semantic pointer graph and scalar width

Locals/parameters/casts/function returns reference ast_type_syntax. Concrete
ast_integer_type_syntax stores the specifier enum; ast_pointer_type_syntax
stores a referent child. Every node's location is syntax provenance and its
cached type starts NULL. Sema resolves it once in the compilation arena; a
parameter's synthesized local borrows the same syntax/cache, not a new type.

Semantic pointer_type has struct type first and an immutable referent pointer.
Compatibility descends referents; primitive signedness/rank identity remains
unchanged. Parser enforces 64 pointer layers, independently of expression depth.
type_value_width accepts integer/pointer scalar types; integer width/rank APIs
remain integer-only. Codegen uses l/loadl/storel/alloc8 and l ABI for pointers.

check_conversion permits integer conversions, compatible pointers or pointer to
_Bool only. Unary arithmetic and all binary arithmetic/comparison diagnose
pointers before promotion/opcode helpers; !, logical and control flow accept
scalar truth. Loads/assignment still address named local slots; M13b will add
address/indirection ASTs and general lvalue-address lowering, not a slot shortcut.

## M13b object lvalue addresses

ast_address_expression analyzes its operand without value conversion; an object
lvalue yields pointer-to-its-type. ast_indirection_expression analyzes a pointer
value and yields a referent lvalue. Existing value contexts insert ast_load, with
all new nodes/loads counted in semantic depth. Object pointers remain scalar
referents; function/void/array type categories require explicit later changes.

codegen_address returns an l temporary: copy a named %v slot address or evaluate
an indirection operand once. General assignment and ast_load consume that address,
selecting memory width/sign by the object type. Known initializer/parameter spills
can still target their slots directly. Address computation never implicitly loads
a pointee, preserving &*null cancellation and once-only side effects. Returned
assignment values retain their earlier target-type conversion. No local-slot
encoding is reused as a fake arbitrary memory address.

## M13c compatible pointer equality

Sema handles pointer ==/!= before integer promotion: both operands must be
pointers with recursively compatible referents. Generic binary ASTs retain their
loaded pointer children, checked depth and int result. Backend dispatches pointer
comparison before integer signedness and uses ceql/cnel with word boolean results.
No pointer enters integer width/rank helpers. Integer comparisons are unchanged.

## M13d pointer scaling and typed lowering

The scalar-only target type_object_size API reports storage bytes, independently
of host sizeof, integer rank or local allocation alignment. Sema replaces parsed
binary +/- nodes with separate ast_pointer_offset_expression or
ast_pointer_difference_expression nodes. Operands are already typed/loaded;
shared children are not reanalyzed. Offset integer promotion and every inserted
node count toward typed depth. Offset result preserves the base pointer type;
difference result is target signed long. Parsed nodes remain arena-owned.

QBE widens word indices with extsw/extuw by their promoted signedness, without a
fake semantic cast to long; long indices stay long. Scale by referent object size
then add/subtract the base. Differences signed-divide address byte differences
by referent size. Compatible pointer ordering dispatches before integer property
queries and uses full-width unsigned address comparisons on the flat LP64 target.
The backend does not supply runtime array bounds/lifetime checks. Every operand
is evaluated once, in a C-permitted order, including symmetric integer+pointer.

## M13e postfix subscript lowering

Lexer conversion owns bracket/digraph language-token mapping without changing
pp-token identity. The shared postfix suffix loop accepts calls/subscripts and
checks depth after each suffix; each index enters parse_expression's nesting
budget. Parsed ast_subscript_expression retains left/right syntax children.

Sema analyzes/loads children once, normalizes pointer/index roles with the
factored typed lower_pointer_offset builder, then replaces syntax through its
slot with an indirection lvalue around the offset. The common completion path
checks/annotates that lvalue and inserts a value load only when required. No fake
parsed binary node is built/reanalyzed. Offset/difference semantics are unchanged;
backend needs no new address/load/store path and rejects unlowered subscript ASTs.

## M13f array objects, decay and target layout

Concrete ast_array_type_syntax stores element syntax and a borrowed literal bound
token; the restricted bound grammar is explicit. Cached array_type stores complete
element/count and compares both recursively. type_is_complete_object includes
arrays, enabling inferred pointer-to-array; type_is_scalar/width/rank do not.
Target size multiplication is validated by division before array construction.
Target alignment is independent of stronger QBE local-slot allocation alignment.

Ordinary value completion replaces array lvalues with ast_array_decay_expression,
whose child remains the actual array lvalue and whose result is pointer-to-element.
No scalar load reads array bytes. Address-of suppresses decay; assignment rejects
array targets. Array initialization diagnoses before scalar conversion. General
name/indirection addresses now accept every complete implemented object, while
ABI/load/store helpers still accept only scalar values. Codegen decay simply
computes the child address; slots use target object size/alignment.

Sema counts declared object bytes (parameters included) against the 1 MiB budget,
retains counts across scope exits because all slots allocate at entry, and resets
for each function. Resource limits precede codegen; every decay counts in typed
depth. Source/pp lifetime rules also apply to borrowed array-bound tokens.

## M13g recursive array shape composition

Parser buffers at most 64 opening/bound token pairs in one declarator-local list,
then wraps array syntax right-to-left. This is not a translation-unit token
vector. Each syntax node retains its own diagnostic locations and cache. Existing
recursive array compatibility, checked size/alignment and one-level decay need
no new semantic/backend representation. A matrix decays to pointer-to-row, never
int**; a selected row may decay to its scalar-element pointer for fixed host ABI
calls. Resource accounting includes the recursively computed complete object size.

## M13h byte decoding and static literal objects

A pure bounded parse_byte_escape helper shares existing character escape rules
with parse_string_spelling. The latter measures with NULL output or writes only
within capacity, returning decoded length without implicit NUL; error output is
discarded. Lexer validates/measures on demand and caches string_length. Parser
checks per-literal/TU/count budgets before arena allocation, decodes into owned
bytes, appends NUL and builds concrete ast_string_expression.

Sema registers literals once in unit order with unique object IDs and array-of-
char types/lvalues. Ordinary completion inserts existing array decay. General
address lowering copies $.Lkcc.string.N; QBE emits unexported align-1 byte objects
before functions. Scalar memory/ABI helpers never receive an array. Separate
occurrences are not merged; source-level mutation remains undefined. Object-list
ownership and all source views share the existing compilation lifetime.

Lexer fuzzing checks arbitrary decoder slices, exact capacity guards, byte-octal
roundtrips and cached length. Pipeline fuzzing asserts static object IDs/counts,
array types, terminal NUL, size/alignment and total storage before IL emission.
No generated fuzz program executes.

## M13i adjacent decoded fragments

Parser collects bounded fragment token records in source order, validates sum/
fragment/object/storage budgets, then decodes directly into one arena buffer and
appends one NUL. No intermediate decoded buffers or inter-fragment terminators
exist. Individual lexer validation prevents greedy escapes crossing quotes.
The AST constructor now accepts location/bytes/length, not a fabricated aggregate
token; the first fragment supplies expression provenance. Sema/static-list/codegen
and scalar array decay remain unchanged. Fragment counts are TU-wide and distinct
from resulting object counts. Borrowed include/macro spelling views remain alive
through final decoding, including after include EOF has restored the parent.

## M13j declared versus effective parameters

Parameter syntax retains its resolved declared type. A separate parameter.type
records one-level array-to-pointer adjustment; function signature compatibility
and call conversion use this effective type. Inner row shape survives, outer
count does not. Binding accepts an explicit effective type rather than resolving
the synthesized parameter local back into its declared array. Parameter storage,
address-of and assignment therefore see an ordinary pointer spill. Nonparameter
locals still resolve syntax before the common binding path; normal local name
visibility and initialization order remain unchanged. Codegen consumes the same
scalar spill and call contracts without an array-parameter special path.

## M13k unknown parameter cardinality

AST array syntax explicitly distinguishes has_bound from a present zero token.
A separate incomplete-array constructor records count zero as unknown, requiring
a complete element. Complete-array construction retains its positive-count and
overflow invariants. Complete-object queries exclude unknown arrays; size and
alignment retain their complete-type preconditions. Declared syntax caches the
incomplete type, then parameter adjustment removes exactly its outer array.
Unknown/known array compatibility checks elements recursively; no fake storage
or pointer referent completeness relaxation is introduced.

## M14a object declarator construction

Declaration specifiers build the integer base separately. A parser-local result
holds the current syntax chain and its unfilled base slot. Direct grouping
extends the same result, suffixes append in source order, and prefix stars append
in reverse source order. Finally attach the base once; no unfilled node reaches
sema. Pointer and array syntax retain concrete structs, locations and caches.
The on-demand token stream is never rewound or materialized as a TU vector.

Local/parameter/cast contexts control name and abstract-form legality. Grouping
is bounded separately, while star/dimension counts cover the entire declarator.
Sema checks scalar cast targets before the scalar conversion helper, and checks
pointer referent completeness before its current constructor. Address/decay/
stride/layout and QBE paths operate on the resulting graph without special
parenthesized-expression or pointer-to-row backend nodes.

## M14b incomplete object referents and composite visibility

Object and complete-object predicates are distinct. Pointer construction accepts
object referents, including unknown arrays; array elements and stored local
objects must be complete. Unknown array indirection/address/decay uses existing
lvalue paths without a size query. Offset/subscript lowering checks its referent
completeness before stride calculation; difference lowering checks both sides.
Complete local-address and scalar conversion helpers keep their preconditions.

Recursive type_composite accepts compatible integer/pointer/array/function graphs
and returns an arena-owned merged type without rewriting syntax caches. Known
array counts survive later unknown declarations. Function symbols update their
visible signature after a compatible redeclaration, while definition parameters
retain independently resolved effective types. Prior call arguments remain typed
as analyzed; compatible pointer signature merging does not change their ABI.

## M14c shared specifiers and ordered declaration lists

A declaration group parses one integer base; each derived parser result fills
its own chain around that base. Only immutable specifier syntax/cache is shared.
The parser returns existing local block items in source order, and compound
appending advances through the whole new list. Every local charges an item;
compound non-declaration items charge once, and for-header locals also charge.

The for AST owns a mutually exclusive initializer-declarations list or expression.
Existing list sema/codegen handle all declarations without adding an extra scope.
Binding and initialization retain source order; codegen entry allocation order
does not alter initializer sequencing. Original single-header typed tests were
migrated to the explicit list field and retain their binding/loop assertions.

## M14d unnamed definitions and positional ABI

Each parameter always retains declared syntax and adjusted semantic type. Its
local pointer is NULL for prototypes and unnamed definition parameters; only a
named definition parameter is bound/spilled. Signature emission uses parameter.type,
not the presence of a local. Stores are conditional on the local, but argument
indices always advance. Caller conversion/evaluation still processes every
argument, including arguments unused by an unnamed callee parameter.

## M14e concrete fixed-function syntax

Function suffixes fill the same syntax-chain base slot as arrays. Concrete
ast_function_type_syntax owns return syntax, parameter list/count and cache.
External declaration return/parameter fields are views of its outer function
node. Integer specifiers and one derived parser now serve all declaration/type-
name contexts; external parsing no longer has a separate prefix-star grammar.

After an abstract opening parenthesis, the current specifier/void/closing token
disambiguates a function suffix from grouping without rewind. The shared parser
nesting wrapper covers grouping and nested parameter types; flat function layers
are separately bounded. Sema resolves one cached function graph, adjusts arrays
and checks return/parameter categories before constructing signatures. Composite
symbol graphs do not rewrite syntax caches. Existing fixed call/return QBE paths
need no special array-pointer-return representation.

## M14f designators and calls

Concrete function-designator nodes identify symbols; concrete decay nodes
produce pointers without an object load. A call stores its resolved signature
snapshot and an optional direct symbol only for a pure named designator. Other
callees evaluate exactly once before arguments. Address-of suppresses decay;
&* cancellation forwards its pointer. Function parameters adjust once, keeping
declared syntax separate from effective types. QBE indirect targets and narrow
return canonicalization share the fixed-call ABI. Function referents never
reach object layout or pointer offset helpers.

## M14g real void and effect-only emission

Concrete void syntax resolves to the singleton type_void; object classification
does not imply completeness or scalar representation. Fixed signatures accept
void returns, never void stored parameters. Return AST values may be NULL; sema
checks this against the function return category. Shared conversion checks and
all condition/unary/binary/logical contexts diagnose void instead of asserting.
Indirection of void * is not an lvalue, but address-of's unary-* exception allows
&* cancellation. No void load, slot, size or QBE value type is manufactured.

The factored call emitter accepts an optional output pointer: scalar calls retain
canonical ABI results, void calls produce none. Discard emission routes void
calls, casts and indirections through effect-only paths. Ordinary expression
statements and for-header initializer/step use this path. Function signatures,
explicit returns and void fallthrough omit the QBE result type/value.

## M14h object/void pointer value conversion

A named sema predicate checks both pointer categories and their immediate
referents. It broadens check_conversion, not type_compatible or type_composite.
Assignment-like conversion inserts concrete ast_conversion_expression nodes
with original operands, target types and checked depth. Mixed ==/!= converts
only the object-pointer operand to the existing void-pointer type, then follows
the ordinary compatible-pointer comparison path. Relational comparison does
not take this normalization path. QBE's existing full-pointer-width copy remains
sufficient; no type flattening, dereference, stride or ABI modification is used.

## M14i explicit versus assignment-like conversion

check_cast permits object/object and function/function referent categories only
for explicit cast nodes, then falls back to the existing scalar conversion
constraints. check_conversion, compatibility and declaration composites are not
weakened. Cast operands and concrete syntax caches preserve actual source/target
types and exact typed depth. QBE keeps pointer-width copies with no invented
loads or function adapters. Runtime targets are called only through compatible
function signatures in tests, including both narrow and mixed stack ABIs.

## M19a full expressions versus separator lists

Pratt comma uses powers 0/1; assignment remains 1/1. Calls and scalar
initializers parse at floor 1, while grouped/full expressions use floor 0.
A distinct ast_comma_expression retains both children; sema applies ordinary
value conversion to each, preserves the right type and rejects lvalue use.
Both parse and typed depth use max(children)+1. Scalar codegen discards left,
then evaluates right; void discard recursively discards both, with branch
merges and no fabricated result. Lists still own separator tokens. There is
no TU token buffer, AST flattening or unsequenced argument lowering.

## M14j1 immutable qualification model

Every semantic type header has a qualifier set. type_qualified unions root
qualifiers; type_unqualified clears root qualifiers; both return shared no-op
results or arena-owned concrete copies, NULL on allocation failure. Functions
cannot be qualified. Array constructors inherit element qualifiers, and array
qualification recurses through elements, never pointer referents. Compatibility
is strict; type_unqualified_compatible deliberately ignores only root/equivalent
array qualifiers. Composite reconstruction preserves root pointer qualification
and known-bound array shapes. Consumers must distinguish representation-neutral
qualifiers from source constraints; parser/sema integration is M14j2, not present
in this checkpoint. New type units run under the standard CI sanitizer matrices.

## M14j2 qualified syntax and ordinary values

ast_qualified_type_syntax owns a base syntax and qualifier bits; underlying
pointer referent holes remain in actual pointer syntax. Builtin/star repetitions
share one wrapper per level. Syntax caches retain written qualification. Sema
normalizes function return/signature parameter types, but ast_parameter.type and
its definition local retain adjusted object qualification. Lvalue conversion and
casts strip root qualifiers without altering pointees; initializers target an
unqualified value type, not an unqualified binding. Const lvalue writes reject.

Assignment-like pointer conversion checks immediate qualifier inclusion and
root-unqualified referent compatibility or the object/void rule. Deeper pointer
levels remain strict. Comparisons build real common referent/composite types and
conversion nodes with checked depth. Pointer difference ignores immediate
qualification but checks both referents complete before layout. QBE remains
kind/width-driven; no invalid loads, read-only automatic-storage promise or
function adapters are introduced. Other qualifier bits are not implemented yet.

## M23a1 boolean constants

lex.c maps bool/true/false only at token_from_pp, retaining distinct debug kinds
for bool versus _Bool. Parser constructs ast_boolean_expression with bool value,
location and depth 1. Sema annotates type_bool without integer literal ranking;
ordinary promotions insert explicit conversions as usual. QBE emits canonical
word 0/1, then existing scalar/ABI width rules apply. pp identifiers are not
keywords; defined tests macros, and #if remaining true is handled independently.

## M19b conditional control flow

ast_conditional_expression owns condition/then_value/else_value. Pratt power 2
is below logical-or 3 and above assignment 1; middle floor 0, final floor 2.
Sema checks all operands, ordinary-converts each, computes a real common type,
inserts conversions and recomputes max typed depth. common_pointer_type builds
composite immediate referents with qualifier union after callers validate allowed
categories; no fabricated binary node or deeper pointer covariance. Compatible
comparison snapshots stay unchanged. Scalar QBE uses actual end labels for each
phi arm; void discard branches evaluate exactly one arm without a dummy result.

## M18a unevaluated layout queries

Separate AST structs preserve expression operands versus type syntax. sizeof's
immediate expression is semantically visited with value_required=false, suppressing
only root lvalue/function/array conversion. Children retain normal constraints.
Check complete objects before target layout APIs; result is type_ulong and checked
depth includes the retained typed operand. Codegen emits only precomputed layout
constants. It must never traverse operands or manufacture runtime loads/calls.
alignof spelling is converted after pp expansion, not treated as a predefined macro.

## M18b1 pure constant query

consteval.c accepts only already checked, depth-bounded typed ASTs. Success has
canonical low target-width bits, root type/location and no message. Failures
preserve the located offending node and a static reason, separating not_constant
from invalid arithmetic. Consumers own diagnostics and constant requirements.
Queries allocate nothing and do not mutate ASTs or emit QBE. Skipped operands
retain ICE form constraints without arithmetic; sizeof/alignof do not descend.

## M18b2 assertion declarations

ast_static_assertion owns condition and optional diagnostic-only decoded string;
concrete block/external wrappers own their respective common list headers.
Parser uses conditional floor 2, bounded message concatenation and existing item/
external quotas; a for initializer owns one declaration item, never an expression.
Sema checks in current source-order scope, then queries ICE and diagnoses located
failure. Message rendering is bounded and byte-preserving through escapes. Do not
register diagnostic messages in unit.strings or local slots. Codegen skips the
assertion wrappers entirely; unreachable declarations are still checked by sema.

## M13l1 array-bound and prototype-scope contract

ast_array_type_syntax.bound is an optional expression pointer, never duplicated
has_bound/token state. Parser consumes an assignment-expression at Pratt floor 1.
Sema resolves the element, checks the bound normally and queries consteval;
nonconstant versus invalid arithmetic stay distinct diagnostics. Count bits are
interpreted using the result type's signedness before positive/size checks.
Resolved count/layout and retained typed bound syntax have arena lifetime.
Codegen never visits bound syntax, and parameter adjustment still occurs once.

Function return syntax resolves before parameter scope entry. Parameters resolve
left-to-right; each adjusted name is bound only after its declarator. Temporary
scope links are stack-local and restored on every exit; type-only declaration/
binding ASTs are arena-owned but never linked into runtime locals or assigned
slots. Nested callback scopes cannot leak names. Actual definition parameter
locals are separately created in the body and remain the runtime bindings.

## M13m expression-aware null conversion contract

Sema queries consteval only on checked integer trees, including the operand of
an explicit unqualified void * cast. A pure null-constant predicate never treats
query failure, zero variables or arbitrary pointer values as constants. Existing
conversion nodes retain the operand/target/location and are depth-accounted.
Explicit casts retain their own nodes. Conversion constraints are expression-
aware only for null constants; all other pointer compatibility checks survive.

Equality may normalize a null constant to the opposite pointer type before
common-pointer construction. Relational operators never do this. Conditional
arms preserve arithmetic processing first and choose the other pointer type
before generic object/void common-type rules. QBE's existing extension/copy
path implements the documented all-zero 64-bit target null representation;
there is no new ABI wrapper, pointer bit reinterpretation or optimizer.

## M23a2 nullptr leaf and value contract

Raw pp nullptr remains an identifier; post-expansion conversion yields its own
keyword. A depth-one ast_nullptr_expression resolves to shared immutable
type_nullptr (scalar/object/complete, not integer/pointer). Type helpers handle
this leaf explicitly in qualification, identity, composites and width/layout.
Sema's null-constant predicate recognizes the literal; a separate wrapper also
admits any nullptr_t value for permitted conversion/equality/conditional rules.
Original typed operands survive inside explicit conversion/cast nodes. Equality
between nullptr_t and a null constant lowers both to one void * type; pointer
pairs preserve the opposite pointer's exact type. Conditional nullptr_t/zero is
not accepted. Codegen emits l-width zero and uses existing copy/truth/phi paths.
Consteval is unchanged: nullptr-derived evaluated forms are not integer ICEs;
sizeof(nullptr) is an opaque integer leaf. No additional runtime slot or static
object is allocated. Future type naming must not confuse this type with void *.

## M19c1 prefix update evaluation contract

The parser constructs one concrete prefix node at prefix binding power, with
operand depth plus one. Sema retains its operand as a modifiable lvalue (without
load/decay), records integer promotion or unqualified pointer calculation type,
and obtains stride only after a complete-object referent check. The expression
result has the stored unqualified type and is not an lvalue. QBE obtains one
address and performs one load/store; narrow values canonicalize after arithmetic
and bool compares the promoted result to zero. There is no assignment expansion
or duplicated call/subscript address subtree. Consteval sees a nonconstant form;
sizeof still validates the operand but never executes it. Runtime signed overflow
and invalid pointer range remain C undefined behavior, never curated execution.

## M19c2 old-value update contract

Postfix has its own concrete node and suffix grammar; it is not a prefix mode.
The shared semantic helper checks/updates the one operand slot and records
calculation type/stride while the ordinary completion path checks result depth.
The shared backend helper returns a local previous/current temporary pair after
one address/load/store. Each concrete expression branch selects its own value.
No source ordering guarantee beyond C sequencing is introduced. Both kinds are
nonconstant evaluator forms; opaque sizeof skips all update code generation.

## M19d1 compound assignment contract

+=/-= have their own concrete node, retaining one left lvalue subtree and a
normally evaluated right subtree. Sema records the usual arithmetic type or
complete-object pointer stride; the stored result type is unqualified and not
an lvalue. Integer RHS conversions are explicit nodes. The old left value is
loaded and converted using a value-based backend helper, not a second AST load
or expanded assignment. QBE chooses RHS-first, computes one address, loads once,
arithmetically updates, converts back and stores once. Pointer indices use the
existing signedness-aware extension. No particular operand evaluation order is
promised beyond C. Bool truth conversion examines the whole calculation width.
Consteval rejects evaluated compound forms; sizeof checks but does not emit them.

## M19d2 integer compound calculation contract

The same concrete compound node now supports *= /= %= &= ^= |= <<= >>= without
changing the once-only lvalue/RHS contract. Nonadditive operators forbid pointer
left operands. Integer shifts record promoted-left calculation type and promote
RHS independently; other operators record usual arithmetic type. The backend
uses the existing signedness-aware integer instruction selector and a shared
word shift-count helper. Neither RHS signedness nor its rank silently changes
left shift/right-shift calculation type. Back-conversion is exactly the same
whole-value bool/narrow/scalar conversion path as additive compound assignment.

## M19e1 named-label and consumed-name contract

A consumed identifier selects colon-label versus an ordinary name expression
with one demand peek only. The ordinary path constructs its name once, resumes
postfix then shared Pratt infix parsing, and owns the same bounded expression
recursion frame. No rewind or extra language-token buffer is introduced.
Concrete labels, standalone block label items and secondary labeled statements
are separate. Sema uses a function-local label namespace, independent of object
scopes; duplicates are checked through skipped/unreachable syntax and the
namespace resets between functions. Labels add no local/string object. Codegen
ignores standalone labels and propagates child termination for labeled statements
without goto; a future jump-target change must revisit unreachable traversal.

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
