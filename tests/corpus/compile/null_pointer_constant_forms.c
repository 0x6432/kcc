int *f(void)
{
	int (*p)[]=0;
	const int *q=(void *)(unsigned char)256;
	if (p==0 && q==0)
		return 0?(1,2):0;
	return (int *)0;
}
