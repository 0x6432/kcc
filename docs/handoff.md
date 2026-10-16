# Handoff

## Current checkpoint

M13h implementation: static ordinary byte strings, fixed multidimensional arrays
and explicit decay/target layout, pointer
subscripts, scaled offsets, signed-long differences and compatible
comparisons, plus concrete address/indirection ASTs and general object lvalue
addresses, with pointer mutation, fixed calls/returns/casts
and scalar truth. Integer/pointer syntax resolves a separate semantic type graph.
All baseline primitive integers, ordinary byte characters, explicit conversions,
on-demand tokens, RDP/Pratt and single-file stages remain intact.
Branch: development. Public repository: https://github.com/0x6432/kcc
Commit identity: 0x42 <noreply@localhost> (repository-local).
Get the exact latest hash with git log -1; avoid a circular self-commit reference.

Latest confirmed exact-source CI: M13g e472687, run 38828318658, passed GCC/Clang
normal/sanitizer and fuzz jobs; M13e/f also passed their exact-source CI.
M13h full normal GCC, both-host new runtime/ABI and bounded sanitizer fuzz checks
passed; full isolated/remote status is recorded chronologically below. Existing
M12h/i/j isolated full matrices have passed; M13 snapshots queue under an
external flock. Logs/snapshots are in /data/tools and /data/validation-* outside the repo.
Check actual logs before claiming completion; older-source passing runs do not
prove a newer source. Lower CPU priority/serial queues do not omit checks.

Next: M13i adjacent ordinary strings, designed in m13-string-concatenation.md.
Null constants, void/functions/full declarators,
general array bounds/initializers, string concatenation/encodings and remaining
C23 features stay unfinished. &*null cancellation
is valid and tested using host-supplied null; actual invalid dereferences are
never executed. Read current limitations, not old checkpoint entries alone.

Working policy: continue across small milestones without asking for approval;
stop only for a real blocker or user interruption. Preserve rigorous regression,
QBE/reference/ABI, sanitizer/fuzz checks and commit/push each tested checkpoint.
Never execute arbitrary fuzz-generated C. Keep credentials ephemeral and outside
the repository. No subagents are authorized.

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

## M12a tested source checkpoint

Runtime signed-int unary ~ and binary & ^ | << >> are implemented across token
conversion, Pratt parsing, concrete AST operators and QBE lowering. Sema retains
explicit lvalue loads and int-only depth checks; the word backend uses and/xor/
or/shl/sar. The parser's BNF and precedence table include the new operators.

GCC full normal regressions/QBE/reference/ABI and 102 full-value operator/model
programs passed; the 102 also passed Clang host/QBE execution. Comparisons inside
C check all 32 result bits, not only process status. Cases cover precedence,
associativity, arithmetic negative right shift, assignments, sequencing, loops,
calls, token paste, typed AST loads and rejection/depth constraints. Undefined
shift inputs are never executed. Sanitized fuzzing passed 25260 lexer and 83847
pipeline inputs (109107 total), 26 seconds each, with no arbitrary C execution.
Full isolated M12a host/sanitizer matrix and exact-source CI are pending.

M11l repair 37857c4 exact-source CI passed run 38812950255. Its isolated local
GCC matrix passed; the local Clang matrix remains in progress. M11m full local
matrix is queued after it and remote CI is still running. M12b shared integer
spelling decoding is designed in m12-integer-spellings.md before implementation.

## M11l repaired checkpoint final verification

37857c4 passed the full isolated GCC/Clang normal + ASan/UBSan matrix with
unit/CLI/oracle and QBE/reference/ABI execution. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38812950255
M11l is complete within its computed-quoted scope. The original 0ffd06c failure
is preserved above; this success belongs to its explicit fixture repair.
M11m and M12a validation remain separate and pending their own matrix/CI checks.

## M12b tested source checkpoint

The pure bounded decoder in lex.c now serves both preprocessing and language
conversion. Runtime unsuffixed decimal/octal/hex/binary/separator literals are
accepted within signed-int range. U/L/LL runtime suffixes and values requiring
wider types remain explicit errors, while preprocessing retains intmax/uintmax.
Its old signed-only integer grammar comment and context-specific spelling
messages were corrected alongside the refactoring.

