void step(int *p) { *p=*p+1; }
int main(void) { int x=0,y=(x=1,41); step(&x),step(&x); return (x=1,y+x); }
