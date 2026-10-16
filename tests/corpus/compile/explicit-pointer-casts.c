int id(int x) { return x; }
int main(void) { int (*p)(int)=id; void (*q)(void)=(void (*)(void))p; return ((int (*)(int))q)(42); }