GCC full normal regressions/QBE/reference/ABI and all shared-decoder units passed
(90 base/suffix combinations, malformed/overflow cases and exact byte slices).
Runtime spelling tests passed 50 GCC host programs plus six separately modeled
legacy separator gaps; Clang accepted all 56 originals. All 56 QBE/model programs
passed with each host, with macro-paste/newline and range-rejection regressions.
Sanitized fuzzing passed 24002 lexer/decoder and 92882 pipeline inputs (116884
total), 26 seconds each, including a pure-decoder uint64 decimal round-trip
invariant. Arbitrary generated C is never executed. Full isolated M12b host/
sanitizer matrix and exact-source CI are pending.

M11m remote CI passed run 38813251318; its local GCC normal/sanitizer matrix
passed, local Clang still running. M12a local GCC likewise passed; local Clang
and exact-source CI still need final verification. M12c unsigned-int types and
explicit AST conversions are designed in m12-unsigned-int.md before coding.

## M11m and M12a final verification

d33f7ae and b80ec53 each passed their full isolated GCC/Clang normal + ASan/UBSan
matrices, including unit/CLI/oracle and QBE/reference/ABI execution. Exact-source
CI passed for M11m run 38813251318 and M12a run 38813971204. Both are complete
within their documented scopes. M12b validation remains independent.

## M12c tested source checkpoint

Signed/unsigned 32-bit int now flows through declaration syntax, literal base/U
metadata, distinct semantic types, generic function signatures and explicit
integer conversion AST nodes. Sema implements usual arithmetic conversions and
destination contexts; shifts retain left type and logical/comparison results
remain int. QBE uses validated types to choose unsigned division, remainder,
comparisons/right shift, while low-word copies implement int/uint conversion.
Common AST headers remain first; type specifiers are separate from annotations.

GCC full normal regressions/QBE/reference/ABI passed. New typed AST tests cover
loads and conversion placement in initialization, assignment, arithmetic, calls
and returns; conversion-only depth overflow is rejected. Both GCC and Clang
passed 130 full-value model/QBE programs and separate-object mixed int/uint ABI
calls in both directions, including high bits and eight arguments. Malformed
specifier/signature/range cases and old diagnostic-provenance regressions pass.
Former U rejection fixtures now use still-unsupported L suffixes intentionally.
Sanitized fuzzing passed 24121 lexer and 85617 pipeline inputs (109738 total),
26 seconds each, with no arbitrary generated program execution. Full isolated
M12c normal/sanitizer matrix and exact-source CI are pending.

M12b exact-source CI passed run 38815061741; its isolated local full matrix is
still running and must be checked separately. M12d explicit int/unsigned casts
are pre-designed in m12-integer-casts.md. Other integer ranks remain absent.

## M12d tested source checkpoint

Explicit int/unsigned casts now have their own concrete AST nodes. Parser
consumes '(' before choosing type syntax or a grouped primary with the shared
postfix suffix helper; the public token cache remains one token. Sema loads and
types cast operands, preserves non-lvalue results and checks structural depth.
QBE copies target word bits; implicit conversion nodes remain distinct.

Full normal GCC regressions/QBE/reference/ABI passed. All 71 new full-value
model/host/QBE programs passed with GCC and Clang, including nested casts,
comparison/division/right-shift signedness, grouped named calls, macro type
specifiers and side effects. Typed cast/load AST checks, malformed casts,
non-lvalue assignments and exact parser/typed-depth boundaries pass. Sanitized
fuzzing passed 25342 lexer and 87518 pipeline inputs (112860 total), 26 seconds
each, without arbitrary generated C execution. Full isolated M12d normal/
sanitizer matrix and exact-source CI remain pending.

M12b/M12c full local verification remains pending independently; M12c remote CI
is still running. M12e LP64 long/unsigned long is designed before implementation
in m12-long-integers.md, including a successful curated QBE width/extension probe.
Do not claim compiler long support until that separate increment is implemented.

## M12b final verification

98b9a03 passed its isolated GCC/Clang normal + ASan/UBSan matrix, including all
unit/CLI/oracle and QBE/reference/ABI checks. Exact-source CI passed:
https://github.com/0x6432/kcc/actions/runs/38815061741
M12b is complete within its recorded spelling scope. M12c/M12d verification
remains separate; do not substitute M12b evidence for those later sources.

## M12e tested source checkpoint

LP64 long/unsigned long now extends declarations, U/L literal candidate typing,
casts, semantic usual conversions and QBE word/long values, memory and calls.
Target width/rank/signedness lives in type.c. Widening uses source signedness;
narrowing preserves low words. Every branch/logical path normalizes the entire
value before jnz, and 64-bit shift counts narrow explicitly only after typing.
Long long and LL suffixes remain intentionally unsupported for the next step.

