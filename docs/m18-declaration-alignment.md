# M18: declaration alignment, bounded automatic-object slice

This is an implementation checkpoint, not M18 completion or a tested/release
checkpoint. Under the x86-64 SysV/QBE target, `alignas` and `_Alignas` are
recognized after preprocessing and accepted on a single ordinary automatic
block object declarator (including for-init declarations). Up to 32 specifiers
per declaration are retained in source order and must precede the declared
type specifier (storage and qualifiers may precede them). The operand is a complete object
type-name or checked integer constant expression. Zero has no effect; nonzero
requests are combined by maximum and must not weaken the object's natural
alignment. The supported requested values are 1, 2, 4, 8 and 16. The request
is storage metadata, not a type qualifier: sizeof, alignof(type), compatible
types and array stride remain unchanged. QBE local slots use alloc4/8/16.

Out of scope and explicitly rejected: file-scope objects; block static,
thread-local, extern and register objects; record members; parameters;
typedefs and type-names; functions; inferred-auto declarations; multiple
aligned declarators; alignment specifiers after a type specifier; and requests
above 16. These are implementation limits,
not claims that all such C programs are invalid. In particular, linkage and
cross-declaration alignment consistency, record padding/stride, external ELF
alignment, and larger extended alignments need separate end-to-end designs.

Alignment operands are checked in order before the declared type is resolved
and before the object is bound; they generate no runtime evaluation. Type names and expressions use existing bounded parsers and
constant evaluation. The maximum effective request is checked against the
natural alignment after resolving the declared type. The ordering restriction avoids resolving a later type definition before an
earlier alignment operand. Full C23 specifier-order support requires additional
work and tests before broadening this slice.

Added focused acceptance, rejection, IL and optional QBE-runtime tests, wired into
both project test targets. Per task instruction no tests, fuzzing, or test suites
were run; a compiler build alone was performed. Full normal/sanitizer, native
oracle, QBE/runtime, bounded fuzz and exact-source CI gates remain outstanding.
No conclusion about M17 approval follows from this work.
