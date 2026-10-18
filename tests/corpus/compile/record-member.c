struct S { char a; int b; }; struct S x; int main(void) { struct S y; x.b=42; y=x; return y.b; }