Full normal GCC regressions/QBE/reference/ABI passed. New type tests cover all
16 usual-conversion pairs, literal candidate identities and widening/narrowing
AST nodes. All 138 full-width model/host/QBE programs passed with GCC and Clang,
including high-only-bit truth in !/logical/if/while/do/for, mixed ranks, recursion,
unsigned wrap and signed division. Mixed word/long eight-argument separate-object
ABI calls, extensions and returns passed both directions with both hosts.
Old L/range rejection fixtures moved to still-unsupported floating numbers or
unrepresentable decimal values, preserving their diagnostic purpose explicitly.
Sanitized fuzzing passed 25253 lexer and 81809 pipeline inputs (107062 total),
26 seconds each, without executing arbitrary generated C. Full isolated M12e
host/sanitizer matrix and exact-source CI remain pending.

M12c exact-source CI passed run 38816221787; local GCC matrix passed, local
Clang remains pending. M12d local GCC likewise passed; Clang/remote still need
final verification. M12f distinct long-long rank and suffixes are designed in
m12-long-long.md before coding. Equal width must not imply compatible types.

## M12c final verification

37d33e9 passed the isolated GCC/Clang normal + ASan/UBSan matrix (including
all QBE/reference/ABI checks). Exact-source CI passed run 38816221787. M12d
exact-source CI also passed run 38817002032, with its local Clang leg still
running at this observation. These are separate source-specific results.

## M12f tested source checkpoint

Long long and unsigned long long now have distinct compatible-type identities
and rank above long, sharing its 64-bit representation. Full six-type conversion
matrix and literal candidates are covered by AST/type units. Same-width long
versus long-long prototypes conflict. LL/ULL runtime suffixes and valid two-long
specifier permutations are accepted; malformed suffixes and three-long remain
errors. Backend width-based lowering is unchanged.

Full normal GCC regressions/QBE/reference/ABI passed. All 93 new full-width
model/host/QBE programs passed with GCC and Clang; mixed-width eight-argument
long and long-long separate-object ABI tests passed both directions with both
hosts. Sanitized bounded lexer/pipeline fuzzing passed (counts below), without
executing arbitrary generated programs. Full isolated M12f GCC/Clang normal/
ASan/UBSan matrix and exact-source CI remain pending. M12g ordinary runtime
character constants are pre-designed in m12-character-constants.md.

M12f fuzz counts: lexer 23668, pipeline 86086 (109754 total), 26/26 seconds.

## M12d final verification / M12e remote verification

66e7c07 passed its isolated GCC/Clang normal + ASan/UBSan matrix, including
QBE/reference/ABI. Exact-source CI passed run 38817002032. 609164f (M12e)
exact-source CI passed run 38818409002; its isolated local matrix remains
pending independently. M12f CI is running at this observation.

## M12g tested source checkpoint

Ordinary character constants now have distinct language tokens and concrete AST
nodes, with int type/non-lvalue semantics. Preprocessing/runtime share a pure
explicit-slice character decoder. All 256 target byte values have octal/hex unit
coverage; 617 printable/escape checks in 44 full-value host/model/QBE programs
passed with GCC and Clang. Macro and pasted-prefix diagnostics retain invocation
locations; source splicing and three line-ending forms pass. Former valid 'x'
rejection became unsupported 'xy', preserving its original lexical boundary.

Full normal GCC regression/QBE/reference/ABI passed, including prior conditional
character oracles. Direct decoder and on-demand stream invariants are fuzzed.
ASan/UBSan bounded fuzzing passed 24619 lexer and 81387 pipeline
inputs (106006 total), 26/26 seconds,
without executing arbitrary generated C. Full isolated host/sanitizer matrix
and exact-source CI remain pending. M12h char types, promotions, canonical byte
values and QBE sub-word ABI are designed in m12-char-types.md before coding;
its curated QBE mechanics probe passed with both hosts, not compiler ABI yet.

## M12f remote verification

619ba96 passed exact-source CI run 38819398360 (GCC/Clang normal and sanitizer
jobs plus bounded fuzz). Its isolated local matrix is queued separately; do not
claim that queued run completed. M12g exact-source CI is still in progress.

## M12h tested source checkpoint

