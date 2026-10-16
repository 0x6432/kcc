# M14l2c: nested typedef-to-typedef shadowing

Design before implementation. A typedef declaration in an inner scope introduces
an independent ordinary identifier even if a visible outer typedef has the same
spelling. Resolve its written type before publishing the new binding, so
`typedef T T` refers to the outer T in its declaration specifiers. Within one
scope, repeated typedef declarations still require the same non-VM type, not
merely a compatible type. Do not replace an outer binding or mutate its type.

The syntax classifier only needs to know whether a spelling is a typedef name;
its existing scoped list already answers that question when either declaration
is visible. No new lexer classification, parser lookahead, or grammar is needed.
Sema's binding already carries its scope pointer: apply the redeclaration check
only when the nearest binding belongs to the current scope; otherwise prepend a
new binding. Existing compound/function/for save-and-restore lifetimes reveal
the outer binding again on scope exit. Written syntax caches and resolved types
remain immutable and declaration-local; typedefs still create no local storage.

This increment does not permit typedef/object/function shadowing in either
direction, change parameter/prototype scopes, add storage-class permutations, or
weaken the 4096-node/128-depth expanded-type budgets. Keep those subset diagnostics
separate from same-scope type conflicts and invalid initializers.

Test same- and different-type inner aliases, source order, declaration-list
publication, casts, array bounds, function and pointer aliases, qualified types,
queries, labels, loops and restoration across siblings/functions. Native C23
for-typedef grammar gaps must still be probed and reported exactly, never counted
as agreements. Check concrete AST inner/canonical/outer type identity and no
alias locals; preserve exact shape/item budgets, original-source differentials,
24 both-direction mixed-stack primitive ABI arrangements per host, full normal
and QBE regressions, both-host targeted ASan/UBSan and bounded nonexecuting fuzz.
