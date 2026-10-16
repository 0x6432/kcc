int missing(void);
int f(int n, int a[sizeof n], int (*cb)(char n, int b[sizeof n]))
{
	char x;
	int local[sizeof x + 1][1 ? 2 : 1 / 0];
	int (*p)(int x, int y[sizeof x]);
	static_assert(sizeof local == 16);
	return sizeof missing() + sizeof p + sizeof a;
}
