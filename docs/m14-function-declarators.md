# M14e: fixed function declarator syntax (design before implementation)

Unify the remaining restricted external return-prefix/name parser with the
single-pass declarator builder. Add a concrete ast_function_type_syntax holding
return syntax, fixed parameter declarations/count and source location/cache.
Function suffixes append through the same base slot as arrays; no token replay,
second parse, union or special textual decoding of parenthesized declarators.
This increment supports parenthesized external function names and functions
returning complete/unknown array pointers, for example int (*row(int))[3].

    declarator ::= { '*' } direct-declarator { array-suffix | function-suffix }
    direct-declarator ::= identifier | '(' declarator ')'
    function-suffix ::= '(' ('void' | [ parameter-list ]) ')'

Abstract forms omit the identifier. After an abstract opening parenthesis,
void/declaration-specifier/right-parenthesis begins a function suffix, whereas
star/left-parenthesis/name begins grouping. Use the one current token after
consuming the opening; never backtrack or materialize the TU. Empty () is the
C23 zero-parameter function suffix, no longer an empty object grouping error.
A declaration context still requires an external/local name; casts forbid names.
Nested parameter declarations use the same general parser.

External declarations must have a function outer type; nonfunction file-scope
objects remain diagnosed until M15. Keep one explicit outer signature syntax
on ast_function_declaration; existing parameter lists/return fields may be views
of that same function node, never separately reparsed or copied type trees.
Sema resolves/caches the concrete function syntax, adjusts array parameters and
builds the existing function_type graph. Composite redeclarations remain M14b's
immutable operation. Definitions bind only their own named parameters, not
prototype names from another declaration or nested function type. Return types
must be implemented scalars: arrays/functions as returns are constraints, not
QBE assertions. Existing fixed calls/returns/codegen use resolved scalar types.

Keep the next boundary honest: function pointer values/designator decay and
indirect calls belong to M14f, not this syntax increment. Pointer referent
validation still rejects function types with an explicit unsupported-function-
pointer diagnostic before construction; direct function-typed parameters are
similarly diagnosed before scalar ABI helpers. Local function declarations stay
unsupported until block-scope linkage work. Do not accidentally accept unsupported
function pointer objects merely because they parse. Void return/types, qualifiers,
typedefs, variadics, globals and general bounds remain later increments.

Bound function suffix layers to 64 alongside the existing 64-star/64-array
counts. Shared parser declarator nesting must also cover nested parameter types,
not reset at every new parameter list. Preserve the exact existing 64/65 grouping
boundary: the outer declarator is level zero. A wrapper with one cleanup path
keeps the shared counter balanced. This prevents function parameter recursion
from bypassing bounded on-demand parsing or overflowing sema's recursive graph.

Tests: parenthesized external function names, named/unnamed C23 definitions,
row/matrix-pointer returns, unknown-bound pointer returns, static string-array
address returns, recursion and both host linkage directions. Cover exact syntax/
cache/return/parameter sharing, compatible composite returns, invalid array/function
returns, unsupported pointer/function parameters and block/file-scope objects.
Migrate old parser-only function-grouping negatives to genuine invalid forms;
retain unsupported-feature diagnostics rather than weakening constraints. Test
64/65 function layers and nested parameter/group depth without executing invalid
or uninitialized resource fixtures. Full regression, both GCC/Clang/QBE/reference/
ABI, bounded sanitized fuzz, isolated matrices and exact-source CI remain required.

Next M14f must explicitly add function designator ASTs/decay, function referent
pointers, parameter function-to-pointer adjustment, address/indirection cancellation
and once-evaluated indirect call targets. It must reject function pointer arithmetic,
keep object/function categories distinct and retain direct-call diagnostics/ABI
coverage. Do not implement an integer-address or QBE-text shortcut for callbacks.
