# M12a: signed-int bitwise and shifts (design before implementation)

Start runtime integer work without changing declaration/type syntax yet. Add
~ & ^ | << >> as language tokens and AST operator enumerators. Retain separate
concrete unary/binary structs and sema-inserted lvalue conversions. The only
runtime arithmetic type is still signed 32-bit int; no unsigned or wider integer
support is implied by preprocessing's independent 64-bit evaluator.

Pratt precedence: assignment < || < && < | < ^ < & < equality < relational <
shift < additive < multiplicative < prefix < postfix. Binary operators associate
left; assignment remains right. Update BNF comments with the added operators.
Unary ~ uses xor -1; binary bitwise ops use QBE and/xor/or; signed right shift
uses sar, left shift uses shl, all word operations. Negative signed right shifts
use the selected target's arithmetic policy. Negative/out-of-range counts and
nonrepresentable/negative signed left operands retain C's undefined-behavior
preconditions; do not claim masked QBE counts as defined C behavior. No constant
folding or sanitizer instrumentation is introduced in this small milestone.

Tests: all token spellings including macro paste, AST grouping and sema loads,
assignment/result/short-circuit interaction, associativity and comparison-vs-shift
precedence. Host/QBE runtime comparisons use only defined counts 0..31 and
nonnegative representable left shifts; test arithmetic negative right shift as
the explicit target choice. Deterministic bounded generated expressions must
have a defined independent model. Existing constraints, tree-depth bounds and
negative syntax remain enforced. Add lexer/pipeline fuzz seeds, never execute
arbitrary fuzz input. Run both hosts, sanitizers, ABI regressions and remote CI.

Next M12b will design runtime literal spelling and explicit type representation;
all integer types/promotions/conversions/casts must not be squeezed into M12a.
Remaining preprocessing encodings/contextual headers/#line/#pragma audit belongs
to the existing M23/M25 gap milestones rather than a full-M11 conformance claim.
