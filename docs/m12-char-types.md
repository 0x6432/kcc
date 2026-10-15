# M12h: char types and integer promotions (design before implementation)

Add three distinct compatible-type identities: plain char (target signed), signed
char, unsigned char, width 8, shared rank below int. Parse char with optional sign
in either order; disallow int/long/duplicate char combinations. Ordinary character
constants remain int, as implemented in M12g. Short/bool are separate increments.

Add type_integer_promotion(): all three byte types promote to int. Unary +,-,~
and both shift operands get explicit promotion nodes; arithmetic/comparisons
promote before usual conversions. Logical/! operators need truth, not a changed
source value. Assignment/init/arguments/returns convert to their exact declared
type without a default promotion. Recompute/check typed depths after inserted
nodes. Plain char and signed char are incompatible despite identical bits.

Invariant: each emitted integer value is canonical for its semantic type in its
QBE base word/long. Signed byte values are sign-extended in a word; unsigned byte
values are zero-extended. Cast/conversion to byte uses extsb/extub even from long
(low-word operand is legal QBE subtyping). Byte->64 uses extsw/extuw according to
source signedness after that canonicalization. Byte->word copies canonical bits.
Assignment expression values must reflect narrowing, not the unconverted RHS.

Separate QBE base types (w/l) from ABI names (sb/ub/w/l), loads (loadsb/loadub)
and stores (storeb). Function/call signatures use sb/ub. Narrow call results have
unspecified upper bits in QBE and MUST be explicitly canonicalized immediately,
even when the next operation is truth, assignment or a same-type cast. Function
parameters spill their low byte before signed/unsigned byte loads. Byte locals
use alloc4 1 (valid stronger stack alignment), not nonexistent alloc1; target
byte alignment remains 1 for future layout. No pointer/object-layout claim yet.

QBE 1.2 curated probe passed both GCC and Clang: sb/ub parameters/returns, explicit
return-result extensions, storeb/loadsb/loadub and alloc4 1, exit status 42. Full
compiler tests must cover promotion type identities, byte wrap and signed narrow
policy, high-bit truth, every conversion source/target width/sign, assignment
results, macro type syntax, typed-depth bounds and incompatible prototypes.
Add both-direction host separate-object byte ABI, including eight mixed arguments
and deliberately dirty upper return bits. Run prior regressions, both hosts,
sanitizers and bounded fuzz. Do not infer ABI correctness from kcc-to-kcc alone.
