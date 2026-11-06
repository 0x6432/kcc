# Restrict-qualified pointers

The `restrict` keyword qualifies pointer types to objects, including pointers
to incomplete objects and `void`, and arrays of such pointers through typedefs.
It is accepted in pointer declarators, type-specifier qualifier lists, inferred
objects, and outermost parameter-array brackets. Repeated qualifiers are
idempotent. The qualified parameter object keeps its qualifier, while top-level
parameter qualification does not affect function type compatibility.

Qualifying a non-pointer or pointer to function is rejected. Restrict does not
make an object const; const-qualified restricted pointers remain unmodifiable.
The compiler currently emits conservative code without restrict-based alias
optimizations or runtime checking. Programs must still obey C's restrict
access rules. Volatile and atomic pointers remain outside the implemented subset.

The compiler builds and focused declaration smoke checks were performed. The
new regression and runtime suites have not been run.
