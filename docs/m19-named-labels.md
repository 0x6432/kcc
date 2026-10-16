# M19e1: named labels before goto (design before implementation)

Implement identifier labels first as a small control-flow foundation, without
claiming goto/case/default/switch support. N3096 6.8.1/6.8.2 distinguishes standalone
block-item labels from labeled statements: a compound block label is translated
as if followed by a null statement, allowing labels before declarations or at a
block end. A secondary labeled statement still requires a following statement.
Use separate concrete ast_label, ast_block_label and ast_labeled_statement types;
do not force declarations into statement nodes or synthesize a runtime scope.

Retain one-token demand lookahead. At the beginning of a block item or statement,
consume an identifier once and inspect the next token. Colon selects a label;
otherwise construct the already consumed name and resume postfix/Pratt suffix
parsing. Extract the existing Pratt infix continuation without changing binding
powers or losing parser recursion/depth accounting. No rewind, second token
buffer or pretokenized translation unit. Add subset BNF comments for the new
identifier-leading alternatives and expression continuation.

Function-wide labels occupy their own namespace, independent of parameters,
locals and function names. Sema checks duplicates even in unreachable/constant
skipped statements. Store arena-owned function-local label bindings using exact
token spelling comparisons (including macro provenance). Label declarations have
no storage or type. Set an explicit 512-label/function resource limit, distinct
from duplicate-label C constraints, and retain statement nesting/block-item
limits. A labeled secondary statement checks its child in the existing scope;
it must not hide ordinary object bindings. Reset the label namespace per function.
No VLA/jump constraint is claimed because goto is not implemented yet.

Labels alone do not change control flow. Codegen ignores standalone block labels
and emits the child of a labeled statement, propagating its termination result.
No fabricated QBE target or unreachable traversal is needed in this increment.
The next goto milestone will assign targets and retain reachable labels after
terminators, including inside nested branches/loops; do not pretend that old
stop-at-return code can already support forward goto.

Test ordinary/chained labels, labels on if/loop/block/return/break/continue,
separate function scope and ordinary namespace, macro spelling and provenance,
missing child/colon, duplicates in disjoint/constant-skipped/unreachable scopes,
exact nesting and 512/513 resource limits, and zero extra runtime/local/string
objects. C23 declaration/end-block labels are tested on original source; if a
legacy host rejects exactly that grammar, label it as a host grammar gap instead
of rewriting source and claiming native agreement. Keep strict native evidence
for ordinary label programs separate. No goto executed or claimed supported.
Run full normal/QBE, both-host targeted sanitizer tests and bounded fuzz, then
commit/push with limits/coverage/contracts/handoff updated.
