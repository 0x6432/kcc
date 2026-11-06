# Bounded volatile scalar types

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

Volatile arrays, volatile aggregate types and members, and volatile atomic
objects are rejected. Scalar braced initializers, including empty initializers
and automatic compound literals, emit one volatile store after evaluating the
surviving initializer expression. Static scalar initializers are also supported. No general aggregate volatile copy or C23 conformance is claimed.
The compiler and runtime archive build, and focused compile/IL checks were run.
Regression, QBE backend, signal, concurrency and generated-program runtime tests
remain unrun.
