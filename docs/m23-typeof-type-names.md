# M23d1: typeof and typeof_unqual with type-name operands

Design before implementation, N3096 6.7.2.5. Keep this first increment small:
implement type-name operands only. M23d2 will add expression operands with
unevaluated root typing; do not silently decay values or fake typeof as a macro.
No GNU spelling aliases, typedef names, atomic types, VLA evaluation or bit-fields
are implied. The standalone function-declarator/sole-void-parameter alias cases
need a later declarator-normalization increment; report clear subset errors
rather than constructing synthetic parameter ASTs.

Add demand-language typeof/typeof_unqual tokens after preprocessing. Add a
concrete ast_typeof_type_syntax with a type-name operand and operator flag,
keeping source location and the ordinary resolved-type cache. RDP parses
("typeof" | "typeof_unqual") "(" type-name ")" with subset BNF comments.
One demand peek distinguishes currently supported type-name starts; expression
operands have an explicit unsupported diagnostic until the next increment.
Type-query nesting is bounded at 64, including queries nested through casts,
sizeof and array bounds; this counter is independent of the existing expression
and declarator guards and restored on failure.

Declaration specifiers allow qualifiers before/after one typeof specifier but
reject duplicate queries or mixes with other actual type specifiers. Resolve the
operand through existing immutable type syntax; typeof shares its type, while
typeof_unqual calls existing target-independent root-unqualification. C23 array
qualification follows elements until a pointer, and pointer referent qualifiers
remain unchanged. Reject attempted qualification of a function type before the
existing qualifier helper's assertion. Ordinary declaration/parameter/function
return checks still apply. Type queries add no expression runtime instructions;
sizeof/static_assert/array-bound consumers see existing target layout and ICEs.

Tests cover all integer categories, pointers/arrays/function pointers, qualified
root versus referent types, nested queries, surrounding qualifiers, casts/void,
prototype/definition compatibility, adjusted array parameters, callbacks, bounds,
source locations/cache identity, const-write rejection, invalid type mixes and
exact nesting limits. Original-source native comparisons run only on hosts that
accept the actual C23 keywords. A tiny exact-diagnostic legacy probe labels host
absence, never substitutes __typeof__ or counts rewritten-source agreement.
Run both-host targeted ASan/UBSan, full normal/QBE, cross-object ABI and bounded
lexer/pipeline fuzz before commit/push and handoff updates. Generated fuzz C is
never executed.
