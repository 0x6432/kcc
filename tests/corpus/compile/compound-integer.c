#define JOIN(a,b) a##b
int f(unsigned char c,int i,long l,_Bool b,unsigned short s)
{
	c*=3UL;
	i>>=1UL;
	l JOIN(<<,=) 2U;
	b|=4294967296UL;
	i<<=s;
	return c+i+l+b;
}
