#include "lex.h"

#include <assert.h>
#include <stdio.h>

static void assert_same_pp_token(struct pp_token left, struct pp_token right)
{
	assert(left.kind == right.kind);
	assert(left.location.source == right.location.source);
	assert(left.location.offset == right.location.offset);
	assert(left.length == right.length);
	assert(left.leading_space == right.leading_space);
	assert(left.at_line_start == right.at_line_start);
	assert(left.has_non_directive_space == right.has_non_directive_space);
}

static void check_raw_stream(const struct source *source, struct diagnostics *diagnostics)
{
	struct pp_lexer lexer;
	size_t previous_end = 0;
	bool at_line_start = true;

	pp_lexer_init(&lexer, source, diagnostics);
	for (size_t steps = 0; ; steps++) {
		size_t errors = diagnostics->errors;
		struct pp_token peek = pp_lexer_peek(&lexer);
		struct pp_token next;

		assert(steps <= source->length);
		assert(diagnostics->errors == errors + (peek.kind == pp_invalid ? 1u : 0u));
		errors = diagnostics->errors;
		assert_same_pp_token(peek, pp_lexer_peek(&lexer));
		next = pp_lexer_next(&lexer);
		assert_same_pp_token(peek, next);
		assert(diagnostics->errors == errors);
		assert(next.location.offset >= previous_end);
		assert(next.location.offset <= source->length);
		assert(next.length <= source->length - next.location.offset);
		assert(next.at_line_start == at_line_start);
		assert(!next.has_non_directive_space || next.leading_space);
		if (next.kind == pp_eof) {
			assert(next.location.offset == source->length && next.length == 0);
			assert_same_pp_token(next, pp_lexer_next(&lexer));
			assert_same_pp_token(next, pp_lexer_peek(&lexer));
			assert(diagnostics->errors == errors);
			return;
		}
		assert(next.length > 0);
		if (next.kind == pp_newline)
			assert(next.length == 1 && source->data[next.location.offset] == '\n');
		at_line_start = next.kind == pp_newline;
		previous_end = next.location.offset + next.length;
	}
}

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
	assert(source_prepare(&source));
	assert(source.length <= size);
	for (size_t i = 0; i <= source.length; i++) {
		size_t physical = source_physical_offset((struct source_location) { &source, i });

		assert(physical <= size);
		if (i == source.length) {
			assert(physical == size);
			break;
		}
		assert(physical < size);
		assert(source.data[i] == data[physical] ||
			(source.data[i] == '\n' && data[physical] == '\r'));
		assert(source_physical_offset((struct source_location) {
			&source, i + 1 }) > physical);
	}
	check_raw_stream(&source, &diagnostics);
	lexer_init(&lexer, &source, &diagnostics);
	for (size_t steps = 0; ; steps++) {
		struct token peek = lexer_peek(&lexer);
		struct token token = lexer_next(&lexer);

		assert(steps <= source.length);
		assert(peek.kind == token.kind);
		assert(peek.location.offset == token.location.offset);
		assert(peek.length == token.length);
		assert(peek.integer == token.integer);
		assert(source_physical_offset(token.location) <= size);
		assert(token.location.offset >= previous_end);
		assert(token.location.offset <= source.length);
		assert(token.length <= source.length - token.location.offset);
		if (token.kind == token_eof) {
			assert(token.location.offset == source.length && token.length == 0);
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
