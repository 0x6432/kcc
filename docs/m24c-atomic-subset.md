# M24c: bounded atomic types and sequentially consistent loads/stores

This is an intentionally small x86-64 SysV subset, not full C atomic support.
Atomic complete enum types, `_Bool`, `float`, `double`, `char`, signed and
unsigned `char`, `short`, `int`, `long`, `long long`, and signed/unsigned
`_BitInt` widths 2–64 signed and 1–64 unsigned are recognized using
both qualifier and type-specifier syntax, including typedefs, const, pointers
to these types, arrays of them,
`sizeof`, `alignof`, and the existing `typeof` facilities. Each has the same size and alignment as its non-atomic integer counterpart:
enum size and alignment follow the underlying type, 1 byte for `_Bool` and `char`, 2 bytes for `short`, 4 bytes for `int` and `float`, and 8 bytes for `double`, `long` and `long long`. Ordinary
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
8-byte libatomic read-modify-write operations (except `_Bool`, enums, floating
types and non-native-width `_BitInt`). Non-native-width `_BitInt` uses
width-aware compare-exchange loops instead, so results wrap to the declared
width and storage padding remains zero. Subword results are sign- or
zero-extended according to their C type. Prefix, postfix and compound expressions yield the
appropriate new or old value, and the object address is evaluated once. Atomic
compound assignments also support multiplication, division, remainder and shifts
for supported integer types, and arithmetic with floating operands. Supported
atomic `_Bool` and enum objects accept integer compound assignments; supported
atomic `float` and `double` objects accept `+=`, `-=`, `*=` and `/=`. The usual
promotions, arithmetic conversions and final conversion to the object type apply.
These additional forms use an initial sequentially consistent load and a strong
sequentially consistent compare-exchange retry loop, not an ordinary load/store.
The lvalue address and RHS are evaluated once, before retries; the successful
stored value is the expression result. Comparison is by representation, including
for NaNs. An entry-allocated, invocation-local expected-value buffer is reused
across expressions, so repeated execution does not grow the stack. As elsewhere
in the floating subset, floating-environment semantics are not modeled: failed
retries do not restore floating exceptions or the environment. Normal C arithmetic
constraints and undefined cases (such as division by zero or invalid shifts) apply.
Atomic pointers
to complete object types support `++`, `--`, `+=`, and `-=` via the corresponding
8-byte libatomic read-modify-write functions. Integer offsets are scaled by the
referent size before the call. Pointer bounds and lifetime rules still apply.

The partial `stdatomic.h` also offers sequentially consistent exchange and
fetch-add/subtract/and/or/xor via libatomic (non-native-width `_BitInt` fetches
use compare-exchange loops); each evaluates its pointer and
integer operand once and returns the previous value. Their `_explicit` forms
and explicit loads/stores also accept a runtime `memory_order`, evaluated once
and passed to libatomic. The six order values follow GCC/libatomic's 0–5 ABI;
invalid values, release or acquire-release loads, and consume, acquire or
acquire-release stores are outside the supported contract. These additions are
subject to the existing runtime and interoperability tests. Strong and weak compare-exchange, including explicit-order
variants, use the matching `__atomic_compare_exchange_N` for the object size. The weak form is implemented as
strong and may therefore never fail spuriously. The expected argument must point
to a mutable matching non-atomic integer or pointer; failure updates that object. All
arguments are evaluated once. Callers must supply valid success/failure orders:
failure cannot be release or acquire-release or stronger than success.
The fallback header declares the out-of-line libatomic `atomic_thread_fence`
and `atomic_signal_fence` functions. They take a runtime memory order and require
a libatomic providing these functions. Signal handling remains outside the supported concurrency contract. Volatile
atomic scalars use these same atomic access paths; their automatic initialization
uses the separately linked `libkccrt.a`. Fence interactions have not been tested.
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
pointer. Pointer bitwise intrinsics are rejected.
Atomic record or
union members, including arrays of atomic members, are rejected because existing
aggregate copies are bytewise. Pointers *to* atomic objects may be members.
Aggregate and array atomic types,
and other atomic library operations are not implemented. `_Atomic(type-name)` rejects
qualified, atomic, array, function and unsupported operands. Existing syntax and
resource limits still apply; nested atomic type specifiers share the 64-deep type
query limit. The libatomic ABI's reserved function names must not be redefined by
user programs.

