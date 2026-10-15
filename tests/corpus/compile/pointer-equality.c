int *get(int *p) { return p; }
int main(void) { int x=42; int y=0; int *p=&x; int *q=&y; if(get(p)==&x && p!=q) return 42; return 0; }
