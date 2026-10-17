typedef char T; typedef long I;
int step(int *p) { *p+=1; return *p; }
int main(void) { int n=40; auto (T)=step(&n); for(auto I=0;I<1;I++) T++; I restored=42; return n==41 && restored==42?T:1; }
