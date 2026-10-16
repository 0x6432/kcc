typedef int A[2][3];
int main(void)
{
	register A a;
	typeof(a) copy;
	copy[1][2] = 42;
	return sizeof(a) == sizeof(copy) ? copy[1][2] : 1;
}
