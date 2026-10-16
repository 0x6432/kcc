#define NAME entry
int f(int x)
{
	NAME:
	int y=40;
	if(x)
	chosen: y+=2;
	end:
	return y;
	unreachable:
}
