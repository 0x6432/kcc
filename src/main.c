#include "lex.h"

#include <stdio.h>
#include <string.h>

static void print_usage(FILE *stream)
{
	fputs("Usage: kcc --help | --version | --tokens file.c\n", stream);
	fputs("Educational C23 compiler; only token inspection is supported.\n", stream);
}

static int dump_tokens(const char *path)
{
	struct source source;
	struct diagnostics diagnostics = { stderr, 0 };
	struct lexer lexer;
	bool output_ok = true;

	if (!source_load(&source, path)) {
		perror(path);
		return 1;
	}
	lexer_init(&lexer, &source, &diagnostics);
	for (;;) {
		struct token token = lexer_next(&lexer);

		if (printf("%zu:%s\n", token.location.offset,
				token_kind_name(token.kind)) < 0)
			output_ok = false;
		if (token.kind == token_eof)
			break;
	}
	if (fflush(stdout) != 0)
		output_ok = false;
	source_destroy(&source);
	return diagnostics.errors || !output_ok ? 1 : 0;
}

int main(int argc, char **argv)
{
	if (argc == 2 && strcmp(argv[1], "--help") == 0) {
		print_usage(stdout);
		return 0;
	}

	if (argc == 2 && strcmp(argv[1], "--version") == 0) {
		puts("kcc milestone m02");
		return 0;
	}

	if (argc == 3 && strcmp(argv[1], "--tokens") == 0)
		return dump_tokens(argv[2]);

	fputs("kcc: error: expected --help, --version or --tokens file.c\n", stderr);
	print_usage(stderr);
	return 1;
}
