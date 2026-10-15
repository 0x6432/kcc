unsigned long mix(long x, unsigned y, unsigned long z)
{
	long a=x+y;
	return (unsigned long)a ^ (z>>33L);
}
int main(void)
{
	long n=1L<<40;
	while(n) {
		n=0;
		if (mix(-1, 1U, 0xffffffffffffffffUL))
			return 42;
	}
	return 1;
}
