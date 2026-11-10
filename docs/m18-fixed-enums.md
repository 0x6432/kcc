# Fixed underlying enums: implementation checkpoint

## Extended-integer underlying types

A fixed enum may use the target's width-specific extended integer type obtained
from a 33–63-bit long-base field expression, for example
`typedef typeof(+field) T; enum E : T { A=0 };`. Its size and alignment are
eight bytes, while its range, rank, promotions, arithmetic, storage conversions
and signed representation follow that extended type. Qualified copies, static
initializers, fixed/variadic calls and bit-fields up to the underlying width
are supported. Different widths are not compatible merely because their types
share a signedness. Direct `auto` inference from such fields uses the same
width-specific type after lvalue conversion.

`tests/test_enum_extended_underlying.py` exercises all 62 signed/unsigned
widths and cross-object fixed and variadic ABI with GCC primitive surrogates.
GCC 11 cannot compile the C23 fixed-enum syntax; surrogate results verify
representation and calling convention, not native enum syntax or semantic
agreement. These additions do not complete M18, general enums or C23.

The older checkpoints below preserve their original status and are superseded
where later sections describe expanded functionality.

This incremental change adds a bounded C23 fixed-underlying-enum slice to the
ordinary enum implementation. It is not a tested checkpoint.

- Integer types from bool and char through unsigned long long are
  accepted after `:`, including typedef names and `typeof`/`typeof_unqual`
  yielding those types. Target signedness, rank, size, alignment,
  ABI width and promotions follow the chosen underlying integer type.
- `enum E : unsigned short;` declares a complete fixed enum immediately. A
  matching later definition shares the nominal identity and may repeat or omit
  the underlying type; scope shadowing and mismatched definitions are checked. Matching
  same-scope definitions may repeat their members with the same values.
  A fixed enum specifier without an enumerator list is restricted to a
  standalone tag declaration; use `enum E value;` for an object.
- Fixed enum constants have the nominal enum type, including during their
  definition. Explicit ICE values must be representable; implicit successors
  must not overflow the underlying range. Unsigned explicit arithmetic may wrap
  in its own expression before the representability check. Values use target
  bits with checked conversion, including 64-bit unsigned and signed minima.
- Different enums remain distinct, while compatibility with the declared
  underlying integer type and composite-type identity are retained. Small
  enum constants are canonicalized to the target's signed/unsigned word form.

Boundaries: enum types as fixed underlying types are explicitly rejected.
Qualifiers on an underlying integer type are discarded; atomic spellings are
limited by the existing atomic type subset. Direct fixed enum definitions in
outer parameter declaration specifiers and supported nested parameter type
syntax are supported. A bare tag-only `enum E;` is rejected because it
declares no entity, even if the tag is already visible. An unknown non-fixed
tag cannot be introduced this way. Non-fixed enum constants remain restricted to signed int range,
with no general C23 changing-enumerator-type or underlying selection rules.
This change is not a full C23 enum or cross-toolchain ABI conformance claim.
The typedef and `typeof` extension has been built but not tested.

Lexer/type/sema and end-to-end fixtures have been added or updated but have not
been run. A compiler build was used during implementation. Exact-source full
regression, QBE and host ABI interop, sanitizers, bounded fuzz and CI remain
required. See WG14 N3030 for the fixed enum model:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3030.htm

## Correction: bare enum tag-only declarations

The earlier same-scope `enum E;` checkpoint incorrectly accepted a declaration
that declares no entity. ISO C 2024 draft N3220 6.7.1p2 and 6.7.3.4p11–13
only give the standalone tag-declaring form to a fixed enum with its type
specifier. Bare references to complete enums remain valid in declarations
with declarators. The incorrect acceptance has been removed and rejection
fixtures added; no fixtures have been run. This corrects the earlier
checkpoint, not an M18 completion claim.

## Boolean underlying type checkpoint

A fixed enum may use `bool`, `_Bool`, or an unqualified alias thereof as its
underlying type. Its representation and promotion follow the existing target
bool model. Enumerator values must be representable as 0 or 1, including
implicit successors; ordinary scalar conversions to the enum normalize to 0
or 1. The implementation extends constant folding, static initialization,
scalar conversion and updates to recognize bool-compatible enums. Enum underlying types remain rejected.

Semantic and optional host/QBE runtime fixtures were added but not run. The
compiler build succeeded; one focused boolean enum source later compiled
successfully. This is not enum conformance, a tested checkpoint,
or approval of M18 or M17. Further integration, ABI and regression testing
remain necessary.

## Qualified underlying types and standalone syntax

Qualifiers on a fixed integer underlying type are removed before comparison,
representation and conversion, including atomic int/unsigned int types already
supported by the atomic subset. An enum specifier with an explicit underlying
type but no enumerator list is now rejected unless it is a standalone tag
declaration; the former `enum E : int object;` extension was contrary to the
C23 constraint. Positive, negative and runtime fixtures were updated but have
not been run. The compiler build succeeded. This is not M18 completion.
See ISO C 2024 draft N3220, 6.7.3.3 paragraphs 5–8:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3220.pdf

## Inherited fixed underlying type in definitions

A definition or matching same-scope redefinition of a previously declared fixed
enum may omit the enum type specifier: `enum E : unsigned char; enum E { A=42 };`.
The fixed type is inherited from the existing tag; enumerator types, range and
successor constraints, and enum layout continue to follow that type. A mismatched
explicit base is still rejected. A definition in a nested scope introduces a
new tag rather than inheriting an outer scope's type unless that scope has its
own fixed declaration. This does not change the rejection of a bare tag-only
`enum E;` declaration.

The semantic AST suite and fixed, boolean, compatibility and successor enum
fixtures ran successfully with QBE 1.2. The available host does not support
C23 fixed-enum syntax, so no independent native agreement is claimed. This is
not M18 completion or full C23 conformance.
