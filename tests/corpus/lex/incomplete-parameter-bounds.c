int sum(int a[], int n)
{
	if (n == 0)
		return 0;
	return a[0] + sum(a + 1, n - 1);
}

int matrix(int a[][3]);
int matrix(int a[7][3])
{
	return a[1][2];
}

int main(void)
{
	int a[3];

	a[0] = 13;
	a[1] = 14;
	a[2] = 15;
	return sum(a, 3);
}
