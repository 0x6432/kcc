# M11i: unsigned preprocessing integers (design before implementation)

Replace the evaluator's implicit signed scalar with one explicit private value
struct containing uint64 bits and an unsigned-type flag. This is not a universal
AST union and does not affect C runtime types. All signed/unsigned conditional
integer types act as intmax_t/uintmax_t for this target (64 bits). Retain checked
signed evaluation and add modulo-2^64 unsigned arithmetic.

Literal selection: decimal without U must fit intmax; valid U suffix combinations
(u/U with optional l/L/ll/LL before or after) select uintmax. Unsuffixed nondecimal
values above INT64_MAX and at most UINT64_MAX select unsigned. Preserve full
spelling validation and report values beyond uint64, rather than wrapping them.
Bit-precise wb/WB suffixes and character literals remain separately deferred.

Centralize usual arithmetic conversion: if either operand is unsigned, convert
both to uintmax; otherwise remain intmax. Comparisons and logical operators yield
signed 0/1. Bitwise and arithmetic operators retain their common operand type.
Shifts retain the left type and do not convert via the right operand; validate
right counts using its own type. Unsigned left shifts wrap, unsigned right shifts
are logical, and signed right shifts keep the documented arithmetic policy.
Unary +/~ retain type; unary - wraps for unsigned but checks signed minimum.
Division/modulo by zero always diagnose when evaluated; MIN/-1 only fails for
signed operands. Avoid implementation-defined uint64-to-int64 casts through one
explicit mathematical bit-pattern decoder for values above INT64_MAX.

Ternary requires type information from both branches even when one is not
selected: parse/type both, evaluate only one, compute common signedness and
convert the chosen value accordingly. Unevaluated arithmetic returns harmless
bits but the correct type, so expressions such as (1 ? -1 : 1U) < 0 evaluate
correctly. Logical short circuit follows the same parse/type/evaluate distinction.

Tests must cover mixed signed/unsigned arithmetic/comparisons, maximum wrap,
negation, complement, division, shift counts/types, ternary common type with
unselected failures, macro-generated suffixes, overflow and resource regressions.
Use Python integer models with explicit masks, GCC/Clang stream agreement,
QBE/reference selection programs, and sanitizer fuzzing. Preserve all earlier
bounds, ownership and EOF/parser contracts; validate committed snapshots before
claiming completed full matrix/CI.
