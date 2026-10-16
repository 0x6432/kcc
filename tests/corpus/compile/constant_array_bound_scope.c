int f(void)
{
	char n;
	int (*p)(int n, int a[sizeof n]);
	int a[sizeof n];
	int (*q)(int a[sizeof a]);
	static_assert(sizeof a == 4);
	return sizeof p + sizeof q;
}
