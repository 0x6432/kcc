# Handoff

## Current checkpoint

M02: on-demand lexer, token inspection, regression tests and fuzz CI. Branch: `development`. Repository: `0x6432/kcc`.
Commit identity: `0x42 <noreply@localhost>` (repository-local configuration).
Find the exact checkpoint with `git log -1 --oneline`; this file is committed
with the checkpoint, so it does not embed a circular reference to its own hash.

## Resume after a reset

1. Clone/fetch the public repository without credentials for reading.
2. Compare `git rev-parse HEAD` with `git ls-remote origin refs/heads/development`.
3. Inspect `git status`; do not discard uncommitted work. Fast-forward only when
   the checkout is clean and no divergence exists.
4. Read this file, the milestone ledger, limitations and component contracts.
5. Run `make clean && make test` before continuing.
6. Obtain write authorization separately. Never save tokens in this repo,
   documentation, remote URL or logs.

## Environment

Local GCC: 11.5.0. Make, Python 3 and Git available. Clang 15.0.7 and compiler-rt were installed for local fuzzing. QBE 1.2 built outside the repo for later backend testing. Rebuild it
from the checked release hash if absent; `/data/tools` is not guaranteed to
survive resets. Budget dependencies/builds for a 4 GB sandbox.

## Verification and next action

Normal and ASan/UBSan CLI tests passed locally. The sandbox has sanitizer
libraries in GCC's private directory but lacks their SONAME lookup links;
local tests used external links in `/data/tools/sanitizer-runtime` and
`LD_LIBRARY_PATH` pointing there. Sanitizer compilation used `-fno-pie` and
linking used `-no-pie`. This workaround is not needed on Ubuntu CI.
Remote CI results are
separate from local results; check them after push. M02 GCC/Clang regression tests, ASan/UBSan tests and 197,465 fuzz inputs
passed locally. Next: M03 concrete AST structs, exact subset recursive-descent
parser, independent sema and QBE IL for a single main returning an int literal.
Pratt expression parsing begins with actual operators in M04, not a placeholder. Do not skip to later features.
