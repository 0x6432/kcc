typedef int number, *pointer, pair[2], signature(number);
signature f;
int f(int x) { return x; }
int main(void) { pair a; pointer p=&a[1]; *p=42; return f(*p); }
