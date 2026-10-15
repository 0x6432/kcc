#if (0 ? 1/0 : (1<<62)>0) && ((-8>>1)==-4) && ((5^3)==6)
int main(void) { return 42; }
#elif ~0 & 42
#error unselected
#endif
