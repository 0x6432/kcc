#define READONLY const
const int read(READONLY int *const p) { return *p; }
int main(void) { int x=41; const int *p=&x; const void *v=p;
 const int *q=v; *(int *)q=42; return read(p); }
