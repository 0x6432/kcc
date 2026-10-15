# Handoff

## Current checkpoint

M07B: Do/while loops. Branch: development.
Public repository: https://github.com/0x6432/kcc
Commit identity: 0x42 <noreply@localhost> (repository-local configuration).
Each M07 subcheckpoint is committed/pushed after testing. Find the latest exact
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

A distinct do-statement node executes its body before the condition. Continue targets the condition; break and return bypass it. Body scopes do not leak into the condition. Sema still validates unreachable conditions. QBE emits well-formed condition/exit blocks conservatively without claiming whole-loop reachability inference.

Unsupported: for, function calls, comma/update/compound-assignment operators and preprocessing.
One main(void), only int types. ++, comma expressions and compound assignments
are not implemented: use i=i+1 for increments. No zero-fill of automatic locals;
uninitialized reads may be UB. Limits: 16 MiB source, 128 expression/statement
nesting, 128 typed expression depth, 4096 block items and 256 locals/function.

Parser only builds syntax and enforces resource bounds. Sema runs once on a
fresh AST, inserts explicit load nodes and resolves names/loop jump targets.
Scope/loop frames are stack-local and restore parents on errors; arena bindings
retain declarations but never frame pointers. All declarations remain on the
function-local slot list, distinct from scoped lookup. Don't recurse through
initializer backlinks: self-initializers can create reference cycles.

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
Sanitized fuzzing: pipeline: 395480 inputs in 13 seconds.
Remote CI is checked after push; do not infer it from local passes.
All executable loop cases are bounded; fuzzing never executes arbitrary inputs.

## Next milestone

M07c: for headers with optional declaration/expression initialization, optional condition and step; scope the initializer across the loop only and send continue through the step.
