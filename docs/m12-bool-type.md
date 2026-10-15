# M12j: _Bool type (design before implementation)

Implement the standard boolean type through the existing _Bool keyword first.
C23 bool/true/false spelling remains M23a, explicitly not silently implemented
as int macros in the language. _Bool is a distinct unsigned integer type with
storage width 8, value range 0..1 and rank below char. Increase property rank
numbers consistently, preserving existing order. It promotes to int. Integer
literal candidate lists never include bool. No new literal AST construct yet.

The only declaration specifier combination is _Bool alone (qualifiers/storage
remain later work). Reject signed/unsigned/char/short/int/long or duplicate _Bool
combinations. Signature compatibility must distinguish bool from unsigned char.
Assignments, initialization, arguments, returns and casts to bool compare the
ENTIRE source integer to zero. This is not truncation to a byte or extraction of
a low bit: converting 256 or a high-only-bit long yields 1. Evaluate operands
exactly once and keep explicit conversion/cast nodes and typed-depth accounting.

Reuse byte storage/load and ub ABI. Valid bool objects/ABI values have low byte
0 or 1; call results first discard unspecified upper register bits with extub.
Do not compare the whole raw register to zero for a bool ABI return whose low
byte is zero and upper bits are dirty. By contrast, a conversion from an ordinary
long to bool MUST compare the whole long. Keep these two operations distinct.
Canonical boolean temporaries are 0/1 words. A truth-normalization helper can
operate on an already evaluated temporary and its source type; avoid generating
the operand twice. Bool->other conversions preserve its canonical 0/1 value.

Test all source widths/signs, even and high-only-bit values, negative values,
unary/binary promotions, assignment-result normalization, side effects and fixed
argument/return normalization. Add bool/byte compatibility negatives and both-
direction mixed-eight-argument SysV calls plus dirty upper return-bit functions
with valid low-byte 0/1. Use _Bool-spelled C11 host oracles, no fake true/false
macros. Full regressions, both hosts/sanitizers, bounded fuzz and exact-source CI
are required. C23 keyword/constants will get their own later tests and AST nodes.

Pre-implementation QBE 1.2 probe passed GCC/Clang: bool ub calls/returns, one-byte
storage and comparison of a high-only-bit long before conversion, exit status
42. Compiler integration and dirty-bit tests remain required independently.
