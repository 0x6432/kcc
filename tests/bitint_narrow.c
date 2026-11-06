typedef _BitInt(8) B8;
typedef unsigned _BitInt(8) U8;
typedef _BitInt(16) B16;
typedef unsigned _BitInt(16) U16;
typedef _BitInt(32) B32;
static_assert(sizeof(B8) == 1 && alignof(B8) == 1 && sizeof(U16) == 2 && alignof(U16) == 2);
static_assert(_Generic((B8)1, B8: 1, signed char: 0, U8: 0, B16: 0, default: 0));
static_assert(_Generic(+(U8)1, U8: 1, default: 0));
static_assert(_Generic((U8)1 + (B8)1, U8: 1, default: 0));
static_assert(_Generic((U8)1 + (B16)1, B16: 1, default: 0));
static_assert(_Generic((U16)1 + (B8)1, U16: 1, default: 0));
static_assert(_Generic((U16)1 + (B32)1, B32: 1, default: 0));
static_assert(_Generic((U8)1 + (unsigned char)1, int: 1, default: 0));
static_assert(_Generic((U16)1 + (short)1, int: 1, default: 0));
static_assert(_Generic((U8)1 << 1, U8: 1, default: 0));
static_assert((U8)255 + (U8)1 == 0 && ~(U8)0 == 255);
static_assert((B16)(B8)-1 == -1 && (U16)(B8)-1 == 65535);
static_assert(((B8)-8 >> 2) == -2 && (U16)65535 + (U16)1 == 0);
struct S { B8 a; U16 b; B8 c[2]; };
static_assert(sizeof(struct S) == 6 && alignof(struct S) == 2);
static B8 g = -128;
static U16 h = (U16)-1;
static struct S s = { -3, 65535, { -1, 4 } };
static U8 table[3] = {255, (U8)256, 3};
int main(void) {
 volatile B8 a = -3; U8 u = 255; U16 v = 65535; B16 b = -300;
 B8 xs[3] = {-1, -2, -3}; B8 *p = xs + (U8)2;
 if (g != -128 || h != 65535 || s.a != -3 || s.b != 65535 || s.c[0] != -1 || table[1] != 0) return 1;
 if ((u + (U8)1) != 0 || (~(U8)0) != 255 || (-(U8)1) != 255) return 2;
 if (((u + (U8)1) + (U8)1) != 1 || ((v + (U16)1) == 0) == 0) return 3;
 if (((B8)-8 >> 2) != -2 || ((U8)128 >> 7) != 1 || ((U8)128 << 1) != 0) return 4;
 if ((long)a != -3 || (unsigned long)a != 18446744073709551613UL ||
     (B8)4294967295UL != -1 || (U16)4294967295UL != 65535) return 5;
 if ((double)b != -300.0 || (B8)-5.0 != -5 || (U16)65535.0 != 65535) return 6;
 if (*p != -3 || p[(B8)-1] != -2) return 7;
 if (u++ != 255 || (v += (U16)2) != 1 || (a += (B8)1) != -2) return 8;
 if (u != 0 || v != 1 || a != -2 || (U8){255} != 255) return 8;
 p += (B8)-1; if (*p != -2) return 8;
 switch (a) { case -2: break; default: return 9; }
 switch (v) { case 1: break; default: return 10; }
 switch (b) { case -300: break; default: return 10; }
 if (((U8)17 / (U8)2) != 8 || ((B8)-17 % (B8)5) != -2) return 11;
 for (int i = 0; i < 256; i++) {
  U8 x = (U8)i;
  if (~x != (255 ^ i) || -x != ((-i) & 255)) return 12;
  for (int j = 0; j < 256; j++) {
   U8 y = (U8)j;
   if (x + y != ((i + j) & 255) || x - y != ((i - j) & 255) ||
       x * y != ((i * j) & 255) || (x & y) != (i & j) ||
       (x | y) != (i | j) || (x ^ y) != (i ^ j)) return 13;
   if (j && (x / y != i / j || x % y != i % j)) return 14;
  }
 }
 return 0;
}
