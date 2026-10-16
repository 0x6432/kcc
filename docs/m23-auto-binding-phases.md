# M23e0: separate local name, storage and initializer phases

Design recorded before implementation after validated/pushed bd77dc3.
The M15a2 primary/isolated frozen hashes matched after full validation. This is a
behavior-preserving semantic preparation step, NOT inferred-auto support.

## Reason and bounded scope

N3096 6.2.1 paragraph 7/6.7.9 require an unavailable-name interval for inferred
auto: its initializer must not see either the new object or an outer namesake.
Current bind_local combines name reservation, effective type/storage completion
and initializer analysis. A future inference path cannot safely call it after
analyzing an initializer: that would both expose an outer namesake and analyze
lowered loads/decays twice. Do not add such an inference path in this increment.

Factor only the existing sequence into explicit private sema.c functions:
1. reserve_local_name: same-scope typedef/object conflict checks, 256-local guard,
   arena binding allocation and insertion, in exactly the existing order.
2. complete_local_storage: assert the complete effective object type; retain its
   source syntax, set type, enforce/add the 1 MiB budget, reject array initializer,
   assign slot, advance count and prepend to the function locals list, same order.
3. sema_local_initializer: if present, unqualify the target, analyze once, convert
   once; otherwise succeed. No lowered-tree reanalysis or alternate flag path.
The existing bind_local remains the explicit ordinary wrapper calling all three
left-to-right. Real parameter spills keep using it; ephemeral prototype objects
remain entirely separate. No AST/type/parser/codegen interface changes, new
barriers, unavailable-type handling, storage class, scope, budget or inference
feature. Ordinary explicit declarations still bind AFTER complete declarators
and BEFORE initializers. All existing failure diagnostics/order remain.

## Tests and validation

Add focused defined originals for all primitive types using self-size queries,
ordinary/explicit-auto/register locals, address identity, shared comma bases,
array decay, own-bound outer typedef visibility, initializer's new object meaning,
loops/scope restoration, adjusted parameter spill types, function decay and
string initializer ownership. C23 typeof operands must remain non-evaluated and
captured only once. Invalid self/address/type/initializer/budget forms compile
only. AST assertions verify self-size binding, address/array/function/string decay
identities, exactly one string object and ordinary local slot/list order.

Retain exact local/item/storage/expanded-typedef boundaries and both-direction
mixed-stack ABI for all primitives. Rerun all storage suites against four original
native hosts; new refactor originals should need no new native gap classifier.
Full normal/QBE modern oracles, both-host targeted ASan/UBSan and compile-only
bounded fuzz; serial helpers before parallel frozen validation. Record actual
local/remote evidence and version, commit/push promptly. No full C23 claim.

The later inferred-auto feature still requires a separate final design, including
its concrete syntax, one-pass initializer ownership, name barrier, qualifiers,
single-declarator/underspecified-UB policy, derived syntax and typedef-name ambiguity policy.

## Completion evidence

Implemented as a behavior-preserving factorization only. Read the M23e0 ledger
for exact frozen full/QBE/native/ABI/sanitizer/fuzz evidence and remote CI state.
No inference feature or barrier exists yet. The future-work wording above uses
underspecified-UB policy rather than claiming N3096 6.7 paragraph 12 is a required
constraint diagnostic; native probes were never executed. Read the research notes
before the next separate implementation design. Not full C23.
