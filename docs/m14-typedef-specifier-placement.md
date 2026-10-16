# M14l4: typedef placement in declaration specifiers

Design recorded before implementation, following a7a9528. Native compile-only
GCC 11.5, Clang 15.0.7, GCC 14.2.1 and Clang 18.1.8 probes accept typedef among
integer/const/alias specifiers; GCC 14 also accepts the unchanged C23 for form.
Support the one implemented storage class in any declaration-specifier position,
not arbitrary storage classes or a post-declarator keyword.

## Parser and component plan

Extend the existing declaration-specifier scan with an optional output token for
typedef. A non-NULL output permits that storage class and retains its actual
written location; a NULL output is a type-name/parameter context and rejects it.
Accept at most one typedef token; preserve the requirement for an actual type,
all incompatible-type diagnostics and the rule that a second alias begins the
declarator rather than extending specifiers. The scanner must never infer types.

File and block declaration entry points scan specifiers once, then select the
existing concrete alias or ordinary declaration construction path. Convert the
two typedef-list parsers into tails receiving the already parsed base and actual
typedef token. Local declarations (including for initializers) select their tail
after scanning. The consumed-identifier block path must make the same selection
without replaying tokens; alias-named labels still take priority. Type names,
parameters, casts and typeof/sizeof/alignof type operands reject typedef.

Preserve the shared base across comma declarators and publication after each
complete declarator. Own bounds, later comma names, masking/restoration, captured
identities and every alias/expanded-type/resource bound remain unchanged. Sema
receives exactly the existing AST kinds and independently checks constraints;
no semantic/type/codegen changes, new runtime alias locals, or QBE storage.
Other storage classes, typedef initializers, globals, block function declarations,
VM types and bare alias-derived definitions remain outside this increment.

## Validation

Test file/block/for placement, integer/const/alias/query specifiers, comma-derived
shapes, same-scope conflicts and repeated compatible aliases, point of declaration,
parameter/object masks and scope restoration. Keep all original C intact when
comparing native hosts; count exact known for-typedef grammar gaps separately.
Reject duplicate typedefs and storage classes in type-name/parameter contexts.
Check AST base sharing, actual typedef source locations and no alias storage;
exact external/block/expanded-depth limits; primitive both-direction mixed-stack
ABI; full normal/QBE regression; both-host targeted sanitizers; bounded compile-
only lexer/pipeline fuzz on frozen bytes. Build normal helpers serially first.
Do not execute invalid curated or fuzz-generated C. Record CI independently.

## Completion evidence

The recorded plan is implemented without changing semantic/type/codegen or AST
interfaces. The M14l4 ledger records exact frozen normal/QBE, native original,
ABI/AST/storage/resource, sanitizer/fuzz results and CI status. Scope and counter
fixture corrections occurred before freezing; no failed run was counted as a
pass and no invalid or generated source was executed.
