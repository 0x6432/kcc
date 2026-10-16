int main(void)
{
	int item = 40;
	int *saved = &item;

	{
		typedef long item;
		item amount = 2;

		*saved += amount;
	}
	return item;
}
