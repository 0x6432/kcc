#define JOIN(a,b) a##b
int main(void)
{
	unsigned char x=255;
	x JOIN(+,=) 2;
	x-=1;
	return x;
}
