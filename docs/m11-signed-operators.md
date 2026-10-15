# M11g: remaining signed preprocessing operators (design before implementation)

Extend the signed-decimal expression evaluator with unary ~, shifts << >>,
bitwise & ^ | and the conditional operator ?: without changing the C AST or
runtime language subset. Keep one visible Pratt table: multiplicative, additive,
shifts, comparisons, equality, &, ^, |, &&, ||, then ?:, in decreasing precedence.
Binary operators remain left-associative; ?: is right-associative, with a full
expression between ? and :. Comma remains unsupported.

For ?: parse both branches but evaluate only the selected one; both branches
are still the same signed-64 type in this increment. Nested arithmetic failures
in an unselected branch must not diagnose, while malformed syntax still does.

Shift counts must be in [0,63]. Evaluated signed left shifts require a nonnegative
left operand and a representable result. Implement through checked unsigned
bits to avoid host UB. Negative right shifts use the target's arithmetic
(sign-extending) policy, implemented with nonnegative arithmetic/shifts rather
than relying on implementation-defined host negative shifts. int64_t bitwise
operations use its exact two's-complement representation.

Reuse existing raw/expanded token, recursion and ownership budgets. Add units,
GCC/Clang/model selection tests, executable QBE/reference tests and fuzz seeds;
verify short-circuit and ternary nesting failures, precedence, associativity,
shift boundaries and signed target policy. Unsigned and other literal types
remain a later independent increment, not silently approximated here.
