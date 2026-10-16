# M13i: adjacent ordinary string concatenation (design before implementation)

Extend string-primary grammar to ordinary-string-token { ordinary-string-token }
after preprocessing. Whitespace/comments, expanded macros and removed directives
may separate fragments; comma/operator tokens stop the sequence. Prefix/Unicode
rules and initializer limitations remain explicit. Do not concatenate raw text
before escape decoding: each fragment's octal/hex escapes stop at its own closing
quote. For example "\x12" "3" is byte 18 followed by '3', not hex escape 0x123.

Collect only this bounded sequence in parser-local linked fragment records, not
a translation-unit token vector. Measure lengths from already validated token
metadata, check subtraction-based sum/storage limits before allocation, then
decode each borrowed spelling directly into its part of one final arena buffer.
Append exactly one final NUL, retaining embedded NUL bytes and no inter-fragment
terminators. Preserve the first fragment's expression location. Update the string
AST constructor to take location/bytes/length rather than a fabricated aggregate
token; semantic static-object registration/array type/codegen need no changes.

Resource limits apply to resulting objects: 1 MiB decoded bytes per sequence,
8 MiB total object bytes including one final NUL per sequence, and 4096 result
objects per TU. Add 4096 fragments per sequence and 16384 fragments per TU to
bound temporary records even for empty strings. Keep counters across functions.
All spelling views obey the existing pp/source/arena lifetime contract.

Test direct/macro/comment/directive/spliced adjacency, empty fragments, embedded
NUL, greedy hex and three-digit octal boundaries, postfix precedence and static
host ABI in both directions. Assert one combined array/static object and original
first-fragment location in typed units, exact fragment/decoded/storage limits,
and literal count versus fragment count. Compile only giant limit fixtures.
The prior now-valid adjacency rejection must become a permanently unsupported
prefixed/mixed-encoding sequence, preserving its unsupported-string constraint.
Run every previous regression, both hosts, sanitized bounded fuzz, isolated
normal/sanitizer matrices and exact-source CI. Never modify or order/subtract
separate literal occurrences to manufacture a test oracle.
