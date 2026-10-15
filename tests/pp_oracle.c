/* Test-only spelling dump for comparison with an external C preprocessor. */
#include "preprocess.h"

#include <stdio.h>

int main(int argc, char **argv)
{
	struct source source;
	struct diagnostics diagnostics = { stderr, 0 };
	struct preprocessor preprocessor;
	bool output_ok = true;

	if (argc != 2 || !source_load(&source, argv[1]))
		return 1;
	if (!source_prepare(&source)) {
		source_destroy(&source);
		return 1;
	}
	preprocess_init(&preprocessor, &source, &diagnostics);
	for (;;) {
		struct token token = preprocess_next(&preprocessor);
		const struct source_location spelling = token.spelling_location;

		if (token.kind == token_eof)
			break;
		if (printf("%s:", token_kind_name(token.kind)) < 0 ||
			fwrite(spelling.source->data + spelling.offset, 1, token.length, stdout) !=
			token.length || putchar('\n') == EOF)
			output_ok = false;
	}
	if (fflush(stdout) != 0)
		output_ok = false;
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	return diagnostics.errors || !output_ok ? 1 : 0;
}