Three distinct byte types now flow through declarations, signatures, casts,
storage and calls. Sema explicitly promotes bytes to int for unary arithmetic
and binary/shift operands. Values remain canonical signed/unsigned words, with
byte ABI return normalization before any use. QBE base types, ABI names and
memory operations are separate helpers; byte locals use alloc4 1.

Full normal GCC regressions/QBE/reference/ABI passed. New 462 width/sign checks
in 69 full-value host/model/QBE programs passed with GCC and Clang. Typed AST
units cover identity, promotion nodes and usual-conversion combinations. Exact
typed-depth 128/129 boundaries, assignment narrowing, macro types, loops and
prototype conflicts pass. Both-direction mixed eight-argument byte ABI and
deliberately dirty upper-return bits passed with both hosts. The first depth
fixture accidentally formed ++ tokens; spacing unary + fixed the test, not the
compiler. No source workaround or relaxed depth bound was introduced.

ASan/UBSan bounded fuzzing passed 23257 lexer and 80030 pipeline
inputs (103287 total), 26/26 seconds,
without arbitrary generated program execution. Full isolated normal/sanitizer
matrix and exact-source CI remain pending. M12i short/unsigned short, inter-rank
conversions and halfword ABI are designed in m12-short-types.md before coding;
a curated QBE mechanics probe passed both hosts, not yet compiler short support.

## M12e final verification

609164f passed the isolated GCC/Clang normal + ASan/UBSan matrix, including
QBE/reference/ABI. Exact-source CI passed run 38818409002. M12f/M12g isolated
matrices are now running separately; M12h is queued behind them. M12g/M12h remote
CI remains pending at this observation.

## M12g remote verification

d4db0ef passed exact-source CI run 38820235372: GCC and Clang normal/sanitizer
jobs plus bounded fuzz all completed successfully. Its isolated local matrix
is still running. M12h remote normal/sanitizer steps remain in progress.

## M12i tested source checkpoint

Short/unsigned short now have 16-bit storage, rank between char and int,
independent promotion to int and canonical halfword values in QBE words.
Valid declaration permutations and short/signed-short identity are supported.
sh/uh ABI results normalize before any use, memory uses halfword operations,
and two-byte locals use stronger alloc4 alignment without changing C alignment.

Full normal GCC regressions/QBE/reference/ABI passed. 700 width/sign checks in
68 full-value host/model/QBE programs passed with GCC and Clang, including all
eleven current integer types, byte/halfword crossings, signed and unsigned
promotions, assignments, returns, shifts, macro types, loops and typed-depth
128/129 boundaries. Both-direction mixed-eight-argument halfword ABI and dirty
upper-return bits passed with both hosts. Existing byte and long tests still pass.
ASan/UBSan bounded fuzzing passed 24007 lexer and 76502 pipeline
inputs (100509 total), 26/26 seconds,
without arbitrary generated C execution. Full isolated host/sanitizer matrix
and exact-source CI remain pending. M12j _Bool is designed in m12-bool-type.md:
whole-value conversion is distinct from discarding unspecified ABI upper bits.
C23 bool/true/false remains planned M23a; _Bool is the next baseline type increment.

## M12h remote verification

76944c4 passed exact-source CI run 38821148738, including GCC/Clang normal and
sanitizer jobs plus bounded fuzz. Its isolated local full matrix remains queued
separately; M12i remote CI is still running.

## M12j tested source checkpoint

_Bool now has distinct type identity, rank below char, storage one byte and
canonical 0/1 values. Explicit value conversion compares the whole source width;
ABI return normalization independently drops unspecified upper bits. Unary/binary
promotions, assignment/init/fixed argument/return conversions and exact signature
compatibility follow the existing typed AST pipeline. C23 keyword/constants are
still planned M23a, not represented with fake int-valued macros.

Full normal GCC regressions/QBE/reference/ABI passed. 418 width/sign checks in
36 full-value host/model/QBE programs passed with GCC and Clang. Tests cover
high-only-bit long and even integers, narrowing-before-bool distinctions,
negative values, assignment normalization, once-only side effects, short-circuit
skips, typed-depth boundaries and invalid specifier/prototype combinations.
Both-direction mixed-eight-argument bool ABI and valid-low-byte/dirty-upper-bit
returns passed with both hosts. The first INT64_MIN fixture incorrectly used an
unrepresentable positive decimal magnitude after unary minus; it now uses the
standard (-MAX-1) expression, without relaxing compiler literal constraints.
ASan/UBSan bounded fuzzing passed 23090 lexer and 79394 pipeline
inputs (102484 total), 26/26 seconds,
without arbitrary generated C execution. Full isolated normal/sanitizer matrix
and exact-source CI remain pending. M13a pointer declarations and concrete type
syntax are pre-designed in m13-pointer-declarations.md; no pointers implemented
at this checkpoint. Local source syntax migration must retain every integer test.

