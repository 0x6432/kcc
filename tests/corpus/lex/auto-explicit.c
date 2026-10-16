typedef long T;
int main(void)
{
	auto int a[2], *p = a;
	T auto T = 40, *q = &T;
	p[1] = *q;
	for (int auto i = 0; i < 2; i++)
		p[1]++;
	return a[1];
}
