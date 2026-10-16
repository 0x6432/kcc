# M18b1: integer constant-evaluation foundation (design before implementation)

Introduce one readable consteval.c stage (plus interface header) over the already
validated typed AST, using C23 N3096 6.6. This foundation is queried by tests and
the bounded pipeline fuzzer, not yet by declarations, null-pointer conversions,
static assertions or an optimizer. No new source feature is claimed until its
consumer milestone is implemented and tested.

Result is a value struct: status value/not_constant/invalid, source type, canonical
low target-width uint64_t bits, source location and a static explanation on failure.
Queries are pure: no diagnostics, AST mutation, allocation, source reads or QBE.
The caller supplies a semantically checked bounded tree and decides when a failed
constant requirement is a diagnostic. Keep not_constant distinct from invalid
constant arithmetic. Qualified integer source types use existing width/sign APIs.

Supported forms: integer/boolean/character constants, fixed sizeof/alignof nodes,
integer explicit/implicit conversions, unary + - ! ~, implemented integer binary
operators, short-circuit logic and conditional expressions. Pointer expressions,
loads, names, calls and assignments are not integer constant expressions, even in
skipped arms, because the current operands cannot meet 6.6p8. sizeof/alignof are
opaque leaves: their operands were already checked by sema and are not visited.
Comma is accepted only inside a subexpression that is not evaluated, with both
operand forms still checked. Skipped integer arithmetic is form-checked without
performing overflow/division/shift operations. Thus 1?42:1/0 is valid, 1?42:x is
not_constant, and evaluated (1,42) is not_constant. Do not conflate generic static
initializer constants with the narrower integer constant-expression category.

Represent target values as bits, never depend on host signed overflow, large
unsigned-to-signed casts, negative signed shifts, or compiler extensions such as
__int128. Decode signed values mathematically via -1-(mask-bits). Extend signed
sources before narrowing/masking; bool conversion compares the complete source.
Target signed narrowing follows existing two's-complement modulo policy.
Unsigned arithmetic wraps at target width. Detect signed add/subtract/multiply/
negate overflow before host arithmetic; division/remainder reject zero and
minimum/-1. Check shift count against promoted left width and reject signed
negative/overflowing left shifts per 6.5.7. Signed right shift is the target's
arithmetic shift, implemented mathematically without host negative shifts.
Comparison operands already carry sema's usual conversions; shift counts retain
their own promoted type. Validate all result bits against their target width.

Unit/oracle tests must separate native ICE form checks (-pedantic-errors) from
runtime value checks and known legacy-host extensions. Execute only curated
defined constant arithmetic, never invalid cases or arbitrary fuzz C. Test all
12 integer types/conversions, 32/64 boundaries, high unsigned bits, minimum values,
shift counts and overflow, short-circuit forms, conditional common conversions,
unevaluated sizeof side effects, comma restrictions, const local loads versus
constants, and result/source-location preservation. Add sanitizer units and a
small file-based oracle; fuzz queries on top-level checked expression/initializer/
return roots without altering compilation success or executing emitted programs.
Full regression/QBE/fuzz/CI remains required. Next consumers are separate M18b2
constant requirements/static assertions and M13 generalized constant bounds;
null pointer constants require a deliberate pointer-conversion integration.
