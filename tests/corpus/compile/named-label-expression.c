int id(int x)
{
	return x;
}
int main(void)
{
	int x=40;
	int a[1];
	a[0]=x;
	x+=id(a[0])-39;
	if(1)
	x++;
	x?x:0;
	return x;
}
