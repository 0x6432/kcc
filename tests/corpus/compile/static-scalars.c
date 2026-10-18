static int value;
extern int value;
static int (*callback)(int);
static int (*incomplete)[];
static int increment(int x) { return x + 1; }
int inspect(void)
{
	if (value || callback || incomplete)
		return 1;
	callback = increment;
	value = callback(41);
	return value;
}