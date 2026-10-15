#if (1 ? -1 : 1U/0) > 0 && ((1U<<63) == 9223372036854775808U)
int main(void) { return 42; }
#elif 18446744073709551615U+1U
#error hidden
#endif
