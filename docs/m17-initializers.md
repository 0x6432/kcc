# M17: initializers, designators and compound literals

## Implemented scope

For the compiler's existing integer/bool/nullptr, pointer, fixed array and
struct/union types, initialization supports scalar braces and C23 empty braces,
nested aggregate lists, brace elision, member/index designator chains, current
object continuation, anonymous members, union selection, overrides and recursive
zero fill. Character arrays include char, signed char and unsigned char; string
initializers preserve decoded length/embedded NUL, optional braces and the legal
terminator-omission case. Unknown outer array bounds complete only after a
successful initializer, never early enough to rescue invalid self-size queries.

The same checked plans serve automatic, file, internal, block-static and thread
storage. Later whole-subaggregate initializers reset the subaggregate's omitted
remainder; later partial updates retain disjoint earlier explicit fields,
including slices of an earlier record copy (N3096 6.7.10 example 12 and DR413).
This includes a copied union followed by a partial update of its selected member.
Bytes made unspecified by changing union members (6.2.6.1p7) are not portable
retained-value oracles. All written initializers receive type/constraint/depth
checks even when later overridden.
Wholly overridden runtime expressions are omitted as a permitted implementation
choice. Surviving expressions are captured once in source order before destination
clearing and ordered writes. This also preserves previous live compound-literal
contents on reevaluation. It is not a portable promise about otherwise
indeterminate self-initialization reads in an ordinary uninitialized declaration.

Compound literals are postfix lvalues of scalar, array or record type, not casts
or temporary record values. File literals have static duration; block literals
have automatic duration by default, stable identity within an enclosing block
execution, fresh automatic activation storage, and initialization at each
actual evaluation. Existing C23 static/register/thread_local storage spellings
are checked against corresponding object-definition rules. Register-address and
evaluated register-array restrictions remain enforced. Unevaluated/prototype
contexts check types, expressions and static initializer constraints but publish
no literal owner, automatic slot or literal/string data storage. Query-only
static addresses use a distinct AST identity tag rather than a fabricated symbol.

## Constant initialization and lowering

Static writes cache target integer/null/symbolic-address values after validating
the original source before narrowing. Pointer-result constant conditionals may
select a valid address/null arm without applying strict ICE operand restrictions
to an unselected arm. Conditions can use proved pointer truth, logical operators,
same-base comparisons, same-array pointer differences and definitely distinct
named-object/function starts;
loads and evaluated calls/comma remain nonconstant. Strict integer constant
expression rules remain unchanged for bounds, designators and assertions.
Pointer-to-bool initialization converts a proved address/null to target 1/0.

Address proofs retain canonical base plus checked signed addend and immutable
source-point domains. Pointer differences additionally compare the full canonical
member path, distinguishing overlapping union arrays; unknown outer bounds do not
erase identity. Ambiguous cast recovery cannot manufacture nominal array identity.
Initial struct/union member reciprocal conversions and
character views can recover actual captured subobjects and real array domains;
casts never invent an array of an unrelated type. Member/row decay does not
launder a one-past position into a new object. TLS addresses are not static
address constants. Comparisons needing unknown linker placement or unspecified
string/literal merging are not guessed. Such unresolved placement-dependent
constant predicates are explicitly unsupported rather than executed or folded
from numeric pointer sentinels.

Written initializer syntax is separate from the semantic plan. Sparse zero runs
and final winning writes avoid allocating one node per omitted element. Sliced
record copies share one captured expression value. Static emission sorts checked
nonoverlapping writes, emits zero holes and actual symbolic relocations, and
preserves target extent/alignment/linkage. Automatic large clear/copy operations
use bounded loops, not proportional machine-code expansion or hidden libc calls.

## Explicit boundaries

This is not full C23 conformance. Bounded constexpr compound literals are supported; see `m23h-constexpr-integers.md` for scope. C23
expanded record compatibility/redefinition rules remain M23h. Floating/complex,
_BitInt, VLA, atomics, bit-fields/flexible arrays and by-value aggregate ABI
belong to their listed milestones; bounded aggregate calls are described in
`m21-aggregate-abi.md`. Explicit integer-pointer casts are supported at runtime using the target LP64
representation; integer-constant casts and explicit pointer cast chains can
initialize static pointers.
Pointer arithmetic on those values and pointer-to-integer relocations remain
unsupported in static initializers.
Optional broader arithmetic constant forms (for example skipped ordinary calls
outside strict arithmetic-constant operand shape) are not claimed as mandatory
C constraints or native agreement. Undefined behavior and native extensions are
kept separate from defined execution and standard constraint oracles.

## Resources, rollback and evidence

