# M14l3b: parameter names hiding outer typedefs

Design recorded before implementation, following 966995b. Extend the existing
syntax-only ordinary-name chain to named parameters; do not merely remove the
old parser rejection. No semantic type lookup moves into parsing.

## Lifetimes and point of declaration

- Each function suffix saves the incoming parser name head. Resolve each written
  parameter declarator completely, then publish its name as an object before
  parsing the next parameter. Its own bounds still see the incoming typedef;
  later bounds, sizeof, casts and typeof see the parameter object.
- Restore the incoming head after the closing parenthesis, including failure.
  Nested callback parameters therefore cannot leak into later outer parameters,
  sibling function suffixes, object declarations or the surrounding block.
- Trailing derived return syntax sees the incoming scope, not parameter names.
  Existing sema resolves return syntax before entering its ephemeral prototype
  scope. GCC 11 and Clang 15 compile-only probes must confirm the unchanged rule:
  with typedef long T, int (*f(int T))[sizeof(T)] returns int (*)[8], not [4].
- For a definition only, republish the outer function syntax's named parameters
  around body parsing, then restore file scope on every exit. Do not republish
  names inside callbacks or return-type functions. Parameters and outermost body
  declarations share semantic scope; existing sema diagnoses conflicts.
- The literal sole void marker and unnamed parameters publish nothing. Keep
  parameter-list ambiguity rules: int (T) with a visible typedef T is an unnamed
  function parameter declaration, not a parenthesized parameter name.

## Component interactions and limits

Sema already resolves parameter types left-to-right in ephemeral object scopes
and binds adjusted parameter types after complete declarators. Its nearest-object
barrier hides outer aliases; real definition locals use the resolved effective
parameter types. Keep these paths and captured declaration identities unchanged.
No new AST nodes, lexer buffering, backtracking, aliases-as-locals or QBE slots.
Only named definition parameters allocate runtime locals; prototype names never
do. Function declaration compatibility remains name-independent. Duplicate names
and same-scope body typedef/object conflicts remain errors. Existing 128 parameter,
256 runtime local, nesting, external/item and expanded typedef budgets remain.
Globals, VM types, block function declarations, other storage classes and bare
alias-derived function definitions remain outside this increment. Not full C23.

## Validation plan

Focused original-source programs cover all primitive parameter types; own and
later declarators; adjusted arrays/functions; nested and sibling callback scopes;
trailing return syntax; definitions, recursion, declaration compatibility and
post-definition restoration; body sizeof/casts/typeof and nested block/for scopes.
Check native constraints separately from unsupported VM/subset syntax. Execute
only curated valid programs. Test both-direction mixed-register/stack ABI for all
12 primitive integer types; inspect AST type-only binding versus real-local
identity, captured query bindings, exact 128/129 parameters and 256/257 locals,
and no prototype/typedef storage. Add compile-only lexer/pipeline fuzz seeds.
Run serial normal helper builds before full normal/QBE and modern native suites,
both-host targeted ASan/UBSan and bounded compile-only fuzz on frozen source.
Record actual tools/results and CI status, not assumptions or old snapshot claims.

## Completion evidence

The lifetime plan above is implemented. The GCC 11.5 pre-implementation
compile-only probe and Clang 15.0.7 follow-up both confirmed the stated
trailing-return rule.
Read the M14l3b ledger entry for exact frozen validation, native gap counts,
fixture corrections and CI status. No semantic/type/codegen change was needed;
parameter objects already had the required semantic lifetimes and adjustment.
