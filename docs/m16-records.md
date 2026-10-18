# M16: records, layout and member values

## Implemented target scope

Struct and union definitions, forward tags, tag scopes, anonymous members and
`.`/`->` member selection compose with the existing integer, pointer, array,
qualification, storage and query features. Record identity is shared by qualified
views and forward references. Completion is sequential: a later definition does
not rescue an earlier invalid `sizeof`, member access or pointer operation.
Member-list static assertions are checked at their declaration point. Plain
standalone forward declarations retain current-scope shadowing semantics.
Storage/qualifier-decorated tag-only forms introduce fresh tags when none is
visible, but do not redeclare a visible tag and are then diagnosed as declaring
no entity. Definitions declare a tag independently of vacuous decorations.
Tagged no-declarator member declarations are rejected; anonymous record members
are distinct valid syntax.

Linux amd64 layout uses natural member alignment, struct padding/tail padding and
union maximum member size/alignment. No bit-fields, packed layout or flexible
array members are claimed. Anonymous promotion retains the actual leaf member
and cumulative offset. Recursive pointer graphs do not require recursive nominal
type comparisons. Recursive const subobjects restrict whole-record assignment
without making a mutable sibling member unwritable.

Existing file, block-static and thread storage can hold zero-initialized records
and arrays of records. Automatic same-type expression initialization, `auto`
expression inference, assignment, comma and conditional record values are
supported. General braces, designators and compound literals remain M17.
Record prototypes and function-pointer types are representable, but evaluated
by-value aggregate calls and function definitions remain M21. Unevaluated calls
are type-checked without performing an ABI call or reserving a value temporary.
Pointer-based native interoperability is tested; aggregate-by-value ABI is not
silently approximated with a pointer calling convention.

## Representation and lowering

Record values are address-backed. Evaluated record lvalue conversions reserve a
separate entry-allocated snapshot, not an alias to the assignable source object.
Assignment copies that value into its destination and returns the value snapshot.
Member bases are evaluated once. Small copies use bounded QBE `blit`; larger
copies use a compact eight-byte loop plus a bounded byte tail, rather than
unbounded generated instructions or an implicit `memcpy` dependency.

Distinct snapshots are a conservative implementation policy. WG14 C23 issue1088
leaves some temporary-address sharing questions open; ambiguous native probes
are not presented as portable conformance tests or GCC failures.

Static member-address proofs preserve canonical base identity and checked logical
relocation addends, then start a domain for the selected subobject. One-past record
selection, sibling-domain laundering, null fake-offset addresses, TLS bases and
loads of stored pointer members are not mistaken for constant member addresses.
General remaining initializer-expression/cast-domain limitations stay M17.

## Explicit C23 boundary

This milestone implements nominal record compatibility. C23 expanded same-tag
cross-scope compatibility and qualifying repeated definitions require additional
rules from N3096 6.2.7 and 6.7.2.3 and remain **M23h**. Distinct nominal types or
redefinitions refused by this implementation are not universally C23 constraint
violations. The project remains an incomplete C23 compiler.

## Resource and failure contracts

Semantic limits are 512 record identities, 512 members per record, 4096 members
per translation unit, by-value/definition nesting 64, and record storage 1 MiB.
Parser limits separately bound member/declaration syntax. Functions admit at most
256 record value temporaries and 1 MiB combined automatic-object/temporary
storage. Queries do not reserve evaluated snapshots. Failed completion restores
the prior definition, member counters and cached state; earlier forward pointers
keep their identity without seeing partially published layout. This is fail-fast
compilation, not general semantic error recovery or arena rollback.

## Required delivery gates

Both full make targets retain all earlier suites and add independent layout,
runtime/interop and exact legacy-token promotion tests plus record AST helpers.
Layout tests inspect real ELF extent/alignment/binding; runtime tests inspect
member relocations, copy bounds and native pointer interoperation. Negative
oracles include malformed/mutated evidence and full diagnostic-stream controls.
Normal and ASan/UBSan runs, bounded fuzzing and exact-commit GitHub CI are release
gates. Implementation or a focused checkpoint pass alone is not release success.
