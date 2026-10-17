static int f(int),g(int); extern int f(int); int f(register int x) { return x; } int g(int x) { return f(x); } int main(void) { return g(42); }
