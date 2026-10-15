/* Test-only spelling dump for comparison with an external C preprocessor. */
#include "preprocess.h"

#include <stdio.h>
#include <string.h>

static bool load_include(void *context, struct source *source, const char *path)
{
	(void)context;
	return source_load(source, path);
}

int main(int argc, char **argv)
{
	struct source source;
	struct diagnostics diagnostics = { .stream = stderr };
	struct preprocessor preprocessor;
	bool output_ok = true;
	bool pp_mode = argc == 3 && strcmp(argv[1], "--pp") == 0;

	if ((!pp_mode && argc != 2) || !source_load(&source, argv[pp_mode ? 2 : 1]))
		return 1;
	if (!source_prepare(&source)) {
		source_destroy(&source);
		return 1;
	}
	preprocess_init(&preprocessor, &source, &diagnostics);
	preprocess_set_include_loader(&preprocessor, load_include, NULL);
	for (;;) {
		struct source_location spelling;
		size_t length;
		const char *kind;

		if (pp_mode) {
			struct pp_token token = preprocess_next_pp(&preprocessor);

			if (token.kind == pp_eof)
				break;
			spelling = token.location;
			length = token.length;
			kind = pp_token_kind_name(token.kind);
		} else {
			struct token token = preprocess_next(&preprocessor);

			if (token.kind == token_eof)
				break;
			spelling = token.spelling_location;
			length = token.length;
			kind = token_kind_name(token.kind);
		}
		if (printf("%s:", kind) < 0 ||
			fwrite(spelling.source->data + spelling.offset, 1, length, stdout) != length ||
			putchar('\n') == EOF)
			output_ok = false;
	}
	if (fflush(stdout) != 0)
		output_ok = false;
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	return diagnostics.errors || !output_ok ? 1 : 0;
}
