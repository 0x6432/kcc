#include <stdio.h>
#include <string.h>

static void print_usage(FILE *stream)
{
	fputs("Usage: kcc --help | --version\n", stream);
	fputs("Educational C23 compiler; input is not supported yet.\n", stream);
}

int main(int argc, char **argv)
{
	if (argc == 2 && strcmp(argv[1], "--help") == 0) {
		print_usage(stdout);
		return 0;
	}

	if (argc == 2 && strcmp(argv[1], "--version") == 0) {
		puts("kcc milestone m00");
		return 0;
	}

	fputs("kcc: error: expected --help or --version\n", stderr);
	print_usage(stderr);
	return 1;
}
