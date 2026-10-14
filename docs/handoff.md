# Handoff

## Current checkpoint

M04: integer arithmetic through on-demand lexing, concrete AST structs,
BNF-documented recursive descent/Pratt parsing, sema and QBE IL.
Branch: `development`. Public repository: https://github.com/0x6432/kcc
Commit identity: `0x42 <noreply@localhost>` (repository-local configuration).
M00-M04 are separate commits. Find the exact latest checkpoint with
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

Single `int main(void) { return expression; }`, decimal literals <= INT32_MAX,
parentheses, unary +/- and binary + - * / %. No variables or preprocessing.
Source size: 16 MiB. Pratt recursion and AST structural depth: 128 each.
Compiler emits IL, not assembly/executables. Source spellings outlive all AST
nodes; destroy arena before source. Sema must succeed before codegen.

## Environment and local verification

GCC 11.5.0, Clang 15.0.7 + compiler-rt, Make, Python 3 and Git were available.
QBE 1.2 was built outside the repo. Rebuild dependencies after a reset; `/data`
is not proof that tools/checkouts are current. Budget all builds for 4 GB.

Local GCC/Clang, ASan/UBSan, IL/rejection, QBE executable and differential
arithmetic tests passed. Lexer and pipeline fuzz harnesses completed bounded
sanitized runs without failures; counts are in docs/milestones.md. Tests
cover excessive nesting/flat chains and source-output failure.

The sandbox's GCC sanitizer libraries initially lacked SONAME lookup links.
Local sanitizer tests used links outside the repo in
`/data/tools/sanitizer-runtime` and LD_LIBRARY_PATH pointing there, with
`-fno-pie` compilation and `-no-pie` linking. Ubuntu CI needs no such workaround.

GitHub Actions M00-M03 were observed completed successfully. Check the latest
M04 commit's Actions run separately. A local pass is not a remote-CI result.

## Next milestone

M05: local int declarations, assignment and expression statements. Before
implementation, specify statement lists, declaration AST nodes, parser scope
vs semantic scope, lvalue/rvalue handling, source initialization rules and
QBE local storage. Preserve Pratt parsing; assignment needs right associativity
and a separate AST kind. Add name resolution, shadowing, redeclaration and
read/write runtime tests, plus corpus seeds. Do not skip ahead to loops.
