#include "lex.h"

#include <assert.h>
#include <stdio.h>

/* libFuzzer requires this spelling; compiler identifiers remain snake_case. */
int LLVMFuzzerTestOneInput(const unsigned char *data, size_t size)
{
	struct source source;
	struct lexer lexer;
	FILE *stream;
	struct diagnostics diagnostics;
	size_t previous_end = 0;

	if (size > 65536)
		return 0;
	stream = fopen("/dev/null", "w");
	assert(stream);
	diagnostics = (struct diagnostics) { stream, 0 };
	assert(source_from_bytes(&source, "fuzz.c", data, size));
	lexer_init(&lexer, &source, &diagnostics);
	for (size_t steps = 0; ; steps++) {
		struct token peek = lexer_peek(&lexer);
		struct token token = lexer_next(&lexer);

		assert(steps <= size);
		assert(peek.kind == token.kind);
		assert(peek.location.offset == token.location.offset);
		assert(peek.length == token.length);
		assert(peek.integer == token.integer);
		assert(token.location.offset >= previous_end);
		assert(token.location.offset <= size);
		assert(token.length <= size - token.location.offset);
		if (token.kind == token_eof) {
			assert(token.location.offset == size && token.length == 0);
			assert(lexer_next(&lexer).kind == token_eof);
			break;
		}
		assert(token.length > 0);
		previous_end = token.location.offset + token.length;
	}
	source_destroy(&source);
	assert(fclose(stream) == 0);
	return 0;
}
