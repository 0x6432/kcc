# M14l1b: same-type file-scope typedef redeclarations

Design before implementation. N3096 6.7p3 permits a non-VM typedef to be
redeclared in the same scope only for the same type. Keep block typedefs,
shadowing and comma declarations deferred; this increment removes only the
unique-name restriction for already supported file-scope aliases.

Add an explicit type_same query beside type_compatible in the type stage.
Both follow normalized immutable semantic types, but same-type array comparisons
require identical counts, including unknown versus known bounds. Compatibility's
array-bound wildcard is not typedef equality. Compare all qualification levels,
pointer referents, function returns and adjusted signature parameters; names and
written top-level parameter qualification are not part of a function type.
A pointer-identity fast path is valid because types are immutable. Keep the
expanded alias node/depth limits before recursive same-type comparisons.

Parser recognizes the prior alias in specifier/declarator disambiguation but
reuses its existing syntax-only name binding. Sema resolves each written syntax
in source order. For a valid same-type redeclaration annotate the new declaration
with the prior canonical immutable alias type without modifying the earlier
syntax cache or adding another alias binding. A different type is a genuine C
constraint, not a subset restriction. Ordinary function/alias namespace collisions
remain checked independently. No composite strengthening or runtime storage.

Test all primitive aliases, qualified pointers/arrays, incomplete arrays, adjusted
function aliases, repeated names and canonical AST identity; distinguish compatible
but nonidentical arrays and nested function/pointer array bounds. Keep 512 external
items, bounded alias shapes, ABI/non-emission and exact syntax/scope subsets.
Use unchanged original sources with strict native GCC/Clang oracles and compile-only
invalid fixtures. Full normal/QBE, both-host sanitizers and bounded fuzz remain
required before landing. Scope-aware aliases are a separate later design.
