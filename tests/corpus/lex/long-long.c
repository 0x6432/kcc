long int unsigned long f(long long x) { return x+0xffffffffffffffffULL; }
int main(void) { return (int)f(42LL); }
