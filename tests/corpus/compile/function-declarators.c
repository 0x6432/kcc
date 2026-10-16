int (*row(int (*)[3], int))[3];

int (*(row)(int (*p)[3], int n))[3]
{
	return p + n;
}

int main(void)
{
	int a[2][3];
	int (*p)[3] = row(a, 1);

	(*p)[2] = 42;
	return a[1][2];
}
