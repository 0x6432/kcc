int identity(int x)
{
	return x;
}

int apply(int callback(int), int x)
{
	return callback(x);
}

int (*factory(void))(int)
{
	return identity;
}

int main(void)
{
	int (*p)(int) = factory();
	int (*a[2])(int);

	a[0] = p;
	a[1] = &identity;
	return apply(a[1], 42);
}
