#if ('\xff' < 0) && ((1 ? '\xff' : 0U/0)>0) && ('\123'==83)
int main(void) { return 42; }
#else
#error bad
#endif
