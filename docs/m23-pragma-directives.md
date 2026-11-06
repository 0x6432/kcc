# Pragma directives

A `#pragma` directive with an unrecognized body is consumed as raw preprocessing
tokens and has no effect; its body is not macro-expanded. Empty pragmas are also
accepted. Malformed preprocessing tokens remain errors. Directives in inactive
conditional groups remain ignored.

`#pragma once` suppresses later inclusions with the exact same source name
returned by the configured loader, including recursive inclusion. Paths are not
canonicalized: different spellings or symlinks to the same file are not treated
as identical. The loader is still called before a repeated include is skipped.

The implementation rejects `#pragma STDC` and `#pragma pack`
rather than silently discarding requested floating-point or layout effects.
`_Pragma("...")` is supported in the main expanded token stream, including
macro-produced operands such as `#define DO_PRAGMA(x) _Pragma(#x)`. The ordinary
string literal is destringized by unescaping `\\` and `\"`, then handled like
`#pragma`; `once` uses the operator's actual expansion file. Malformed forms,
wide/prefixed operands, nested operators and operators encountered during
isolated macro-argument or directive expansion are rejected. Diagnostics for
pragma-body errors can refer to synthesized spelling. Processing shares the
existing expansion, storage and include limits. Other implementation-specific
effects and complete standard floating-environment support remain unimplemented.
The compiler builds and focused direct, macro, once and negative examples were
compiled; regression and runtime tests remain unrun.
