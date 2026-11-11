# Bounded volatile object types

`volatile` is recognized on scalar integer, enum, floating and pointer types,
including pointed-to types, parameters, and adjusted array-parameter pointers.
Top-level qualification is preserved for compatibility, address taking and
`typeof`, and removed from value conversions and `typeof_unqual`. Volatile
scalar loads and stores, including discarded reads and read-modify-write
expressions, are emitted as calls to separately compiled runtime helpers. The
helpers perform one width-specific volatile access and the compiler transports
floating and pointer representations as bits. Initializer and parameter stores
also use helpers. Linking code that accesses volatile objects requires
`build/libkccrt.a` after the QBE-generated object. Build the runtime without
LTO and with `-fno-strict-aliasing`; the Makefile does this. This implementation
is targeted to naturally aligned x86-64 LP64 scalar objects, with 1-, 2-, 4- and
8-byte representations, and depends on the host C compiler's volatile and
aliasing behavior. It is not a general memory-mapped I/O or concurrency
contract; `volatile` does not make operations atomic.

Arrays of volatile scalar elements, including multidimensional arrays and VLAs,
support indexed access and static initialization. Automatic array initializers,
including strings, designators, implicit zeros
and empty VLAs, use helper stores for each scalar element. Surviving explicit
expressions are captured before stores; implicit zeros and string ranges use
bounded generated loops. Scalar accesses use the same helpers.

Volatile records, unions, their arrays, and volatile scalar or record members
are also supported within the existing aggregate and ABI subset. Whole-record
loads and stores, including records containing volatile members, use bytewise
helper calls over the complete object representation, including padding;
narrow and wide volatile bit-fields use bytewise read/modify/write of touched
bytes; full-width `int` fields use the corresponding scalar-width helper. Automatic
aggregate initialization uses volatile bytewise zero fill and volatile stores
for explicit writes, so an initialized byte can be written more than once.
This implementation-defined access policy does not promise native access widths,
one access per field, atomicity or suitability for memory-mapped devices.

Supported volatile atomic scalars use the atomic paths for accesses and require `-latomic`; initialization uses the volatile
runtime helper where an automatic store is needed. Scalar braced initializers,
including empty initializers
and automatic compound literals, emit one volatile store after evaluating the
surviving initializer expression. Static scalar initializers are also supported.
Atomic record members, aggregate atomics and broader C23 conformance remain unsupported.
`tests/test_volatile_aggregates.py` covers native comparisons, QBE execution,
bit-field widths, instrumented access calls and native/KCC ABI in both directions.
