int owner;
int f(void) { extern int owner; static int count=1; static int *p=&owner; *p=++count; return *p; }
int main(void) { int f(void); return f(); }
