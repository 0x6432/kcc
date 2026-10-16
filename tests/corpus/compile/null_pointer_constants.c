int id(int n) { return n; }
int main(void)
{
	int (*p)(int)=(void *)(1-1);
	int *q=sizeof(int)-4;
	if (p!=0 || 0!=q)
		return 1;
	return (1?id:(void *)0)(42);
}