## M12f/M12g final local verification / M12i remote verification

619ba96 and d4db0ef each passed their isolated GCC/Clang normal + ASan/UBSan
matrices, including QBE/reference/ABI. Their exact-source CI also passed runs
38819398360 and 38820235372 respectively. 81db52e (M12i) exact-source CI passed
run 38821949608. M12h/i/j isolated matrices are running independently at lower
CPU priority so foreground implementation/regressions can progress; no tests
were stopped or omitted. M12j exact-source CI remains pending.

## M13a tested source checkpoint

Declarations/parameters/returns/casts now use concrete integer/pointer syntax
nodes; sema caches separate semantic types, including parameter-local reuse.
Pointer compatibility recursively checks referents; scalar width is separate
from integer rank. Pointers use l/loadl/storel/alloc8 ABI/storage and full-width
truth. Unsupported pointer operations/conversions diagnose before integer helpers.

Full normal GCC regressions/QBE/reference/ABI passed, retaining all integer
literal, conversion and exact-depth behaviors after syntax migration. Pointer
AST/type-cache and compatibility units passed. Both GCC and Clang host-driven
live-object ABI tests passed both linkage arrangements, including eight mixed
pointer arguments, pointer-to-pointer identity, null-pointer truth supplied by
the host and compatible casts. All 19 rejection constraints and exact 64/65
pointer syntax bounds pass. No fabricated/dangling/uninitialized addresses were
executed. ASan/UBSan bounded fuzzing passed 21992 lexer and 69401
pipeline inputs (91393 total), 26/26
seconds, without arbitrary generated C execution. Full isolated host/sanitizer
matrix and exact-source CI remain pending. M13b is pre-designed; lvalue access
must become address-based rather than encoding indirection as a local slot.

New isolated matrix jobs use an external flock queue and lower CPU priority;
existing M12h/i/j snapshots finish independently. This scheduling changes no
validation coverage. Logs/snapshots remain outside the repo and may disappear
on a sandbox reset; remote exact-source CI is the persistent evidence.

## M12j remote verification

1735825 passed exact-source CI run 38822838501: GCC/Clang normal/sanitizer jobs
and bounded fuzz completed successfully. Its isolated local GCC normal/sanitizer
leg passed; Clang is running. M13a remote CI remains pending independently.

## M13b tested source checkpoint

Address-of and indirection now have concrete AST nodes, object-lvalue semantics
and general address lowering. Address computation is separate from value loads;
names copy their slot address and indirection evaluates its pointer operand once.
Every scalar object width/sign uses the existing typed memory helpers. &*E never
loads the pointee, preserving valid cancellation even for host-supplied null.

Full normal GCC regressions/QBE/reference/ABI passed. 53 new full-value host/model/
QBE programs passed with GCC and Clang, covering every primitive integer object,
pointer-to-pointer mutation, recursion, assignment conversion and once-only
address/load/store operand evaluation. Both-direction eight-argument host memory
mutation checks verify byte/halfword/word/long/bool/pointer writes, exact address
identity and &*null cancellation. Typed AST tests and exact 63/64 dereference
semantic-depth boundaries pass; syntax's separate 64-layer limit is unchanged.
No invalid/dangling/uninitialized pointer was executed. ASan/UBSan bounded fuzz
passed 20205 lexer and 59948 pipeline inputs (80153
total), 26/26 seconds, without arbitrary generated C execution.
Full isolated normal/sanitizer matrix and exact-source CI remain pending. M13c
pointer equality is pre-designed; existing integer comparison semantics must
remain unchanged and pointers must never enter integer signedness queries.

## M13c tested source checkpoint

