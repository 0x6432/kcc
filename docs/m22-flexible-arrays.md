# Bounded flexible array members

A named final incomplete-array member is accepted in a nonempty struct with a
previous named member. It contributes its element alignment and offset but no
storage to `sizeof` the struct; ordinary runtime member access uses the member
address and element type. Initializers may initialize the preceding members, not
the flexible member itself. Whole-record copies use the fixed struct size.

This subset rejects structs containing a flexible-array struct as a member or
array element, unions with a flexible array, direct flexible-array initialization,
and static addresses of flexible-array members. These are implementation
boundaries, not a complete C23 flexible-array implementation. Access must stay
within storage actually allocated by the program. Bit-fields remain unsupported.
The implementation has been built but has not yet been integration-tested.

## Promoted names and trailing assertions

A prior named member promoted through anonymous structures or unions satisfies
the nonempty-structure requirement for a final flexible array member, including
nested anonymous containers. A static assertion after the flexible member does
not count as a later member; later actual member declarations are still rejected.
Other nesting, initialization and static-address boundaries above remain.

The compiler build and focused layout, compilation and rejection checks were
run; one example was lowered by pinned QBE and assembled, and the host compiler
accepted an equivalent layout. Generated-program runtime, ABI, regression
fixtures and fuzzing remain unrun. This is not M22 completion or a C23 conformance claim.
