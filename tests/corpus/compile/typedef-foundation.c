typedef int number; typedef number pair[2]; typedef int signature(number); signature f; int f(int x) { return x+2; } int main(void) { pair a; a[0]=40; a[1]=f(a[0]); return a[1]; }
