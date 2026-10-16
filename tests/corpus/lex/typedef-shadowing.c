typedef long item;
int main(void)
{
	item value = 40;
	{
		typedef int item, *pointer;
		item other = 2;
		pointer address = &other;
		value += *address;
	}
	return sizeof(item) == 8 ? value : 1;
}
