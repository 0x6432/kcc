# M18: ordinary enumerations and declaration alignment

This increment completes the remaining implementation portion of M18 alongside
existing fixed `sizeof`/`alignof`, strict integer constant evaluation and static
assertions. Implementation is not release approval: the exact source commit must
pass the complete local normal/sanitized matrix, both make targets in every lane,
exact-commit bounded fuzzing, independent manifest-bound review and remote CI.
No ISO C23 conformance claim is made.

## Target and scope

The target remains Linux x86-64 SysV LP64 with QBE. Ordinary enum definitions
support named/anonymous tags, explicit strict integer constant expressions,
implicit successors and trailing commas. This increment supports enumerator
values representable by signed `int`; standard-valid wider enumerators and
fixed-underlying-type syntax remain M23f, not invented language constraints.
Expanded C23 tag/enumerator redefinitions remain M23h. Attributes, floating
and bit-precise types, VLAs, bit-fields, flexible arrays and aggregate-by-value
ABI retain their existing milestone ownership.

Each enum definition has nominal identity. Its target compatible type is
`unsigned int` when all enumerators are nonnegative, otherwise `int`, with
four-byte size and alignment. Enumerator identifiers themselves have `int`
type. In particular, an unsigned-compatible enum object is not indiscriminately
promoted to signed `int`. Qualifiers share the same enum identity. Enum values
participate in existing integer conversions, checked constant evaluation,
array bounds, case labels, assertions, initialization and supported scalar ABI.
Constants do not allocate runtime objects or data.

Tag references require an already complete visible enum, even behind a pointer;
there is no nonfixed incomplete-enum extension. References within the enum's
own definition cannot use that still-incomplete type. Tags share the record-tag
namespace; enumerators share the ordinary-name namespace. Parser name masks and
semantic bindings preserve declaration points, outer constants in defining
expressions, prototype isolation and definition-parameter scope. A whole
standalone `enum E;` is a constraint violation even for a complete tag: the
reference does not redeclare a tag and declares no declarator or enumerators.
A real declaration such as `enum E x;` remains valid. C23 permits enum definitions
in a `for` initializer; the older C11 auto/register-object-only restriction is
not imposed.

## Declaration alignment

Both `alignas` and `_Alignas` accept checked integer constant expressions or
complete object type names. Supported nonzero target alignments are
`1, 2, 4, 8, 16`; zero has no effect. Extended alignments are explicitly
unsupported target policy, not universally invalid C syntax. Each operand is
validated and the maximum request on one declaration must meet its natural
alignment. An individually weaker request can coexist with a sufficient stronger
request on that same declaration.

Alignment is declaration/member metadata, not a mutation of a scalar type.
An over-aligned `int` still has size and intrinsic type alignment four. Member
requests affect record layout, record alignment and array stride, up to sixteen.
Automatic slots, file/block static objects, supported local-exec TLS, C23
parameters and compound literals carry their effective storage alignment.
Parameter alignment applies after array/function adjustment to the local slot,
not to the function's ABI type. Literal alignment is preserved on the literal
node, including existing M17 automatic/static/thread storage forms.

Alignment is forbidden on typedefs, functions, register objects and bit-fields.
Nonliteral cast/sizeof/alignof type-name contexts cannot carry a declaration
alignment specifier. Legacy host rejection of valid C23 parameter/literal
alignment is a capability gap, never a KCC constraint or native agreement.

## Redeclarations and tentative definitions

A zero-only list has no effective explicit request. A nonzero request equal to
natural alignment remains explicit. All nonzero requests for one canonical
object must agree; requests are not silently max-merged across declarations.
An actual initialized definition, including TLS, must itself carry the matching
nonzero request when any declaration imposes one.

For tentative-only definitions, at least one actual tentative declaration must
carry the nonzero request. Other plain/zero tentative declarations can coexist,
independent of source order. The synthesized definition uses that request;
its emission anchor need not be the aligned declaration. An aligned extern-only
declaration cannot silently upgrade otherwise plain tentative defining
provenance. This final check is deferred so a later aligned tentative or full
definition can make the entity valid.

The tentative rule is a documented project interpretation of N3096 6.9.2 and
6.7.5; the standard does not spell out alignment inheritance during tentative
synthesis. Historical WG14 N1507 rationale is supplementary, not a normative
replacement. Inconsistent alignment across declarations under 6.7.5p8 is a
semantic/undefined-behavior-policy refusal, not a native constraint agreement.
Native compiler behavior differs on zero lists and tentative ordering and must
not be substituted for the declared oracle.

## Stage and resource invariants

Concrete enum syntax/enumerator nodes and a checked enumerator expression leaf
preserve source provenance. Immutable alignment-specifier lists survive parsing;
checked unsigned alignment fields feed layout/codegen. An explicit before/after
core-type marker preserves declaration-specifier order without relying on byte
offsets through macros/includes: PRE operands, core base, POST operands, derived
declarator, then adjustment/inference and final alignment validation. Shared
comma declaration syntax executes each source action once. Incomplete enums never
reach width/layout helpers. Publication journals and scope checkpoints cover
failed enum completion, binding heads, derived syntax caches and canonical
alignment changes, including failure of an enclosing M17 initializer. Failed
units emit no partial QBE IL.

Limits are 512 enum identities, 64 nested enum definitions, 1,024 enumerators per definition, 4,096
enumerators per translation unit and 4,096 alignment specifiers per translation
unit. The bounded semantic publication journal has an independent 65,536-entry
cap; exhaustion diagnoses rather than publishing partial state. All earlier
limits remain. Extended alignment is not implemented using
unbounded stack tricks. QBE `alloc4`/`alloc8`/`alloc16` and explicit data alignment
represent supported local and static storage.

## Evidence requirements

`tests/test_enumerations.py`, `tests/test_enumerations_ast.c`,
`tests/test_alignment_specifiers.py` and `tests/test_alignment_specifiers_ast.c`
are additive gates in both `make test` and `make test-codegen`. Existing tests,
strict diagnostics, fuzz limits and native discrepancy tables are retained.
New lexical tests cover raw preprocessing identifiers, both alignment keyword
spellings, enum keyword promotion and token pasting. Compile-fuzzer seeds add
ordinary enums, scope, records, alignment storage, parameters/literals and
explicit refusal paths without changing execution or resource policy.

Final evidence must bind original source bytes, a fresh KCC/QBE/ELF pipeline,
defined runtime/ABI observations, static layout/relocation proofs, native
compiler identities and exact diagnostics. Native agreements, known
disagreements, capability gaps, constraint refusals, UB-policy refusals and
resource limits are separate categories. No failed invocation, scoped probe or
build-only prewarm is a full release gate.

## Standards references

- C23 draft N3096: 6.7 declarations, 6.7.2.2 enumerations, 6.7.2.3 tags,
  6.7.5 alignment, 6.8.5 iteration, 6.9.2 tentative definitions:
  https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf
- C11 draft N1570, for comparison of superseded restrictions only:
  https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf
- Historical alignment proposal/rationale N1507:
  https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1507.pdf
