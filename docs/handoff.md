# Handoff

## Current checkpoint

M10b: zero-parameter function-like macros and token-carried availability.
Branch: development. Public repository: https://github.com/0x6432/kcc
Commit identity: 0x42 <noreply@localhost> (repository-local).
M10b source c3ee142 CI passed: https://github.com/0x6432/kcc/actions/runs/38749074367
M09/M10a are complete for their subsets; M10b zero-parameter calls are done.
M10c fixed arguments/substitution is next; full M10 is incomplete.
Get the exact latest hash from git log -1; this file avoids a circular reference to its own commit.

## Resume safely

1. Clone/fetch the public repository; reading requires no credentials.
2. Compare git rev-parse HEAD with git ls-remote origin refs/heads/development.
3. Preserve uncommitted/divergent work; fast-forward only a clean safe checkout.
4. Read architecture.md, milestones.md, limitations.md and component-contracts.md.
5. Run make clean && make test. If needed, build pinned QBE with
   sh scripts/build_qbe.sh tools, then run
   make test-codegen QBE="$PWD/tools/qbe-1.2/qbe".
6. Restore Clang/compiler-rt if missing; run make fuzz-lex fuzz-compile.
7. Obtain push authorization when needed. Do not put credentials in the repo,
   remote URLs, documentation or logs. Commit/push each tested checkpoint.

## Architecture and interactions

source_load/source_from_bytes still load raw bounded bytes. source_prepare
runs explicitly before pp_lexer_init and before any token spelling is borrowed.
It normalizes CRLF/lone CR, then deletes immediate backslash-newline pairs
while traversing original physical units. Do not rescan newly adjacent output.
This precedes comment recognition, so continued line comments and split comment
markers are intentional. No whitespace after backslash splice extension.

Prepared source.data/length and token spelling offsets/lengths are logical bytes.
Name lookup, types and QBE symbols keep using contiguous logical spelling.
Changed sources own optional physical_data/physical_length plus sparse offset
checkpoints; unchanged sources keep identity offsets without an extra buffer.
Lone CR changes bytes but needs no offset checkpoint. source_physical_offset
binary-searches the map; logical EOF maps to original EOF. Diagnostics use
physical lines/columns with eight-column tabs; --tokens prints physical starts.
Never use physical offsets to index logical spelling data.

Preparation is idempotent and transactional on allocation failure. Call it only
on an initialized source, before any borrowed spellings; destroy frees optional
buffers/maps too. Both fuzz harnesses and every lexer caller were updated.
Future callers must prepare explicitly; pp_lexer_init asserts this precondition.
No full-file token vector or new parser grammar/API was introduced.

M09b adds pp_token/pp_token_kind and pp_lexer in lex.h/lex.c. Raw numbers have
no value, keywords are identifiers, and punctuators use longest spelling first.
Raw quotes recognize ordinary/u8/u/U/L prefixes and escaped delimiters without
interpreting values. Invalid/partial tokens diagnose once and advance. Raw ASCII
other characters are preserved until conversion; UCN/Unicode/header-name context
is not complete. No per-token allocations or TU token vector.

pp_token carries leading_space, at_line_start and has_non_directive_space.
External newlines are explicit tokens and reset line-start state. A block
comment, including internal newlines, is one space; it does not end a directive.
Line comments stop before their newline. leading_space does not include an
already-emitted newline; a macro consumer must handle that explicit token.
VT/FF outside comments set has_non_directive_space; the preprocessor validates it only
in directive separators after # (not before #). EOF and repeat-peek flags are
stable, with no repeated diagnostics.

A stateless token_from_pp still converts raw tokens in lex.c; it must not receive
pp_newline and never rediagnoses pp_invalid. The temporary struct lexer adapter
has been removed. preprocess.c owns raw input and the sole parser-facing next/
peek cache. parse_translation_unit now takes struct preprocessor; every driver/
test/fuzz consumer migrated. No grammar/AST/sema/codegen changes. --tokens shows
language tokens after null removal; --pp-tokens remains raw inspection with its
unchanged physical_offset:kind:logical_length:leading_space:at_line_start:
non_directive_space format (one line, final three fields 0/1).

