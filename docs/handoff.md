# Handoff

## Current checkpoint

M11b: optional-operand stringizing with bounded substitution-only cursors.
Branch: development. Public repository: https://github.com/0x6432/kcc
Commit identity: 0x42 <noreply@localhost> (repository-local).
M11b source CI passed: https://github.com/0x6432/kcc/actions/runs/38766305589
M09–M11b are complete for their stated subsets; M11c token pasting is next.
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
including __VA_ARGS__/__VA_OPT__, raw parameter #/%: and #__VA_OPT__. No token
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

M11c: token pasting. Read m11-optional-stringizing.md and m11-stringizing.md.
Design #/## ordering, raw versus expanded operands, left/right empty arguments,
placemarker propagation/removal and optional-body interactions before coding.
Re-lex a synthesized spelling as exactly one pp token; do not source-prepare it
as physical input or accept concatenated multi-token results silently. Preserve
hide-set/provenance ownership and bound retained generated bytes/work. Decide
which small #/## subset to validate first; stringizing inside optional operands
must remain substitution-only until the appropriate operator phase completes.
Includes/conditions need separate bounded source/evaluation designs. No silent
GNU comma swallowing. M25 still owns predefined provenance and the audit gaps.

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


## M11b implementation checkpoint

Read m11-optional-stringizing.md for pre-implementation decisions. The only new
production algorithm is in preprocess.c: selected optional bodies use exclusive
range cursors with parameter/inner-# substitution before ordinary rescan. Normal
frames have a NULL range end. Temporary body copies use existing arena records;
helper cursors are malloc/free pairs, limited to 32 active helpers and restored
to zero on all exits. No AST/parser/sema/QBE change. Empty operands generate "".

New tests preserve 706 previous agreements and add 134 expanded-pp cases, plus
one explicitly non-agreement inactive-argument diagnostic policy. Unit tests
check exact 32/33 nesting without exponential strings, failed-definition recovery,
original call locations, generated lifetime/caches and byte-limit cleanup.
Both fuzz seed paths include nested optional stringizing and discard programs.
Final validation evidence will be recorded below; do not infer it from this entry.


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

## M11c source checkpoint

Implemented ##/%:%: with definition validation, raw argument boundary pastes,
placemarkers, generated token re-lexing, optional-region and stringizing phases.
See m11-token-pasting.md for rationale. No parser/sema/codegen expansion needed;
generated keywords and names flow through existing language conversion.

Local make test, GCC-host QBE/reference execution and separate-object ABI passed.
GCC/Clang oracles each passed 564 language + 444 expanded-pp agreements; one
normative C23 H4 example (legacy GCC disagreement) and five whitespace plus one
inactive-argument diagnostic policy groups are counted separately. Sanitized
fuzzing passed 21801 lexer/preprocessor and 137656 pipeline inputs (159457 total),
26 seconds per target, without executing arbitrary generated code. Exact 32/33
paste nesting and shared 1 MiB spelling boundary tests passed, with counter
cleanup and failed-definition recovery. Full GCC/Clang normal + ASan/UBSan
matrix and source-commit CI are pending and must be recorded after completion.

The user's updated instruction is to continue across milestones without asking
for approval, stopping only for a real blocker or interruption. Next implement
small diagnostic directives, then continue the preprocessing roadmap. Keep
checkpoint pushes and handoff evidence current. Do not claim full C23 coverage.

## M11c final verification and M11d start

The full local GCC/Clang normal and ASan/UBSan matrix completed successfully
before the previous interruption (both MATRIX PASSED lines are in the saved
log). Source commit 66920ed passed remote GitHub CI:
https://github.com/0x6432/kcc/actions/runs/38773969266
No production changes followed that validation. M11c is complete within its
documented scope. M11d diagnostic directives are designed in
m11-diagnostic-directives.md before implementation; validation is not yet claimed.

## M11d tested source checkpoint

#error/#warning implementation, designated diagnostic initialization and separate
warning counts are implemented. GCC make test and QBE/reference/ABI execution
passed. The 1008 inherited macro agreement streams and separately counted policy
cases remain passing. New diagnostic tests cover 48 directive inputs across
three driver modes, LF/CRLF/CR and digraph markers, host preprocessing status,
24 warning-bearing QBE runs, two diagnostics in one compilation, and a long
adjoining-token message. Unit tests check warning/error counts, stable peek,
raw macro spelling, string/number messages, comments, empty/EOF bodies,
physical spliced locations and malformed bodies. Sanitized fuzzing passed 14547
lexer/preprocessor + 89800 pipeline inputs (104347 total), 21 seconds each.
No arbitrary fuzz-generated program was executed.

