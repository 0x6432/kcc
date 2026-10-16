# M14a: parenthesized object declarators (design before implementation)

Replace the split prefix-star / name / array-suffix handling for local objects,
parameters and abstract cast type names with one single-pass recursive-descent
object declarator parser. Keep integer declaration specifiers separate. Reuse
concrete pointer/array type-syntax nodes; do not introduce a union, token vector,
parser rewind, fabricated bound or second parse of a declarator.

Grammar of this increment:

    object-declarator ::= { "*" } direct-object-declarator { array-suffix }
    direct-object-declarator ::= identifier | "(" object-declarator ")"
    array-suffix ::= "[" integer-token "]"
    abstract-object-declarator ::= the same derived shape without an identifier

An abstract declarator may be absent, but an empty grouping () is not an object
abstract declarator: it belongs to later function declarators. Parameters allow
named or abstract forms; cast types forbid identifiers. Local objects require a
name. Only an effective parameter's outermost array bound may be omitted, as in
M13k. Parenthesized pointers to incomplete arrays remain a diagnosed limitation,
not an assertion failure or a fictitious complete type. Function suffixes,
qualifiers, typedef names, multiple declarators and file-scope objects remain
later increments. External fixed function declarations still use their existing
return-prefix/name grammar; this is not full C declarator support.

Build the semantic-order syntax chain through an explicit unfilled base slot.
From the identifier outward, append suffixes in source order, then append the
prefix pointer chain in reverse star order. A parenthesized recursive parse
fills the same result before its enclosing suffixes. Finally attach the shared
integer base syntax once. Thus *a[2] is array -> pointer -> int, (*p)[3] is
pointer -> array -> int, and *(*a[2])[3] retains every alternating layer. The
unfilled slot is parser-local construction state, never part of a published AST;
all type syntax is complete before sema. Keep star and bracket source locations.

Bound the entire declarator to 64 pointer layers and 64 array dimensions, across
parentheses, and nesting to 64 groups. These are separate from expression depth;
cast operands retain the existing Pratt and typed-tree depth accounting. Sema
checks completeness before pointer construction and complete array element/size
queries. One-level parameter adjustment still depends on the final outer type,
not on how many brackets appeared in its spelling. Existing lvalue, array decay,
scaled pointer offsets and QBE address/storage paths need no new AST expressions
or backend special cases.

Test all primitive/pointer leaves with pointer-to-row locals, arrays of row
pointers, nested pointer/array alternation, parenthesized scalar/name forms,
named/unnamed parameter equivalence, abstract compatible pointer casts, row
subscripts/differences, once-only access and both-direction host ABI. Typed units
must inspect the exact syntax/cache graph and effective parameter type. Add
precedence counterexamples, incompatible row shapes, forbidden cast names,
empty/function grouping, missing delimiters and exact nesting/pointer/dimension
resource checks. Compile huge/uninitialized limit fixtures only. Run complete
regression/QBE/reference tests, both hosts, bounded sanitized lexer/pipeline fuzz,
isolated sanitizer matrices and exact-source CI. Never execute arbitrary fuzz C.
