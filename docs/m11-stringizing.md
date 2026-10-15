# M11a: raw argument stringizing

## Decisions before implementation

Reference: WG14 N3096 6.10.4.2:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

Implement # and its %: digraph before named parameters or __VA_ARGS__ in
function-like replacement lists, including inside selected __VA_OPT__ bodies.
Validate operator operands at definition time and preserve transactional
redefinition. # before a nonparameter is an error. The valid C23 form
#__VA_OPT__(...) is explicitly deferred to M11b: it needs optional-body argument
substitution semantics and will diagnose as unsupported, not silently stringify
raw operator text. ##/%:%: remain unsupported until their own checkpoint.
Object-like # remains an ordinary replacement token, never a directive.

Stringize raw argument tokens without prescan, even if a nested macro call has
wrong arity. Strip leading/trailing trivia; collapse intertoken whitespace to
one space; retain all other spelling bytes. Escape backslashes and double quotes
only within string/character preprocessing tokens (including their prefixes).
Choose to escape every backslash within those literals; UCN support remains a
later lexical milestone. An empty argument yields "". A nonliteral standalone
backslash is rejected rather than manufacturing an invalid string spelling;
valid-string requirements and UCN support are not guessed from this subset.

Own synthesized spelling in the preprocessing arena. Each generated token gets
an arena-allocated prepared source view and NUL-terminated byte buffer; it does
not masquerade as a slice of the original input. The view borrows a static name,
owns nothing independently and must never be passed to source_destroy. Its
lifetime is preprocess_destroy, after all AST use. Diagnostic locations remain
the outermost original invocation. Keep token/source APIs unchanged; consumers
must read spelling_location.source (or pp_token.location.source), not assume
it equals the original input. Count views in the auxiliary-record budget and
cap cumulative synthesized bytes, including terminators, at 1 MiB per TU.
Measure safely before allocation, stop early at the remaining byte budget,
charge raw-token visits as work, and latch invalid then EOF on resource failure.

Stringizing makes whitespace metadata semantically observable. Preserve source
newlines as separation when discarding newline tokens. On expansion, the first
replacement/argument token inherits the invocation/parameter occurrence spacing,
not the definition's leading trivia or the argument's stripped leading trivia.
Carry separation across empty replacements/arguments/optional regions. Optional
operator delimiters do not emit whitespace; selected bodies inherit the marker's
spacing. Maintain explicit per-frame first-token spacing and cursor deferred
spacing, including completed frames and pending lookahead. Test nested expansion
and empty-region cases against both hosts rather than infer from pretty output.

Expose preprocess_next_pp for expanded preprocessing-token consumers. It shares
the same cursor; clients choose pp reads OR cached language reads, never mix
while a language lookahead is pending. Convert preprocessing failures to pp_invalid
without adding diagnostics. The parser still receives cached language tokens;
string/character semantics and concatenation remain M13. Test-only pp inspection
can observe generated string tokens without pretending they compile as C strings.

All production stringizing code stays in preprocess.c. No parser/AST/sema/QBE
changes. Extend oracle/unit/provenance/cache/resource tests and both fuzz seeds;
add defined QBE programs that generate then discard string tokens. Keep prior
oracle coverage, add pp-mode comparisons, and validate normal/sanitized GCC/Clang,
QBE/ABI, bounded fuzzing and exact pushed-commit CI. Update limitations/contracts/
coverage/handoff, and push tested checkpoints before lengthy final validation.


## Implementation refinements and observed host differences

Raw collection clears only the first token's original argument trivia. Prescan
may create meaningful leading/trailing separation when an internal macro expands
to nothing; cache that separation and retain it when injecting the argument.
Expanded public EOF is normalized even when deferred whitespace remains; internal
prescan EOF still exposes deferred separation to its owning argument cache.

The oracle found GCC/Clang differences in two-level stringizing around empty
optional bodies, optional-body edge spacing and removed macros inside arguments.
kcc chooses the tested GCC behavior for this checkpoint. Five explicit policy
groups verify kcc's chosen output and retain both observed reference outputs;
they are not part of the 706 cross-host agreement streams. This is an unresolved
interpretation/conformance audit item, not a declaration that ISO permits every
host difference. The implementation does not copy Clang's optional-delimiter
whitespace or discard GCC's internally created argument separation.
