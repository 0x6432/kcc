# M23e3: inferred identifiers hiding visible typedef names

Design recorded before implementation after validated/pushed 77e2acb (M23e2).
Primary/isolated frozen manifests matched and remote development matched HEAD.
At design time M23e2 CI was independently pending; local passes implied no
remote success. Its final green result is recorded in completion evidence.
Research/native probes were compile-only, never executed.

## Scope and grammar argument

Extend the current single-identifier inferred subset to outer typedef names:
`typedef long T; int f(void) { auto T=42; return T; }`, and balanced grouped
identifiers `auto (T)=42`. The existing general ambiguity rule for parameter
lists (6.7.6.3p10) is NOT applied to these block/for object definitions. In the
bare form, the '=' after the one identifier forces the inferred-object grammar
of 6.7.9p2; interpreting T only as a type would leave no required init-declarator.
Types and objects share the ordinary namespace and outer typedefs can be hidden.
This must not reinterpret valid explicit `auto T x`, `T auto x`, or shared bases.

GCC 14 rejects both bare/grouped alias-name originals while Clang 18 accepts
both. Treat this conservatively as a native typedef-inference grammar feature
gap, not native proof that the supported C23 form is forbidden and not a claim
that every rejection is a missing constraint diagnostic. Probe basic inference
independently, then probe the exact header-free typedef-name inferred definition.
If basic inference works but this probe has the exact known ordinary failure
status/full diagnostics (GCC 14), count zero new alias-inference native source
agreements/constraints on that host. Do not rewrite originals as explicit types
or alter programs to make GCC agree. Clang 18 must compare all originals.
Legacy hosts retain the independent exact basic-inference absence classification.
Native ordinary helpers/drivers can still verify both-direction ABI on all hosts.

Only outer-name hiding is supported: same-scope prior typedef/object declarations
remain refusal probes; underspecified same-scope/multiple declarations have UB
under 6.7p12, not required native constraints, and NEVER execute. The new name
must hide the alias and stay unavailable in its initializer, including sizeof,
typeof, addresses, calls and dead branches; no fallback to the outer type.
After completion it denotes the same inferred object. Block/for exit restores
the alias. Both plain and register inference follow this rule; qualifiers and
real register identity remain unchanged. No globals, parameters, inferred derived
declarators, braced initializers, constexpr/attributes/VM or aggregate inference.

## On-demand parser design

Two tiny grammar-specific changes, no replay or whole-token vector:

1. Rename the private declaration_storage result to declaration_head and add an
already-consumed inferred_name token (ordinary storage and auto tokens remain).
In the shared scanner's visible-typedef branch, only when no explicit type has
been seen, auto has ALREADY been read, and the token immediately after consuming
that one identifier is '=', construct the existing inferred syntax and return
that identifier explicitly in the result. Do this BEFORE allocating a typedef-
name syntax or treating it as an explicit combined-storage type. Current query/
builtin/consumed-alias branches remain explicit; auto T x and T auto T are not
reclassified. Specifiers after a would-be identifier do not qualify for this
one-token decision. File-auto still rejects before any symbol registration.

2. For an inferred base, use a private grammar-specific identifier parser rather
than general derived declarators: identifier (including a visible typedef) or
balanced parentheses around that identifier. Preserve the exact existing 64
nesting limit using the parser's declarator_nesting counter and clean decrement
on success/failure. Reject pointer/array/function-derived forms explicitly. If
the scanner returned inferred_name, use that token directly; otherwise invoke
the grammar helper. Count the local/item once, publish the same syntax-only
object mask AFTER the complete identifier/declarator and BEFORE initializer
parsing, require assignment initialization, then keep the one-declarator rule.
Do not add name ownership to type syntax or a second initializer owner.

No semantic/type/codegen change should be needed. Existing reserved-no-type
local hides aliases, ordinary conflict checks reject same-scope prior names,
and the one-pass initializer path completes the same object/type/storage. The
completed source type cache, captured object/function identities, alias-free
runtime storage and scoped restoration remain. No new public API or flags.

## Validation plan

Original curated positives for both bare/grouped names, all primitive initializer
ranks versus deliberately different outer alias types, const loss/written const,
pointer/array/string/function/nullptr conversions, once-only side effects,
register source/ordinary copied flags, prior explicitly typed comma declarations
and captured object/function bindings. Nested block/for alias restoration and
completed typeof/sizeof queries. Only defined curated positives execute.

