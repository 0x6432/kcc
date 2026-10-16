# M23e1: single-identifier block/for auto inference

Design recorded before implementation after validated/pushed 9c08154.
M23e0 source hashes matched after full validation and before commit. This extends only inferred automatic
objects, not register combinations, globals, constexpr, attributes or VM types.

## Standard, grammar and deliberately bounded subset

N3096 6.7.9 paragraph 2 infers the initializer assignment-expression's type AFTER
ordinary lvalue/array/function conversion, additionally applying written type
qualifiers. Existing sema already unqualifies scalar loads/casts/function returns;
reuse those rules without promotion or a new semantic inference type.

Accept one bare or parenthesized identifier with an assignment initializer,
optionally const-qualified auto at block/for scope. A converted initializer must
have an implemented complete scalar object type; ordinary arrays/functions decay
to pointers and nullptr retains its existing distinct type. Reject inferred
derived pointer/array/function declarators explicitly rather than claiming the
optional implementation-defined extended grammar. No braced initialization.

Keep the shared scanner's existing typedef-name disambiguation: a visible alias
is an explicit type specifier. Thus `auto T x` remains explicit auto, while the
ambiguous `auto T=42` (also parenthesized `auto (T)=42`) with visible typedef T remains outside this first inferred
subset. GCC 14 rejects the latter and Clang 18 accepts it; do not silently change
explicit-auto alias parsing or label either behavior proof of a constraint.

N3096 6.7 paragraph 12 gives UB to underspecified definitions with no/multiple
ordinary identifiers or a prior declaration in the same scope. Refuse multiple
inferred declarators explicitly, but keep such probes compile-only and NEVER
count native acceptance as a missing required constraint diagnostic. GCC 14 and
Clang 18 diverge on accepting them. Derived/incomplete/missing-initializer/void
forms are also compile-only refusals with precisely stated categories.

## Name lifetime — not ordinary point of declaration

6.2.1 paragraph 7/6.7.9 example 2 hide an outer namesake when the inner declarator
finishes, but the new name is unavailable until its definition completes. Its
initializer may NOT use either binding, including inside sizeof/typeof or dead
branches. A publish-only-after-initializer shortcut is incorrect.

Parser can reuse its syntax-only object mask: publish after the complete inferred
identifier/declarator and before parsing its initializer, just like ordinary
syntax, so an outer alias is not exposed. No semantic meaning is inferred there.
Sema must deliberately reserve the actual local name with type NULL before
initializer analysis, using M23e0's name phase. In expression_name, a found local
with no completed type is an explicit underspecified-name diagnostic; NEVER skip
it and fall back to an outer object/function/typedef. Existing ordinary and
prototype locals always have types before use. After successful inference,
complete the same binding/storage and expose its type for subsequent items.
Existing block/for/function restoration and declaration identities remain.

## Concrete AST and one-pass initialization

Add concrete ast_inferred_type_syntax with the common syntax header and written
qualifier bits, plus its AST constructor/type_syntax kind. It does not own or
copy an initializer. The concrete local declaration continues to own exactly one
initializer and actual runtime object; no optional guessed-int semantic type or
new runtime local is invented. The shared scanner constructs this syntax only
when auto has no explicit type; type-name/parameter auto remains rejected before
that point, and external auto remains unsupported.

Local tail rejects inferred derived syntax (type_syntax != shared base), requires
'=', publishes the syntax mask, parses one assignment-expression and rejects a
following declarator comma. Parentheses around the identifier leave base identity
unchanged and use existing nesting budgets. Explicit auto paths are unchanged.

A dedicated inferred-local semantic path: reserve name; analyze initializer ONCE
with value conversions; require an implemented complete scalar; qualify its type
with written const; cache that completed type on the inferred syntax; complete
ordinary local storage; convert the already-analyzed initializer to the unqualified
target without calling sema_expression again. Only then is the declaration usable.
Do not call the ordinary initializer helper on lowered loads/decays/conversions.
A generic attempt to resolve inferred syntax outside this local path fails clearly.
No new semantic type kind, inference variables, QBE/backend or ABI protocol.

All ordinary explicit declarations still use M23e0's unchanged wrapper and bind
before their initializer. Parameter spills/prototype-only objects are unchanged.
Register flags never propagate into inferred copies. Arrays still obey the
existing register-decay refusal. Storage budgets count the inferred scalar once;
source syntax/type caches and one-occurrence string ownership remain immutable.

## Focused and full validation

