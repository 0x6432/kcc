# Bounded flexible array members

A named final incomplete-array member is accepted in a nonempty struct with a
previous named member. It contributes its element alignment and offset but no
storage to `sizeof` the struct; ordinary runtime member access uses the member
address and element type. Initializers may initialize the preceding members, not
the flexible member itself. Whole-record copies use the fixed struct size.

This subset rejects structs containing a flexible-array struct as a member or
array element, direct flexible-array members in unions, and direct flexible-array initialization. These are implementation
boundaries, not a complete C23 flexible-array implementation. Access must stay
within storage actually allocated by the program. The bounded named int bit-field
subset is documented in `m22-bit-fields.md`.
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

A union may contain a named or anonymous structure with a flexible array member,
or another such union recursively. The restriction is propagated: the resulting
union may not be a member of a structure or an array element. Other earlier
flexible-array limits remain.

The compiler build and focused layout, initializer and rejection checks were
run; one example was lowered through pinned QBE and assembled. Generated-program
runtime, host ABI, regression fixtures and fuzzing remain unrun. M22 is not
complete or approved.

## Static addresses of flexible members

Static initializers can form the zero-position address of a flexible member,
including array decay, `&object.member[0]`, and `&object.member`. The address
must still be based on a proven static record subobject; thread-local bases are
not static address constants. The initial checkpoint assumed zero usable
flexible elements, rejecting offsets beyond zero; the following tail-padding
checkpoint supersedes that restriction while retaining conservative bounds.
It does not justify accessing uninitialized elements. The compiler rebuilt. Eight focused address/relocation examples compiled,
lowered through pinned QBE 1.2 and assembled; five invalid or unsupported
examples were rejected. Regression, generated-program runtime and ABI
validation remain pending.

## Guaranteed tail-padding address bounds

For a flexible member of a proven static record subobject, the address proof
can use elements that fit in the record type's own fixed size after the member
offset, including their one-past address. It does not assume any extra extent
from an enclosing union, allocation, cast, or later declaration. If no element
fits, only the starting address is accepted; forming an imaginary one-past
pointer is rejected. This permits address formation only and does not justify
loading uninitialized elements or extending object lifetime.

The compiler rebuilt. Five focused relocation examples compiled, lowered via
pinned QBE 1.2 and assembled; four out-of-bound examples were rejected. A host
C11 syntax and layout check succeeded. Regression, generated-program runtime,
ABI and fuzzing remain unrun. This does not complete M22.

## Anonymous union members with flexible arrays

An anonymous struct containing a flexible member, or an anonymous union
recursively containing such a struct, may be a union member. Promoted names,
record layout, initializers for fixed members, member access and bounded static
addresses use the existing machinery. The enclosing union remains prohibited as
a struct member or array element, and flexible-member initialization is still
rejected.

The compiler rebuilt. Two layouts, three relocation addends and a member access
were inspected in IL, lowered through pinned QBE 1.2 and assembled; six invalid
examples were rejected. Equivalent host C11 syntax/layout checks succeeded.
Regression fixtures, generated-program runtime, ABI and fuzzing remain unrun;
M22 remains incomplete.
