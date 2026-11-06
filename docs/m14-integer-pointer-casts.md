# Explicit integer-pointer casts

Explicit casts between integer types and object or function pointers are
accepted for runtime expressions on the LP64 target. Integer values narrower
than 64 bits are sign- or zero-extended according to their source type;
pointer-to-integer conversion uses the low target-width bits (with normal
subword normalization). Null pointers use the target all-zero representation.
These are implementation-defined representation choices; fabricated pointers
must not be dereferenced or called unless valid for the execution environment.
Implicit non-null integer/pointer conversions remain rejected. Nonzero numeric
static pointer initializers and integer objects initialized from pointer
relocations are not yet supported. Pointer-to-bool behavior is unchanged.

The compiler was built and focused compile/IL checks were run. Regression,
backend and runtime tests have not been run.
