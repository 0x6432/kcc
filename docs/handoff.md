# Handoff

## Current checkpoint

M06C: Short-circuit logical operators. Branch: development.
Public repository: https://github.com/0x6432/kcc
Commit identity: 0x42 <noreply@localhost>, configured only for this repository.
Find the exact current checkpoint with git log -1 --oneline. Each M06 subcheckpoint is committed separately after tests; this file does not embed its own circular hash.

## Resume after a reset

1. Clone/fetch the public repo (reading requires no credentials).
2. Compare git rev-parse HEAD with git ls-remote origin refs/heads/development.
3. Inspect git status and preserve any uncommitted/divergent work. Fast-forward
   only when safe; never blindly reset to a potentially stale sandbox copy.
4. Read architecture, milestone ledger, limitations and component contracts.
5. Run make clean && make test. Rebuild QBE if absent with
   sh scripts/build_qbe.sh tools, then
   make test-codegen QBE="$PWD/tools/qbe-1.2/qbe".
6. Restore Clang + compiler-rt if needed. Run make fuzz-lex fuzz-compile.
7. Obtain push authorization separately. Never store tokens in the repo, Git
   remote URLs, docs or logs. Commit and push each tested milestone.

## Current behavior and invariants

Distinct logical-expression AST nodes lower &&/|| through conditional branches and phi values. Unary ! and all comparisons normalize int results to 0/1. The emitter records the current block label so nested RHS phi predecessors remain correct. Sema checks skipped operands too; codegen does not evaluate them at runtime.

One int main(void), int locals, arithmetic, assignment and supported statements.
Still unsupported: loops, calls and preprocessing.
Limits: 16 MiB source; expression/statement recursion 128; typed expression
structural depth 128; 4096 block items and 256 locals per entire function.
Uninitialized objects are not zero-filled; tests avoid undefined behavior.

Parser creates distinct node types, never performs semantic lookup. Sema runs
once on a fresh tree and uses the arena for bindings and explicit load nodes.
Scope frames are stack-local; bindings do not retain pointers to scope frames.
All declarations stay on function->locals for slot allocation, but name lookup
uses scopes, not that list. Do not traverse declaration initializer backlinks:
self-initializers can create reference cycles. Sema checks unreachable source.
Codegen relies on validated types/bindings, does not resolve names, and stops
emitting statements after terminators. Source outlives AST; destroy arena first.

## Verification/environment

GCC 11.5.0, Clang 15 + compiler-rt, Make/Python/Git and pinned QBE 1.2 were used.
Dependencies may vanish on reset even when /data retains files. Budget 4 GB.
GCC sanitizer SONAME links may be absent: local tests used external links in
/data/tools/sanitizer-runtime, LD_LIBRARY_PATH, -fno-pie and -no-pie.
Ubuntu CI does not need this workaround.

Normal, sanitizer, semantic AST and QBE/runtime/reference tests passed.
Sanitized pipeline fuzzing: lexer: 339202 inputs in 21 seconds; pipeline: 622309 inputs in 21 seconds.
Remote CI is checked after pushing; local passes are not remote-CI results.

## Next action

M07: while/do/for with distinct statement structs, loop scopes and bounded nesting, explicit break/continue targets, and correct QBE back edges. Do not skip ahead to functions.
