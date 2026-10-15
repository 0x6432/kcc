int mix(int x, int n)
{
	return (~x & 63) ^ ((x << n) | (x >> n));
}
int main(void)
{
	return mix(21, 1);
}
