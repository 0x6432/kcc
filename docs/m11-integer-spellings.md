# M11h: signed preprocessing integer spellings (design before implementation)

Extract numeric conversion from the conditional operand parser into a small
helper. Extend signed-intmax preprocessing literals with octal, hexadecimal,
C23 binary notation, valid digit separators and signed l/L/ll/LL suffixes.
These changes apply only to #if/#elif; runtime C expressions retain their
current int-only decimal conversion and must not silently gain other types.

Scan prefix/base, digits/separators and suffix separately. A separator must be
between two valid digits for that base, never next to a prefix or suffix. Reject
missing digits, invalid base digits, mixed-case long-long suffixes and unknown
suffixes. Bound accumulation against UINT64_MAX before multiplication/addition.

All accepted values in this increment must fit INT64_MAX. Standard unsigned
suffixes and nondecimal values requiring uintmax_t are explicitly rejected as
not implemented, not reinterpreted as negative signed values. Decimal values
outside intmax_t also diagnose. Keep distinct messages for spelling errors,
64-bit overflow and unsupported unsigned semantics. _BitInt wb/WB suffixes,
character constants and floating constants remain later work.

Use units for prefixes, suffixes, separators, min/max and invalid forms, plus
GCC/Clang conditional-selection and QBE/reference checks. Old GCC lacks C23
digit separators: test those explicit normative values separately, with known
legacy behavior recorded rather than counted as agreement. Add lexer/pipeline
fuzz seeds and run complete normal/sanitizer snapshot validation. Preserve all
short-circuit syntax, resource budgets and call-site diagnostic contracts.
