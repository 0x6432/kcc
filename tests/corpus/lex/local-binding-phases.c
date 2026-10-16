typedef char T;
int main(void)
{
	long T = sizeof(T), *p = &T;
	char *s = "*";
	int a[2], *q = a;
	q[1] = *s;
	return *p == 8 ? q[1] : 1;
}
