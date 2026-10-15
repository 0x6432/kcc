# M11e: macro-existence conditional groups (design before implementation)

This increment implements #ifdef/#ifndef, C23 #elifdef/#elifndef, #else and
#endif with %: spellings. #if/#elif expression evaluation is the next increment;
active instances remain explicitly unsupported rather than guessed as false.
A nested #if inside an excluded group must still be balanced structurally.

Keep a fixed 128-entry conditional stack in the preprocessor, not the C AST.
Each group records parent activity, current branch activity, whether any branch
was selected, whether else appeared, and the opening source location. Selecting
one branch prevents evaluating subsequent alternatives. Macro existence tests
consult the current define/undef binding without macro-expanding the name.
A condition actually evaluated must contain exactly one identifier. An excluded
condition consumes its raw line without validating its operand expression.
Else/endif have no operands; orphaned, repeated and misordered controls diagnose.
Validate each control transactionally before changing stack or macro state.

Inactive ordinary tokens bypass expansion and language conversion. Only source
line-start directive names are structural: nested openers, alternatives and
endif are processed; define/undef/error/warning/include/unknown directives are
drained without effects. Raw lexical errors still diagnose because translation
phase 3 precedes conditional exclusion. A generated # is never a directive.
Never hide a malformed active #if or #elif behind this subset.

EOF with an open group diagnoses at its opener once and returns stable EOF;
existing diagnostic counts suppress IL even if no invalid parser token is
returned. Exceeding the nesting bound stops preprocessing predictably. Existing
macro-invocation lookahead restrictions remain explicit; this increment does not
make directives inside macro arguments supported. No include stack yet.

Tests cover branch/macro state, undef, nested excluded unsupported directives,
nonexpansion, C23 alternatives, digraphs, all newline policies, structural errors,
128/129 depth, EOF diagnostic/cache stability and active-operand constraints.
Compare selected pp-token streams with GCC and Clang, execute defined selected
programs through QBE/reference compilers, and add both fuzz seeds. Test complete
normal/sanitizer host matrices on isolated committed snapshots so continuing
implementation cannot race validation builds.
