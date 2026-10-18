inline int f(int x) { static const int k=2; return x+k; }
extern int f(int);
int main(void) { return f(40); }
