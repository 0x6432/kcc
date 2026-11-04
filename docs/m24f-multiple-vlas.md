# Multiple outermost VLAs

Multiple uninitialized, naturally aligned, one-dimensional automatic
integer-element VLAs can be declared in a function's outermost block. Each
bound is evaluated once in declaration order, and `sizeof` uses the saved size
of the corresponding array. They share the existing 1 MiB local-storage
budget, after fixed-size locals; an invalid bound or exhausted budget calls
`abort` before allocation.

Other restrictions of the existing outermost VLA subset remain: no VLAs in
nested blocks or loops, multidimensional or non-integer-element VLAs, VLA
initializers, explicit alignment, VM typedefs or parameters, whole-array address
or `typeof`. Functions containing VLAs reject `goto`. The compiler was built;
the added regression cases and runtime behavior have not been tested.