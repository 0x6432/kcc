typedef _BitInt(32) B32;
typedef unsigned _BitInt(32) U32;
typedef _BitInt(64) B64;
typedef unsigned _BitInt(64) U64;
typedef const B32 CB32;

static_assert(sizeof(B32) == 4 && alignof(B64) == 8);
static_assert(_Generic((B32)1, B32: 1, int: 0, U32: 0, default: 0));
static_assert(_Generic((CB32)1, B32: 1, default: 0));
static_assert(_Generic((B32)1 + (U32)2, U32: 1, default: 0));
static_assert(_Generic((B32)1 + 1, int: 1, default: 0));
static_assert(_Generic((U32)1 + 1, unsigned int: 1, default: 0));
static_assert(_Generic((B64)1 + 1U, B64: 1, default: 0));
static_assert(_Generic((U64)1 + 1L, unsigned long: 1, default: 0));
static_assert(_Generic(+(B32)1, B32: 1, default: 0));
static_assert(_Generic((B64)1 + (U32)1, B64: 1, default: 0));
static_assert(_Generic((U64)1 + (B32)1, U64: 1, default: 0));
static_assert(_Generic((B64)1 + 1LL, long long: 1, default: 0));
static_assert(_Generic((U64)1 + 1LL, unsigned long long: 1, default: 0));
static_assert(_Generic((typeof((B32)1))1, B32: 1, default: 0));
static_assert(sizeof(B32 *) == 8 && sizeof(B64[2]) == 16);
static_assert(_Generic((B32)1 << 1, B32: 1, default: 0));
static_assert((U32)-1 == 4294967295U);
static_assert((B64)(B32)-4 == -4);
static_assert((U64)(B32)-1 == 18446744073709551615ULL);
static_assert((U32)4294967295U + (U32)1 == 0);

B32 global = -9;
U64 large = 18446744073709551615ULL;
struct Pair { B32 a; U64 b; };
struct Pair pair = { -4, 8 };
int read_b32(B32 *p) { return *p; }

int main(void) {
 B32 a = -9; U32 b = 4294967295U; B64 c = a; U64 d = large;
 B32 arr[2] = {3, 4}; B32 *p = arr;
 volatile B32 v = -3;
 if (sizeof(arr) != 8 || sizeof(pair) != 16 || c != -9) return 1;
 if (b + (U32)1 != 0 || d + (U64)1 != 0) return 2;
 if ((B32)-9 / (B32)2 != -4 || (B64)-9 % (B64)2 != -1) return 3;
 if (((B32)-8 >> 2) != -2 || ((U32)0x80000000U >> 31) != 1) return 4;
 if ((B64)b != 4294967295LL || (U64)a != 18446744073709551607ULL) return 5;
 a += (B32)4; a++; v += 2;
 if (a != -4 || p[1] != 4 || pair.a != -4 || pair.b != 8 || global != -9 || v != -1 || read_b32(&a) != -4) return 6;
 if ((double)(B32)-7 != -7.0 || (B32)9.0 != 9 || (B32){-5} != -5) return 7;
 if (((~(U32)0) ^ (U32)0xff) != 0xffffff00U) return 8;
 if ((U64)0x8000000000000000ULL / (U64)2 != 0x4000000000000000ULL) return 9;
 return 0;
}
