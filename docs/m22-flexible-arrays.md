# Bounded flexible array members

A named final incomplete-array member is accepted in a nonempty struct with a
previous named member. It contributes its element alignment and offset but no
storage to `sizeof` the struct; ordinary runtime member access uses the member
address and element type. Initializers may initialize the preceding members, not
the flexible member itself. Whole-record copies use the fixed struct size.

This subset rejects structs containing a flexible-array struct as a member or
array element, direct flexible-array members in unions, and direct flexible-array initialization. These are implementation
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

## Unions containing flexible-array structures

A union may contain a named structure with a flexible array member, or another
such union recursively. The restriction is propagated: the resulting union may
not be a member of a structure or an array element. Anonymous members containing
such a type remain outside this subset, as do the earlier flexible-array limits.

The compiler build and focused layout, initializer and rejection checks were
run; one example was lowered through pinned QBE and assembled. Generated-program
runtime, host ABI, regression fixtures and fuzzing remain unrun. M22 is not
complete or approved.

## Static addresses of flexible members

Static initializers can form the zero-position address of a flexible member,
including array decay, `&object.member[0]`, and `&object.member`. The address
must still be based on a proven static record subobject; thread-local bases are
not static address constants. The proof intentionally assumes zero usable
flexible elements even when padding or an enclosing union might provide room:
pointer offsets beyond zero are rejected. It does not justify accessing an
element or claim extra storage exists. The compiler rebuilt. Eight focused address/relocation examples compiled,
lowered through pinned QBE 1.2 and assembled; five invalid or unsupported
examples were rejected. Regression, generated-program runtime and ABI
validation remain pending.
