int row(int (*)[3]);
int row(int a[][3])
{
	int (*p)[3] = a + 1;

	(*p)[2] = 42;
	return (*p)[2];
}

int main(void)
{
	int a[2][3];
	int (*p[2])[3];

	p[0] = a;
	p[1] = (int (*)[3])a;
	return row(p[1]);
}
