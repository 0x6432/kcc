typedef long T;
int main(void)
{
	int value = 40;
	T register T = 2, *p = &value;
	for (register int i = 0; i < T; i++)
		(*p)++;
	return &*p == &value ? value : 1;
}
