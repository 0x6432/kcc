# Component contracts

Interfaces are introduced with their implementing milestone, not speculative
empty headers. Any incompatible contract change must identify affected stages
and update their tests in the same checkpoint.

| Producer | Consumer | Contract |
| --- | --- | --- |
| source | lexer/diagnostics | Owned immutable bytes, explicit length, filename and byte locations; EOF is not a sentinel byte in the input |
| lexer | preprocessor/parser | One token per request; slices refer to live source; stable EOF; invalid bytes produce diagnostics and make forward progress |
| preprocessor | parser | Same token API; expanded tokens retain spelling and expansion provenance |
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
