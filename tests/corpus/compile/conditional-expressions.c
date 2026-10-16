int id(int x) { return x; }
void set(int *p,int x) { *p=x; }
int main(void) { int a[3]; a[1]=42; int (*p)[]=&a; bool b=true; (b?set(&a[0],0):set(&a[0],1)); return (b?id:id)((*(0?p:&a))[1]); }
