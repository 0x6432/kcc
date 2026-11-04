# Function-name identifier

Within a function body, an otherwise unbound `__func__` denotes a static
const-char array containing the function's name and terminating NUL. Repeated
references in a function refer to the same object; different functions have
separate objects. `sizeof`, indexing and ordinary array decay are supported.

This implementation does not yet synthesize a parser-visible implicit
declaration: explicit declarations or typedefs named `__func__` can change
lookup or diagnostics rather than following all standard scope and
redeclaration rules. The new implementation and assertion-header use have been
built but not regression-tested.