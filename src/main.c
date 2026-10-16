#include "codegen.h"
#include "parse.h"
#include "sema.h"

#include <stdio.h>
#include <string.h>

enum driver_mode {
	driver_compile,
	driver_tokens,
	driver_pp_tokens,
};

struct driver_options {
	const char *source;
	const char *directories[preprocess_include_directory_limit];
	size_t directory_count;
	enum driver_mode mode;
};

static bool parse_options(int argc, char **argv, struct driver_options *options)
{
	bool has_mode = false;

	*options = (struct driver_options) { 0 };
	for (int i = 1; i < argc; i++) {
		const char *argument = argv[i];

		if (strncmp(argument, "-I", 2) == 0) {
			const char *directory = argument + 2;

			if (!*directory) {
				if (++i == argc)
					return false;
				directory = argv[i];
			}
			if (options->directory_count == preprocess_include_directory_limit)
				return false;
			options->directories[options->directory_count++] = directory;
		} else if (strcmp(argument, "--tokens") == 0 || strcmp(argument, "--pp-tokens") == 0) {
			if (has_mode)
				return false;
			has_mode = true;
			options->mode = strcmp(argument, "--tokens") == 0 ? driver_tokens : driver_pp_tokens;
		} else if (argument[0] == '-' || options->source) {
			return false;
		} else {
			options->source = argument;
		}
	}
	return options->source != NULL;
}

static void print_usage(FILE *stream)
{
	fputs("Usage: kcc [-I dir] [--tokens | --pp-tokens] file.c | ", stream);
	fputs("--help | --version\n", stream);
	fputs("Educational C23 subset compiler; output is QBE IL.\n", stream);
}

static bool load_include(void *context, struct source *source, const char *path)
{
	(void)context;
	return source_load(source, path);
}

static bool dump_language_tokens(const struct source *source, struct diagnostics *diagnostics,
	const struct driver_options *options)
{
	struct preprocessor preprocessor;
	bool output_ok = true;

	preprocess_init(&preprocessor, source, diagnostics);
	preprocess_set_include_loader(&preprocessor, load_include, NULL);
	if (!preprocess_set_include_directories(&preprocessor, options->directories, options->directory_count)) {
		preprocess_destroy(&preprocessor);
		return false;
	}
	for (;;) {
		struct token token = preprocess_next(&preprocessor);

		if (printf("%zu:%s\n", source_physical_offset(token.location),
			token_kind_name(token.kind)) < 0)
			output_ok = false;
		if (token.kind == token_eof)
			break;
	}
	preprocess_destroy(&preprocessor);
	return output_ok;
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

static int dump_tokens(const struct driver_options *options)
{
	const char *path = options->source;
	struct source source;
	struct diagnostics diagnostics = { .stream = stderr };
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
	if (options->mode == driver_pp_tokens)
		output_ok = dump_pp_tokens(&source, &diagnostics);
	else
		output_ok = dump_language_tokens(&source, &diagnostics, options);
	if (fflush(stdout) != 0)
		output_ok = false;
	source_destroy(&source);
	return diagnostics.errors || !output_ok ? 1 : 0;
}

static int compile_source(const struct driver_options *options)
{
	const char *path = options->source;
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { .stream = stderr };
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
	preprocess_set_include_loader(&preprocessor, load_include, NULL);
	if (!preprocess_set_include_directories(&preprocessor, options->directories, options->directory_count)) {
		preprocess_destroy(&preprocessor);
		source_destroy(&source);
		return 1;
	}
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	if (unit && sema_translation_unit(unit, &arena, &diagnostics) &&
		diagnostics.errors == 0) {
		success = codegen_translation_unit(stdout, unit);
		if (!success)
			fputs("kcc: error: cannot write QBE output\n", stderr);
	}
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	return success ? 0 : 1;
}

int main(int argc, char **argv)
{
	struct driver_options options;

	if (argc == 2 && strcmp(argv[1], "--help") == 0) {
		print_usage(stdout);
		return 0;
	}

	if (argc == 2 && strcmp(argv[1], "--version") == 0) {
		puts("kcc milestone m14g");
		return 0;
	}

	if (parse_options(argc, argv, &options)) {
		if (options.mode != driver_compile)
			return dump_tokens(&options);
		return compile_source(&options);
	}

	fputs("kcc: error: expected a source file or supported option\n", stderr);
	print_usage(stderr);
	return 1;
}
