# M23d2 correction: nullptr assignment-like conversions and native cast gaps

Audit before implementation. Public CI 38919183328 revealed GCC accepts
`typeof(nullptr) n=0;` while kcc rejects it; Clang rejects the separately valid
explicit `(typeof(nullptr))0` cast. These are not the same oracle failure.
N3096 6.5.16.1's normative constraint explicitly admits a null pointer constant
on the right of a nullptr_t assignment, contradicting its stale footnote 127.
The later official public N3220 6.5.17.2 retains that normative rule and removes
the contradictory footnote. Follow the normative text, not the footnote: fix
kcc's implicit conversion gate for initialization, assignment, arguments and
return. Do not label GCC's correct acceptance a host extension.

Extend the existing expression-sensitive null-source gate to nullptr_t targets,
using the same checked null constant classifier as pointer conversion and explicit
casts. Keep explicit typed conversion nodes, depth checks and general scalar
conversion constraints; no broad integer-to-nullptr conversion. Literal/ICE zero,
(void *)zero ICE and nullptr_t values qualify. Nonconstant zero, nonconstant null
pointer objects, nonzero and non-ICE zero expressions do not qualify. No codegen
representation change is needed: the existing LP64 conversion emits zero bits.

Replace obsolete rejection fixtures with valid runtime cases and retain all
four assignment-like invalid-context checks using nonconstant zero objects.
Add typed-tree and context/once-only tests and seeds. The valid explicit-cast
fixtures must remain kcc/QBE checks. Any native cast rejection must be classified
by exact original source and exact expected diagnostics, never a GNU rewrite or
broad failure skip. Do not count these as agreements. Validate actual modern
hosts where possible, full normal/QBE, both local host ASan/UBSan and bounded
compile-only fuzz. Update the earlier design and contracts to correct the claim,
record CI evidence separately and commit/push after validation.
