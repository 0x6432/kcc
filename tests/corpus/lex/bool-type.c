#define FLAG _Bool
_Bool f(long value) { return value; }
int main(void) { FLAG a=256; if(a && f(1L<<40)) return 42; return 0; }
