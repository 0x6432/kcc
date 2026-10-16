#define QUERY typeof
int f(int x, QUERY(x) y)
{
	typeof((x++, x ? y : x)) z;
	typeof_unqual(*p) a;
	typeof(nullptr) n = (typeof(nullptr))(void *)0;
	return sizeof(typeof("bytes"));
}
