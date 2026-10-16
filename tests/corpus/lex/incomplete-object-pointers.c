int read(int (*)[]);
int read(int (*)[3]);
int read(int (*p)[])
{
	int (*q)[] = p;

	return (*q)[2];
}

int main(void)
{
	int a[3];
	int (*p)[] = &a;

	a[2] = 42;
	return read(p);
}
