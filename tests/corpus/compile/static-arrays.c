typedef int Unknown[];
static int items[3];
extern int items[];
static Unknown items;
static int rows[2][3];
static typeof(rows) copy;
static int (*callbacks[2])(int);
static int increment(int x) { return x + 1; }
int inspect(void)
{
	items[2] = 40;
	rows[1][2] = 1;
	copy[0][1] = 1;
	callbacks[1] = increment;
	return callbacks[1](items[2] + rows[1][2]);
}