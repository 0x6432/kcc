# M15i2: null-pointer initialized file-scope definitions

## Supported boundary

Explicit object/function pointer targets, including incomplete referents and
const-qualified pointer objects, accept a proved null source. Storage spelling,
typedef/query roots, mixed lists, self-name visibility, linkage and one explicit
definition reuse M15i1. nullptr_t object targets remain deferred.

The pure `evaluate_null_initializer` query runs on the semantically checked
original BEFORE assignment conversion. It admits literal nullptr, existing
strict integer ICEs whose value is zero, and pointer/nullptr cast or conversion
nodes recursively rooted in those forms. It carries status/location/message,
not fake integer pointer bits. Evaluated invalid integer arithmetic is preserved
through casts; integer/bool casts are not transparently stripped.

Normal semantic cast and assignment constraints still apply. For example,
`(void *)0` is a null pointer constant that can initialize a function pointer;
`(const void *)0` is not that special form and cannot discard qualifiers into
`int *`. A typed null pointer value is not necessarily a null pointer CONSTANT.

Examples include `int *p=0;`, `int *p=2-2;`, `int *p=(int *)0;`,
`int (*f)(void)=(void *)0;`, `int *const p=nullptr;` and
`int *p=(int *)(typeof(nullptr))nullptr;`. Semantically supported nullptr casts
such as `(typeof(nullptr))0` are checked independently of native availability.
Native compilers can have keyword/conversion gaps; they are never agreements.

Object reads, calls, evaluated comma/assignment expressions, pointer conditionals,
address expressions, pointer arithmetic (including null+0), nonzero integer
casts, arbitrary address conversions, arrays/braces and aggregate/runtime
initialization remain deferred. Native acceptance is not a defined-address or
strict-constant proof, especially for skipped operands and invalid arithmetic.

## Storage, ownership and failure

The canonical `static_data_value` distinguishes integer bits from null pointers.
Only integer data uses `integer_bits`; null has no fake base, address or sentinel.
Codegen selects the documented Linux amd64 eight-byte all-zero null encoding
(`l 0`), not a language-wide claim about every C target. Null definitions have
no relocations and no runtime initializer stores or new local slots.

An explicit null definition supersedes tentative storage, including prior zero
anchors; later tentative/extern declarations cannot reset its owner. Extern-only
objects allocate nothing. Internal/external binding, duplicate ownership, main
object restrictions and source-point compatibility remain unchanged.

All fallible expression analysis, source proof and assignment conversion occur
before definition/data publication. Existing canonical symbols are fully
snapshotted/restored on failure; newly registered symbols/list counts are removed.
Failed declarations do not publish successful symbol/type fields. This remains
object-state rollback in a fail-fast compiler, not full semantic recovery; private
arena caches/reference/string side effects may remain after a failed TU.

## Validation gates

Independent source/standards review and focused runtime probes are complete;
independent storage/AST tests and the frozen full normal/QBE/sanitizer matrix
are required. Exact-commit GCC/Clang/fuzz CI is checked after push, never inferred
from local success. Null storage evidence must check actual bytes, width,
alignment, binding, sole definition and NO relocation, including observable
native const storage and multi-TU value observation. Existing integer regression
and diagnostic/fresh-output adversarial gates stay intact.

Next: direct zero-addend symbolic addresses, then provenance-checked offsets.
Relocations require their own exact ELF relocation oracle; byte-zero alone is
not proof that a symbolic initializer survived.
