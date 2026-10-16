# M14l1: unshadowed file-scope typedef foundation

Design before implementation. Keep the next step small: one unique file-scope
`typedef declaration-specifiers declarator ;` at a time, using existing supported
fixed types. Recognize aliases in later type names, locals/for declarations,
parameters, casts, sizeof/alignof, typeof, arrays, pointers and function signatures.
A typedef denotes the existing immutable semantic type, not a new nominal type.
Function aliases may feed M14k2's semicolon declaration path; bare alias-derived
function definitions remain outside the subset.

This first increment deliberately rejects block typedefs, comma typedef lists,
typedef redeclarations, ordinary declarators shadowing an already visible alias,
other storage classes, initializers and VM/aggregate types. Give explicit subset
diagnostics for valid-but-deferred shadowing/redeclaration cases; never call them
C constraints or silently parse with a stale global alias. Genuine file-scope
ordinary-namespace collisions still require semantic rejection. Full scope-aware
alias shadowing is M14l2, not an accidental claim of this foundation.

Keep raw preprocessing identifiers unchanged. Add the typedef language keyword at
on-demand token conversion. The parser maintains a bounded arena-owned list of
previous successfully declared alias names solely for syntax disambiguation; it
never stores semantic types there. Add a distinct ast_typedef_name_type_syntax
with its source token and a concrete typedef declaration plus external wrapper.
Sema independently resolves aliases in source order, checks ordinary-namespace
collisions and annotates immutable type caches. No typedef emits runtime storage,
parameters, function definitions or QBE instructions.

Do not merely reorder the block-item identifier branch: labels have a separate
namespace, so `typedef int T; ... goto T; T: T x=42;` must work. Consume one
identifier, check for a colon with the existing demand peek, then either keep the
label path or pass the already-consumed alias token into a shared declaration-
specifier/local-declaration tail. Avoid replay, token vectors, a second lexer or
semantic resolution during parsing. Recognize aliases at every existing type/
expression ambiguity, including grouped declarators, casts, sizeof, typeof,
for initializers and block item accounting. Stop treating a visible alias token
as another type specifier once a complete actual type specifier is present;
then the declarator's explicit shadowing guard can diagnose `int T` / `T T`
without corrupting token consumption. Keep qualifiers at the correct type level.

Alias parser/semantic lists cannot exceed the existing 512 external-declaration
budget; no arbitrary new bound is necessary. Preserve source/prototype query
scopes, immutable arrays/functions, main checks, parameter adjustment and shared
function registration. Test type alias/cache identity, declaration order, label
namespace, keyword/macro separation, typedef-versus-expression decisions, all
primitive aliases, arrays/function/pointer aliases, const levels, exact subset/
constraint boundaries, byte budgets, ABI and non-emission. Strict native oracles
must use original source; do not rewrite aliases or execute invalid/fuzz inputs.
Run full normal/QBE, both-host ASan/UBSan, modern C23 oracles and bounded lexer/
pipeline fuzz, update coverage/contracts/handoff and commit/push actual results.


Implementation safety refinement: aliases can encode an exponentially expanded
function-type tree with very little source, unlike previously written tree
syntax. Before publishing an alias, sema caches type-DAG shape metrics by actual
immutable type pointer and rejects expanded type shapes above 4,096 nodes or
128 levels (leaf counts as one). Repeated alias names do not expand those nodes
in memory. These are explicit implementation limits on otherwise valid C, not
compatibility errors. Exact boundaries and repeated branching DAGs must be tested.
Alias-named labels must also charge the existing 4,096 block-item budget after
the identifier/colon distinction; declaration-start prediction alone is not enough.
