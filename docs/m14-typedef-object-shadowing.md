# M14l2e: typedefs hiding outer automatic objects and parameters

Design before implementation. Build on M14l2d's visible-typedef expression guard.
An inner block or for scope may introduce a typedef whose spelling hides an outer
automatic object or parameter. An object/parameter and typedef in the SAME scope
still conflict. A function body's outermost compound shares the parameter scope;
a nested compound or for scope does not. Object declarations hiding typedefs in
the other direction remain explicitly unsupported in this increment.

The parser already publishes typedef names after complete declarators and restores
its scoped syntax classifier on compound/for exit. Sema must reject only a current
scope object collision, not any visible outer local. Resolve the written type
before publishing the alias, so typeof(T) can still inspect an outer object T.
The existing expression-name guard rejects value uses of the hidden object, even
in unevaluated operands and bare calls. Captured addresses and earlier AST name
bindings still refer to the original object; exiting the scope reveals it again.
No object is removed from the function-local storage list or given a new slot.

The typedef-first semantic value guard is sound only because declarations of
objects/parameters hiding visible typedefs are still rejected by the parser.
Do not remove that opposite-direction restriction without unifying scope-aware
ordinary-name classification and semantic lookup. No globals/storage-class/VM/
aggregate/prototype-scope change is part of this milestone.

Test outer local and parameter hiding, same-scope conflicts, captured live-object
pointers, array/function-pointer objects, restored assignments after blocks/loops,
queries resolved before publication and nonexecuted hidden-value rejections.
Verify exact AST declaration/storage identities, independent alias bindings and
unchanged item/type-shape limits. Require four-host original defined programs,
24 both-direction primitive ABI arrangements, existing exact for-typedef native
feature probes, full normal/QBE regression, both-host targeted ASan/UBSan and
bounded compiler-only fuzz before landing.
