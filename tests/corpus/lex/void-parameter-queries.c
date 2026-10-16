#define EMPTY typeof(void)
int f(EMPTY);
int (*callback)(typeof((void)0));
int f(typeof_unqual(const void)) { return 42; }
