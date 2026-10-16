int f(int x)
{
	static_assert(1 || x, "not an integer constant expression");
	return x;
}
