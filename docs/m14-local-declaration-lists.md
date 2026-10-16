# M14c: comma-separated local declarators (design before implementation)

Implement declaration-specifiers init-declarator { ',' init-declarator } ';' in
compound blocks and declaration-form for initializers. An init-declarator is an
object-declarator optionally followed by '=' assignment-expression. Commas in
nested call argument lists remain inside their expression; the comma operator
and braced initializers remain later work. Parameters already have a separate
comma-list grammar and must not be merged with this one. File-scope declarations
remain fixed function declarations, not global object lists.

Parse integer declaration specifiers once per group. Build each derived object
syntax independently around that shared immutable base, so int *p, a[2], x does
not give a or x p's pointer layer. Reuse M14a's single-pass chain construction;
there is no token replay, fake grouped type, or union AST. Return an ordered list
of existing concrete local-declaration block items. When appending a group to a
compound body, advance the tail through the whole list, not only its first item.

A for statement explicitly owns an initializer-declarations block-item list,
mutually exclusive with its initializer expression. Use existing list sema and
initializer codegen without creating an extra scope: every header declarator is
visible to later header initializers, condition, step and body, but not after the
loop. Existing local binding-before-initializer rules apply in source order.
Later declarators are not prematurely visible; same-group redeclarations remain
constraints. Preserve source locations for each name and initializer.

Charge every concrete local declaration to the existing 4096 function-wide item
budget, including for-header declarations. Compound statements charge their
other block items once; a comma list must not bypass resource accounting. The
256 actual local/spill and 1 MiB storage limits remain separately enforced.
Bounds, completeness, array initializer restrictions and typed expression depth
retain their existing contracts. Codegen still allocates slots at function entry
and executes initializers in source order, including for-header side effects
exactly once before entering the condition.

Tests: all primitive integer leaves, mixed pointer/scalar/array/row-pointer types
in one group, nested shadowing and initializer order, nested call commas,
short-circuit initializers, for-header scope/side effects and nested loops with
break/continue. Typed units check distinct derived chains/shared specifier base,
source-order binding and the complete for-header list; ABI relays exercise values
created by grouped declarations. Reject duplicates, forward references, trailing
commas, repeated specifiers, unsupported comma expressions/array initializers
and incomplete objects. Check 256/257 locals, 4096/4097 concrete item accounting
and storage limits without executing invalid/uninitialized resource fixtures.
Run full regression, both hosts, QBE/reference/ABI, bounded sanitized fuzz,
isolated matrices and exact-source CI. Do not execute arbitrary generated C.
