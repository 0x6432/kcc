# Bounded C23 attribute placements

`[[maybe_unused]]` and empty attribute lists are accepted at declaration
prefixes and after object, function, typedef, parameter, and named member
declarators; prefixes are accepted for named members and named parameters,
for-declaration initializers, and labels in compound blocks. No unused-entity
warnings are emitted, so the attribute does not change generated code.

`[[fallthrough]];` is accepted in a compound statement within a switch when the
next block item is a case or default label. Other placements are rejected.
Other attributes, argument lists, attributes on anonymous members, unnamed
parameters and static assertions are rejected. Parsing remains limited to 256
attributes and attribute lists per sequence. This is not complete C23 attribute
handling, and unknown attributes are diagnosed rather than ignored. Expanded
placements have been built but have not been regression-tested yet.
