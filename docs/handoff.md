# Handoff

## Current checkpoint

M11a: raw argument stringizing, owned spellings and expanded-pp inspection.
Branch: development. Public repository: https://github.com/0x6432/kcc
Commit identity: 0x42 <noreply@localhost> (repository-local).
Previous M10d final CI passed: https://github.com/0x6432/kcc/actions/runs/38760829356
M09–M10d are complete for their stated subsets. M11a final validation is pending.
Full preprocessing and full C23 remain incomplete.
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
Null/define/undef, object-like and fixed/variadic function macros are supported,
including __VA_ARGS__/__VA_OPT__ and raw parameter #/%:. No #__VA_OPT__, token
pasting, C string expressions, other directives, other
types, pointers/function values, variadic functions, local
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

M11b: #__VA_OPT__ operator interaction. Read m11-stringizing.md first. Decide
how to substitute optional-body parameters without prematurely rescanning the
whole body, remove placemarkers and apply stringizing escaping. The current raw
parameter path must not stringify the unprocessed operator text. Token pasting
is a subsequent checkpoint requiring generated spelling re-lex and placemarker
semantics. Includes/conditions need separately bounded source/evaluation designs.
Do not silently add GNU comma swallowing. M25 still owns predefined provenance.

M10c uses concrete arena-owned macro_parameter, macro_argument and argument_token
records. Definition tokens have parameter_index or SIZE_MAX. Parameter name/order
is part of compatibility. Each invoked fixed macro owns an argument array;
arguments retain raw and lazy cached prescan lists. Empty () is zero arguments
for a zero-parameter macro, one empty argument if parameters exist. Only nested
parentheses protect commas; collect before expansion and check arity first.
Unused arguments are lexed/collected but not macro-expanded.

preprocessor.cursor is the main source cursor. A prescan cursor is temporary
heap storage, with isolated argument input and synthetic EOF: it cannot steal
following source. Prescan does not prematurely add the enclosing macro's hide
bit. Each substituted token unions its own cached hide set with the call base.
Cached tokens are immutable. Frames stream definition tokens or argument tokens;
parameter occurrences inject streams rather than flatten whole replacements.
A separate pending unexpanded token remains distinct from language lookahead.

Source directive LINES during invocation probing/collection still explicitly
fail; inline # is an ordinary argument token and can be discarded. Generated #
never dispatches. Prescan does not convert numbers/keywords to language tokens,
so a later unused parameter can discard unsupported literals. Raw-invalid input
retains lexer diagnostics. Errors/resources stop once then latch EOF; malformed
definitions retain line draining and preserve the old binding.

Ownership/init/destroy APIs are unchanged; destroy preprocessing after AST use
and before source. Diagnostics use the outermost macro call; spelling remains
original. Raw lexical errors retain physical input locations. Future __LINE__/
__FILE__ support must review richer argument provenance, not guess from these
outermost diagnostic offsets. Fixed argument metadata never reaches the C AST.

Limits: 1024 names, 1024 replacement tokens/definition, 65536 retained definition
tokens, 128 retained frames, 65536 work units. New: 128 fixed parameters, 128
argument parentheses, 64 nested prescans, 65536 auxiliary records across parameter
nodes, invocation array entries and raw/cached token copies (including abandoned
attempts). Work includes argument collection/input/copying and injected streams.
No arena reclamation before destroy; temporary cursor malloc/free is paired on
all paths. Fuzz checks main cursor/cache state, auxiliary bounds and prescan
unwind. The oracle now has 374 streams under GCC and Clang; old unit/runtime/ABI
regressions remain. Do not mistake host agreement for full C23 conformance.

Run normal GCC/Clang, stream/source/oracle/AST, QBE/reference/ABI, ASan/UBSan and
both fuzz paths. Clang/compiler-rt vanished on this resume and were restored with
sudo dnf install -y clang compiler-rt; do not assume dependencies persist. Commit/
push each tested checkpoint and update docs. Final M10c local/fuzz results are
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


## M10d implementation checkpoint

Read m10-variadics.md for decisions recorded before coding. Variadic macros
allocate one final argument slot, retain internal raw commas and reuse isolated
lazy prescan. Optional regions are validated/annotated on the flat definition
list and stream through the current replacement frame when selected. Empty
expanded variable arguments suppress them. Definition validation and compatible
redefinition remain transactional. No parser/AST/sema/QBE API changed.

New tests cover omitted/empty/expanded-empty tails, callbacks and rescan across
optional boundaries, suppression, arity/definition/provenance errors and exact
limits. Both fuzz paths have variadic/optional seeds. Final validation evidence
will be recorded below; do not infer passes from this implementation record.


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


## M11a implementation checkpoint

All production stringizing code is in preprocess.c. Arena-owned prepared source
views and byte buffers preserve existing token layouts while allowing non-input
spellings. Both parser language conversion and expanded-pp reads share one cursor;
choose a mode and never bypass pending language lookahead. See the stringizing
design, current limitations and latest component contract before changing this.

New tests cover raw/no-prescan behavior, escaping, empty/variadic arguments,
optional-body operators, transactional definition validation, generated lifetime,
original-call diagnostics, cache/EOF stability and exact single/cumulative 1 MiB
bounds. The expanded-pp fuzz path re-lexes generated strings and checks their
source ownership. Five explicit whitespace-policy groups distinguish host
disagreements from 564 language + 142 expanded-pp agreement streams. Follow-up
ISO interpretation audit is still needed; do not overstate host agreement.
Final local/fuzz and exact-commit remote results will be recorded below.


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
