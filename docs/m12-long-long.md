# M12f: distinct long long rank (design before implementation)

After M12e, add signed/unsigned long long as distinct compatible-type identities
with 64-bit LP64 representation and rank above long. Same representation is not
type compatibility: long f(long) and long long f(long long) conflict. Extend the
central primitive-property rows; usual-conversion logic already handles a
higher-rank signed type that cannot represent an equally wide unsigned operand
by choosing its unsigned counterpart (long long + ulong -> unsigned long long).

Accept at most two long declaration specifiers in valid orders, with optional
int/sign and no duplicates/conflicts otherwise. Add AST specifier enum values,
map them in sema, and permit the shared decoder's ll/LL suffix metadata at runtime.
Keep mixed-case lL/Ll invalid. Literal candidates follow standard rank order:
no suffix: int/long/ll for decimal, int/uint/long/ulong/ll/ull otherwise;
U: uint/ulong/ull; L: long/ll or long/ulong/ll/ull by base;
UL: ulong/ull; LL: ll or ll/ull by base; ULL: ull.
All magnitudes still fit the decoder's uint64 bound. Decimal >INT64_MAX without
U still has no candidate; never reinterpret it as unsigned or wrap it.

QBE width/storage/control and extension machinery should not change: both new
types are 64 bits. Test candidate identity and the complete rank conversion
matrix, prototype compatibility failures despite equal widths, LL spelling and
casts, full-value arithmetic/shift/return cases and separate-object host ABI.
Move old valid-LL rejection fixtures to unsupported floating pp numbers or
malformed LLL suffixes; preserve their diagnostic purpose explicitly. Run full
regressions, both hosts/sanitizers, fuzz and CI. char/short/ordinary character
runtime constants remain separate upcoming milestones, not implicit scope here.
