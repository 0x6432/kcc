/* Compilation-only fuzz input: never execute. */
int f(int x)
{
	x/=0;
	x<<=-1;
	return x;
}
