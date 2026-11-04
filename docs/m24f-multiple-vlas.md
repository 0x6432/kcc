# Multiple outermost VLAs

Multiple uninitialized, naturally aligned automatic VLAs can
be declared in a function's outermost block. Complete element types include
pointers, floating types, records that do not contain flexible arrays, and
fixed-size arrays, allowing a runtime outer dimension with fixed inner
dimensions. Each
bound is evaluated once in declaration order, and `sizeof` uses the saved size
of the corresponding array. They share the existing 1 MiB local-storage
budget, after fixed-size locals; an invalid bound or exhausted budget calls
`abort` before allocation.

Other restrictions of the existing outermost VLA subset remain: no VLAs in
nested blocks or loops, runtime inner dimensions, VLA
initializers, explicit alignment, VM typedefs or parameters, whole-array address
or `typeof`. Functions containing VLAs reject `goto`. The compiler was built;
the added regression cases and runtime behavior have not been tested.