Pointer ==/!= requires recursively compatible types and produces int without
integer promotions or pointer signedness queries. QBE compares full-width long
addresses. Full normal GCC regressions/QBE/reference/ABI and 15 new full-value
programs passed; the new suite also passed with Clang. Separate-object live/null
host tests cover both linkage directions, every primitive and deep referent,
once-only calls, assignment results and short circuit. Typed AST units pass.
The earlier now-valid p==p rejection is changed to p&p, a permanent pointer
operation constraint. No general integer-pointer/null-constant conversion added.
Sanitized bounded fuzz passed 22894 lexer + 73861 pipeline inputs (96755 total),
26 seconds each. Arbitrary generated C was not executed. Full isolated matrix
and exact-source CI remain pending; M13d is designed but not implemented yet.
M13a exact-source CI passed 38823808449; M13b run 38824691700 is in progress.

## M13d tested source checkpoint

Sema lowers parsed pointer arithmetic to concrete typed offset/difference nodes,
sharing already analyzed children and explicitly promoting only integer indices.
Object size is target storage size, not host sizeof or ultimate-pointee size.
QBE extends word indices by promoted signedness, scales and adds/subtracts;
pointer differences signed-divide bytes and return target long. Comparisons
use full-width pointer opcodes before any integer property query.

Full normal GCC regressions/QBE/reference/ABI passed. 14 new full-value scalar
programs and both-direction host-array ABI tests passed with GCC and Clang:
all twelve primitive referents plus pointer objects, all integer indices,
signed negative indices, promoted bytes/shorts/bool, signed differences, all six
comparisons, one-past addresses and once-only/short-circuit calls. Unit tests
assert replaced syntax nodes, integer promotion, exact target sizes, long
differences and depth; runtime tests check the 128/129 typed-depth boundary.
The initial unit fixture used a nonexistent ast_function_definition struct name;
it was corrected to the existing ast_function, without changing compiler code.
Earlier now-valid p+1 and p<p rejection fixtures became invalid p*2 and p/p;
no constraint coverage was silently discarded. No invalid pointer program or
arbitrary generated C was executed. Bounded sanitized fuzz passed
24192 lexer + 74272 pipeline inputs (98464 total),
26/26 seconds. Full isolated/remote matrix remains pending.
M12j 1735825 completed both local normal/sanitizer compiler legs, with previously
passed exact-source CI 38822838501. M13e pointer subscripts are pre-designed.

## M13e tested source checkpoint

Parsed subscript ASTs lower to shared typed pointer offsets plus indirection;
ordinary value completion inserts loads, address contexts do not. Factored
pointer-offset construction preserves prior arithmetic checks without fake
binary syntax or analyzing typed children twice. Postfix suffixes alternate
calls/indexing with normal binding, and language brackets include digraphs.

Full normal GCC regressions/QBE/reference/ABI passed. 15 new full-value programs
and both-direction read/write ABI passed with GCC and Clang, covering every
primitive/pointer referent and integer index, symmetric/negative/chained indexing,
assignment results, once-only calls, macros, digraphs and one-past address-only
uses. Typed units prove syntax replacement, explicit promotion, lvalue/load
separation and exact depth. 42/43 chained subscripts test typed 128/131 depth;
deep nested indices separately diagnose parser nesting. Earlier invalid arithmetic
fixtures remain invalid with more precise offset diagnostics; no rejection test
was silently dropped. No undefined pointer program or arbitrary generated C was
executed. Sanitized bounded fuzz passed 23753 lexer + 35805 pipeline
inputs (59558 total), 26/26 seconds.
Full isolated/remote verification remains pending. M13f fixed local arrays,
explicit decay and bounded target layout are designed before implementation.

M12h/M12i 76944c4/81db52e now passed both isolated compiler normal/sanitizer legs,
with prior exact-source CI 38821148738/38821949608. M13b 6f5e5ab exact-source CI
passed 38824691700. M13c/d and queued M13 local matrices remain pending separately.

## M13f tested source checkpoint

Local arrays have concrete literal-bound syntax and cached semantic element/count
identity. Scalar/pointer elements decay explicitly in ordinary value contexts;
address-of preserves pointer-to-array. Array assignment/initialization diagnose
before scalar conversion helpers. Complete-object addressing and independent
target size/alignment support entry storage without an array-as-scalar load.
The 1 MiB declared-object budget includes parameter spills/scopes and resets per
function; each count is division-checked before multiplication. Bounds remain
literal tokens, not a shortcut constant-expression evaluator.

