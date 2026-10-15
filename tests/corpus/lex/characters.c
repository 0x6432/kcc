#define CHAR '\xff'
#define ID(x) x
long f(int x) { return x; }
int main(void) { if (f(ID(CHAR)) < 0L) return 'A'-'\27'; return '\0'; }
