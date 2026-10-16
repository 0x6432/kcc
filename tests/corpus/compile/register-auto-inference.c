int step(int *p) { *p+=1; return *p; }
int main(void) { int n=40; register auto x=step(&n); auto y=x; int *p=&y; for(auto register i=0;i<1;i++) *p+=1; return n==41?*p:1; }
