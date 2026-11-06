# M24c: bounded atomic types and sequentially consistent loads/stores

This is an intentionally small x86-64 SysV subset, not full C atomic support.
Atomic `char`, signed and unsigned `char`, `short`, `int`, `long`, and `long long`
are recognized using
both qualifier and type-specifier syntax, including typedefs, const, pointers
to these types, arrays of them,
`sizeof`, `alignof`, and the existing `typeof` facilities. Each has the same size and alignment as its non-atomic integer counterpart:
1 byte for `char`, 2 bytes for `short`, 4 bytes for `int`, and 8 bytes for
`long` and `long long`. Ordinary
lvalue conversion performs a sequentially consistent atomic load; simple
assignment performs a sequentially consistent atomic store and yields the stored
non-atomic value. Atomic pointers are also supported for ordinary loads and simple
stores, using the target’s 8-byte pointer size and alignment and libatomic’s
`__atomic_load_8` and `__atomic_store_8` ABI. Addresses are evaluated once. Unevaluated expressions emit no
operation. Object initialization (including parameter initialization, zero and
aggregate initialization) is initialization, not a concurrent atomic store;
programs must not access an object concurrently before initialization completes.

QBE has no atomic instruction in this compiler's IL subset. Loads and stores call
the corresponding `__atomic_load_N` and `__atomic_store_N` functions for
object sizes N = 1, 2, 4 or 8 bytes, using GCC/LLVM libatomic's
ABI with memory-order argument 5 (`__ATOMIC_SEQ_CST`). The call boundary prevents
QBE from replacing these operations with ordinary QBE loads/stores. Link generated
assembly with `-latomic`; the target libatomic must implement this ABI and provide
x86-64 compatible sequential consistency, including interoperation with native
C atomic operations. Natural alignment and valid object lifetimes remain required;
non-atomic accesses to the same object and data races are not made safe by casts.

Sequentially consistent atomic `++`, `--`, `+=`, `-=`, `&=`, `|=` and `^=`
on the supported atomic integer types use the corresponding 1-, 2-, 4-, or
8-byte libatomic read-modify-write operations. Subword results are sign- or
zero-extended according to their C type. Prefix, postfix and compound expressions yield the
appropriate new or old value, and the object address is evaluated once. Atomic
compound multiplication, division, remainder, shifts and floating right operands
are rejected rather than expanded as a non-atomic load and store. Atomic pointers
to complete object types support `++`, `--`, `+=`, and `-=` via the corresponding
8-byte libatomic read-modify-write functions. Integer offsets are scaled by the
referent size before the call. Pointer bounds and lifetime rules still apply.

The partial `stdatomic.h` also offers sequentially consistent exchange and
fetch-add/subtract/and/or/xor via libatomic; each evaluates its pointer and
integer operand once and returns the previous value. Their `_explicit` forms
and explicit loads/stores also accept a runtime `memory_order`, evaluated once
and passed to libatomic. The six order values follow GCC/libatomic's 0–5 ABI;
invalid values, release or acquire-release loads, and consume, acquire or
acquire-release stores are outside the supported contract. These additions are
not yet tested. Strong and weak compare-exchange, including explicit-order
variants, use the matching `__atomic_compare_exchange_N` for the object size. The weak form is implemented as
strong and may therefore never fail spuriously. The expected argument must point
to a mutable matching non-atomic integer or pointer; failure updates that object. All
arguments are evaluated once. Callers must supply valid success/failure orders:
failure cannot be release or acquire-release or stronger than success.
The fallback header declares the out-of-line libatomic `atomic_thread_fence`
and `atomic_signal_fence` functions. They take a runtime memory order and require
a libatomic providing these functions. Signal handling and volatile atomic
objects remain outside the compiler's supported subset. Fence interactions have
not been tested.
The fallback `atomic_flag` uses the naturally aligned four-byte atomic unsigned
representation and implements test-and-set and clear using exchange and store.
This relies on the target libatomic providing lock-free 4-byte operations on
x86-64. Its representation must not be assumed compatible with native compilers'
`atomic_flag` types, which may use a different size or layout. Explicit variants
accept runtime orders; a clear order must be valid for an atomic store. Flag
interoperability and concurrency remain untested.
Atomic pointers also support load, store, exchange, and strong/weak compare-
exchange intrinsics, including explicit-order forms, using the corresponding
8-byte libatomic ABI. The expected compare-exchange argument must point to a
mutable matching non-atomic pointer. `atomic_is_lock_free` queries libatomic
for supported integer and pointer atomic objects, evaluating
its pointer once. Pointer fetch-add/subtract and explicit-order variants accept
an integer offset for a complete object referent, convert it to the target’s
`ptrdiff_t` representation, scale it by the referent size, and return the old
pointer. Pointer bitwise intrinsics are rejected. These pointer intrinsics have
not been runtime-tested.
Atomic record or
union members, including arrays of atomic members, are rejected because existing
aggregate copies are bytewise. Pointers *to* atomic objects may be members.
Bool, enum, floating, aggregate and array atomic types,
volatile atomic types and other atomic library operations are not implemented. `_Atomic(type-name)` rejects
qualified, atomic, array, function and unsupported operands. Existing syntax and
resource limits still apply; nested atomic type specifiers share the 64-deep type
query limit. The libatomic ABI's reserved function names must not be redefined by
user programs.

Tests are added for compiler output, negative cases, runtime values and a
cross-compiler pthread sequential-consistency litmus; they have not been run in
this implementation lane. The litmus is a regression check, not a proof of the
memory model. Run normal, sanitizer, QBE and concurrency tests independently
before integration; no conformance claim follows from this bounded subset.

The built-in header provides atomic character and short typedefs and `atomic_long`, `atomic_ulong`, `atomic_llong`, and
`atomic_ullong` alongside `atomic_int` and `atomic_uint`. The new 8-byte integer
and narrow integer paths have not been runtime- or concurrency-tested.