Compile-only self-unavailability and register-address/const constraints; same-
scope prior aliases/objects and multiple underspecified identifiers as UB
refusals; explicit-type combined register/auto constraints; unsupported derived/
missing/braced/global forms. Native rejection in a host lacking the grammar is
NOT counted as semantic constraint agreement. Negative-test the feature-gap
classifier against signals, other statuses, extra/duplicate diagnostics and
wrong probe text. Do not silently broaden it to arbitrary failures.

AST assertions: pending/balanced identifier becomes one concrete inferred local,
not a typedef syntax/runtime alias; old shared explicit bases and captured local
pointers retain identity; new type differs appropriately from outer alias;
subsequent loads/queries bind the new object; one string occurrence, exact slots
and reverse local list. Failed initializer captures the untyped inner object,
not the alias. Exact locals/items/storage/grouping/expanded-type boundaries,
including 128 named parameter spills. Generated sibling blocks may reuse the
outer alias while accumulating real locals; they compile only, never execute.
Twenty-four both-direction mixed-stack primitive ABI arrangements per host.

Replace the two old visible-typedef ambiguity refusals in auto_inference with
new positive coverage, explicitly documented. All prior inference/register/
explicit-auto/binding suites rerun with existing gap counts unchanged. Add focused
suite to both Makefile recipes, both-host sanitizers and compile/lex corpus.
Serial helpers before frozen full normal/QBE/both-host sanitizers/bounded fuzz.
Verify source manifests and old/new unaffected corpus output equivalence. Update
current design/handoff/coverage/contracts/limitations/ledger/version; commit/push
promptly and check exact CI separately. Incomplete C23, no conformance claim.

## Completion evidence

Full make test passed with GCC 11.5/GCC 14.2.1/Clang 18.1.8 as native
comparison hosts; normal C11 helpers were built with GCC 11. Full make
test-codegen passed with QBE 1.2 and both modern native hosts. GCC 11 and Clang
15 ASan/UBSan lexer/sema plus 23 targeted suites passed; inferred-typedef,
register-inference, ordinary inference and binding suites also passed with Clang
18 as native oracle. Normal helpers were built serially before parallel runs.
Frozen primary and isolated source/test/Makefile manifests matched before/after.
Bounded compile-only sanitized fuzz passed 10,381 lexer / 19,799 pipeline inputs
in 26 seconds each. No invalid curated or generated C executed. Logs/manifests
/data/tools/m23e3-*, isolated trees /data/validation-m23e3-final/{gcc,clang}.

The previous M23e2 sanitized compiler and frozen M23e3 compiler have identical
return codes/stdout/stderr on all 151 pre-existing compile corpus files
(119 accepted / 32 rejected), compiled only, excluding the new typedef seed.

Focused inferred-typedef suite: 54 unchanged original C23 programs passed through
kcc/QBE; Clang 18 strictly agrees on all 54 and rejects 43 constraints, including
36 unavailable-name barriers. GCC 14 supports basic inference but rejects the
exact independent typedef-name inference probe with two known grammar errors;
zero new source agreements or semantic constraint agreements are counted on
that host. Legacy GCC 11/Clang 15 lack basic inference on the separate exact
probe; likewise zero new agreements. No originals rewritten to explicit types
or native failures masked. The grammar-gap classifier requires exact probe text,
status 1 and complete diagnostic records; wrong text/status, signals, extra notes,
warnings, fatal errors and duplicate records are negative-tested.

All four hosts pass 24 both-direction mixed-stack primitive ABI arrangements
with inferred kcc code and ordinary native helpers/drivers; linkage does not
masquerade as native syntax support. Five UB refusals and nine subset refusals
compile only. Ordinary/register inference, explicit auto, binding and both
register suites reran on all four hosts with existing native gap counts unchanged.
Two old visible-typedef subset refusals in auto_inference were replaced by this
new positive coverage; that suite now has nine subset refusals.

AST assertions cover bare, grouped and register forms: old shared typedef bases
and captured object addresses remain identical, outer alias stays long while the
new inferred object is int, completed typeof/loads capture the new declaration,
ordinary copies have no register flag, and four real slots/reverse-list entries
exclude alias storage. Failed bare/grouped self-size initializers capture the
reserved untyped INNER object, not the old alias, with no completed runtime local
or IL. A string-inference IL probe has one static string and one real slot;
existing AST string-occurrence invariants remain in the sanitizer matrix.
Exact 256/257 locals (including 128 named spills), 4096/4097 items, 1 MiB/overflow
storage, 64/65 grouped typedef identifiers and 128/129 expanded-type depth pass.
Generated sibling-block and other boundary programs compile only, never execute.

M23e1 CI run 38982126026 completed/success, all three jobs green.
M23e2 CI run 38984165289 completed/success, all three jobs green.
New M23e3 exact-commit CI is pending until checked after push.
