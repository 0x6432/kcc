unsigned int f(signed x, int unsigned y) { return x+y; }
int main(void) { return f(-1, 0xffffffffU) >> 31U; }
