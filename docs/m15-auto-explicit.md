# M15a2: explicit-type automatic objects

Design recorded before implementation after validated/pushed 8e1c641.
M15b1 primary and isolated frozen hashes matched before completion records. Add the traditional explicit auto storage class
for existing block/for object declarations, not C23 inferred types.

## Scope and standard

N3096 6.7.1 retains explicit auto for block-scope automatic objects. Its C23
combinations/file-scope use indicate inferred typing and need a separate design
(6.7.1 paragraphs 4/14 and 6.7.9). Accept one written auto with an explicit builtin,
typedef or typeof-derived type anywhere among specifiers, including comma groups
and for initializers. Objects behave exactly like currently unadorned automatic
objects: same addressability, arrays, ordinary local slots and lifetimes. No
storage-class effect propagates through typeof. Still reject type names,
parameters, file scope, duplicates and typedef mixes. Reject auto/register
combinations explicitly as unsupported C23 combination/inference syntax, not a
claim that all combinations are invalid. Auto without a type is an explicit
inference subset refusal; do not invent int or publish an inferred identifier.

## Components

Language token_auto conversion only, after macro expansion; pp keywords/macros
remain identifiers. Extend the existing shared specifier scanner's optional
storage-token result with auto. Type-name/parameter NULL paths give an explicit
forbidden-auto diagnostic; external declarations refuse file-scope auto/inference.
The supported object's semantics match the ordinary path, so no new AST storage
flag/type/backend interface is needed: only register has the additional
addressability constraint. Local tail receives the actual storage token to reject
explicit syntactic function declarators with auto before publication; resolved
alias-derived function types continue through existing semantic block-function
refusal (unsupported block function declarations). No promise to support those
invalid object cases or improve every preexisting diagnostic in this increment.

Keep shared base caching, complete-declarator publication/initializer visibility,
scoped masks and no-alias-storage invariants. No new inference node/lifetime
policy, token replay, scope mechanism or future-storage enum. Subsequent inferred
auto needs its own AST/sema plan, including the initializer's name visibility.

## Validation

Original-source positives for all 12 integer types, addressability/pointers,
arrays, callbacks, const, specifier positions, aliases, shared comma bases,
self-bound alias visibility, initializer identity, scopes/for restoration and
keyword macros. C23 typeof/bool/nullptr forms separately probed. Native Clang 18
C23 probes already show exact auto/late-type grammar errors on valid spellings
(e.g. int auto and T auto), whereas C11 original-source probes accept them.
Preserve originals; classify only exact eligible source/status/diagnostic records,
not a broad auto-error allowlist. Record strict C23 agreements/gaps separately
from optional unchanged-source C11 corroboration. No source rewriting or fake
C23 agreement. Constraint and inference/combination subset sources compile only.

AST checks retain no-register flags, ordinary type/slot identity, array decay and
addressability; test exact local/item/storage/expanded-typedef limits. Full
normal/QBE modern oracles, four-host originals/both-direction mixed-stack ABI,
both-host targeted sanitizers, bounded compile-only fuzz; serial helpers and
frozen source hashes. Update current docs/ledger/version, commit/push promptly,
then check exact remote CI separately. Never execute invalid/generated C.

## Completion evidence

Implemented the explicit-type object subset above. Read the M15a2 ledger for
exact frozen full/QBE/sanitizer/fuzz and original/ABI/boundary evidence. Clang 18
C23 errors are matched only on exact eligible originals/status/full diagnostics;
16 unchanged standard originals independently pass C11 and are NOT C23 agreements.
No new AST/type/sema/backend interface, storage flag or inferred-name lifetime
was introduced. Next inferred-auto/combination scope requires a separate design.
No full C23 conformance claim.
