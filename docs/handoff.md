# Handoff

## Current checkpoint

M07C: For loops and complete M07 iteration subset. Branch: development.
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

A distinct for-statement node records optional initializer declaration/expression, condition and step. Initializer declarations are visible in condition/body/step but not after the loop. Continue executes the step before the condition; missing condition means unconditional iteration. All loop kinds preserve scoped local initialization, short-circuit conditions and nearest-loop jump targets.

Unsupported: function calls/prototypes/parameters, comma/update/compound-assignment operators, other types and preprocessing.
One main(void), only int types. ++, comma expressions and compound assignments
are not implemented: use i=i+1 for increments. No zero-fill of automatic locals;
uninitialized reads may be UB. Limits: 16 MiB source, 128 expression/statement
nesting, 128 typed expression depth, 4096 block items and 256 locals/function.

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

M08: integer functions, declarations/prototypes, parameters, calls and recursion. Specify translation-unit function lists, signature compatibility, separate function/local scopes, entry parameter slots and QBE call ABI before implementation.

M08 planning note: parameter names and outermost function-body declarations
must share the correct C scope (do not accidentally allow a parameter to be
redeclared in a newly created outer-body child scope). Reset local/loop contexts
per function and retain real source-order declaration/prototype visibility.
