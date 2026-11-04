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
`_Pragma`, other implementation-specific effects, and complete
standard floating-environment support remain unimplemented. This is a source
checkpoint; the added tests have not yet been run.
