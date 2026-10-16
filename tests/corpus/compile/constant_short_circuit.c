int named(void);
int f(int x)
{
	0 && (1 / 0);
	1 ? 42 : (1 / 0, 2);
	0 ? ((1, 2), (3, 4)) : 42;
	1 ? 42 : named();
	sizeof(x = 1);
	return alignof(long) + sizeof(int[2][3]);
}
