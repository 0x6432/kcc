int missing(void);
unsigned long measure(int (*a)[3]) { return sizeof *a+alignof(int[3]); }
int main(void) { int a[3]; if(measure(&a)!=16 || sizeof missing()!=4 || sizeof(true?false:true)!=4) return 1; return 42; }
