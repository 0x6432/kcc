# M15a1: block-scope scalar register objects

Design recorded before implementation, following 7c5b79f (CI run 38958469583
completed/success for GCC, Clang and fuzz). Add explicit register storage for
implemented scalar objects at block/for scope. This is a C storage constraint,
not a promise to reserve hardware registers or bypass the existing local slots.

## Standard and scope

N3096 6.7.1 paragraph 11 and footnote 142 permit ordinary addressable implementation
storage, but 6.5.3.2 paragraph 1 forbids computing a register object's address.
Scalar reads/writes, const, sizeof and typeof retain their usual rules. Taking
an ordinary pointee's address through a register pointer (&*p) remains valid;
taking the register pointer object's own address (&p) is a constraint, including
inside unevaluated queries. Storage is not part of a semantic type.

Register array objects are an explicit subset limit: their array-to-pointer
conversion has undefined behavior (6.3.2.1 paragraph 3), and a later increment
needs an unevaluated-array policy. Never execute such conversion programs.
Register parameters are also outside this first step. Per 6.7.6.3 paragraph 12,
their storage specifier is ignored unless they are actual definition parameters;
do not propagate the flag indiscriminately into temporary prototype bindings.
The observed GCC/Clang divergence on sole register void also needs a separate
normative plan. No parameter implementation is part of this increment.

## Components and invariants

- Add the language register token only at demand conversion. Raw preprocessing
  identifiers/macros remain unchanged, including keyword-named macros.
- Generalize the existing nullable typedef-token output to a storage token.
  Recognize typedef/register in any specifier position, allow at most one, and
  retain the old duplicate-typedef and forbidden-typedef diagnostics. File scope
  rejects register; NULL type-name/parameter contexts reject it with an explicit
  unsupported-context diagnostic. Mixed/duplicate storage classes are errors.
- Add is_register to the concrete local declaration AST, defaulting false in its
  constructor. Propagate one written register class to every comma declarator,
  including consumed alias starts and for initializers. Publication and shared
  base caching remain unchanged; aliases allocate no runtime storage.
- Sema accepts implemented scalar register objects and rejects register function
  declarations/array objects before binding. Unary & checks the resolved direct
  name's declaration flag after ordinary operand analysis. Parenthesized names
  still resolve to that node; indirection/subscript address rules are unchanged.
- Types, conversion graphs and QBE interfaces do not change. Register objects
  use the same slots, alignment and ABI as ordinary automatic objects. All prior
  scope, object-storage, local/item/type/recursion budgets remain enforced.

## Validation

Cover all 12 primitive integer types, pointers/function pointers, const/query
bases, declaration-specifier positions, comma/initializer publication, own-bound
outer aliases, nested typedef/object restoration, loops and keyword macros.
Reject direct/parenthesized/unevaluated address-taking, invalid storage mixes,
file-scope register and register functions. Keep valid-C parameter/array subset
rejections separate from native constraints. Compare original defined programs
with four hosts; test both-direction mixed-stack ABI; verify AST flags/captured
identities/slots and exact local/item/storage bounds. Run full normal/QBE,
both-host targeted sanitizers and bounded compile-only fuzz on frozen source,
after serial normal helper builds. Never execute invalid or generated C.

## Completion evidence

Implemented as designed. Read the M15a1 ledger for exact frozen local evidence,
native agreements and separately counted strict Clang keyword-macro diagnostics.
AST tests retain existing explicit load nodes rather than bypassing them. All
register parameters/arrays remain a distinct unsupported subset, not constraints.
The previous M14l4 remote CI is green; this increment's exact-commit CI must be
queried after push. No full C23 conformance claim.
