# M15 — storage, linkage and multiple translation units

## Closure boundary

M15 storage/linkage is complete for the compiler's existing supported types on
Linux amd64 with QBE 1.2. This is not complete C23, complete initialization syntax,
or a hosted-environment conformance claim. M16/M17/M20/M23–M25 dependencies below
remain real work. Earlier M15 documents are historical checkpoints, not the
current feature inventory.

## Storage and lexical identity

- Block `extern` object declarations and block function declarations (with or
  without `extern`) bind lexical names to canonical linked entities. Compatible
  repeated declarations retain one identity. Block-only names disappear when
  the scope ends; canonical registries do not make them visible elsewhere.
- A declaration's captured visible composite is separate from the entity's TU
  composite and file-visible composite. Block completion of an incomplete array
  or function-pointer signature cannot leak into sibling/file scopes or rewrite
  earlier expressions. Visible prior internal linkage is inherited; hidden
  internal-linkage conflicts are conservatively refused.
- Static block objects have unique no-linkage identities per declaration and TU,
  persistent storage, and compile-time zero/integer/null/address initialization.
  They never consume automatic slots or run startup/repeated stores. Recursion,
  nested same names and separate TUs retain distinct objects.
- `thread_local` and `_Thread_local` support file external/internal objects and
  block `static`/`extern` objects, with agreement on every redeclaration. QBE
  `thread data` and thread-aware address operands implement local-exec TLS.
  Concurrent native pthread companions check per-thread values, live addresses,
  persistence, and fresh-thread initialization in both ownership directions.
- A file TLS declaration without an initializer and without `extern` is a ZERO
  DEFINITION, not a tentative definition (C23 6.9.2). It requires a complete
  visible type, cannot receive the tentative one-element fallback, and duplicate
  definitions are refused. Ordinary tentative objects retain their prior rules.
- Existing `typeof(nullptr)` scalar objects now support static null storage.
  Standard-library/header type exposure is still M23c/M25.
- Register arrays remain refused on evaluated decay (undefined behavior) and
  direct address-taking (constraint), but non-VM unevaluated inner decay in
  `sizeof`/`typeof` is admitted. Sole unnamed `register void` markers are accepted.
  Explicit `auto` provenance still rejects alias/query function declarations.

## Inline linkage, not an optimizer

`inline` is a function specifier, independent of storage/type. Repeated spelling
is accepted. A function with external linkage declared inline must have a
same-TU definition. After all declarations, a body is inline-definition-only if
all FILE-SCOPE declarations have inline and lack extern. A plain or extern file
prototype before or after the body makes it an external definition. Block
prototypes do not change this predicate. Static-inline bodies remain internal.

The implementation performs no inline substitution. Inline-only bodies are
fully checked but not emitted; calls and addresses reference the single external
function supplied elsewhere. No private clone or alternate function address is
introduced. TU-end checks reject modifiable static/thread object definitions and
internal-linkage identifier references only in actual external inline definitions;
const static objects are permitted. Declarator/body queries are included.

## Address constants

A pure checked-AST query retains canonical object/function/string identities and
an explicit signed byte addend, never fake host addresses or integer sentinels.
Source-captured domains support scalar-as-one-element, complete arrays of any
current rank, whole-array addresses, strings including their terminator, nested
subobject decay, subscripts and `&*`/function-designator cancellation. Every
known-bound intermediate is checked, including one-past and moves back; a
one-past row cannot become a new array. Integer indices use strict ICE semantics,
checked signed/magnitude decoding, and checked relocation arithmetic.

Unknown-bound external arrays retain an UNKNOWN upper extent; symbolic offsets
are admitted without inventing later bounds or claiming whole-program validity.
Provable underflow and relocation overflow are refused. Final defined root-based
addends are nonnegative; the representation is signed to match ELF relocations.

Checked direct object-pointer casts require guaranteed root/addend alignment;
explicit qualifier removal is distinct from forbidden implicit qualifier loss.
Function-pointer casts preserve identity without promising that an incompatible
signature may be called. Character views cover the actual pointed object's bytes,
not an invented larger enclosing object. Latent original domains survive
reversible casts and can be restored at compatible, aligned positions. Incompatible
casts never create a new typed array extent. TLS addresses are NOT static address
constants, even when the initialized target itself has thread duration. Runtime
automatic pointers may take TLS addresses normally.

## Dependencies still outside this storage/linkage milestone

- M16: struct/union definitions, members and layout.
- M17: general braced/nested/array/string-to-array initialization, designators,
  compound literals, and generalized constant-initializer expression/domain
  handling. This includes remaining pointer conditional/comma forms, casts whose
  alignment/domain cannot be established by this implementation, and arithmetic
  in new reinterpreted domains rather than restored original/character domains.
  These are explicitly initializer subsets, NOT missing pointer-cast syntax.
- M14/M18/M23: remaining qualifiers, alignment/attributes, broader inferred-auto
  storage combinations and constexpr. Ordinary explicit storage is implemented;
  legal deferred inference is diagnosed as unsupported, not a fabricated C
  constraint. Obsolescent `_Noreturn`/noreturn behavior remains M23g/M19, not a
  storage/linkage implementation or an effect of supporting inline.
- M20/M24: floating, atomic, complex, VLA/VM, wide and other unimplemented types.
- M25: headers, environment/libc conformance and further target/PIC/shared-library
  TLS ABI coverage. The tested TLS contract is local-exec executable Linux amd64;
  dynamic TLS/shared-object interoperability is not claimed.

## Quality gates

New dedicated block-storage, TLS, inline and address-offset Python suites and
semantic AST helpers run in BOTH full `make test` and `make test-codegen` targets.
Legacy legal originals are exact-promoted into positive ownership/object/runtime
checks; genuine constraints and deferred forms remain negative tests. Tests keep
constraint/UB/subset/resource failures distinct and never execute undefined
programs or generated fuzz inputs.

The oracles check real bytes/alignment/binding, sole ownership, absence of common
merging, normalized ELF relocation bases/slots/types/addends, TLS types/section
flags/address relocations, and unchanged-source native interoperability. Every
producer removes stale output and requires fresh nonempty artifacts. Full-stream
diagnostic signatures and native keyword/diagnostic disagreements are explicit:
a skipped/disagreeing native case is NOT an agreement. Ownership/private-clone,
stale-output, damaged ELF/IL and diagnostic poisoning controls must fail closed.

Independent source, AST and test audits bind immutable source/test hashes.
Normal and ASan/UBSan full regression/backend matrices and bounded lexer/compiler
fuzzing remain required. CI retains four independent GCC/Clang normal/sanitized
jobs and unchanged fuzz budgets. A local focused pass is not a remote CI pass;
the exact pushed commit's run is recorded separately at delivery.
