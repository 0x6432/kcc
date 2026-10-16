# M14k2: file-scope query-derived function declarations

Design before implementation. `typeof(int(int)) f;` and `typeof(previous) f;`
are declarations of functions even though their outer written type syntax is a
query, not a function suffix. Parsing must not resolve queries, invent parameter
names, copy another declaration's parameter nodes, or turn a function pointer
object into a function. A function-type query declares a new symbol with that
type, not a linker alias for the operand's function.

Add a separate concrete ast_external_type_declaration for a semicolon-terminated
file-scope declaration whose outer syntax is a typeof/typeof_unqual query (possibly
wrapped in qualifiers). Preserve the original type syntax and name. Sema annotates
its resolved type and function symbol only after successful checking. Ordinary
written function declarators keep ast_function_declaration, their parameter nodes
and their existing function-definition representation. No fake syntax is created.

Resolve the new declaration in source order. Only a semantic function type is
supported in this increment; an object, pointer, array or void retains the explicit
file-scope-object subset diagnostic. Query-derived bare definitions, initializers,
comma-separated external declarations and block function declarations stay out of
scope. The parser still handles one demand token and existing documented RDP/Pratt
rules; add a BNF comment for the small semicolon declaration path.

Extract existing function registration into one helper used by both declaration
forms: main signature checks, function count, compatibility, immutable composites
and redefinition checks must not diverge. Keep definition parameter bindings and
body analysis in the existing definition path. Install definitions before their
body as before, preserving recursion. A query-derived declaration contributes no
body, parameters, locals, QBE definition or alias instruction. Calls/function
addresses use the existing shared function symbol and ABI unchanged.

Test query type-name/expression forms, nested queries, parenthesized identifiers,
zero/real unnamed parameters, adjusted array/function parameters, pointer and
callback results, new-symbol versus operand identity, compatible declarations in
both orders, composite array-bound retention, recursion, declaration visibility,
main checks, constraints and explicit subset boundaries. Add AST identity/cache/
symbol tests, exact original-source native oracles with legacy keyword detection,
24 both-direction primitive-result mixed-stack ABI arrangements, bounded compile-
only fuzz seeds and full normal/QBE plus both-host ASan/UBSan validation. Do not
execute generated fuzz C or invalid curated input. Update limits, contracts,
coverage and handoff; commit/push after actual validation. Typedef names, storage
classes, objects, variadics, VLA and full C23 remain separate increments.
