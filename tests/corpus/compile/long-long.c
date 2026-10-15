long long f(unsigned long x)
{
	return (long long)(x+1LL);
}
int main(void)
{
	unsigned long long bits=1ULL<<63LL;
	if(bits && f(41UL)==42LL)
		return 42;
	return 1;
}
