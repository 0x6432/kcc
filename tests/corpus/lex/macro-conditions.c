#define YES 0
#ifdef NO
#if unused expression
#error hidden
#endif
#elifdef YES
int main(void) { return 42; }
#else
12u invalid
#endif
