# Fixed underlying enums: implementation checkpoint

This incremental change adds a bounded C23 fixed-underlying-enum slice to the
ordinary enum implementation. It is not a tested checkpoint.

- Builtin unqualified non-bool integer spellings from char through unsigned
  long long are accepted after `:`. Target signedness, rank, size, alignment,
  ABI width and promotions follow the chosen underlying integer type.
- `enum E : unsigned short;` declares a complete fixed enum immediately. A
  matching later definition repeats the underlying type and shares the nominal
  identity; scope shadowing and mismatched/repeated definitions are checked.
- Fixed enum constants have the nominal enum type, including during their
  definition. Explicit ICE values must be representable; implicit successors
  must not overflow the underlying range. Unsigned explicit arithmetic may wrap
  in its own expression before the representability check. Values use target
  bits with checked conversion, including 64-bit unsigned and signed minima.
- Different enums remain distinct, while compatibility with the declared
  underlying integer type and composite-type identity are retained. Small
  enum constants are canonicalized to the target's signed/unsigned word form.

Boundaries: `_Bool`, qualifiers, typedef names and `typeof` as fixed underlying
spellings are explicitly rejected in this slice; repeated fixed declarations
using a compatible alias are therefore not supported. Fixed definitions in
parameter lists remain unsupported. A fixed forward tag's definition must
repeat its underlying spelling; bare non-fixed tag-only declarations remain
unsupported. Non-fixed enum constants remain restricted to signed int range,
with no general C23 changing-enumerator-type or underlying selection rules.
This change is not a full C23 enum or cross-toolchain ABI conformance claim.

Lexer/type/sema and end-to-end fixtures have been added or updated but have not
been run. A compiler build was used during implementation. Exact-source full
regression, QBE and host ABI interop, sanitizers, bounded fuzz and CI remain
required. See WG14 N3030 for the fixed enum model:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3030.htm
