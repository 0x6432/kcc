# M13h: ordinary byte string literals (design before implementation)

Add one ordinary unprefixed ASCII/byte-escape string token as a primary expression.
Keep C23 encoding prefixes, Unicode/UCNs, adjacent literal concatenation and array
initializers separate increments. A literal denotes a static array of signed
plain char with decoded bytes plus a final NUL; embedded NUL bytes are retained.
Its ordinary value use decays through the existing array path. Address-of retains
pointer-to-array, and returning a literal pointer has static—not automatic—lifetime.

Factor only existing simple/octal/hex byte-escape decoding into a pure bounded
helper shared by character and string decoders. Preserve current character rules/
diagnostics. Ordinary string bytes exclude raw NUL/newline/CR, delimiter quote
and non-ASCII source bytes; escaped values 0..255 preserve their target byte bits.
Single quotes are valid ordinary string bytes. Hex escapes remain greedy, octal
escapes consume at most three digits, and over-one-byte/unknown escapes diagnose.

parse_string_spelling takes an explicit slice, optional output buffer/capacity
and decoded length (excluding the implicit trailing NUL). A NULL output measures
without allocation. Never read beyond the slice or write past capacity; partial
output on error is discarded. Lexer conversion validates/measures, records
string length in the on-demand token and allocates no decoded buffer. Token cache
invariants include that length. Parser allocates arena bytes, decodes again,
appends NUL and builds concrete ast_string_expression, not a fake identifier or
integer address. Limit one decoded literal to 1 MiB, total literal object bytes
to 8 MiB per translation unit, and literal count to 4096 before allocation.
These are resource limits, separate from automatic-object storage budgets.

Sema gives each literal an array-of-char type, lvalue category and unique static
object ID, recording a unit-owned list. Use the existing complete-object address
and array-decay paths; no string-as-scalar memory load. Do not merge occurrences
or promise pointer equality between separate literals. Modification of literal
storage remains undefined, never executed; lack of const qualifiers is not a
promise that writes are valid.

QBE emits unexported byte data objects before functions, with implicit NUL and
one-byte alignment. Private symbols use $.Lkcc.string.N so source C identifiers
and separately compiled units cannot collide. codegen_address for a string copies
its symbol into an l temporary; all indexing/loads/calls use existing typed paths.
A curated QBE probe with ASCII, embedded NUL, byte 255 and trailing NUL passed
GCC/Clang with signed-char loads and this private symbol convention.

Tests cover empty/ASCII/escapes/all 256 byte spellings, greedy hex/octal boundaries,
embedded/trailing NUL, static-lifetime returns, IL checks of whole-array
pointer strides (never subtract separate literal occurrences), macro stringizing/provenance and both host ABI directions. Add
pure decoder slices/capacity guards and direct fuzz roundtrips, typed array/decay/
static-object list units, count/byte/depth resource limits and no-dedup promises.
Earlier stringizing rejection fixtures must retain invocation anchors while now
rejecting invalid pointer-to-int returns; token conversion tests must expect a
valid string token, not drop the checks. Run all regressions, both hosts, bounded
sanitized fuzz, isolated normal/sanitizer matrices and exact-source CI.