Full GCC/Clang normal/sanitizer matrix and source-commit CI are pending at this
checkpoint. Validation will use a committed isolated snapshot to avoid racing
continued M11e implementation. The Clang packages disappeared in the sandbox
reset and were restored. Source/documentation are the durable state, not tools.
M11e is designed in m11-macro-conditions.md; no implementation claimed yet.

## M11d final verification

The isolated fce649b snapshot passed the full GCC/Clang normal + ASan/UBSan
unit/CLI/oracle/QBE/reference/ABI matrix. Both MATRIX PASSED records are in
/data/tools/m11d-final-validation.log (the path is a local aid, not durable
source evidence). Exact-source remote CI passed:
https://github.com/0x6432/kcc/actions/runs/38803546331
M11d is complete within its documented scope. The diagnostic input count above
is corrected to 48 inputs, each checked in all three driver modes.

## M11e tested source checkpoint

Macro-existence conditionals and excluded-group filtering are implemented.
GCC make test and QBE/reference/ABI passed. New conditional streams cover 321
host agreements with each GCC/Clang; four explicit C23 alternative cases agree
with Clang but are separately counted as legacy GCC 11 nonagreements. Twelve
new LF/CRLF/CR QBE/reference programs passed. Units cover structural/operand
errors, 128/129 nesting, define/undef effects, excluded directives, EOF and
stable caches. Existing macro/diagnostic suites remain passing.

Initial pipeline fuzzing caught a real boundary bug: deferred EOF diagnostics
could coexist with a non-NULL parser AST. Fixed parse_translation_unit's final
success check, added a direct AST test and minimized conditional-eof corpus seed.
The corrected final sanitizer fuzz runs passed 25799 lexer/preprocessor and
141778 pipeline inputs (167577 total), 26 seconds per target; no generated code
was executed. Do not count the earlier failing run as successful validation.

Full isolated GCC/Clang normal/sanitizer matrix and exact-source CI are pending
at this checkpoint. M11f initial expression design is recorded before coding in
m11-conditional-expressions.md. Active expression #if/#elif remains unsupported
by M11e; includes and full C23 are unfinished. Preserve the EOF/parser contract.

## M11e final verification

Isolated committed snapshot de93224 passed the full GCC/Clang normal +
ASan/UBSan unit/CLI/oracle/QBE/reference/ABI matrix. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38805070048
M11e is complete within its macro-existence scope, including the fuzz-found EOF
parser-success fix and regression. No production changes were made to its
validation snapshot while later milestones were developed.

## M11f tested source checkpoint

Initial #if/#elif evaluation is implemented in preprocess.c, using signed-decimal
64-bit arithmetic and an isolated macro cursor. Literal defined operands are
handled before expansion; remaining identifiers become zero (C23 true/false
are 1/0). Arithmetic checks avoid host UB and logical short circuit suppresses
evaluation, not expansion or syntax checks. Raw reserved variadic identifiers
are rejected consistently, including inside defined operands.

GCC make test and QBE/reference/ABI passed; 540 new host/model agreements passed
with each GCC/Clang, plus eighteen LF/CRLF/CR QBE/reference expression programs.
Units cover precedence, defined/paste/function macros, signed min/max overflow,
zero division, inactive arithmetic, malformed syntax, explicit unsupported
literal/operator cases, and exact 128/129 recursion and 1024/1025 raw-token
limits. Existing tests remain passing. Final sanitized fuzz runs passed 21975
lexer/preprocessor and 96461 pipeline inputs (118436 total), 21 seconds each.
No arbitrary generated program was executed. Earlier exploratory runs are not
included in this final-source count.

Full isolated matrix and exact-source CI remain pending at this source
checkpoint. See m11-conditional-expressions.md for the supported subset and
m11-signed-operators.md for M11g's pre-recorded design. Do not claim unsigned,
nondecimal/character literal, remaining-operator or include support yet.

## M11g tested source checkpoint

Remaining signed preprocessing operators are implemented: ~, shifts, & ^ | and
right-associative ?: with arithmetic short circuit. Negative right shifts follow
the documented target policy using nonnegative host operations. Evaluated left
shifts and counts are checked; conditional branches still parse when unselected.
No runtime C expression/type expansion is implied.

GCC make test and QBE/reference/ABI passed. The expanded expression oracle passed
642 host/model streams with each GCC/Clang. Thirty LF/CRLF/CR expression programs
passed QBE/reference execution. Added exact 127/128 ternary-chain depth boundary
units; inherited arithmetic, raw-token, diagnostic and macro tests remain passing.
Sanitized fuzzing passed 25625 lexer/preprocessor and 123113 pipeline inputs
(148738 total), 26 seconds per target, without executing arbitrary generated C.

