# M14l1c: file-scope typedef declaration lists

Design before implementation. Accept typedef declaration-specifiers declarator
{ ',' declarator } ';' for the same fixed supported types. Each declarator gets
its own derived syntax around the one written shared specifier base, a concrete
typedef declaration and existing external wrapper. No universal list AST or
synthetic declaration is needed. External next links retain source order.

Publish each syntax-only alias name after its complete declarator, before parsing
the next comma declarator. Later declarators can name it in parameter types,
array bounds/layout and type queries. An alias does not enter its own declarator's
scope early. Sema independently resolves the resulting external chain in source
order, reusing same-type redeclaration and namespace checks. No backend changes.

Translation-unit counting must charge every concrete external declaration, not
every invocation of parse_external_declaration. Pass the remaining external-item
budget into the typedef-group parser; check it before each declarator, so a huge
single group cannot allocate beyond the existing 512-item limit. Preserve exact
single-declaration/function/static-assert budgets and independent alias-shape,
function-symbol, local/item limits. Comma groups do not bypass any budget.

Typedef initializers remain invalid and receive an explicit diagnostic. Block
scope aliases, alias shadowing, other storage classes and VM/aggregate types remain
separate. Test shared specifier versus distinct derived chain identity, intra-group
name visibility and redeclarations, void/function/pointer/array combinations,
ordinary namespace collisions, exact 512/513 group/mixed boundaries, ABI and
non-emission. Compile original valid sources with strict native GCC/Clang; never
execute invalid/fuzz sources. Full normal/QBE, both-host sanitizers and bounded
fuzz remain required before landing.
