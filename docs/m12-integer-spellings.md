# M12b: shared integer spelling decoder (design before implementation)

Put one side-effect-free bounded integer spelling decoder in lex.c, declared in
lex.h. Input is an explicit byte slice; output records uint64 value, base,
unsigned suffix and long suffix count (0, 1, 2). Return a static error string or
NULL on success. It must never diagnose, allocate, read beyond the slice or
select a C type. This is token spelling work shared by language conversion and
preprocessing, not a new compiler stage/file.

Move M11's base/separator/suffix checks into that helper, retaining uint64 checked
accumulation and complete-token consumption. Preprocessing calls it and then
applies its existing intmax/uintmax typing; signed decimal >INT64_MAX still
fails without U, nondecimal high values select uintmax. Character parsing stays
unchanged. Correct the stale M11h signed-only grammar comment while touching it.

Runtime conversion initially accepts unsuffixed decimal/octal/hex/binary numbers
and C23 separators; sema still requires every literal to fit signed 32-bit int.
Valid U/L/LL suffixes remain an explicit unsupported numeric-literal error until
M12c types/conversions exist. Thus 0xffffffff cannot silently become signed int,
and -2147483648 remains rejected as a literal needing a wider positive type.

Test the pure decoder independently (all bases, suffix orders/cases, invalid
separators, invalid digits, UINT64_MAX/overflow, exact nonterminated slices).
Keep the complete preprocessing signed/unsigned oracle matrix. Add runtime
literal token/value, macro-paste, newline, host/model and QBE tests. GCC 11's
known lack of digit-separator support is recorded separately from host agreement;
Clang C2x accepts those cases. Fuzz both stages under sanitizers. No AST/type/ABI
change and no wider-type or full C23 claim belongs in this spelling checkpoint.
