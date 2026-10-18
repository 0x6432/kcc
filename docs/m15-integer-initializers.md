# M15i1: integer-constant file-scope definitions

## Supported boundary

Existing integer and boolean file-scope objects accept an assignment-expression
initializer that satisfies the compiler's checked integer-constant-expression
(ICE) contract. Unadorned, static and extern spellings, const-qualified targets,
typedef/typeof roots and mixed declaration lists use the same semantic path.
Initializing const objects is allowed; assignment conversion uses the
unqualified declared target.

Pointer/nullptr targets, address constants, arrays, braces/designators,
aggregates, inferred file objects, block storage and runtime initialization
remain deferred. Static initializer constant expressions in C are broader than
this selected ICE subset: native acceptance alone does not broaden it. Existing
ICE form restrictions and source-point unevaluated-expression checks remain.

## Ownership and declaration points

A file-scope initializer is an external definition regardless of the extern
specifier or internal linkage (N3096 6.9.2p1). A canonical object retains both
its first successful tentative anchor and its one explicit `definition` anchor.
Only the explicit anchor emits storage when present, including explicit zero;
otherwise existing tentative finalization/emission applies. Extern-only objects
still emit nothing. A later tentative or extern declaration never clears a
previous explicit owner or its bits.

Extern inherits prior internal linkage. Unadorned objects do not; the existing
mixed-linkage UB refusals remain unchanged. Duplicate initialized definitions
are refused, but their diagnostic taxonomy depends on linkage: internal
duplicates violate 6.9p3, while external duplicates violate the semantic
requirement in 6.9p5. Neither duplicate nor incompatible-declaration probes
should be counted indiscriminately as mandatory native constraint rejections.

The identifier is visible after its complete declarator, before its initializer
and later list declarators. Thus `int value=sizeof value;` is supported, while
`int value=value;` sees the identifier but is not a supported ICE.

## Constant values and target representation

Analyze and check the original initializer before assignment conversion.
Evaluated signed overflow, division by zero and invalid shifts cannot be hidden
by conversion to char or bool. Unsigned arithmetic wraps under existing rules.
Conversion to bool tests the full source value before normalization; integer
narrowing and signed conversions follow the existing documented target policy.

One target-width unsigned bit pattern is cached on the canonical symbol only
after successful conversion and a second checked constant query. Data emission
uses QBE b/h/w/l fields with the final object's target alignment, canonical
linkage and no runtime initialization stores or extra local slots.

## Failure invariants

Registration checks namespace, linkage and compatible source-point composite
types. During initializer checking a stable canonical symbol is temporarily
visible, enabling self `sizeof`. Every later failure restores the previous
object's complete canonical snapshot, or removes a newly registered symbol and
restores the object count. The failed declaration has no successful symbol/type
publication; earlier expression and declaration snapshots remain immutable.

This is an object-registration transaction, not whole-semantic-state recovery:
failed private expression caches or ancillary string/reference analysis can
remain arena-owned. The compiler is fail-fast and performs no codegen after a
parse/sema failure. No invalid, maximal-resource or fuzzed program is executed.

## Validation status and remaining work

Independent implementation/standards review and the frozen full normal and QBE
suites passed locally, both unsanitized and ASan/UBSan-instrumented, using
GCC11/QBE1.2. Source/test/Makefile manifests matched before and after validation.
Strict Clang18 source compilation and independent AST rollback checks passed.

The focused unchanged-source matrix passed 172 KCC/QBE/actual-ELF/runtime cases;
GCC passed 156 native agreements with 16 exact keyword gaps (not agreements),
and Clang18 passed all 172. Both hosts passed 12 exact per-original constraints.
The 68 KCC compile-only refusals/resources and initialized resource boundaries
passed. Full-stream per-original/per-fixture diagnostic gates and fresh-output
producers passed adversarial controls, including independent reproductions of
previous false-pass cases.

Sanitized coverage-guided libFuzzer runs completed 18,714 lexer and 104,703
compiler inputs without findings in bounded 31-second runs each. Generated
programs were not executed. Exact-commit GCC/Clang/fuzz GitHub CI remains pending
until the pushed commit is checked; local passes do not imply remote success.

M15 and M17 remain incomplete. Relocatable pointer constants and aggregate
initialization require distinct designs, not silent extension of this payload.