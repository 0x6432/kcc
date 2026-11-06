# M18: declaration alignment (implementation checkpoint)

This is not M18 completion or a tested/release checkpoint. Both `alignas` and
`_Alignas` are recognized after preprocessing. This slice supports automatic,
static, file-scope and thread-local objects, including linked extern objects,
and named struct/union members. A declaration list shares one specifier group;
the group is resolved exactly once before any list identifier enters semantic
scope, interleaving preceding non-builtin type resolution as described below. Up to 32 specifiers are allowed. They
may be interleaved with type, storage and qualifier specifiers. A preceding
non-builtin type specifier is resolved before a later alignment operand, so
tags and typedef bindings follow source order.

An operand is a complete object type-name or checked integer constant
expression. Zero has no effect; nonzero requests combine by maximum and cannot
weaken the natural alignment. Supported values are 1, 2, 4, 8 and 16. An
incomplete record object with a nonzero request is rejected until its natural
alignment is known; an unknown-bound array with complete element type has a
known alignment. Object alignment is storage metadata, not a type qualifier.
QBE local slots use alloc4/8/16 and static/TLS data use the effective alignment.

For record members, the request affects struct offsets, union/struct alignment,
tail padding, aggregate size and array stride. Nested record layouts retain
these properties. Bit-fields remain unsupported; flexible members are subject
to the bounded flexible-array implementation. Cross-scope C23 structural compatibility and common-initial-
sequence interactions remain separate work (see WG14 issue 1041).

For linkage, a canonical object stores its nonzero request; definitions and
nonzero redeclarations must agree, and a definition without a request cannot
follow a nonzero requested declaration (nor vice versa). Zero is treated as
absent. Tentative-only definitions inherit the canonical request at TU end.
Different nonzero extern-only requests are conservatively rejected even before
a definition exists. C23 6.7.6p8 has open interpretation questions about
zero, equivalent requests and tentative definitions (WG14 issue 1044); this is
an explicit implementation policy, not a claim those questions are resolved.
Across translation units kcc cannot verify matching declarations; callers must
supply consistent alignment themselves.

Still unsupported: alignment on typedefs, register objects,
functions, or
requests above 16. Alignment on inferred automatic objects is supported.
These are implementation limits, not claims that all such programs violate C. No broader C23 alignment conformance is claimed.

Focused acceptance, rejection, IL, transactional layout and optional
QBE/native-runtime tests are added to the project test targets. Per task
instruction, no tests, fuzzing, or test suites were run; only a compiler build
was performed. Normal/sanitizer, native-oracle, QBE/runtime, bounded fuzz and
exact-source CI gates remain outstanding. No conclusion about M17 approval
follows from this work.

References: https://www.open-std.org/jtc1/sc22/wg14/issues/c23/issue1044.html
and https://www.open-std.org/jtc1/sc22/wg14/issues/c23/issue1041.html.

## Built-in specifier placement checkpoint

Alignment specifiers now also appear after or between built-in type keywords,
for automatic, static, thread-local and file-scope objects and named record
members. Built-in keywords create no semantic bindings, so evaluating the shared
alignment group before the type retains operand ordering. Declarator-list and
existing alignment constraints are unchanged. Fixtures cover keyword permutations,
storage and record layouts, constraint failures, and binding in an alignment
operand; they have not been run. The compiler build succeeded at this checkpoint. The later checkpoint below supersedes the restriction on other specifier
types. No milestone completion or approval is implied.

## Alignment placement after non-builtin type specifiers

Alignment specifiers can follow a typedef name, record, enum, typeof, or
supported atomic type specifier. The alignment group resolves the preceding
type before later operands, while retaining earlier alignment operands before
the type. The resolved type is cached so that a later operand introducing a
name cannot change an earlier typedef lookup. Declarator-list sharing and
existing placement/storage limits remain in force. New fixtures cover
source-order dependencies, typedef shadowing, record layout, and rejection of
forward use. The compiler build succeeded and three focused source-order examples compiled.
The new fixture suites, runtime, ABI and fuzzing have not been run. This does not complete or approve M18.

## Anonymous record member alignment

Alignment specifiers on supported untagged anonymous struct and union members
use the same evaluation, natural-alignment checks and record layout machinery
as named members. This affects the anonymous container's offset and the
enclosing record's alignment, size and array stride, without changing the
member type or the rules for promoted member names. The existing limits of
0, 1, 2, 4, 8 and 16 remain; tagged declarations without a member declarator
and attributes on anonymous members remain outside this supported syntax.

The compiler build and focused positive/negative compilation checks succeeded.
A focused host GCC syntax/layout comparison succeeded with C23 spellings mapped
to their older underscore forms. Regression fixtures were added but not run;
QBE runtime, ABI, sanitizer, fuzz and full regression checks remain outstanding.
This is an implementation increment, not M18 completion, M17 approval, or a
full C23 conformance claim.

## Parameter alignment

Parameters may have supported alignment specifiers. Requests are checked in
prototype scope, before the parameter enters scope, and are validated against
the adjusted parameter object type; an array parameter therefore has pointer
alignment. A definition's named parameter spill slot uses the requested
alignment. Alignment is not part of the function type or calling convention,
and a prototype's request does not impose storage alignment on a separate
definition. Register parameters and void parameter markers cannot have an
alignment specifier. Requests above 16 remain unsupported.

The compiler build and focused accept/reject and emitted-IL checks succeeded.
Regression fixtures, generated-program runtime, ABI, sanitizer and fuzz checks
were not run. This does not complete or approve M18.
