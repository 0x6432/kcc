# Bounded C23 attribute placements

`[[maybe_unused]]` and empty attribute lists are accepted at declaration
prefixes and after object, function, typedef, parameter, and named member
declarators; prefixes are accepted for named members and named parameters,
for-declaration initializers, and labels in compound blocks. No unused-entity
warnings are emitted, so the attribute does not change generated code.
It is also accepted after the `enum` keyword in an enum definition and after
enumerator names; these are distinct from attributes on a declaration prefix.

`[[deprecated]]` and `[[deprecated("message")]]` are accepted on the same
supported declaration positions. Messages may contain adjacent ordinary
string fragments. The compiler does not currently issue the recommended
warnings when deprecated names are used, and does not advertise the attribute
through `__has_c_attribute`. It is also accepted on enum definitions and
enumerators in the positions above.

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
visible nodiscard function. It also accepts `nodiscard` on an enum definition
and warns for a stand-alone call returning that enum, including an indirect
call. It does not warn for indirect calls to a nodiscard function, nested discarded
expressions or all declaration-redeclaration scopes. `(void)` casts suppress this
limited warning. It does not advertise partial support through `__has_c_attribute`. Typedef- and `typeof`-derived
function identifiers are resolved semantically; objects, record definitions
and other unsupported placements are currently rejected. The flag is retained
on declaration nodes for future warning support.

The `noreturn` attribute is additionally accepted as a file- or block-scope prefix or declarator suffix on
function identifier declarations; its other placements are rejected. Known
standard attributes other than `maybe_unused`, `deprecated`, `fallthrough`,
this bounded `nodiscard` and `noreturn` are still rejected; arguments for `maybe_unused` and `fallthrough` are rejected. Attributes on anonymous
members, unnamed parameters and static assertions are rejected. Parsing remains limited to 256
attributes and attribute lists per sequence. This is not complete C23 attribute
handling, including placement and token-grammar coverage. Expanded
placements have been built but have not been regression-tested yet.
Enum-specifier and enumerator positions accept the same bounded unknown
attributes. `nodiscard` is supported on enum definitions but not enumerators;
enum-reference or fixed-forward forms with an attribute after `enum` are rejected.
Nodiscard and deprecated message text is not yet included in diagnostics.

`__has_c_attribute` is recognized in preprocessing conditions, accepts an
identifier or scoped identifier, and currently returns zero for every
attribute: no attribute is advertised as fully supported while placements
remain restricted. The operand is macro-expanded. Query coverage is untested.
