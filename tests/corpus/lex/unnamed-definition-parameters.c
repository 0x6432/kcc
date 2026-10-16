long long select(char, int x, short, long, int *, unsigned, long long, long long y)
{
	return x + y;
}

int main(void)
{
	int a = 0;

	return select(1, 13, 2, 3, &a, 4, 5, 29);
}