- All 12 primitive types via explicit initializer casts and pointer compatibility;
  full-width values, _Bool, pointers/const referents, functions/callbacks, array
  and string decay, nullptr, const inference and const loss after value conversion.
- Runtime side-effect-once initializers; ordinary old declaration self-size meaning
  remains; subsequent queries see the completed inferred object; nested blocks,
  for scopes, function capture and restoration. Only defined curated positives run.
- Compile-only unavailable-name cases hiding outer objects/functions, including
  sizeof/typeof and dead branches; missing/void/derived/alias-ambiguous forms;
  multiple underspecified identifiers are UB refusals, not native constraints.
- AST assertions for concrete syntax/qualifiers, captured initializer identity,
  one load/decay/call analysis, exactly one string occurrence, completed types,
  no register propagation and normal slot/list order. Failed barriers emit no IL.
- Exact locals/items/storage/parenthesis/expanded-typedef boundaries, including
  128 named spills plus inferred locals/storage. Boundary/generated C never runs.
- Probe native inferred-auto syntax independently of typeof support. Modern
  original C23 comparisons remain unchanged; legacy missing inference is an exact
  feature absence, never agreement. Both-direction mixed-stack primitive ABI uses
  ordinary native helper/driver objects and inferred kcc objects; 24 arrangements
  per host do not masquerade as legacy inference source support.
- Update the old block-inference subset refusals into new positive coverage and
  update remaining file-scope diagnostic expectations explicitly, not silently
  delete tests. Preserve register-combination and parameter refusals.
- Serial helpers, frozen full normal/QBE modern regressions, both-host targeted
  ASan/UBSan and bounded lexer/pipeline compile-only fuzz. Update all current docs,
  ledger/version and component contracts; commit/push promptly, check exact CI.

This is an incomplete C23 subset. Implementation follows this recorded pre-implementation design and the full
milestone workflow.

## Completion evidence

Full make test passed with GCC 11.5/GCC 14.2.1/Clang 18.1.8 as native
comparison hosts; normal C11 helpers were built with GCC 11. Full make
test-codegen passed with QBE 1.2 and both modern native hosts. GCC 11 and Clang
15 ASan/UBSan lexer/sema plus 21 targeted suites passed; the new inference and
binding suites also passed with Clang 18 as native oracle. Normal helpers were
built serially before parallel validation. Frozen primary and isolated source,
test and Makefile manifests matched before/after. Bounded compile-only sanitized
fuzz passed 11,433 lexer / 28,284 pipeline inputs in 26 seconds each. No invalid
curated or generated C executed. Logs/manifests /data/tools/m23e1-*, isolated
trees /data/validation-m23e1/{gcc,clang}.

The previous M23e0 sanitized compiler and frozen M23e1 compiler have identical
return codes/stdout/stderr on all 149 pre-existing compile corpus files
(117 accepted / 32 rejected), compiled only, excluding the new inference seed.

Focused inference suite: 65 original C23 programs passed through kcc/QBE;
GCC 14 and Clang 18 strictly agree on all 65, without rewriting originals or
adding gap exceptions. Independent inferred-auto probes identify exact legacy
GCC 11/Clang 15 absence (zero inference agreements, not an implicit-int fallback).
Each of four hosts passes 24 both-direction mixed-stack primitive ABI
arrangements with inferred kcc code and ordinary native helpers/drivers; native
linkage does not masquerade as inferred-source support. Sixteen unavailable-name
barriers plus four other constraints are rejected by both modern native hosts;
three UB refusals and thirteen subset refusals are compile-only, never executed.
Auto-explicit/binding/both register suites were rerun on all four hosts with
existing native gap counts unchanged. Old unsupported block-inference assertions
were explicitly replaced by this new positive coverage; file-auto diagnostics
were updated, not silently dropped. Their subset counts are now five/three.

AST assertions verify concrete syntax and cached qualifiers/types, root const
loss on value conversion, no register flag propagation, captured load/array/
function/string identities, one static-string occurrence and seven exact real
slots/reverse-list entries. A failed self-size initializer captures the reserved
INNER local with no type/storage, not the outer typed object; no IL is emitted.
Exact 256/257 locals, 4096/4097 items, 1 MiB/overflow storage, 64/65 parenthesized
identifier nesting and 128/129 expanded-typedef depth boundaries pass. Extra
128 named spills plus inferred local/storage tests retain shared accounting.

M15a2 CI run 38977217404 completed/success, all three jobs green.
M23e0 CI run 38979609085 is still pending; no remote pass is claimed.
New M23e1 exact-commit CI is pending until independently checked after push.