Initializer nesting is bounded at 64; initializer nodes, designators and resolved
entries at 16384, designator depth at 64 and compound syntax identities at 4096.
Semantic store-allocation work is independently capped at 65536. Objects retain
the existing 1 MiB limit and automatic storage/slot/snapshot budgets. Pure actual
subobject search memoizes shared type-DAG failures and caps each search at 16384
visits; it does not recursively expand shared union graphs without a bound.
Semantic union-ancestry searches use a shared TU cache with at most 4096 states
per query and 1048576 total work steps, including edge and hash-probe work.
Exhaustion is an explicit checked resource failure, never an assumed absence.
Failed initialization restores canonical publication/type/definition state and
nested literal registrations; bytewise snapshots preserve padding too. No arena
rewind or general error recovery is claimed.

Both full make targets retain all prior gates and add independent initializer
and compound-literal Python/AST suites plus exact legacy-original promotions.
Oracles inspect actual fresh ELF bytes, extents, binding, alignment and relocation
base/addend rather than only process status. Unknown stderr, stale artifacts,
wrong runtime results and poisoned ELF/diagnostic records must fail closed.
GCC/Clang capability gaps and known defined-runtime disagreements are reported
separately, never counted as agreements. Normal/sanitized full matrices, bounded
lexer/pipeline fuzzing and exact-commit remote CI remain mandatory release gates;
results are recorded separately, not inferred from component checkpoints.

## Floating arithmetic conditions for static addresses

A pointer-result conditional initializer can select a previously supported
symbolic address or null using a supported floating or floating-derived
arithmetic condition. These conditions also compose with the existing proved
pointer logical conditions. Floating truth and the numeric values of checked
integer casts remain distinct; out-of-range casts and unsupported evaluated
conditions are rejected. This does not expand strict ICE, pointer-offset,
thread-local address, or static symbolic-address proof rules.

The compiler rebuilt; eight relocation values and one null were checked in IL,
lowered with pinned QBE 1.2 and assembled. Six invalid or unsupported cases
were rejected. Regression fixtures, generated-program runtime, ABI, sanitizer
and fuzz checks remain unrun. This does not imply M17 approval.

## Pointer-derived integer conditions

Symbolic address proofs have no numeric integer value. Pointer-to-integer casts
in static address-selection conditions are rejected rather than treating a
proof as an integer or crashing. Pointer-to-bool truth conversion remains
supported. Five focused unsupported forms produced diagnostics rather than a
crash; two supported pointer-truth forms compiled, and the earlier focused
floating-pointer checks continued to pass. The compiler rebuilt. Regression
fixtures, generated-program runtime and fuzz checks remain unrun.

## Address-derived scalar initializers

Static integer and boolean initializers may use values calculated by the
existing symbolic address-condition evaluator, including proved pointer truth,
same-object comparisons and differences, and arithmetic around their results.
Those integer values can also be converted to float/double static objects.
Conditional/logical evaluation retains the initializer-only treatment of
unselected branches; it does not make these expressions integer constant
expressions. Pointer loads, thread-local addresses, unproved string identity,
pointer-to-integer numeric values and evaluated invalid arithmetic remain
rejected. Floating-valued conditionals with proved pointer conditions are
covered by the subsequent checkpoint.

The compiler rebuilt; ten scalar values were inspected in IL, lowered by pinned
QBE 1.2 and assembled, and nine invalid or unsupported examples were rejected.
Added regression fixtures, generated-program runtime, ABI, sanitizer and fuzz
checks remain unrun. This does not imply M17 approval.

## Pointer-conditioned floating values

Supported static float/double conditionals may select their value using a
proved pointer or nullptr truth condition, address comparison/difference, or
logical combination with a supported arithmetic condition. The selected arm
must fold and the skipped arm must satisfy the existing bounded arithmetic
form check. Pointer loads, unsupported address relationships, thread-local
addresses, pointer-to-integer numeric casts and evaluated invalid arithmetic
remain rejected; strict ICE rules are unchanged.

The compiler rebuilt; eight values were inspected in IL, lowered through
pinned QBE 1.2 and assembled; six invalid or unsupported examples were
rejected. Regression fixtures, generated-program runtime, ABI, sanitizer
and fuzz checks remain unrun. M17 remains unapproved.

## Address-selection boundary

The initializer-only integer address evaluator is used only when the expression
contains a pointer/nullptr operand or pointer difference; it does not broaden
unrelated integer or floating conditional initializers to accept arbitrary
skipped loads. Address-containing conditionals retain the existing permissive
selection behavior, including for skipped branches, so this is a conservative
implementation boundary rather than a complete form classification. Four
focused pre-existing nonconstant arithmetic cases were rejected; the focused
address-derived scalar, floating and pointer examples still compiled and their
previous IL and assembler checks were repeated. The compiler rebuilt; the
regression suites and generated-program runtime remain unrun.
