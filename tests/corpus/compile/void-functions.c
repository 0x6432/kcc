void set(int *p) { *p=42; return; }
void apply(void callback(int *),int *p) { (void)callback(p); }
int main(void) { int x=0; apply(set,&x); return x; }
