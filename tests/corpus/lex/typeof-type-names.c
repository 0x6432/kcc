#define QUERY typeof
QUERY(int) f(typeof_unqual(const int *) p)
{
	typeof_unqual(const int[2]) a;
	typeof(int (*)(int)) callback;
	return sizeof(typeof(int)) + _Alignof(typeof_unqual(const long));
}
