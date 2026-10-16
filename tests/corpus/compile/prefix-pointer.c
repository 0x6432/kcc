int f(void) { int a[2]; int *p=a; return ++p==a+1 && --p==a; }
