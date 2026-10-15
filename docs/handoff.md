# Handoff

## Current checkpoint

M05: local int declarations, name resolution, assignment, expression/empty
statements and explicit lvalue conversions on top of the M04 pipeline.
Branch: `development`. Public repository: https://github.com/0x6432/kcc
Commit identity: `0x42 <noreply@localhost>` (repository-local configuration).
M00-M05 are separate commits. Find the exact latest checkpoint with
`git log -1 --oneline`; this file is committed with the checkpoint, avoiding
a circular reference to its own hash.

## Resume safely after a reset

1. Clone/fetch the public repo without credentials for reading.
2. Compare `git rev-parse HEAD` with
   `git ls-remote origin refs/heads/development`.
3. Inspect `git status`. Preserve uncommitted work. Fast-forward only when the
   checkout is clean and has no divergence; do not blindly reset.
4. Read architecture, milestone ledger, limitations and component contracts.
5. Run `make clean && make test`.
6. If QBE is missing, `sh scripts/build_qbe.sh tools`; run
   `make test-codegen QBE="$PWD/tools/qbe-1.2/qbe"`.
7. With Clang + compiler-rt installed, run `make fuzz-lex fuzz-compile`.
8. Obtain write authorization separately. Never save credentials in the repo,
   docs, Git remote URL or logs. Commit and push each verified milestone.

## Supported subset and limits

Single `int main(void)` with int locals (one name per declaration, optional
initializer), return/expression/empty statements, local names, arithmetic and
simple assignment. Assignment is right-associative and requires an lvalue.
Falling off main returns zero. No nested blocks, shadowing or preprocessing.
Source size: 16 MiB. Pratt recursion/typed AST depth: 128. Block items: 4096.
Locals: 256. These are explicit resource policies. Uninitialized objects are
not zero-filled; reading one may be UB. Runtime tests avoid UB.

Compiler emits IL, not assembly/executables. Source spellings outlive all AST
nodes; destroy arena before source. Sema receives the arena and runs once on a
fresh parsed unit, inserting load nodes and declaration references. Those
references may form cycles through initializers; traverse expression operands,
not declarations' initializer backlinks. Sema must succeed before codegen.

## Environment and local verification

GCC 11.5.0, Clang 15.0.7 + compiler-rt, Make, Python 3 and Git were available.
QBE 1.2 was built outside the repo. Rebuild dependencies after a reset; `/data`
is not proof that tools/checkouts are current. Budget all builds for 4 GB.

Local GCC/Clang, ASan/UBSan, IL/rejection, QBE executable and differential
arithmetic tests passed. Lexer/pipeline fuzz runs completed 272,299/425,201 inputs in 21 seconds
each without failures. Tests also assert typed AST binding/load shape and
resource boundaries; updated diagnostics/self-assignment tests passed normal and sanitizer builds.

The sandbox's GCC sanitizer libraries initially lacked SONAME lookup links.
Local sanitizer tests used links outside the repo in
`/data/tools/sanitizer-runtime` and LD_LIBRARY_PATH pointing there, with
`-fno-pie` compilation and `-no-pie` linking. Ubuntu CI needs no such workaround.

GitHub Actions M00-M04 were observed completed successfully. Check the latest
M05 commit's Actions run separately. A local pass is not a remote-CI result.

## Next milestone

M06: nested blocks/scopes, if/else, comparisons and logical short circuit.
Before implementation, separate semantic scope bindings from function->locals
(which must retain all declarations for codegen), add bounded block nesting,
then build branch labels and terminated-block handling in QBE. Add tests for
shadowing and post-block lookup; do not let an inner local escape its scope.
Logical operators must not evaluate a skipped RHS. All branches are still
checked semantically. Keep the existing load nodes and assignment lvalue rules.
Do not skip ahead to loops, which belong to M07.
