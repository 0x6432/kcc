# M18: declaration alignment (implementation checkpoint)

This is not M18 completion or a tested/release checkpoint. Both `alignas` and
`_Alignas` are recognized after preprocessing. This slice supports automatic,
static, file-scope and thread-local objects, including linked extern objects,
and named struct/union members. A declaration list shares one specifier group;
the group is resolved exactly once before the declared type and before any
list identifier enters semantic scope. Up to 32 specifiers are allowed. They
may be interleaved with built-in type, storage and qualifier specifiers.
They must precede a typedef, record, enum, typeof, or atomic type specifier: these
can introduce bindings whose source order is not yet modeled by this slice.

An operand is a complete object type-name or checked integer constant
expression. Zero has no effect; nonzero requests combine by maximum and cannot
weaken the natural alignment. Supported values are 1, 2, 4, 8 and 16. An
incomplete record object with a nonzero request is rejected until its natural
alignment is known; an unknown-bound array with complete element type has a
known alignment. Object alignment is storage metadata, not a type qualifier.
QBE local slots use alloc4/8/16 and static/TLS data use the effective alignment.

For named members, the request affects struct offsets, union/struct alignment,
tail padding, aggregate size and array stride. Nested record layouts retain
these properties. Anonymous aligned members, bit-fields, and flexible members
remain unsupported. Cross-scope C23 structural compatibility and common-initial-
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

Still unsupported: specifiers after non-builtin type specifiers, alignment on
typedefs, parameters, register objects, functions, anonymous members, or
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
operand; they have not been run. The compiler build succeeded at this checkpoint. Other specifier types remain restricted as above, and no milestone
completion or approval is implied.
