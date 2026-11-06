# Fixed underlying enums: implementation checkpoint

This incremental change adds a bounded C23 fixed-underlying-enum slice to the
ordinary enum implementation. It is not a tested checkpoint.

- Integer types from bool and char through unsigned long long are
  accepted after `:`, including typedef names and `typeof`/`typeof_unqual`
  yielding those types. Target signedness, rank, size, alignment,
  ABI width and promotions follow the chosen underlying integer type.
- `enum E : unsigned short;` declares a complete fixed enum immediately. A
  matching later definition repeats the underlying type and shares the nominal
  identity; scope shadowing and mismatched/repeated definitions are checked.
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
limited by the existing atomic type subset. Fixed definitions in
parameter lists remain unsupported. A fixed forward tag's definition must
repeat its underlying type; a bare tag-only `enum E;` is rejected because it
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