Only raw #/%: with at_line_start dispatches. Null directives accept space/tab/
comments up to external newline or the documented EOF extension. VT/FF before
# is allowed, after it outside comments fails. That diagnostic anchors the next
token/terminator; its returned error token marks the nonempty directive marker.
Unknown/unsupported/malformed/misplaced directives fail and drain their raw line,
without converting body numbers or keywords. Raw-invalid names retain lexical
locations/diagnostics; distinct lexical errors while draining may add errors.
Repeated peek/EOF never duplicates them. Debug inspection can continue next line;
compilation stops on errors and produces no IL. Null-only streams are accepted
here; the current parser still rejects an empty TU. M10a adds macro state below.

One implementation file per stage, concrete AST structs, on-demand lexer with
one cached token, recursive descent/BNF comments and Pratt expressions remain.
The TU contains an ordered external declaration list; prototypes and definitions
are distinct structs. Each definition references its declaration header. Sema
registers canonical functions in source order before checking definition bodies;
there is no forward hoisting. Prototypes share compatible name-independent types.
Calls resolve visible function symbols, respecting local ordinary-name shadowing.
Bare function values and indirect calls are unsupported.

Each parameter has a semantic local backlink. Parameters receive the first slots
and share the outermost body scope; nested blocks may shadow them. Scoped lookup
is separate from the all-local storage list. Scope/loop contexts restore on
failure and reset between functions. Call/loop/parameter semantic backlinks are
not ownership edges; do not recursively traverse them as AST children.
Sema runs once and inserts explicit lvalue loads, including in call arguments.
Source outlives AST/symbol spellings; destroy the arena before the source.

QBE codegen emits exported int functions with w parameters/results, entry alloc4
slots and stores for parameters. Local initialization stays at source positions.
All argument IL, including nested control flow, finishes before emitting a call
line. Argument lowering is left-to-right, not a C sequencing guarantee. Labels,
temporaries and loop frames reset per definition. Logical phi predecessors use
the actual current block label. A terminated block is not proof a loop returns.

## Supported subset and limits

Int literals/locals/parameters/returns; arithmetic, simple assignment, signed
comparisons, !/&&/||; scoped blocks, if/else, while/do/for, break/continue;
function prototypes/definitions, direct calls and direct/mutual recursion.
C23 () and (void) specify zero parameters. Prototype names optional; definition
names required until later C23 work. Main must take no parameters. Library units
need no main. Declared undefined functions are the host linker's responsibility.
Main fallthrough returns zero. Non-main ABI zero filler is not a promised C
implicit return value. No automatic local zeroing or missing-return warning.

Raw quoted literals and punctuators do not enable their C semantics. Only brace
digraphs are newly accepted language spelling; int-only conversion still applies.
Null/define/undef, object-like and zero-parameter function macros are supported.
No named/variadic macro arguments,
macro operators, other directives, other types,
pointers/function values, variadics, local
prototypes, globals/storage classes, comma/update/compound-assignment operators.
Partial phases only: no header-name context, encoding/UCNs/BOM,
#line presumed locations or full expansion-stack notes yet. Missing terminal newlines
remain an acceptance extension, not strict phase-2 validation. No synthetic
newline is appended. Allocation failures are handled but fault injection is
not yet tested. No full C23 conformance claim. Resource limits: 16 MiB source, expression and
statement nesting/typed depth 128, 512 external declarations, 256 functions,
128 parameters/arguments, 256 parameter/local slots and 4096 body items/function.
Runtime recursion has no added stack guard. Tests execute bounded defined C;
fuzzing compiles arbitrary inputs but never executes them.

## Tests and environment

GCC 11.5.0, Clang 15/compiler-rt and QBE 1.2 were used locally. Dependencies may
vanish after resets; keep artifacts small under the 4 GB sandbox budget. QBE
release/checksum are pinned in scripts/build_qbe.sh. Locally it is available at
/data/tools/qbe-1.2/qbe; do not assume that external path survives a reset.
GCC sanitizer SONAME lookup may need external /data/tools/sanitizer-runtime
links plus LD_LIBRARY_PATH, -fno-pie and -no-pie. CI needs no local workaround.

