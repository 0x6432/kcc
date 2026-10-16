void *erase(int *p) { return p; }
int *restore(void *p) { return p; }
int main(void) { int x=42; void *v=&x; if(v!=&x) return 1; return *restore(erase(&x)); }
