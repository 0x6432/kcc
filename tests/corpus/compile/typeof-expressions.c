int add(int x) { return x + 2; }
int run(int x, typeof(x) y)
{
	const int input = 40;
	typeof_unqual(input) value = input;
	typeof(value++) unchanged = 2;
	typeof(add) *callback = add;
	int a[2];
	typeof(a) b;
	typeof(nullptr) null = (typeof(nullptr))0;
	b[0] = callback(value);
	return null == nullptr ? b[0] + unchanged + x + y : 0;
}
