# M11f: initial #if/#elif expressions (design before implementation)

Extend the conditional stack with evaluated #if/#elif, without coupling it to
C AST/sema/codegen. Initially support signed 64-bit decimal preprocessing
integers (intmax_t on the selected LP64 target), parentheses, unary + - !,
* / %, + -, relational/equality operators and short-circuit &&/||. Remaining
integer spellings, unsigned arithmetic, characters, bitwise/shifts and ?: are
explicit subsequent increments, not silently accepted as this subset.
C23 true/false map to 1/0; other remaining identifiers map to zero.

Read only the directive's raw pp tokens into a bounded invocation-like list.
Replace literal defined identifier / defined(identifier) before macro expansion,
without expanding its operand. Expand the rest using an isolated existing macro
cursor that cannot consume source beyond the directive. A defined identifier
produced by expansion is diagnosed rather than assigned a guessed meaning (the
standard leaves that case undefined). All current macro resource budgets apply;
the directive list is separately capped at 1024 raw preprocessing tokens.
Generated defined-result spellings share the existing arena/spelling budget.

Evaluate the expanded stream on demand with recursive descent for operands and
a Pratt binding table for binary expressions. Each function documents its BNF.
Limit syntax recursion to 128. Parse all syntax even in short-circuited operands,
but never perform their arithmetic: 0 && 1/0 and 1 || overflowing arithmetic
must not diagnose evaluation errors. Check signed overflow before operations;
never trigger host signed-overflow/division undefined behavior. Expansion itself
is not short-circuited. Error diagnostics use macro invocation locations.

Collect/validate before selecting a branch, preserving transactional stack
updates. Earlier selected alternatives and children of inactive parents continue
to skip expressions without expansion or evaluation. Empty expressions, missing
operands, unsupported tokens and malformed defined forms diagnose. Compiler IL
remains blocked by diagnostic errors even when stream recovery is possible.

Acceptance: GCC/Clang token selection oracles and deterministic expression
models; precedence, associativity, defined nonexpansion, macro argument/paste
interaction, signed boundaries, overflow/zero division, short-circuit syntax,
exact recursion/list limits, branch state, QBE/reference execution and both
sanitized fuzz targets. Full host/sanitizer validation uses an isolated committed
snapshot. No claim of complete preprocessing integer semantics at this stage.
