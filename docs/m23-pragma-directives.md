# Pragma directives

A `#pragma` directive with an unrecognized body is consumed as raw preprocessing
tokens and has no effect; its body is not macro-expanded. Empty pragmas are also
accepted. Malformed preprocessing tokens remain errors. Directives in inactive
conditional groups remain ignored.

The implementation rejects `#pragma STDC`, `#pragma once`, and `#pragma pack`
rather than silently discarding requested floating-point, inclusion-identity, or
layout effects. `_Pragma`, other implementation-specific effects, and complete
standard floating-environment support remain unimplemented. This is a source
checkpoint; the added tests have not yet been run.
