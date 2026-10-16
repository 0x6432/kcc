typedef long T;
int main(void)
{
	T T = 40, *p = &T;
	{
		typedef char T;
		{
			int T = 2;

			*p += T;
		}
	}
	return T;
}
