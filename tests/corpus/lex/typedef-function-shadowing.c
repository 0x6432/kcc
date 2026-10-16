int value(void)
{
	return 42;
}

int main(void)
{
	int (*saved)(void) = value;

	{
		typedef long value;
		value number = saved();

		if (number != 42)
			return 1;
	}
	return value();
}
