int f(int n)
{
	int a[1 ? 2 : n];
	return sizeof a;
}
