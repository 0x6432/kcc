# Handoff

## Current checkpoint

M09b: distinct raw preprocessing tokens and deferred language conversion.
Branch: development. Public repository: https://github.com/0x6432/kcc
Commit identity: 0x42 <noreply@localhost> (repository-local).
M09a remote CI passed: https://github.com/0x6432/kcc/actions/runs/38717250245
M09b is a separate tested commit/push. Get the latest exact hash from git log -1;
this document avoids a circular reference to its own commit.

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
runs explicitly before lexer_init and before any token spelling is borrowed.
It normalizes CRLF/lone CR, then deletes immediate backslash-newline pairs
while traversing original physical units. Do not rescan newly adjacent output.
This precedes comment recognition, so continued line comments and split comment
markers are intentional. No whitespace after backslash splice extension.

Prepared source.data/length and token location.offset/length are logical bytes.
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
Future callers must prepare explicitly; lexer_init asserts this precondition.
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
VT/FF outside comments set has_non_directive_space; M09c must validate it only
in directive separators after # (not before #). EOF and repeat-peek flags are
stable, with no repeated diagnostics.

A stateless token_from_pp performs keyword/int/punctuator conversion. It must
not receive pp_newline; it propagates raw-invalid errors without rediagnosis.
The transitional struct lexer owns raw input, skips newlines and converts lazily
for the existing parser API. Never read the same owned raw input independently
through both streams. The language bridge still rejects #/%: directives. M09c
will replace this adapter with actual preprocessor dispatch. Other stages keep
their grammar and interfaces. --pp-tokens is raw inspection, not -E or compiling.
Its format is physical_offset:kind:logical_length:leading_space:at_line_start:
non_directive_space (one line; final three fields are 0/1). --tokens is unchanged.

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
No directives/macros, other types, pointers/function values, variadics, local
prototypes, globals/storage classes, comma/update/compound-assignment operators.
Partial phases only: no directives, header-name context, encoding/UCNs/BOM,
#line presumed locations or macro provenance yet. Missing terminal newlines
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

M09c: specify and implement preprocess.c ownership, directive line dispatch and
null directives before coding. Reuse raw pp tokens and token_from_pp; do not
reclassify keywords/numbers while lexing. Decide parser-facing next/peek API and
update every driver/test/fuzz caller together. A # or %: introduces a directive
only at raw line start, with comments/splices already accounted for. Check VT/FF
metadata only after the introducing #; null directives may contain comments and
end at a real newline or the documented EOF extension. Unknown/unsupported or
misplaced directives must diagnose and prevent compiler IL. Preserve diagnostics
and one-token lookahead; no TU vector. No macro expansion yet (M10), includes or
conditional sections (M11). Run normal/Clang/sanitizer/runtime/ABI/fuzz checks,
commit/push each tested slice and update this handoff.

M09b local verification passed: GCC/Clang, raw token/conversion/CLI/source/oracle/
AST tests, QBE/reference execution, separate-object ABI and ASan/UBSan.
Final sanitized fuzzing: 106643 lexer (raw plus converted streams) and 466292
pipeline inputs in 26 seconds each. Earlier 21-second runs passed too
(58630/320824). README factorial exits 120 and raw fixture inspection succeeds.
Retained repo build artifacts are under 10 MiB; external dependencies under
70 MiB. Check M09b remote CI after pushing, independently of local results.
