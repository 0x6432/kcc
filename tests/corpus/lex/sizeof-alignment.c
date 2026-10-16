#define SIZE sizeof
#define ALIGN _Alignof
unsigned long f(void) { return SIZE(int (*)[3])+ALIGN(const int[2]); }
alignof sizeof _Alignof
