# Bounded C23 attribute placements

`[[maybe_unused]]` and empty attribute lists are accepted at declaration
prefixes and after object, function, typedef, parameter, and named member
declarators; prefixes are accepted for named members and named parameters,
for-declaration initializers, and labels in compound blocks. No unused-entity
warnings are emitted, so the attribute does not change generated code.

`[[deprecated]]` and `[[deprecated("message")]]` are accepted on the same
supported declaration positions. Messages may contain adjacent ordinary
string fragments. The compiler does not currently issue the recommended
warnings when deprecated names are used, and does not advertise the attribute
through `__has_c_attribute`.

`[[fallthrough]];` is accepted in a compound statement within a switch when the
next block item is a case or default label. Other placements are rejected.
Unrecognized attributes, including scoped vendor names, are ignored in these
supported positions and before ordinary statements, including controlled
statements without braces. Their optional argument lists must contain balanced
parentheses, brackets and braces and are limited to 64 nesting levels and 256
items/tokens per sequence. Argument tokens must be supported language tokens;
this is not yet a general preprocessing-token attribute parser. The `noreturn` attribute is additionally accepted as a file- or block-scope prefix or declarator suffix on
function identifier declarations; its other placements are rejected. Known
standard attributes other than `maybe_unused`, `deprecated`, `fallthrough` and
this bounded `noreturn` are still rejected; arguments for `maybe_unused` and `fallthrough` are rejected. Attributes on anonymous
members, unnamed parameters and static assertions are rejected. Parsing remains limited to 256
attributes and attribute lists per sequence. This is not complete C23 attribute
handling, including placement and token-grammar coverage. Expanded
placements have been built but have not been regression-tested yet.

`__has_c_attribute` is recognized in preprocessing conditions, accepts an
identifier or scoped identifier, and currently returns zero for every
attribute: no attribute is advertised as fully supported while placements
remain restricted. The operand is macro-expanded. Query coverage is untested.
