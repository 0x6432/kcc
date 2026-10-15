# Component contracts

Interfaces are introduced with their implementing milestone, not speculative
empty headers. Any incompatible contract change must identify affected stages
and update their tests in the same checkpoint.

| Producer | Consumer | Contract |
| --- | --- | --- |
| source | lexer/diagnostics | Prepare raw bytes before borrowing; immutable logical spelling slices, explicit length and physical diagnostic mappings; EOF is not an input sentinel |
| lexer | preprocessor | Distinct pp_token on demand, borrowed logical spelling, newline/spacing state, no keyword/value classification; conversion is separate |
| preprocessor | parser | One cached language token, null/define/undef consumed and object/zero-parameter macros rescanned before conversion; separate spelling/invocation locations; errors prevent IL |
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
