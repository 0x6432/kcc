# M14l3a: automatic objects hiding typedef names

Design drafted before implementation; the initial relative-path document write
failed, so this copy is being persisted during isolated testing, before landing.
Build on M14l2e. A local automatic object may hide an outer typedef, including a
file-scope alias. A same-scope typedef and object still conflict. Parameter and
prototype-scope shadowing remain explicitly unsupported: they need a separate
plan for prototype classification lifetimes. No globals, block function
declarations, storage-class permutations or VM types are added.

Replace the parser's typedef-only classifier with a syntax-only ordinary-name
chain: each binding records a token and either typedef or object kind. The first
matching name determines classification. Publish an object after its complete
declarator but BEFORE its initializer; publish each comma declarator independently.
Its own array bounds therefore still see an outer alias, while its initializer
sees the new object. Existing compound and for head restoration must restore both
kinds. Keep on-demand tokens and the existing concrete AST; no backtracking.

Semantic typedef lookup must stop at a nearer ordinary object. Find the nearest
alias, then inspect semantic scopes between the current scope and that alias's
scope for an object with the same spelling. Same-scope alias/object declarations
are constraints, diagnosed before binding a new local. Resolve the written type
before binding its object, then analyze its initializer with that object visible.
Preserve shared declaration-specifier caching: in T T=40,*P=&T the second written
base remains the originally resolved T, while expression T denotes the object.
Alias-first expression diagnostics are sound only with this nearest-scope barrier.
Captured declaration identities and canonical types must remain unchanged.

Test both shadowing directions in nested combinations; point of declaration in
array bounds, initializers and comma lists; casts versus parenthesized expressions;
sizeof/typeof interpretation; loop/block restoration; labels; same-scope conflicts;
and retained parameter limitations. Verify AST object identities/slots and shared
specifier resolution, exact resource bounds, alias-only IL, original defined
programs with four native hosts, 24 both-direction mixed-stack ABI arrangements,
full normal/QBE regression, modern native oracles, both-host targeted ASan/UBSan,
and bounded compile-only fuzz. Invalid and generated C must never execute.
