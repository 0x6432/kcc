int *advance(int *p,unsigned short n) { return n+p; }
long distance(short *p,short *q) { return p-q; }
int main(void) { int x=42; int *end=&x+1; return *(end-1)+(end-&x)-1; }