Tests cover compiler output, negative cases, runtime values and a cross-compiler
pthread sequential-consistency litmus. The litmus is a regression check, not a
proof of the memory model; no conformance claim follows from this bounded subset.

The built-in header provides atomic character and short typedefs and `atomic_long`, `atomic_ulong`, `atomic_llong`, and
`atomic_ullong` alongside `atomic_int` and `atomic_uint`.

`atomic_bool` supports loads, stores, exchange, compare-exchange and lock-free
queries, with scalar values converted to `_Bool`. Atomic bool increment and fetch
arithmetic/bitwise intrinsics remain rejected; compound assignments are supported
as described above.

Complete atomic enum objects support loads, stores, exchange, compare-exchange,
and lock-free queries using the underlying integer representation. Atomic enum
increment/decrement and fetch arithmetic/bitwise intrinsics remain rejected;
compound assignments are supported as described above.

Atomic `float` and `double` support loads, stores, exchange, compare-exchange,
and lock-free queries. Values are bitcast to/from the libatomic integer ABI, so
compare-exchange compares representations. Floating atomic increment/decrement
and fetch arithmetic intrinsics remain rejected; compound assignments are supported
as described above.

The fallback header also declares C23 `atomic_char8_t` and
`ATOMIC_CHAR8_T_LOCK_FREE` for the target unsigned 8-bit `char8_t`. It declares
other atomic character, least/fast-width, pointer-
sized, size, difference and maximum-width integer typedefs using this target’s
integer types. This does not make the fallback header a complete hosted library.

The fallback header reports the standard integer/pointer `ATOMIC_*_LOCK_FREE`
macros as 2 for naturally aligned target objects, relying on the x86-64
libatomic implementation. A local libatomic query reported lock-free for
aligned sizes 1, 2, 4 and 8; other libraries and concurrency remain untested.

The fallback `kill_dependency` is a single-evaluation pass-through. It makes no
optimization promise and can retain stronger ordering than dependency removal
would permit; it does not establish a complete consume/dependency model. The
macro has only been compile-checked, not concurrency-tested.

Byte-width atomic `_BitInt` uses the existing libatomic integer paths. Focused
KCC execution and standard-integer surrogate cross-object checks are covered by
`tests/test_bitint_abi_atomics.py`; native atomic `_BitInt` interoperability and
concurrent stress for these types are not yet validated. Other bit-precise widths have scalar value support but remain unsupported as
atomic objects.

## Compound-assignment regression coverage

`tests/test_atomic_subset.py` is already registered in both `make test` and
`make test-codegen`. It covers compound operations, signed and unsigned widths,
`_BitInt`, bool, enum, float and double, conversions, volatile objects, nested and
side-effecting operands, unevaluated contexts, NaN representations, repeated
execution and invalid constraints. Pthread tests combine KCC double `+=` and
unsigned long `*=` with native C compare-exchange against the same objects.
These stress checks are not a proof of concurrency correctness or full C
atomic/floating-environment support.

## Non-native-width bit-precise atomics

Signed widths 2–64 and unsigned widths 1–64 support the atomic operations
above within the same size, alignment, memory-order and target limits. For
non-native widths the RMW loop normalizes the result and clears padding;
explicit release and acquire-release orders use relaxed and acquire failure
orders respectively. The compiler evaluates operands once before retries.
`tests/test_bitint_atomic_non_native.py` covers all 119 non-native types,
explicit orders, compare-exchange, wraparound and pthread contention. Clang 15
rejects atomic `_BitInt`, so these tests are not a native `_BitInt` atomic
interoperability oracle. Bytewise access that modifies atomic representation
padding and cross-implementation atomic `_BitInt` compatibility are outside
this bounded contract. Aggregate atomic members and other gaps above remain.
