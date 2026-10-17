int cells[];
typedef typeof(cells) Saved;
Saved other;
extern int cells[3];
int rows[][2];
int (*callbacks[])(int);
static int add(int x) { return x+2; }
int run(int x)
{
	cells[2]=x;
	rows[0][1]=2;
	callbacks[0]=add;
	return callbacks[0](cells[2])+other[0]+rows[0][1];
}
