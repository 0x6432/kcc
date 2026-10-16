int next(int *p)
{
	*p = *p + 1;
	return *p;
}

int main(void)
{
	int n = 0, x = next(&n), y = next(&n), total = 0;
	int a[3], (*p)[] = &a, (*q)[3] = p;

	for (int i = 0, end = 3; i < end; i = i + 1)
		total = total + i;
	(*q)[2] = x + y + total + 36;
	return a[2];
}
