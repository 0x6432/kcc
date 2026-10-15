#define C(a,b) a##b
int main(void)
{
	int x=C(0x,2a);
	return (x | 0b10'10) ^ 052 ^ 4'2;
}