M11g full isolated matrix and exact-source remote CI are pending. M11f's longer
isolated matrix/CI also remain pending at this checkpoint; do not mark either
verified before their own results complete. M11h signed integer spellings are
designed in m11-integer-spellings.md before implementation. Unsigned arithmetic,
character constants and include handling remain later work.

## M11f final verification

Committed isolated c52dd27 passed both full GCC/Clang normal + ASan/UBSan
matrices, unit/CLI/oracle tests and QBE/reference/ABI execution. Exact-source CI:
https://github.com/0x6432/kcc/actions/runs/38806159321
M11f is complete within its signed-decimal subset. Later source work did not
modify the validation snapshot. M11g's separate full matrix/CI remains pending.

## M11h tested source checkpoint

Conditional signed integer scanning now separates prefix/base, digit/separator
and suffix validation. Supported bases include octal, hex and C23 binary; signed
L/LL forms and valid C23 separators are accepted up to INT64_MAX. Runtime C
conversion is unchanged. Valid unsigned forms/values still diagnose explicitly.

GCC make test and QBE/reference/ABI passed. Added 94 common literal host/model
agreements with each GCC/Clang and seven independently asserted C23 separator
cases (legacy GCC 11 rejects all seven; Clang agrees). Eighteen new LF/CRLF/CR
literal-selection programs passed QBE/reference execution. Malformed base digits,
prefixes, suffixes/separators and numeric overflow have regression tests. Existing
642 expression, 321 conditional and 1008 macro stream agreement cases remain
passing, with their separately counted normative/policy cases unchanged.
Sanitized fuzzing passed 27905 lexer/preprocessor and 114789 pipeline inputs
(142694 total), 26 seconds each, without executing arbitrary generated programs.

Full isolated matrix and exact-source CI for M11h remain pending; M11g's matrix
is queued/running separately after M11f. Do not call either completed until its
own results are checked. M11i unsigned-value semantics are designed in
m11-unsigned-conditions.md, not implemented at this checkpoint. Use an explicit
value type, retain unselected ternary branch types, and preserve signed checks.

## M11i tested source checkpoint

Preprocessing values now carry explicit uint64 bits and signedness. U suffixes,
large nondecimal constants, intmax/uintmax conversions and wrapping arithmetic
are implemented. Comparisons/logical results are signed; shifts preserve the
left type; ?: derives its common type from both parsed branches even when one
contains unselected arithmetic errors. No runtime C type/AST changes.

GCC make test and QBE/reference/ABI passed. New unsigned tests passed 302
host/model agreements with each GCC/Clang, including 250 modeled value-and-type
binary cases, boundary arithmetic, macro-pasted suffixes and nested ternary/
logical/shift result types. Fifteen LF/CRLF/CR unsigned-selection programs passed
QBE/reference execution. Inherited signed, literal, conditional, macro and
resource tests passed. Sanitizer fuzzing passed 26702 lexer/preprocessor and
106993 pipeline inputs (133695 total), 26 seconds per target, without executing
arbitrary C. A final brace-style-only cleanup was followed by passing unit tests;
full committed-snapshot sanitizer validation still needs separate confirmation.

M11i full isolated matrix and exact-source CI remain pending. M11g remote CI
passed run 38806781592, but its longer local matrix and M11h's full validation
still need final checks. M11j ordinary single-byte preprocessing characters are
designed in m11-character-conditions.md, not yet implemented. Keep signed target
character policy explicit; do not silently extend runtime types or Unicode.

## M11g final verification

Isolated a934115 passed the full GCC/Clang normal + ASan/UBSan unit/CLI/oracle
and QBE/reference/ABI matrix. Its exact-source remote CI also passed:
https://github.com/0x6432/kcc/actions/runs/38806781592
M11g is complete within its signed-operator scope. M11h/M11i later source
checkpoints retain their independent pending validation status until checked.

## M11j tested source checkpoint

Ordinary preprocessing characters now decode single ASCII bytes and standard
simple/octal/hex escapes. Numeric escapes are checked to 0..255 and mapped via
the chosen signed plain-char target policy. Empty/multicharacter, prefixes,
non-ASCII source bytes, universal names and unknown escapes remain explicit
rejections. No C runtime char type or general encoding support is implied.

