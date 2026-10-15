#include "codegen.h"
#include "parse.h"
#include "sema.h"

#include <stdio.h>
#include <string.h>

static void print_usage(FILE *stream)
{
	fputs("Usage: kcc file.c | --tokens file.c | --pp-tokens file.c | ", stream);
	fputs("--help | --version\n", stream);
	fputs("Educational C23 subset compiler; output is QBE IL.\n", stream);
}

static bool dump_language_tokens(const struct source *source, struct diagnostics *diagnostics)
{
	struct preprocessor preprocessor;
	bool output_ok = true;

	preprocess_init(&preprocessor, source, diagnostics);
	for (;;) {
		struct token token = preprocess_next(&preprocessor);

		if (printf("%zu:%s\n", source_physical_offset(token.location),
			token_kind_name(token.kind)) < 0)
			output_ok = false;
		if (token.kind == token_eof)
			return output_ok;
	}
}

static bool dump_pp_tokens(const struct source *source, struct diagnostics *diagnostics)
{
	struct pp_lexer lexer;
	bool output_ok = true;

	pp_lexer_init(&lexer, source, diagnostics);
	for (;;) {
		struct pp_token token = pp_lexer_next(&lexer);

		if (printf("%zu:%s:%zu:%u:%u:%u\n", source_physical_offset(token.location),
			pp_token_kind_name(token.kind), token.length, (unsigned)token.leading_space,
			(unsigned)token.at_line_start, (unsigned)token.has_non_directive_space) < 0)
			output_ok = false;
		if (token.kind == pp_eof)
			return output_ok;
	}
}

static int dump_tokens(const char *path, bool preprocessing)
{
	struct source source;
	struct diagnostics diagnostics = { stderr, 0 };
	bool output_ok;

	if (!source_load(&source, path)) {
		perror(path);
		return 1;
	}
	if (!source_prepare(&source)) {
		fputs("kcc: error: cannot prepare source\n", stderr);
		perror(path);
		source_destroy(&source);
		return 1;
	}
	if (preprocessing)
		output_ok = dump_pp_tokens(&source, &diagnostics);
	else
		output_ok = dump_language_tokens(&source, &diagnostics);
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
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	bool success = false;

	if (!source_load(&source, path)) {
		fputs("kcc: error: cannot read source\n", stderr);
		perror(path);
		return 1;
	}
	if (!source_prepare(&source)) {
		fputs("kcc: error: cannot prepare source\n", stderr);
		perror(path);
		source_destroy(&source);
		return 1;
	}
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
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
		puts("kcc milestone m09c");
		return 0;
	}

	if (argc == 3 && strcmp(argv[1], "--tokens") == 0)
		return dump_tokens(argv[2], false);

	if (argc == 3 && strcmp(argv[1], "--pp-tokens") == 0)
		return dump_tokens(argv[2], true);

	if (argc == 2 && argv[1][0] != '-')
		return compile_source(argv[1]);

	fputs("kcc: error: expected a source file or supported option\n", stderr);
	print_usage(stderr);
	return 1;
}
