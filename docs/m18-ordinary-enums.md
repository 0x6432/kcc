# M18 ordinary enums: int-range implementation checkpoint

This change implements a bounded ordinary-enum subset. The work is an
implementation checkpoint, not a tested or approved milestone.

- Tagged and anonymous definitions have nonempty enumerator lists, optional
  explicit integer constant expressions, implicit successive values, and an
  optional trailing comma. Earlier enumerators are visible to later ones.
- Each enumerator is an int-typed non-lvalue integer constant. Its binding
  occupies the ordinary identifier namespace and follows the surrounding
  file/block scope and typedef-shadowing rules. Tags share the struct/union
  namespace and definitions shadow outer tags in nested scopes.
- A defined enum is a distinct nominal type compatible with signed int for
  this target. It uses the int size/alignment and promotes to int. Qualified
  copies retain nominal identity. Distinct enum types are not compatible.
- Explicit values are evaluated with the checked ICE evaluator. Every value
  and implicit successor must fit the target's signed 32-bit int. A limit of
  1024 enumerators per definition and the existing translation-unit and
  nesting limits bound resource use.

Not implemented: C23 fixed underlying types, wider/out-of-int enumerators and
C23's full changing-enumerator-type and underlying-type selection rules; enum
forward declarations (including tag-only redeclarations); and enum definitions
inside function parameter lists. These are rejected, not silently widened.
There is no cross-compiler enum ABI claim beyond this subset's chosen int ABI.
Implementation-specific corner cases, cross-translation-unit compatibility,
compiler diagnostics, and fuzz safety need independent review.

Semantic and end-to-end runtime fixtures were written, but neither tests nor
fuzz were run for this checkpoint. The compiler was built for implementation.
Full regression, QBE/host interop, sanitizers, bounded fuzz and exact-source CI
are required before claiming a tested checkpoint. No conclusion about M17
approval follows from this change.
