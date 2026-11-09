# Bounded C23 attribute placements

`[[maybe_unused]]` and empty attribute lists are accepted at declaration
prefixes and after object, function, typedef, parameter, and named member
declarators; prefixes are accepted for named members and named parameters,
for-declaration initializers, and labels in compound blocks. No unused-entity
warnings are emitted, so the attribute does not change generated code.
It is also accepted after `struct`, `union`, and `enum` in definitions and after
enumerator names; these are distinct from attributes on a declaration prefix.

`[[deprecated]]` and `[[deprecated("message")]]` are accepted on the same
supported declaration positions. Messages may contain adjacent ordinary
string fragments. The compiler warns on uses of enumerators marked deprecated, including uses
in later enumerator initializers. It also warns on direct references to a named enum, struct, or union after a
deprecated definition (including one completing a forward declaration).
Standalone tag declarations and type references through typedefs of a deprecated tag
do not yet produce warnings. Deprecated typedef names, named parameters and members
now warn on direct use. Uses of
deprecated object and function declarations at file or block scope warn; the
diagnostic follows visible bindings and respects local shadowing. Prefix and
per-declarator suffix forms are supported for those identifiers.
The compiler does not advertise the attribute through `__has_c_attribute`. It is also accepted on enum definitions and enumerators
in the positions above. Matching same-scope enum redefinitions can mark an
existing enumerator deprecated for subsequent uses.

`[[fallthrough]];` is accepted in a compound statement within a switch when the
next block item is a case or default label. Other placements are rejected.
Unrecognized attributes, including scoped vendor names, are ignored in these
supported positions and before ordinary statements, including controlled
statements without braces. Their optional argument lists must contain balanced
parentheses, brackets and braces and are limited to 64 nesting levels and 256
items/tokens per sequence. Argument tokens must be supported language tokens;
this is not yet a general preprocessing-token attribute parser. `[[nodiscard]]` and `[[nodiscard("message")]]` are accepted on function
identifier declarations, at file and block scope, as declaration prefixes or
declarator suffixes. Adjacent ordinary strings are accepted as a message. The
compiler warns for a stand-alone direct call that discards the result of a
visible nodiscard function. It also accepts `nodiscard` on an enum, struct, or union definition
and warns for a stand-alone call returning that type, including an indirect
call. It also warns on discarded direct calls in comma operands, including the
rightmost call when the entire comma expression is discarded. Unevaluated
contexts and explicit void casts suppress these diagnostics. It does not warn for
indirect calls to a nodiscard function, other nested discarded expressions,
or all declaration-redeclaration scopes. `(void)` casts suppress this
limited warning. It does not advertise partial support through `__has_c_attribute`. Typedef- and `typeof`-derived
function identifiers are resolved semantically; objects and other unsupported
placements are currently rejected. The flag is retained
on declaration nodes for future warning support.

The `noreturn` attribute is additionally accepted as a file- or block-scope prefix or declarator suffix on
function identifier declarations; its other placements are rejected. Known
standard attributes other than `maybe_unused`, `deprecated`, `fallthrough`,
this bounded `nodiscard`, `noreturn`, and direct function-declarator contracts
are still rejected; arguments for `maybe_unused` and `fallthrough` are rejected. Attributes on anonymous
members, unnamed parameters and static assertions are rejected. Parsing remains limited to 256
attributes and attribute lists per sequence. This is not complete C23 attribute
handling, including placement and token-grammar coverage. The focused attribute tests exercise the supported placements and diagnostic
behavior; they do not establish full C23 attribute coverage.
Record-specifier, enum-specifier and enumerator positions accept the same
bounded unknown attributes. `nodiscard` is supported on enum definitions but not enumerators;
enum-reference or fixed-forward forms with an attribute after `enum` are rejected;
record references or forward declarations with an attribute after `struct` or
`union` are likewise rejected.
Deprecated declaration warnings are published after a successful declaration;
self-references in its own initializer are not diagnosed by this subset.
Nodiscard and deprecated message text is not yet included in diagnostics.
The supported unprefixed standard attributes also recognize their required
double-underscore spellings, such as `[[__maybe_unused__]]` and
`[[__nodiscard__]]`. The alternate spellings of explicitly unsupported
standard attributes are rejected rather than ignored as unknown attributes.
Scoped vendor attributes remain ignored under the existing bounded policy.

`__has_c_attribute` is recognized in preprocessing conditions, accepts an
identifier or scoped identifier, and currently returns zero for every
attribute: no attribute is advertised as fully supported while placements
remain restricted. The operand is macro-expanded. Query coverage is untested.

Focused development check: the compiler rebuilt and five direct-use, fixed-forward,
redefinition, shadowing, and fixed tag-only examples compiled with the expected
warning counts and lowered through pinned QBE 1.2. The added regression fixtures
have not been run as a suite; no generated program was executed for this change.

Comma-warning development check: the compiler rebuilt and ten focused direct,
indirect-enum, nested, scoped and suppression examples produced the expected
warning counts and lowered through pinned QBE 1.2. Added regression fixtures
and generated-program execution remain pending.

## Record type diagnostics

`struct [[nodiscard]]` and `union [[nodiscard]]` definitions mark the nominal
type so discarded calls returning it warn, including indirect calls and comma
operands. `(void)` casts and unevaluated expressions suppress that warning.
`[[deprecated]]` on a record definition warns on later direct named tag type
references, not typedef-mediated references or standalone tag declarations.
Forward-declaration completion, anonymous definitions, shadowing, standard
`__name__` spellings and layout-altering vendor-attribute refusals are covered
by `tests/test_attributes.py`. Record attributes do not change object layout.
Messages are parsed but are not included in the warnings.

## Deprecated object and function declarations

A direct use of a deprecated ordinary object or function warns, including
address-taking and references in unevaluated expressions. File-scope redeclarations
retain the marker from earlier visible declarations; block-scope extern
redeclarations retain earlier markers in the same scope and do not mark the
file-scope entity merely because a block declaration is deprecated. Shadowing
by a different local identifier suppresses the outer marker. Prefix attributes
on for-declarations and declarator suffixes are covered. Deprecated typedef names warn on use in type syntax. Prefix and per-declarator
suffix forms work at file and block scope; same-scope compatible redeclarations
retain earlier deprecation, and a nearer typedef can shadow an outer one.

## Deprecated parameters and members

Prefix and declarator-suffix attributes mark named parameters and named members.
References to a deprecated parameter warn in its prototype scope and function
body; a separate definition controls its own parameter names and attributes.
Member expressions, `offsetof` paths, and designated initializers warn on the
selected deprecated member, including through anonymous records. Positional
initializers do not name members and do not warn. These warnings include uses in
unevaluated expressions. Message text is not yet included.

## Function-type optimization contracts

Direct function declarators at file or block scope accept `[[unsequenced]]`
and `[[reproducible]]`, including their double-underscore spellings, after the
declarator. They take no arguments. These contracts permit optimizations but
the compiler does not currently use them to transform calls, so generated
code retains ordinary sequencing and call behavior. Other placements, typedef-
derived function types and pointer-to-function attributes remain unsupported;
the compiler does not advertise them through `__has_c_attribute`. The program
is responsible for satisfying the contracts. This is a bounded subset, not full
C23 type-attribute support.
