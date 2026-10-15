#include "codegen.h"
#include "parse.h"
#include "sema.h"

#include <stdio.h>
#include <string.h>

static void print_usage(FILE *stream)
{
	fputs("Usage: kcc file.c | --tokens file.c | --help | --version\n", stream);
	fputs("Educational C23 subset compiler; output is QBE IL.\n", stream);
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

static int compile_source(const char *path)
{
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { stderr, 0 };
	struct lexer lexer;
	struct ast_translation_unit *unit;
	bool success = false;

	if (!source_load(&source, path)) {
		fputs("kcc: error: cannot read source\n", stderr);
		perror(path);
		return 1;
	}
	lexer_init(&lexer, &source, &diagnostics);
	unit = parse_translation_unit(&lexer, &arena, &diagnostics);
	if (unit && sema_translation_unit(unit, &arena, &diagnostics) &&
		diagnostics.errors == 0) {
		success = codegen_translation_unit(stdout, unit);
		if (!success)
			fputs("kcc: error: cannot write QBE output\n", stderr);
	}
	arena_destroy(&arena);
	source_destroy(&source);
	return success ? 0 : 1;
}

int main(int argc, char **argv)
{
	if (argc == 2 && strcmp(argv[1], "--help") == 0) {
		print_usage(stdout);
		return 0;
	}

	if (argc == 2 && strcmp(argv[1], "--version") == 0) {
		puts("kcc milestone m06c");
		return 0;
	}

	if (argc == 3 && strcmp(argv[1], "--tokens") == 0)
		return dump_tokens(argv[2]);

	if (argc == 2 && argv[1][0] != '-')
		return compile_source(argv[1]);

	fputs("kcc: error: expected a source file or supported option\n", stderr);
	print_usage(stderr);
	return 1;
}
