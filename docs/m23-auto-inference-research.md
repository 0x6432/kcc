# Inferred-auto research — not yet an implementation design

Prepared while M15a2's explicit-auto snapshot is frozen. Do not change source
before that checkpoint is fully validated, committed and pushed. Explicit auto
must retain ordinary point-of-declaration rules; inferred auto is different.

N3096 6.2.1 paragraph 7 and 6.7.9 example 2 explicitly forbid using the new
underspecified name in its initializer, EVEN IF an outer object/function/typedef
has the same name. The outer declaration is hidden when the declarator completes,
but the new object's scope starts only after the definition completes. A simple
"publish after initializer" implementation is WRONG: it would expose the outer
object. The parser needs a syntax mask and sema needs an unavailable-name barrier
while inferring the initializer. This is not the ordinary complete-declarator
publication rule implemented for explicit auto/register/ordinary objects.

Compile-only probes (never executed): GCC 14 and Clang 18 both reject
`int x=40; { auto x=x+2; }` with underspecified/self-initializer diagnostics.
Both accept a parenthesized identifier `auto (x)=42;`. N3096 6.7 paragraph 12
explicitly gives undefined behavior to underspecified definitions declaring no
or multiple ordinary identifiers. This is a semantic UB rule, NOT a required
constraint diagnostic. GCC 14 rejects `auto x=40,y=x+2;`; Clang 18 accepts it.
Neither result is native proof of a required diagnostic or a Clang constraint
bug. Such forms must stay compile-only refusal probes, never be executed.

A visible-typedef ambiguity remains: GCC 14 rejects `typedef int T; ... auto T=42;`
while Clang 18 accepts it. The current shared scanner consumes a visible alias
as an explicit type. Any initial inferred subset must deliberately specify this
case rather than silently replay tokens or alter explicit-auto T declarations.
Do not decide grammar from Clang alone, whose explicit-auto C23 parser already
has separately tested alias/query/order gaps.

A future small plan could begin with one bare/parenthesized identifier and an
initializer whose converted type is an implemented complete scalar, no inferred
storage combinations/file scope/VM/derived declarators. It needs a concrete
syntax node and explicit one-pass initializer ownership, NOT nullable types
silently accepted by existing sema paths. Existing sema forbids reanalysis of
lowered loads/decays/conversions. Factor name reservation from storage completion
before implementation if needed: reserve unavailable name, analyze initializer
once, apply declared qualifiers to converted inferred type, complete ordinary
local storage and conversion. Ordinary declarations must still bind before
initializer analysis; parameter spills and no-alias-storage rules remain intact.

These are research notes, not authorization to skip the separate final design,
focused native/AST/name-barrier tests or the complete frozen validation workflow.
