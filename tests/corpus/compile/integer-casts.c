#define U unsigned int
unsigned f(int x)
{
	return (U)(int)(unsigned)x;
}
int main(void)
{
	return (int)(f)(42);
}
