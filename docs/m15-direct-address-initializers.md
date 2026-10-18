# M15i3: direct zero-addend static address initializers

## Supported boundary and value model

A file-scope explicit pointer definition can use a supported direct address:
`&object`, array decay, a function designator or `&function`, and string decay
or `&string`. The base is a stable canonical external-object/function symbol or
arena-owned string node. An extern-only referenced object/function need not be
defined in this translation unit; internal function reference checks still apply.
Self-address such as `void *self=&self;` uses the existing declaration-point
registration transaction. Scalar object value reads are not address formation.

Static data is separately tagged as integer bits, null pointer or symbolic
address. A zero addend is NOT null; a zero pointer slot in a relocatable object
is NOT proof that its relocation exists. Integer ICE and null source validators
remain unchanged. No host address, fake symbol ID or relocation sentinel is
stored in integer bits.

## Pure source proof and conversions

The already checked original is proved before assignment conversion. Address
context recognizes only direct object/function/string storage; value context
recognizes address/array-decay/function-decay nodes and supported conversions.
The query does not register strings, mutate symbols or mark functions referenced.
Captured source types, not later canonical composites, determine origin types.

Compatible pointer/qualifier-adding and ordinary object/void endpoints are
supported. Per-edge AND net origin-to-target validation prevents a void detour
from hiding incompatible reinterpretation, alignment assumptions or qualifier
loss. Assignment constraints remain independently enforced by normal sema;
function/object pointer cross-conversion is not enabled.

No pointer arithmetic or offsets (even +0), subscript address forms, &* operator
cancellation, pointer conditional/comma forms, arbitrary reinterpret casts,
nonzero integer-to-pointer mappings or pointer-to-integer static data are added.
Many such forms are valid C but outside this selected subset; conservative
refusal is not a claim that every deferred form is a constraint or UB.

## Emission, ownership and failure

The canonical explicit definition retains exactly one validated tagged payload.
Earlier tentative history remains separate and later tentative/extern declarations
cannot clear the explicit owner. Internal/exported binding and source snapshots
are unchanged. Data emission uses a symbolic QBE field `l $symbol` or the stable
string label, with zero semantic addend and no startup stores/local slots.

All fallible source analysis, proof, assignment conversion and final converted
address validation precede definition publication. Full prior canonical object
state is restored, or a new symbol/list count is removed, on failure. This is
object-state rollback in a fail-fast compiler; arena/reference/string ancillary
state is not advertised as recoverable semantic analysis. No output is emitted
on a failed translation unit.

## Independent focused evidence

Immutable source/standards/test review passed. The focused suite passed 27
KCC/QBE/exact-relocation/runtime originals and 27 compile-only refusals. GCC11
passed 26 unchanged native agreements plus one exact typeof keyword gap (not an
agreement); Clang18 passed all 27, including a real canonical primary-cc alias
lane that runs the native executable once. Five exact newly legal old owners
were promoted unchanged into paired runtime fixtures.

AST identity, origin captures, explicit/tentative ownership, strings, pure queries
and failed-publication rollback passed strict GCC and Clang18 ASan/UBSan checks.
Independent 48 source boundary probes and 15 SECTION/string/malformed-ELF/IL
negative controls passed. Parent mixed-owner probes also passed unchanged GCC
and Clang native/QBE runtimes with ten exact slot relocations per object.

## Required validation gates

Curated defined native and QBE cases must compare unchanged originals, actual
relocation slot/type/base/addend, storage width/alignment/binding, sole ownership,
linked address identity, reads/calls and strings across translation units. Local
and string symbols may legally canonicalize to section symbols plus addends in
assembler output: normalize that evidence without confusing it with a source
pointer offset. Multiple bases/strings must prove correct identity, not merely
presence of some relocation. True null must still have no relocation.

Fresh-output and exact full-stream native diagnostic gates, adversarial controls,
AST purity/captures/rollback and unchanged integer/null regression suites remain
required. Full frozen normal/QBE/sanitizer and exact-commit GCC/Clang/fuzz CI are
release gates. No implementation, focused pass or pending run alone is a full
release-success claim.

Next increment: provenance-checked pointer offsets with source-visible extents,
intermediate bounds, one-past state and checked signed addends. Multidimensional
subobject provenance and unknown-bound arithmetic require separate design.
