# M14l2: bounded unshadowed block typedef declarations

Design before implementation. Add a concrete ast_block_typedef_declaration wrapper
around the existing ast_typedef_declaration; block aliases are not automatic
objects or expression statements. Parse typedef groups in compound blocks, with
one shared written specifier base and one charged block item per declarator. Reuse
complete-declarator syntax-name publication and semantic type/shape checks.

Parser compound entry saves the syntax-only alias-list head and restores it on
both success and failure. This makes block aliases visible only from their complete
declarator through the end of that block, including nested blocks, type queries,
casts, declarations, labels and nested statement bodies. Function body aliases
must not escape to the next external declaration. For-initializer typedefs remain
invalid C rather than newly accepted storage classes.

Sema independently scopes alias bindings. Save/restore the alias-list head around
both sema_compound and the separately checked outer function body. Tag alias
bindings with their semantic scope; same-scope same-type redeclarations reuse the
canonical immutable type, while typedef shadowing across scopes remains an explicit
subset restriction in this increment. Block aliases may not hide any visible
object/parameter/function yet: reject same-scope collisions as constraints and
outer-scope hiding explicitly as unsupported. Existing object/parameter declarations
that hide an alias remain unsupported. This prevents type-name/value-name lookup
from silently choosing a hidden ordinary declaration before unified namespace work.

The backend skips block aliases as compile-time-only items. They must not enter
function locals, spill slots, runtime effects or IL. Existing 4096 block-item and
4096-node/128-level alias-shape limits apply; the 512 external-item budget does
not count block aliases. No VLA, aggregate, block function declarations or general
storage-class changes are part of this milestone.

Test block and nested lifetime, sibling reuse with different types, source order,
parameter/body namespace collisions, same-type and different-type redeclarations,
explicit shadowing subsets, C23 alias-named labels before typedefs, casts/layout/
queries/function pointers and exact block/external limits. Verify concrete wrapper
and immutable type identity with no alias locals or strings. Use original strict
native GCC/Clang programs, defined QBE runs and both-direction ABI comparisons;
never execute invalid or fuzz-generated C. Full normal/QBE, both-host targeted
sanitizers and bounded fuzz are required before landing.
