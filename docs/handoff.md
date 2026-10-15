# Handoff

## Current checkpoint

M08a: Zero-argument functions, prototypes and calls. Branch: development.
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

Ordered external declarations, compatible zero-argument prototypes and multiple int function definitions are supported. Sema installs canonical symbols in source order; calls resolve visible functions, respect local shadowing and reject duplicate definitions. QBE emits each definition independently and direct w-result calls; prototypes emit no IL.

Only int returns and `(void)` signatures. Unsupported: parameters, function
values/pointers, local prototypes, globals, storage classes and preprocessing.
Library units need no main; unresolved declared functions reach the host linker.
Main fallthrough returns zero; non-main filler is not a defined C return value.
Limits: 512 external declarations, 256 functions; per-function 256 locals and
4096 block items. Expression/statement nesting and typed depth remain 128.

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

M08b: int parameter/argument lists and real signature compatibility, ignoring
parameter names. Parameters and root body locals must share one scope. Give
parameters the first local slots; QBE w entry parameters store into these slots.
Keep source-order visibility and named direct calls. Empty () means zero
parameters in C23, not an old-style unspecified-argument function. M08c then
adds recursion runtime cases and bidirectional GCC/Clang ABI tests, including
more than six arguments. See the M08 design in component-contracts.md.

M08a verification: normal GCC, semantic-AST, QBE/reference execution and
ASan/UBSan passed. Sanitized pipeline fuzzing: 349498 inputs in 13 seconds.
