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
including slices of an earlier record copy (N3096 6.7.10 example 12). All written
initializers receive type/constraint/depth checks even when later overridden.
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
same-base comparisons and definitely distinct named-object/function starts;
loads and evaluated calls/comma remain nonconstant. Strict integer constant
expression rules remain unchanged for bounds, designators and assertions.
Pointer-to-bool initialization converts a proved address/null to target 1/0.

Address proofs retain canonical base plus checked signed addend and immutable
source-point domains. Initial struct/union member reciprocal conversions and
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

This is not full C23 conformance. constexpr compound literals require M23h
constant-object semantics and receive an explicit dependency diagnostic. C23
expanded record compatibility/redefinition rules remain M23h. Floating/complex,
_BitInt, VLA, atomics, bit-fields/flexible arrays and by-value aggregate ABI still
belong to their listed milestones. Baseline nonzero integer-pointer conversion
language is not introduced as a shortcut for initializer address constants.
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
