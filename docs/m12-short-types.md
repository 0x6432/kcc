# M12i: short types (design before implementation)

After M12h, add signed/unsigned short, width 16, rank strictly between char and
int. Update rank numbers without changing existing ordering. Parse one short,
optional int and sign in any order; reject duplicate short and combinations with
char or long. Plain short and signed short have the same type identity. Ordinary
integer/character literal candidate selection is unchanged.

Both short types fit int and use the existing explicit promotion path. Exact
conversions to declared objects/parameters/returns remain distinct from promotion.
Canonical signed/unsigned halfword values occupy QBE words. Add sh/uh ABI names,
loadsh/loaduh, storeh, extsh/extuh normalization, alloc4 2 locals. Normalize narrow
call results immediately. Conversions between bytes/halfwords/words/longs must
respect both source canonicalization and target truncation; never widen raw ABI
bits. The C short type alignment is 2, despite stronger local alloc4 alignment.

A curated QBE 1.2 probe passed GCC/Clang: sh/uh calls/returns, explicit return
extensions, halfword memory and two-byte alloc4 storage. Compiler tests must cover
all boundary bit patterns, signed and unsigned promotions (65535+1 is int 65536),
byte/short conversion crossings, assignment and return wrap, declaration orders,
prototype compatibility and typed-depth bounds. Add both-direction eight-argument
mixed SysV tests and deliberately dirty halfword return bits. Full regressions,
normal/sanitized hosts, bounded fuzz and exact-source CI remain required.

Bool, extended/bit-precise integers, enum, sizeof/alignof, floating and pointers
are separate later increments. Standard integer rank support does not mean full
integer expression semantics or full C23.
