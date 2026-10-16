#define QUERY typeof
int add(int x) { return x + 2; }
QUERY(int) run(typeof(int[2]) a)
{
	typeof_unqual(const int[2][3]) values;
	typeof_unqual(int (* const)(int)) callback = add;
	typeof(const int *) pointer = &a[0];
	typeof(typeof_unqual(const unsigned char)) result = 40;
	_Static_assert(sizeof(typeof(long)) == 8, "LP64");
	values[1][2] = callback(result);
	return values[1][2] + *pointer;
}
