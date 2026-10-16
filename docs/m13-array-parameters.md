# M13j: literal-bound array parameter adjustment (design before implementation)

Accept the existing positive literal-bound array suffixes after optional parameter
names, including unnamed prototypes. General bounds, empty/incomplete dimensions,
static/qualifier syntax and full parenthesized declarators remain separate work.
Reuse the bounded source-order dimension parser, not a second declarator grammar.

Keep the declared array syntax and its cached semantic array graph intact. Add
an effective type field to ast_parameter: the outer array declaration adjusts
to pointer-to-element, exactly one level. Scalar/pointer parameters keep their
resolved type. Function signatures, compatibility, calls and parameter spills
use this effective type. Outer bound differences do not change a function type;
inner row shapes do. A matrix parameter is pointer-to-row, never int**.

Separate ordinary local syntax resolution from local-object binding. A binding
helper accepts an already resolved effective type, preserves syntax provenance,
allocates/accounts its actual local slot and analyzes initializers after binding.
Ordinary locals call it with their resolved declared type; synthesized parameter
locals call it with the parameter's adjusted type. Never mutate the declared
array syntax cache to a pointer or silently re-resolve the adjusted spill as an
array. Existing integer/pointer cache reuse invariants must remain valid.

Only actual effective parameter object bytes count toward the per-function 1 MiB
storage sum (array parameters spill pointers). The existing 1 MiB literal-bound
array-type size cap still bounds declared syntax/type graphs, even in parameters;
document this separately from stack allocation. It is an educational resource
limit. Non-static array parameter bounds do not promise a minimum caller length;
tests may pass a smaller live array when every access remains within it.

The backend should need no new ABI operation: adjusted pointer values use l and
existing complete-object address/load/store paths. Inside a function the array-
spelled parameter is a modifiable pointer object: assigning/rebinding it is valid,
and &parameter addresses the pointer spill, not the caller's entire array.

Test named/unnamed compatible prototypes, different outer/equal inner bounds,
scalar/pointer leaves, matrix row calls and mutation, pointer rebinding/address
identity and both GCC/Clang ABI directions (including enough arguments to spill
to the stack). Add AST declared-cache versus effective/local type units and
storage-budget tests proving pointer-sized parameter spills. Replace earlier
now-valid bounded-array parameter rejection fixtures with permanently unsupported
incomplete/qualified forms, recording their purpose. Keep all regressions,
sanitized bounded fuzz, isolated matrices and exact-source CI.
