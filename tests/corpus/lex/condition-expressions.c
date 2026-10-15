#define X 40
#if defined(X) && X+2==42 && (1 || 1/0)
int main(void) { return 42; }
#elif 0 && (-9223372036854775807-1)/-1
#error hidden
#endif