Full normal GCC regressions/QBE/reference/ABI passed. 18 new full-value programs
and both-direction borrowed-array ABI passed with GCC and Clang: all primitive
and pointer elements, loops/scopes, explicit assignment conversions, macro bounds,
decay/calls, pointer-to-array strides, exact target alignment/size/compatibility
and 1 MiB/depth boundaries. Every executed array element was written first; large
limit sources and uninitialized AST fixtures were compile-only. The first runtime
test caught an old scalar-only named-address assertion: it now correctly requires
a complete object, retaining scalar-only ABI/memory-value helpers. GCC 11 lacks
C23 separators: only that known failing fixture uses an explicit 5U host reference
after original 0b1'01U passed kcc/QBE. Clang passed the original source, no gap.
The earlier a[2] rejection became unsupported incomplete a[]; no coverage dropped.
No undefined or arbitrary generated program was executed. Sanitized bounded fuzz
passed 22758 lexer + 72864 pipeline inputs (95622 total),
26/26 seconds. Full isolated/remote checks remain pending.
M13g multidimensional local arrays are pre-designed; all remaining bound,
initializer, parameter/full-declarator and string limitations are explicit.
M13c exact-source CI passed 38825345451; M13a local GCC leg passed independently.

## M13g tested source checkpoint

Parser accepts up to 64 literal-bound dimensions and wraps syntax right-to-left.
Recursive type compatibility/layout and single-level decay handle matrix shape
without new backend shortcuts. Equal byte counts do not imply compatible types;
selected row pointers are not int**. Literal-only bounds and all initializer/
parameter/full-declarator restrictions remain, as does the 1 MiB object budget.

Full normal GCC regressions/QBE/reference/ABI passed. 15 new full-value programs
and both-direction borrowed-row ABI passed with GCC and Clang: all primitive/
pointer leaves, nested loops, three-dimensional matrices, macro bounds, per-row
mutation, recursive decay and row/whole-array strides. Units check source-order
bounds, caches, equal-byte incompatible shapes and explicit two-level decay.
Exact 64/65 dimension, size-product and 42/43 fully indexed depth limits pass.
Large resource and uninitialized AST/depth fixtures are compile-only; executed
array elements are initialized and no cross-row flattened pointer arithmetic or
arbitrary generated C is executed. The earlier a[2][3] rejection became
incomplete a[2][], retaining the constraint test. Sanitized bounded fuzz passed
25173 lexer + 61850 pipeline inputs (87023 total),
26/26 seconds. Full isolated/remote checks remain pending.
M13h ordinary strings/static byte objects are designed; a curated QBE data/private
symbol probe passed both hosts, not yet compiler string support.
M13d 1435382 exact-source CI passed 38826152470. Baseline M12 integer subset
verification is complete; M13 queued local/source-specific checks remain separate.

## M13h tested source checkpoint

Ordinary byte strings now have arena-owned decoded bytes, explicit trailing NUL,
static array-of-char types and unit-ordered private data IDs. Shared bounded byte-
escape decoding retains character semantics; lexer validates/measures without
allocating decoded token buffers. Parser budgets before allocation; sema uses
ordinary array decay/address paths. QBE emits private align-1 byte data with
$.Lkcc.string.N symbols, safe across user identifiers and separate object files.

Full normal GCC regressions/QBE/reference/ABI passed. 12 new full-value programs
passed with GCC and Clang, including 512 all-byte octal/hex checks, empty/embedded/
trailing NUL, static-lifetime repeated calls, greedy escape boundaries, macro
stringizing and splicing. Both ABI directions and two separately compiled kcc
objects pass. Typed array/decay/list units and pure decoder slice/capacity units
pass. Exact 1 MiB/8 MiB/4096/depth limits compile-only; huge objects do not execute.
Four earlier stringizing errors now remain invalid pointer-to-int returns at the
same invocation anchors; lexer/preprocessor conversion tests now expect valid
strings and retain their provenance checks. No literal modification, unrelated
literal subtraction/order, undefined or arbitrary generated program executes.

After adding static object ID/type/size/alignment/NUL/budget invariants to pipeline
fuzzing, the final sanitized bounded run passed 25149 lexer + 74673
pipeline inputs (99822 total), 26/26 seconds.
An earlier additional bounded run also passed before these extra invariants.
Full isolated/remote checks remain pending. M13i adjacent ordinary string
concatenation is pre-designed; prefixes/encodings/initializers are still later.
M13e/f/g exact-source CI passed 38826762420/38827482501/38828318658. M13a b6ba02d
completed both isolated compiler normal/sanitizer legs; M13b GCC leg passed,
with later local legs/snapshots pending independently.
