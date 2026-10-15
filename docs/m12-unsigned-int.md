# M12c: unsigned int and explicit integer conversions (design before coding)

Add only signed/unsigned 32-bit int, not short/long/char or casts yet. Type
specifiers accept int, signed [int], unsigned [int], int signed/int unsigned;
reject repeats/conflicts. Parser records an AST integer-type specifier enum on
locals, parameters and function return declarations, separate from sema's type
annotations. Default zero enum remains signed int for existing constructors.
Update every declaration start (including for initializers), BNF and reserved
keyword conversion together. main still requires signed int return and no args.

Literal tokens/AST preserve base and U-suffix metadata from the shared decoder.
U literals must fit UINT32_MAX; unsuffixed decimal must fit INT32_MAX; unsuffixed
nondecimal picks int then unsigned int. Values requiring long and all L/LL
suffixes remain explicit errors. Keep unary minus separate from positive literal
typing, so -2147483648 remains unsupported until a wider positive type exists.

Type stage adds type_uint and type_is_integer, and a generic function-type
constructor taking return and copied parameter type arrays (no AST dependency).
Function compatibility distinguishes signed and unsigned signatures. Remove the
old int-only constructor rather than maintain two divergent construction paths.

Sema inserts a separate concrete ast_conversion_expression for int/uint changes,
with target annotation and checked structural depth. Integer promotions are
identity. Arithmetic/bitwise/comparison operands use uint if either is uint;
comparisons return int. Shifts retain promoted left type, independently typed
right operand. ! and logical operators return int; other unary results retain
operand type. Assignment/initialization/return/call contexts convert explicitly
to their destination type. Load nodes retain object type. Recompute depths after
conversion insertion; no codegen-only type inference or universal AST union.

Both types use one QBE word and four-byte slots. Bit-preserving int/uint casts
lower to word copies; choose udiv/urem, unsigned comparisons, logical shr only
from validated operand types. Other ops retain word lowering. Unsigned arithmetic
wraps modulo 2^32. Unsigned-to-signed conversion uses the chosen two's-complement
bit pattern; signed overflow and invalid shifts remain undefined C inputs.
Function calls/returns stay QBE w, verified with separately compiled GCC/Clang
unsigned helpers in both directions, including high bits and stack arguments.

Test AST conversion positions/types/depth, mixed arithmetic/comparison/ternary-
free control, uint literal limits/base selection, signed-vs-unsigned division,
right shifts, all declaration positions and prototype conflicts. Full-value
model comparisons, deterministic random defined unsigned arithmetic, malformed
syntax, all old regressions, host ABI, both sanitizers and bounded fuzzing are
required. Do not execute arbitrary fuzz input or claim all integer types/C23.
