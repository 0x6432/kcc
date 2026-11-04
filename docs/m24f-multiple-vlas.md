# Multiple outermost VLAs

Multiple uninitialized, naturally aligned automatic VLAs can
be declared in the outermost block or nested blocks outside loop and switch
bodies. Complete element types include
pointers, floating types, records that do not contain flexible arrays, and
fixed-size arrays, allowing a runtime outer dimension with fixed inner
dimensions. Each
bound is evaluated once in declaration order, and `sizeof` uses the saved size
of the corresponding array. They share the existing 1 MiB local-storage
budget, after fixed-size locals; an invalid bound or exhausted budget calls
`abort` before allocation. This budget is cumulative across executed VLA
declarations for the whole invocation, even after a nested block ends; storage
is reclaimed on function return.

Other restrictions of the existing outermost VLA subset remain: no VLAs in
loop or switch bodies, runtime inner dimensions, VLA
initializers, explicit alignment, VM typedefs or parameters, or `typeof` of a
VLA. Taking a VLA's address is supported, but pointer arithmetic on a pointer to
the whole VLA remains rejected because runtime referent size is not modeled;
`sizeof` of a VLA expression still requires the array's name. Functions
containing VLAs reject `goto`. The compiler was built;
the added regression cases and runtime behavior have not been tested.
Runtime-bound markers are retained when array qualification is copied or when
two unknown-bound array types are combined.