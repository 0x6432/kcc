# M24: bounded bit-precise foundations (not source-language support)

This incremental checkpoint deliberately does **not** implement `_BitInt` in C
source. The language-token boundary diagnoses `_BitInt` explicitly; the shared
integer-spelling decoder recognizes `wb`/`WB` and optional `u`/`U` but both
ordinary tokens and evaluated preprocessing conditions reject such literals.
Malformed suffixes and values beyond `UINT64_MAX` still fail spelling conversion.
Inactive preprocessing groups keep the existing skipped-group behavior.

`src/bitint.c` supplies independent internal building blocks for a future
implementation, not a replacement for C semantic analysis or code generation:

- A distinct `(width, signedness)` description, with signed widths 2–64 and
  unsigned widths 1–64, and minimal `wb` literal width selection. A signed
  literal value of 2^63 or more requires at least 65 bits and is rejected by
  this bounded model rather than assigned `long long`.
- Identity promotion for non-bit-field bit-precise types and the common type
  of two bit-precise operands. Standard/bit-precise combinations, integer
  bit-fields and their promotion/rank rules are not handled by this API.
- Canonical low-width two's-complement bits, conversions, comparisons, checked
  same-type addition, subtraction, multiplication, division and remainder,
  plus bitwise AND/OR/XOR. Unsigned results wrap at the specified width;
  signed overflow and division by zero are reported. Conversion to an
  out-of-range signed destination follows this model's explicit modulo
  two's-complement choice. The API has no object storage or ABI interpretation.

This is a bounded internal arithmetic model only. The parser, AST, type system,
constant evaluator and backend do not yet use it. Expression shifts and unary operators are not connected to this API; mixed
standard-type conversions, arbitrary-width arithmetic,
objects, layouts, calls, returns, external linkage and ABI interoperability
are not implemented. All source `_BitInt` widths and `wb` literals are rejected,
including those within the model's range. No claim is made that a particular
object layout or ABI is correct; these must be designed and validated before
source acceptance. For width >64 the internal helpers return invalid width.

Tests were added for width inference, bit-precise-only conversion, arithmetic,
source rejection, suffix recognition and preprocessing. They were not run in
this checkpoint at the user's request. `build/kcc`, `build/test_bitint` and
`build/test_lex` compiled successfully; compilation is not a test result.

The internal API also handles unary plus, negation and complement, plus checked
left/right shifts on already-promoted bit-precise operands. Negative shift counts
must be rejected by the caller; counts at least the operand width are rejected
by the helper. Signed right shift uses arithmetic fill; signed negative or
overflowing left shift and negation of signed minimum are rejected. These are
internal foundations only, not source-language support. New cases were added to
the test binary but not run; the compiler and test binary were built.
