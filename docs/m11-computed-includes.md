# M11l: macro-computed quoted include operands (design before implementation)

Extend M11k's quoted include handling by collecting one bounded raw operand line
and rescanning it through an isolated existing macro cursor. Do not interpret
defined as a condition operator here. Require exactly one resulting unprefixed,
nonempty quoted string token; no angle-name combination/search policy yet.
Macro stringizing, pasting and optional regions use their existing phases.
Function-like macro lookahead must stop at the isolated directive EOF and cannot
consume the following line. Expansion/storage/spelling budgets remain shared;
the raw operand list is limited to 1024 pp tokens.

Always resolve relative paths against the source containing the #include marker,
not the resulting string token's spelling source: that source can be an arena-
owned generated view or a macro definition in another header. Diagnostics use
invocation locations. Copy the validated path before loading a child and preserve
M11k's retained source ownership, conditional bases and file EOF rules.

The entire operand line is already consumed before expanded-token validation.
Do not use raw directive-drain recovery afterward or it will eat the next line.
Raw lexical/whitespace errors still drain only their actual source directive.
Expansion/format failures must not call the loader or mutate source stack state.

Tests cover aliases, stringizing paths with punctuation/directories, macros
defined in another header, generated-source relative resolution, empty/multiple/
prefixed results, discarded trailing macros, recursion, failed calls that must
not consume the next line, shared resource limits and loader call counts. Add
hermetic filesystem/unit tests, GCC/Clang pp/QBE comparison and memory-only fuzz
seeds. Includes remain a separately tracked subset until angle/search behavior
and the complete header-name/encoding/environment audit are implemented.
