#if (0x2'aLL == 052) && (0b101'010 == 42) && (1'000L == 1000)
int main(void) { return 42; }
#else
#error bad
#endif
