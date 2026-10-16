# M14l2b: C23 typedef declarations in for initializers

Design before implementation. N3096 6.8.5 / 6.8.5.3 and N3220 6.8.6.4 permit a
for-initializer declaration to be a typedef. Do not reintroduce C17's removed
object/storage-class constraint. Reuse the concrete block typedef parser and AST
items for clause-1; publish each alias after its complete declarator, before
parsing the controlling and step expressions and body.

The parser's guarded for wrapper saves/restores the syntax-only alias-list head
on success and failure. Sema_for independently saves/restores the semantic alias
head around its existing loop scope. Thus aliases are visible throughout their
remaining initializer declaration and loop but not after it; a body compound
has its existing nested scope. Nested and successive loops cannot leak aliases.
No object initialization, slot or QBE operation is emitted for a typedef group.
All existing per-function item and expanded alias limits remain; no shadowing
restriction is relaxed in this increment.

Test visibility in bounds, casts, sizeof/alignof, type queries, condition and step,
body declarations and function-pointer calls; nested/sibling lifetime, source
order and exact 4096-item limits. Preserve canonical concrete AST checks with no
alias locals and test 24 both-direction primitive ABI arrangements. Invalid sources
are compile-only, and fuzz only traverses compiler stages, never generated C.

Native reference policy: original GCC 14 sources should compile and execute;
GCC 11, Clang 15 and Clang 18 currently reject even the exact minimal original
for-typedef probe as a non-variable loop declaration. Detect only that probe's
specific sole diagnostic, report the feature gap separately from agreements, and
still run all original kcc/QBE programs and strict native constraints that do not
contain the unsupported grammar. Do not rewrite typedefs into objects or move
aliases outside the loop just to manufacture a native comparison. Full normal/QBE,
both-host targeted ASan/UBSan and bounded fuzz remain required before landing.
