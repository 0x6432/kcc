int *locate(int *p,int *n)
{
	*n+=1;
	return p;
}
int main(void)
{
	int x=40,n=0;
	*locate(&x,&n)+=2;
	return x+n;
}