Tests cover syntax/constraints/AST, runtime/reference execution, source-order
visibility, signature compatibility, parameter/body scopes and resource bounds.
Separate-object ABI cases run both directions with 0/1/2/6/7/8/12/128 arguments,
signed boundaries and cross-compiler mutual recursion. CI selects GCC/Clang as
host compilers and runs executable/ABI tests with sanitized compiler builds too.
M09a adds source/oracle/physical-position regressions to make test and tests
phase-ordering executable behavior under LF/CRLF/CR. A binary corpus seed keeps
intentional NUL/high or CR bytes; ordinary source corpus files use LF. Existing
CI runs all source tests, compiler sanitizers, QBE/reference/ABI and both fuzz
paths. Final local/fuzz results and remote verification follow below.

## Next milestone

M10c: fixed parameters and argument substitution. Read
m10-zero-parameter-macros.md (current), then m10-object-macros.md (historical).
M10b deliberately implements zero-parameter functions only. Specify balanced
raw argument collection, parentheses vs commas, zero vs one empty argument,
parameter-list redefinition, raw/prescanned ownership and per-token availability
BEFORE coding. Do not disable the outer macro too early during nested F(F(...))
argument prescan. Preserve suppressed argument tokens after substitution/rescan.
Decide argument provenance and bounded memory/work for retained/copied tokens,
even unused arguments or many parameter occurrences. Use another small slice
if needed; variadics may follow in M10d, operators/includes/conditions in M11.

Current preprocessor owns arena definitions and fixed replacement frames.
Macro identities are stable indexes through undef/redefine. Each rescan_token
has pp provenance, source-origin flag and a fixed 1024-bit hide set. Object
expansion adds itself to the name set; zero-parameter function expansion
intersects name/closing-delimiter sets then adds itself. M10a's active-frame
suppression is gone. Availability cannot depend on remaining frames after
lookahead pops them. Future arguments require per-token hide-set union.

One pending UNEXPANDED cursor token is separate from language lookahead.
Calls can cross frames/newlines/comments; a later object producing '(' cannot
retroactively invoke an emitted name. Bare function macro names convert normally.
Definition '(' must be adjacent; whitespace after ')' is optional. Function
bodies reject #/##; object marker behavior is unchanged. Only raw source dispatches
directives. Source markers during invocation probing/delimiters explicitly fail,
not execute speculatively. Nonempty arguments reject before any expansion, even
if they would become empty. Invocation errors stop once then latch EOF;
definition errors drain their line and preserve the old binding.

Ownership/provenance is unchanged: destroy preprocessor after AST use and before
source. Raw pp_token.location is spelling, expansion_location outermost call;
language token.location is diagnostic, spelling_location is for text/value reads.
Limits: 1024 names, 1024 tokens/definition, 65536 retained tokens, 128 retained
frames and 65536 work units (pushes + replacement visits). Pending visits are
not charged twice. Completed streams can disappear, so 201 successive calls
need not occupy 201 frames. Work bounds long chains; hide storage is fixed.
Fuzzing checks language-cache reads preserve cursor/pending/frame/work state.
The 198-case token/spelling oracle covers both GCC and Clang. Old resource,
provenance, runtime and separate-object ABI checks remain in place.

Run normal GCC/Clang, stream/source/oracle/AST, QBE/reference/ABI, ASan/UBSan and
both fuzz paths. Clang/compiler-rt vanished on this resume and were restored with
sudo dnf install -y clang compiler-rt; do not assume dependencies persist. Commit/
push each tested checkpoint and update docs. Final M10b local/fuzz results are
recorded below; verify its remote CI independently after pushing.

Diagnostic performance note: line/column lookup rescans physical prefixes;
raw-line draining with many lexical errors can be superlinear. There is no
error-count cap yet. Preserve existing fuzz input/time limits and consider
line indexing/diagnostic caps with M10 resource design, rather than claiming a
large-hostile-input CPU bound from the byte limit alone.

M09c local verification passed: GCC/Clang, directive/cache/EOF/raw/conversion/CLI,
source/oracle/AST, QBE/reference executables, separate-object ABI and ASan/UBSan.
Final sanitized fuzzing: 69628 lexer/preprocessor and 126498 pipeline inputs in
26 seconds each; earlier runs passed (54419/127155 in 21 seconds each).
The null-directive fixture compiles/links and exits 7. Retained build artifacts
were under 10 MiB; external dependencies under 70 MiB. M09c remote CI was
verified successful on resuming M10a (link above).


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
