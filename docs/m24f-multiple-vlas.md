# Multiple outermost VLAs

Multiple automatic VLAs can
be declared in the outermost block or nested blocks, including loop and switch
bodies. A case or default label is rejected if switch dispatch would enter the
scope of a VLA declared inside that switch; a VLA enclosing a nested switch is
allowed. A loop declaration evaluates its bound and allocates on
every execution. Complete element types include
pointers, floating types, records that do not contain flexible arrays, and
fixed-size arrays, allowing a runtime outer dimension with fixed inner
dimensions. Each
bound is evaluated once in declaration order. Explicit alignment up to 16 bytes
is supported when it does not weaken natural alignment; `sizeof` uses the saved size
of the corresponding array. A C23 empty initializer `{}` zero-initializes the
runtime-sized storage using the target’s all-zero representations; nonempty VLA
initializers remain rejected. They share the existing 1 MiB local-storage
budget, after fixed-size locals; an invalid bound or exhausted budget calls
`abort` before allocation. This budget is cumulative across executed VLA
declarations for the whole invocation, including successive loop iterations, even
after a nested block ends; storage is reclaimed on function return. This is a
conservative implementation limit: a loop can exhaust the budget even when its
individual VLAs have ended their lifetimes.

Other restrictions of the existing outermost VLA subset remain: no runtime inner
dimensions, nonempty VLA initializers, general VM typedefs or
parameters, or `typeof` of a VLA. Taking a VLA's address is supported, but pointer arithmetic on a pointer to
the whole VLA remains rejected because runtime referent size is not modeled;
`sizeof` accepts the array name or direct indirection/address pairs such as
`sizeof *(&a)`; other VLA expressions remain unsupported. A `goto` may stay within or leave VLA scopes, or return to a point before a
VLA declaration; it is rejected if its target enters the scope of a VLA absent
at the source. Re-entering a declaration consumes the cumulative budget again. The compiler was built;
the added regression cases and runtime behavior have not been tested.
Runtime-bound markers are retained when array qualification is copied or when
two unknown-bound array types are combined.