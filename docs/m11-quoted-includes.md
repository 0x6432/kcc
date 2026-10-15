# M11k: direct quoted includes (design before implementation)

Start include handling with direct, unprefixed #include "relative-or-absolute-path"
(and %:). Resolve relative names against the including source's directory; no
system search directories, -I, angle names or macro-computed operands yet. Reject
empty names, backslashes/escaped names and prefixed strings explicitly instead
of pretending the string-literal lexer implements every header-name rule.
Those forms/search policies belong in subsequent increments.

Use an optional source-loader callback on the preprocessor. Default NULL means
no file loading; the file driver and test oracle explicitly supply a wrapper
around source_load. Fuzzers supply only a memory-backed loader, never arbitrary
filesystem access. Loader initializes a fresh source; preprocessing owns successful
children, prepares them before borrowing tokens, and destroys every child only
at preprocess_destroy. AST/source spelling lifetimes therefore do not change.
No global include cache or path canonicalization is needed in this increment.

Keep a bounded stack of parent pp_lexer states. Reading a child's EOF through
ordinary source rescanning restores its parent and continues; directive readers
still see that child's EOF as a line end and cannot accidentally eat the next
file. Include directives themselves contribute no parser tokens. Macros persist
across files; skipped includes perform no loader calls. Expansion and source
lookahead remain on demand, not whole-translation-unit token vectors.

Each source has a conditional-stack base. #else/#endif cannot close a parent
file's group. At child EOF, an unclosed local conditional diagnoses once and
stops predictably rather than escaping into the parent. Preserve the deferred
EOF diagnostic/parser-success contract. Source locations retain the actual
child filename and physical line mapping, including splices and normalized
newlines. Final public EOF remains the root source's stable EOF.

Limits: 32 active include frames, 128 loaded/attempted headers, 64 MiB cumulative
child input bytes, 4096-byte constructed paths, plus existing per-source and
macro budgets. Retain completed child buffers until compilation ends; this is
required ownership, not a leak. Failed loading/preparation must leave no owned
buffer behind or leak partially initialized sources. Document all budgets.

Acceptance: temporary nested headers, relative/absolute resolution, macros and
include guards shared with parents, excluded includes, repeated includes,
condition boundary errors, original filename/line diagnostics, header EOF and
source lifetimes, depth/total-byte/attempt/path limits, all newline variants,
GCC/Clang pp selection and QBE/reference execution. Add memory-only include
fuzzing to pipeline CI, with both successful and failing header loads, bounded
recursion and no execution of arbitrary C. Update source-provenance assertions
only where real child sources are introduced; synthesized views remain distinct.
