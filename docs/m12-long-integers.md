# M12e: LP64 long/unsigned long (design before implementation)

Extend the existing explicit type pipeline to 64-bit long/unsigned long first;
long long remains a separate M12f rank/grammar increment. char/short/promotions
remain subsequent work. Keep primitive type kinds plus centralized type.c
helpers for width, signedness, rank, unsigned counterpart and usual arithmetic
type selection. Do not scatter kind tests through parser/codegen or treat long
and long long as interchangeable merely because LP64 widths match.

Parser adds long specifiers in valid orders (one long, optional int/sign), stores
new AST specifier enum values and handles them in declarations and explicit
casts. Duplicate/conflicting specifiers remain errors. LL and long long diagnose
as unsupported until M12f. Main return remains signed int only.

Preserve base/U/long suffix count as token/AST spelling facts. Sema chooses the
first fitting implemented standard candidate: unsuffixed decimal int,long;
unsuffixed nondecimal int,uint,long,ulong; U uint,ulong; L decimal long and
nondecimal long,ulong; UL ulong. No positive decimal value beyond INT64_MAX may
silently become signed or unsigned without U. Any missing candidate type or
unsupported suffix remains explicit, never a truncation shortcut.

Usual conversions compare rank and representable ranges: signed long represents
all uint values, so long+uint is long; ulong with int/uint/long is ulong. Shift
operands still promote independently. Conversion nodes widen signed 32-bit with
extsw and unsigned 32-bit with extuw, independently of destination signedness;
narrowing uses a word copy; same-width sign changes preserve bits. This includes
negative int -> ulong becoming modulo 2^64, not merely zero-extending low bits.

Codegen must use QBE w/l throughout: literal/copy/unary/arithmetic instructions,
comparison suffix w/l (comparison result always w), load/store and alloc4/alloc8,
function parameter/return declarations and call arguments/results. Long truth
must compare all 64 bits to zero before jnz: never truncate a long condition to
word. Audit !, logical short circuit, if/while/do/for individually. Shift counts
are word operands, narrowing a valid 0..63 count only after source typing. QBE
acceptance of UINT64_MAX textual constants must be checked, not assumed.

Tests require full-width signed/unsigned boundary/type selection and conversion
AST checks, high-only-bit truth in every control flow, mixed int/uint/long/ulong
usual conversions, division/remainder/right shifts, calls/returns/narrowing,
separate-object mixed-width ABI both directions with stack arguments and recursive
functions. Independent models use only defined signed arithmetic/shifts and
modulo unsigned arithmetic. Run full hosts/sanitizers/fuzz/CI and document any
QBE/ABI discovery before extending scope. No floating/pointer/other-width claim.

Implementation notes from the preflight audit:
- A curated QBE 1.2 probe returned 42 after checking UINT64_MAX decimal copy,
  unsigned long division, extsw/extuw, l-to-w copy and a 63-bit logical shift.
  This verifies backend mechanics, not compiler long support.
- Central primitive-property rows (kind/bits/rank/unsigned/counterpart) can keep
  type queries coherent and make later ranks explicit. Literal candidate lists
  should select by representability, not first truncate and inspect a sign bit.
- A typed codegen truth helper should normalize a whole w/l value to a w boolean
  for every branch and logical path. Audit all direct jnz emission sites.
- Existing diagnostic fixtures rejecting L values should move to still-unsupported
  floating pp numbers, rather than churn again at M12f. Range tests that become
  valid with long must move into positive coverage, not remain accidental rejects.
