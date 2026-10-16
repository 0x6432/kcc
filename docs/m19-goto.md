# M19e2: goto targets and reachable labels (design before implementation)

Build on M19e1's distinct block labels and labeled statements. Add demand-language
keyword goto and a concrete ast_goto_statement with the written identifier and a
resolved ast_label target. Parse goto-statement ::= "goto" identifier ";" with
ordinary RDP/BNF comments. Computed goto, case/default/switch, attributes and VLA
scope constraints remain separate unsupported features; never imply support for
GNU label addresses or indirect jumps.

Sema records function-local goto references while checking all statements,
including unreachable ones. After the function body has installed every label,
resolve each reference in that function's separate label namespace. Missing
labels are constraints; ordinary locals/functions or another function's label
cannot satisfy them. Give labels source-order indices and retain the checked
label count on the function for backend target reservation. Bound goto references
to 4096/function explicitly, separate from the existing 512-label limit, object
storage, block-item count and nesting limits. Reset all reference state between
functions. Future variably modified types must add their jump-scope constraint
before claiming VLA support.

Reserve QBE labels 1..label_count for identifier targets and start generated CFG
labels after that range, retaining numeric current-label tracking used by phi
nodes. At each label, terminate an open preceding block with a jump and emit the
reserved target exactly once. Goto emits one direct jump and terminates the block.
A labeled secondary statement emits its target then child and propagates the
child's termination state. Plain block labels resume an open block.

Critically, block traversal must no longer stop at the first terminator: a
forward goto may target a later label, including inside a later branch or loop.
For a non-label runtime item after a terminated block, start a fresh predecessor-
free block before generating it; this preserves nested labels and CFG structure
without inventing a fallthrough edge from a return/goto. Erased static assertions
need no block. Standalone labels after a terminator can emit their target directly.
QBE removes unreachable blocks; a jump into a nested body uses the correctly
nested break/continue codegen context and continues with the enclosing control
flow. Verify QBE accepts unreachable blocks before using this scheme. Do not
perform reachability-based semantic skipping or re-evaluate conditions on an
explicit jump into their bodies. Locals remain allocated at entry, initialized
only when execution reaches their declarations; test sources never use skipped
uninitialized objects or otherwise execute undefined behavior.

Tests cover forward/backward finite jumps, after-return/dead siblings, cross-block
and into-if/while/do/for targets, labels on secondary statements, nested labels
with both branches terminated, correct loop break/continue, function namespace,
C23 block-end/declaration labels, macros/provenance, missing labels even in dead
syntax, target indices and counts, and resource boundaries. Include phi-producing
conditional/short-circuit expressions around targets to catch current-label or
SSA errors. Cross-object fixed-function ABI remains unchanged. Execute only
curated defined programs; never fuzz-generated C. Both-host targeted sanitizer,
full normal/QBE and bounded fuzz must pass before commit/push and handoff updates.
