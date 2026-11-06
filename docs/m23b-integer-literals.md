# M23b: binary integer constants and digit separators

The existing shared integer-spelling decoder already supports the C23 binary
prefixes `0b` and `0B`, and apostrophe separators in integer digit sequences.
This checkpoint exercises that existing implementation rather than introducing
another numeric lexer. Preprocessing-number tokenization remains separate from
integer conversion and retains its maximal-munch rules.

Binary digits are `0` and `1`; a prefix must be followed by a digit. A separator
must occur between two digits valid for the base, including in decimal, octal and
hexadecimal constants. It cannot follow a binary or hexadecimal prefix, precede
a suffix, be doubled, or make an out-of-base digit valid. Standard U, L and LL
suffix combinations retain their existing spelling and type-selection rules.
Accumulation is checked against `UINT64_MAX` before multiplication and addition.
Runtime type selection uses the existing decimal/nondecimal candidate lists;
preprocessor conditions use the existing intmax/uintmax model. Both paths use
the same spelling decoder. Integer typing and diagnostics remain subject to the
compiler's existing target model and supported types.

Bit-precise `wb`/`WB` literals now work in expressions only when their exact
minimum C23 width is 8, 16, 32 or 64, corresponding to supported semantic
`_BitInt` types. Other required widths and signed values requiring more than 64
bits remain rejected in ordinary expressions. Preprocessing conditions and
`#embed` limits accept `wb`/`WB` using the 64-bit intmax/uintmax model,
including literals with other minimum widths; signed suffixes exceeding
`INT64_MAX` and all values exceeding `UINT64_MAX` are rejected. The
unsigned suffix is accepted before or after `wb`/`WB`. See
`m24-bitint-foundation.md`. Floating constants have separate bounded support
in `m20-floating-foundation.md`. This is not full M23b or C23 literal support. The
preprocessing lexer may legally form an invalid preprocessing number that the
integer decoder later rejects; a trailing apostrophe can instead start a
separate malformed character token. No change is made to token boundaries,
quoted literals, macro expansion, or legacy numeric rules.

## Local validation

The focused lexer, preprocessing-token, runtime-spelling and conditional-literal
tests pass with GCC 11.5 as the host. GCC 11 rejects separator syntax, so those
original-source host gaps are reported separately; normalized reference programs
are not native C23 agreement. The focused runtime tests checked compilation but
could not execute kcc output because QBE is unavailable. `make test` passed its
CLI, unit, macro and AST stages, then stopped at `tests/test_compile.py` because
QBE was not installed; the remaining full-suite and QBE/runtime checks are not
claimed. Fuzzing was not run (Clang/libFuzzer is unavailable).

## Later validation

The conditional suffix increment was checked against the C23 draft's
preprocessing integer representation rules, with focused model checks for
signedness, limits, macro pasting, `#elif` and embed limits. The available
GCC 11 host cannot compare `wb`/`WB` syntax; no native C23 agreement is
claimed. Ordinary expression support is still limited as described above.
