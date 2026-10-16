static_assert(1 ? 42 : 1 / 0, "file\0message");
int missing(void);
int f(int x)
{
	_Static_assert(sizeof x == 4, "parameter");
	static_assert(sizeof missing() == 4);
	for (static_assert(1); 0;)
		;
	return x;
}
