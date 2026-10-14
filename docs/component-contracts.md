# Component contracts

Interfaces are introduced with their implementing milestone, not speculative
empty headers. Any incompatible contract change must identify affected stages
and update their tests in the same checkpoint.

| Producer | Consumer | Contract |
| --- | --- | --- |
| source | lexer/diagnostics | Owned immutable bytes, explicit length, filename and byte locations; EOF is not a sentinel byte in the input |
| lexer | preprocessor/parser | One token per request; slices refer to live source; stable EOF; invalid bytes produce diagnostics and make forward progress |
| preprocessor | parser | Same token API; expanded tokens retain spelling and expansion provenance |
| parser | sema | Distinct concrete AST structs, source locations, no inferred semantics |
| sema | codegen | Validated typed AST, explicit conversions, resolved declarations; failure prevents codegen |
| codegen | QBE | Well-formed IL for the pinned target; no source-language validation here |
| arena | AST/stages | Compilation-lifetime ownership; alignment and overflow checked; destruction releases all chunks |
| driver | stages | Explicit initialization/destruction order; diagnostics on stderr, successful output on stdout |

Errors initially stop the affected compilation. Error recovery is a separate
milestone, not an accidental result of uninitialized nodes. Fuzz harnesses must
use the same public interfaces as the driver and release every compilation.

M00 interaction: driver has only argument handling; there are no compiler
stages to invoke yet. It rejects source input rather than pretending to compile.

M01 contracts: source_from_bytes/source_load initialize fresh structs and leave failures
empty; destroy is idempotent. Line/column clamps invalid offsets to EOF.
Diagnostic stream lifetime is caller-owned. arena_alloc(0) allocates one byte;
failed allocation leaves existing chunks intact. No support for over-aligned
types. All support stages have one implementation file.