GCC make test and QBE/reference/ABI passed. New character tests passed 126
chosen-target host/model agreements with each GCC/Clang, including printable
ASCII, all simple escapes, numeric boundaries/sign extension, unsigned/ternary
conversions and macro expansion/identity pasting. Twelve LF/CRLF/CR character
selection programs passed QBE/reference execution. Invalid/unsupported literal
forms diagnose even when unselected. Sanitizer fuzzing passed 26062 lexer/
preprocessor and 106415 pipeline inputs (132477 total), 26 seconds each, without
executing arbitrary generated code. All inherited suites remain passing.

M11j full isolated matrix and exact-source CI are pending. M11h source CI passed
run 38807421895; its local matrix and M11i full verification still need final
checks. M11g local/remote verification is complete as recorded above.
M11k direct quoted includes are designed in m11-quoted-includes.md before coding;
loader/source ownership and fuzz-safe memory-only loading are required. Do not
claim include support, header search paths or full C23 at this checkpoint.

## M11h/M11i final verification

Isolated snapshots 26e27e4 and 0e0a0db both passed full GCC/Clang normal +
ASan/UBSan unit/CLI/oracle and QBE/reference/ABI matrices. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38807421895
https://github.com/0x6432/kcc/actions/runs/38808207982
M11h/M11i are complete within their documented integer subsets. M11j remote CI
also passed run 38809079871, but its separate local matrix was still running
when this entry was written. Keep that distinction explicit.

## M11k tested source checkpoint

Direct quoted includes now use an explicit loader, resolve relative to the
including source or use an absolute path, retain child source buffers until
preprocessor destruction, and share macro state. Conditional bases prevent
cross-file groups. Raw directive readers and macro invocation lookahead see
file EOF; only ordinary expansion resumes the parent. A GCC/Clang audit found
and fixed the initial boundary mistake where header F acquired parent ().
The header EOF regression also rejects incomplete macro calls across files.

GCC make test and QBE/reference/ABI passed. Ten include pp streams agree with
each host, including all nine root/header newline combinations and the macro
EOF boundary. Nine nested-header programs passed QBE/reference execution;
absolute paths, missing final newlines, guards, skipped loads, malformed names,
load errors and original/spliced child diagnostics are covered. Unit memory
loaders check retained spellings, conditional isolation and stable root EOF,
32/33 active-depth and 128/129 attempt limits, 4095/4096 path bytes, plus actual
four 16 MiB child loads at the 64 MiB byte budget and a rejected fifth load.

Sanitizer fuzzing passed 27441 lexer/preprocessor and 107479 pipeline inputs
(134920 total), 26 seconds per target. Pipeline includes are memory-only: requested
paths never reach the filesystem, while arbitrary header bytes, loader failures,
recursion and successful prototype-only units exercise the new boundaries. No
arbitrary generated C is executed. The lexer fuzz preprocessor remains loader-
disabled, preserving its root/generated-spelling provenance assertions.

Full isolated M11k matrix and exact-source CI are pending. M11j source CI passed,
but its local matrix still needs its final result checked. M11l macro-computed
quoted operands are designed in m11-computed-includes.md before coding. Anchor
relative search to the directive source (not generated/header-definition spelling
sources) and never drain the next source line after isolated operand validation.
No angle/system/-I support or complete C23 claim is made yet.

## M11j final verification

Isolated 73b76f8 passed the complete GCC/Clang normal + ASan/UBSan matrix,
unit/CLI/oracle and QBE/reference/ABI execution. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38809079871
M11j is complete within its ordinary-character scope. M11k verification remains
independent and pending until its own matrix/CI results are checked.

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

## M11m tested source checkpoint

Bounded explicit include search and direct/computed basic angle names are
implemented. Direct angle identifiers never expand, while computed operands
retain isolated rescanning. One logical include can try 33 candidates; failed
candidate buffers are destroyed, and successful source ownership is unchanged.
The driver and oracle accept ordered attached/separate -I options in all modes.

Full normal GCC regressions, QBE/reference/ABI, targeted GCC ASan/UBSan units,
and 39 new header streams with each of GCC/Clang passed. All 39 new QBE/host
programs passed. Tests include quote/angle ordering, nested search, filename
spaces, direct-macro collisions, absolute and empty-directory behavior, 32/33
directories, actual 33-candidate cleanup, lexical subset errors and diagnostics.
Sanitized fuzzing passed 25488 lexer and 92079 memory-only pipeline inputs
(117567 total), 26 seconds each, without executing arbitrary generated programs.
Full isolated M11m host/sanitizer matrix and exact-source CI are pending.
M12a signed-int operators are designed in m12-integer-operators.md before coding.
