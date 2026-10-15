# M11j: ordinary single-byte preprocessing characters (design before implementation)

Extend only preprocessing operands with ordinary, unprefixed character constants.
Support a single basic ASCII source character, standard simple escapes, one-to-
three-digit octal escapes and nonempty hexadecimal escapes. Numeric escapes
must fit one unsigned byte. C runtime character expressions/types remain absent.

Use the selected target's eight-bit signed plain-char policy: bytes 128..255
produced by escapes sign-extend before becoming signed intmax values. Document
that preprocessing character values match the chosen target's ordinary narrow
character interpretation; do not rely on host char signedness or locale.
Decode with explicit unsigned byte arithmetic and checked accumulation, never
host compiler evaluation of user text. Keep original invocation diagnostics.

Reject empty/multicharacter constants, non-ASCII source bytes, prefixed L/u/U/u8
forms, universal character names and unknown escapes explicitly. These need
later encoding/type/implementation-defined policy work, not guessed values.
All raw token, macro, syntax and memory limits remain unchanged. Parsing/type
checks apply in unselected operands too; only arithmetic evaluation is skipped.

Tests cover printable characters, quote/backslash/simple escapes, octal/hex
boundaries and target sign extension, malformed/unsupported forms, interaction
with unsigned comparisons and ternary common types, macro expansion/pasting,
LF/CRLF/CR QBE/reference execution, and both sanitizer fuzz targets. Compare
only the explicitly chosen target semantics with GCC/Clang. Record every scope
limitation and full validation status before continuing to include handling.
