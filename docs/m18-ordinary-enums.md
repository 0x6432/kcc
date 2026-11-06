# M18 ordinary enums: int-range implementation checkpoint

This is the earlier ordinary-enum checkpoint. For subsequent fixed-enum work
and fixed-enum tag declarations, see `m18-fixed-enums.md`.

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
forward declarations of unknown non-fixed tags; and enum definitions
inside function parameter lists. These are rejected, not silently widened.
There is no cross-compiler enum ABI claim beyond this subset's chosen int ABI.
Implementation-specific corner cases, cross-translation-unit compatibility,
compiler diagnostics, and fuzz safety need independent review.

Semantic and end-to-end runtime fixtures were written, but neither tests nor
fuzz were run for this checkpoint. The compiler was built for implementation.
Full regression, QBE/host interop, sanitizers, bounded fuzz and exact-source CI
are required before claiming a tested checkpoint. No conclusion about M17
approval follows from this change.

## Wider signed-long ordinary enums

This checkpoint extends ordinary enums beyond int, within a target-LP64 slice.
All values must fit signed 64-bit long; an all-int-range enumeration retains
int compatibility and int member types, while an enumeration with any value
outside int uses signed long as its compatible type and the completed enum as
its member type. During the enumerator list, explicit values fitting int use
int, other explicit values retain the expression type, and implicit successors
use the preceding value's promoted type or widen with the same signedness.
Expressions already checked during the definition retain their earlier types.
Unsigned values above LONG_MAX and successor overflow beyond 64 bits are
conservatively rejected, even if another implementation could accept them.
Cross-translation-unit compatibility remains unsupported; this is not the full C23 enum model or an ABI conformance claim.

The compiler was built and one focused wide-enum source compiled successfully.
The added fixture suite and optional QBE runtime coverage have not been run;
full regression, native ABI and fuzzing remain pending. This does not approve M17 or complete M18. The preceding int-range
description is historical.

## Full 64-bit unsigned ordinary enum values

The target-compatible type selection now chooses unsigned long if a
nonnegative enumerator exceeds LONG_MAX. Values up to ULONG_MAX are accepted;
if such a value is combined with any negative enumerator, no implemented
standard integer type represents the complete range and the declaration is
rejected. The previous signed-long-only limit is superseded. Same-signedness
implicit successor overflow beyond 64 bits remains rejected. Fixtures were
updated but have not been run; the compiler was built and one focused unsigned
64-bit enum source compiled successfully. This is still not a
complete C23 enum or cross-toolchain ABI claim.

## Same-scope enum redefinitions

A subsequent definition of the same tagged enum in the same scope may repeat
exactly the same member names and values, in any order. It reuses the existing
enumerator bindings and their completed types; explicit expressions may refer
to them. Duplicate, missing, new or value-changing members, nested repeated
definitions, and incompatible fixed underlying types are rejected. Fixed and
ordinary enums use the same bounded member matching; this does not implement
C23 cross-scope or cross-translation-unit structural compatibility. Semantic
and runtime fixtures were added but not run. The compiler build succeeded and
one focused source with ordinary, wide, and fixed redefinitions compiled;
regression, ABI interop and fuzz verification remain outstanding.
