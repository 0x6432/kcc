# Function-name identifier

Each function definition has an implicit outer-body binding for `__func__`:
a static const-char array containing the function name and a terminating NUL.
Repeated references name the same object, even across recursion; different
functions have distinct objects. Array decay, indexing, `sizeof`, address-taking,
static pointer initialization, and macro-expanded references are supported.
The implicit binding uses static string storage and does not consume an automatic
local slot.

The parser and semantic analyzer both bind the identifier in the function's
ordinary namespace. It hides a file-scope binding; a nested scope can shadow it,
and a same-scope parameter, object, typedef, function declaration, or enumerator
cannot redeclare it. These explicit `__func__` declarations use a reserved
identifier and are tested as KCC's scope policy, not as portable user programs;
some native compilers treat the spelling as a special token.

`tests/test_function_name.py` exercises object identity, array type, static
initialization, recursion, scope, conflicts and QBE-generated execution. This
does not claim full C23 conformance.
