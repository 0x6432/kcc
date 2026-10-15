# M12g: ordinary character constants (design before implementation)

Add ordinary single-byte character constants to runtime expressions, independently
of the upcoming char/short declaration types. An ordinary character constant has
int type, not char type. Keep a distinct language token and concrete AST struct;
negative target character values must never masquerade as unsigned magnitudes.

Extract M11j's existing escape/target-byte rules into a pure lex.c spelling helper
shared by preprocessing and language-token conversion. It accepts an explicit
byte slice and returns a static error string or a signed value through an output
pointer. It does not allocate, emit diagnostics, inspect source buffers outside
the slice, or choose a context's type. Validate delimiters and empty/truncated
slices before indexing; fuzz arbitrary slices directly, including zero length.

Scope: one ASCII source character or simple escape, octal escape (1–3 digits),
or hexadecimal escape (1+ digits), with escaped value <=255. The target has signed
plain char: bytes 128–255 map to -128–-1. This implementation-defined policy is
shared with existing #if behavior and independent of host char signedness.
Reject prefixes, multicharacter constants, Unicode/UCN, non-ASCII source bytes,
and overlarge escapes explicitly. String literals and char declarations remain
separate work. Do not broaden preprocessing arithmetic or literal types here.

Parser primary-atom gains character-expression, with a BNF-documented helper.
Sema annotates int/non-lvalue and codegen emits a signed word constant. Preserve
macro invocation diagnostics and spelling-source ownership. Extend token dumps,
AST units, shared decoder boundary tests, both-host full-value runtime oracles,
macro/normalization regressions and fuzz corpus/invariants. Run all old conditional
character oracles, full regressions, QBE, sanitizers, bounded fuzz and exact-source
CI before calling the milestone fully verified.
