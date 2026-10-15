# Handoff

## Current checkpoint

M08b: Integer parameters, arguments and signature checks. Branch: development.
Public repository: https://github.com/0x6432/kcc
Commit identity: 0x42 <noreply@localhost> (repository-local configuration).
Each M08 subcheckpoint is committed/pushed after testing. Find the latest exact
hash with git log -1 --oneline; this file avoids a circular reference to itself.

## Resume safely

1. Clone/fetch the public repo; reading needs no credentials.
2. Compare git rev-parse HEAD and git ls-remote origin refs/heads/development.
3. Preserve uncommitted/divergent work; only fast-forward a clean safe checkout.
4. Read architecture, milestones, limitations and component contracts.
5. Run make clean && make test. Build pinned QBE if missing with
   sh scripts/build_qbe.sh tools; then
   make test-codegen QBE="$PWD/tools/qbe-1.2/qbe".
6. Restore Clang/compiler-rt if missing; run make fuzz-lex fuzz-compile.
7. Obtain push authorization separately. Never keep credentials in this repo,
   Git remote URLs, documentation or logs. Commit/push each tested milestone.

## Behavior and invariants

Integer parameter and argument lists are implemented with name-independent function signatures, source-order prototype visibility and argument-count checks. Parameters receive the first local slots and share scope with the outermost body declarations. QBE w entry values are stored into those slots; nested call arguments finish emitting before the call line.

Only int signatures; () means zero parameters (C23), as does (void).
Prototype names optional, definition names required until later C23 work.
Main must have zero parameters. Limit 128 parameters/arguments, 512 external
declarations, 256 functions, 256 parameter/local slots and 4096 block items per
function. Statement/expression nesting and typed depth remain 128. No function
values/pointers, variadics, local prototypes, globals, storage or preprocessing.
Library units need no main; unresolved function declarations reach the linker.

Parser only builds syntax and enforces resource bounds. Sema runs once on a
fresh AST, inserts explicit load nodes and resolves names/loop jump targets.
Scope/loop frames are stack-local and restore parents on errors; arena bindings
retain declarations but never frame pointers. All declarations remain on the
function-local slot list, distinct from scoped lookup. Don't recurse through
initializer or jump-target backlinks: they can create reference cycles.

Codegen uses validated targets, not source name lookup. A terminated block can
be return, break or continue; it does not mean all paths through a loop return.
QBE labels/temporaries have independent counters. Nested logical operands capture
actual predecessor labels for phi. Initializers execute at their source positions,
including each loop iteration, although int storage is allocated at function entry.
Source outlives the AST; destroy the arena before the source.

## Verification/environment

GCC 11.5.0, Clang 15/compiler-rt, Make/Python/Git and QBE 1.2 were used.
Dependencies can vanish on resets; budget 4 GB. GCC sanitizer SONAME lookup may
need the external /data/tools/sanitizer-runtime links and LD_LIBRARY_PATH;
local tests used -fno-pie and -no-pie. Ubuntu CI needs no workaround.

Normal, semantic-AST, ASan/UBSan and QBE/runtime/reference tests passed.
Sanitized fuzzing: lexer: 316096 inputs in 21 seconds; pipeline: 533342 inputs in 21 seconds.
Remote CI is checked after push; do not infer it from local passes.
All executable loop cases are bounded; fuzzing never executes arbitrary inputs.

## Next milestone

M08c: bounded direct/mutual recursion and bidirectional GCC/Clang ABI cases,
including more than six arguments. Use executable defined-C cases, never
unbounded fuzz execution. CI must run host-link tests through test-codegen.
The compiler implementation already permits recursion via source-order symbol
registration before a definition body; add explicit runtime acceptance tests.
Then M09: specify translation phases and on-demand preprocessing token stream
contracts before implementation; don't start full macro expansion at once.

M08b verification: GCC/Clang including reference executables and ASan/UBSan
passed. Sanitized fuzzing: lexer 280937, pipeline 450116 inputs in 16 seconds
each. M08a remote CI passed (run 38714173006); verify M08b after pushing.
