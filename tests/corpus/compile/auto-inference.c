int step(int *p) { *p+=1; return *p; }
int main(void) { int n=40; auto x=step(&n); auto p=&x; for(auto i=0;i<1;i++) *p+=1; return n==41?x:1; }
