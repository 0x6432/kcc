# M24c: bounded atomic types and sequentially consistent loads/stores

This is an intentionally small x86-64 SysV subset, not full C atomic support.
Both `_Atomic int`/`_Atomic unsigned int` and `_Atomic(int)`/`_Atomic(unsigned int)`
are recognized, including typedefs, const, pointers to these types, arrays of them,
`sizeof`, `alignof`, and the existing `typeof` facilities. The type has the same
4-byte size and 4-byte alignment as its non-atomic integer counterpart. Ordinary
lvalue conversion performs a sequentially consistent atomic load; simple
assignment performs a sequentially consistent atomic store and yields the stored
non-atomic value. Addresses are evaluated once. Unevaluated expressions emit no
operation. Object initialization (including parameter initialization, zero and
aggregate initialization) is initialization, not a concurrent atomic store;
programs must not access an object concurrently before initialization completes.

QBE has no atomic instruction in this compiler's IL subset. Loads and stores call
`__atomic_load_4` and `__atomic_store_4`, respectively, using GCC/LLVM libatomic's
ABI with memory-order argument 5 (`__ATOMIC_SEQ_CST`). The call boundary prevents
QBE from replacing these operations with ordinary QBE loads/stores. Link generated
assembly with `-latomic`; the target libatomic must implement this ABI and provide
x86-64 compatible sequential consistency, including interoperation with native
C atomic operations. Natural alignment and valid object lifetimes remain required;
non-atomic accesses to the same object and data races are not made safe by casts.

Atomic read-modify-write operators (`++`, `--`, compound assignments) are
rejected rather than expanded as a non-atomic load and store. Atomic record or
union members, including arrays of atomic members, are rejected because existing
aggregate copies are bytewise. Pointers *to* atomic objects may be members.
Atomic pointer, other integer widths, bool, enum, floating, aggregate and array
atomic types, volatile/restrict, fences, explicit memory orders, atomic library
macros and lock-free queries are not implemented. `_Atomic(type-name)` rejects
qualified, atomic, array, function and unsupported operands. Existing syntax and
resource limits still apply; nested atomic type specifiers share the 64-deep type
query limit. The libatomic ABI's reserved function names must not be redefined by
user programs.

Tests are added for compiler output, negative cases, runtime values and a
cross-compiler pthread sequential-consistency litmus; they have not been run in
this implementation lane. The litmus is a regression check, not a proof of the
memory model. Run normal, sanitizer, QBE and concurrency tests independently
before integration; no conformance claim follows from this bounded subset.
