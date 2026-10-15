#define REF(x) (&x)
int *get(int *p,int *n) { *n=*n+1; return &*p; }
int main(void) { int x=0; int n=0; int *p=REF(x); *get(p,&n)=42; int **q=&p; return **q; }
