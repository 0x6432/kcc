long unsigned int f(long x, unsigned y) { return (unsigned long)x+y; }
int main(void) { return (int)f(-1L, 0xffffffffU); }
