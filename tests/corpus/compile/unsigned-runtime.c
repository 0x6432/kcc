unsigned mix(int x, unsigned y)
{
	unsigned a=x;
	int b=y;
	return (a+b) ^ (y>>1);
}
int main(void)
{
	unsigned x=0xffffffff;
	if (x/2==2147483647U && mix(-1,1)==0U)
		return 42;
	return 1;
}
