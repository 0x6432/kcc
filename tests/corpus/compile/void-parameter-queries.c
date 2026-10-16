int answer(typeof_unqual(const void))
{
	return 42;
}
int run(typeof((void)0))
{
	int (*callback)(typeof(void)) = answer;
	return callback();
}
