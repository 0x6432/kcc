int sum(int a[2][3]) { return a[0][0]+a[1][2]; }
int main(void) { int a[2][3]; a[0][0]=20; a[1][2]=22; return sum(a); }
