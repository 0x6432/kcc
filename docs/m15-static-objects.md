# M15h1–h2: internal-linkage tentative objects

## Scope

M15h1 adds file-scope `static` tentative scalar objects for existing integer,
boolean, nullptr, object-pointer and function-pointer types. M15h2 extends the
same canonical symbols and storage emission to complete fixed arrays, including
rows and arrays of qualified, pointer and callback elements. No new scalar kind,
backend operation, runtime local slot or startup initialization code is added.

The compiler still rejects explicit object initializers, block-scope storage,
thread storage, variably modified arrays and aggregates.

## Linkage and source-point constraints

N3096 6.2.2p3–5 distinguishes objects from functions:

- `static int object; extern int object;` retains internal linkage.
- Repeated compatible `static` declarations denote one internal object.
- An unadorned file-scope **object** declaration has external linkage. Therefore
  `static int object; int object;` mixes internal/external linkage (6.2.2p7).
  The compiler conservatively refuses this undefined-behavior chain, as well as
  external-first then static. These are not claimed as mandatory native
  constraint rejections.
- Unadorned function redeclarations retain their existing extern-like behavior.

Internal tentative objects must have complete types at their declaration
(6.9.2p3), using their visible prior composite (6.2.7p4):

```c
static int items[3];
extern int items[];
static int items[];       // valid: the visible composite already has bound 3
static int (*pointer)[];  // valid complete pointer; referent remains incomplete
```

By contrast, `static int items[];` as the first declaration is invalid, even if
a later declaration supplies a bound. TU-end fallback to one element applies
only to the existing eligible external-linkage tentative arrays, never to an
incomplete internal tentative definition.

## Representation and invariants

Written static/extern provenance remains on concrete or unresolved declaration
nodes; canonical object symbols carry internal linkage. Linkage is not a type
qualifier and never propagates through `typeof`, typedefs or ordinary copies.

The first tentative declaration remains the single storage-emission anchor.
Compatible redeclarations construct immutable composites; source declaration,
typedef, query and expression captures are not rewritten. Linkage/type/
completeness checks finish before canonical type or anchor publication.

QBE internal data omit `export`, with the same explicit final size/alignment
and zero allocation as external tentative data. Distinct translation units may
own same-spelled private objects without symbol collision or interposition.
Extern-only objects still emit no storage or runtime slots.

Existing independent declaration/object/function/local/type/depth budgets remain
unchanged, including the 1 MiB per-array-type ceiling. Pointer referents are
never recursively completed.

## Validation contract

`tests/test_static_objects.py` checks scalar source/AST provenance, canonical
symbols, compatible pointer snapshots, initialized-native interoperability,
both-direction mixed-stack ABI, local symbol binding, private names in separate
translation units, constraints, explicit subset limits and resource boundaries.

`tests/test_static_arrays.py` checks unchanged native fixed-array programs,
independently expected C23 runtime fixtures, rows, callbacks, original migrated
acceptance fixtures, source-point completeness, local QBE data, ELF BSS extent/
offset/alignment evidence, separate-TU isolation in both backend directions,
compile-only constraints/linkage refusals/budgets and `/dev/full`.

`tests/test_static_array_ast.c` checks immutable incomplete written/typedef
captures versus complete canonical arrays, first anchors, query objects,
incomplete pointees, no runtime locals and no canonical publication on failed
registration. Both normal and backend test targets include it.

Only curated defined programs execute. Invalid, maximal-resource and fuzzed
inputs compile only. Native syntax absence is reported separately from
agreement; unaudited diagnostics are not ignored. QBE's missing ELF data-size
metadata is not treated as proof of allocation size.

The required integration gate is the frozen normal test suite, QBE execution
suite, sanitizer checks, independent review and the actual GitHub CI result.
Configured CI or a local pass alone is not a remote success claim.

## Next bounded increment

Initialized scalar definitions need a distinct definition-precedence and
duplicate-ownership design. Start with checked integer constant initializers;
do not silently extend to symbolic addresses, aggregates or runtime initializers.