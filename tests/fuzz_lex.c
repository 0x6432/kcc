#include "preprocess.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void assert_same_pp_token(struct pp_token left, struct pp_token right)
{
	assert(left.kind == right.kind);
	assert(left.location.source == right.location.source);
	assert(left.location.offset == right.location.offset);
	assert(left.expansion_location.source == right.expansion_location.source);
	assert(left.expansion_location.offset == right.expansion_location.offset);
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

static void check_expanded_stream(const struct source *source, FILE *stream)
{
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	size_t previous_offset = 0;

	preprocess_init(&preprocessor, source, &diagnostics);
	for (size_t steps = 0; ; steps++) {
		struct pp_token token = preprocess_next_pp(&preprocessor);
		const struct source *spelling = token.location.source;

		assert(steps <= source->length + preprocess_work_limit + 1);
		assert(token.kind != pp_newline);
		assert(token.expansion_location.source == source);
		assert(token.expansion_location.offset >= previous_offset);
		assert(token.expansion_location.offset <= source->length);
		assert(spelling->prepared && token.location.offset <= spelling->length);
		assert(token.length <= spelling->length - token.location.offset);
		assert(preprocessor.expansion_work <= preprocess_work_limit);
		assert(preprocessor.auxiliary_records <= preprocess_auxiliary_limit);
		assert(preprocessor.spelling_bytes <= preprocess_spelling_limit);
		assert(preprocessor.prescan_depth == 0);
		assert(preprocessor.optional_depth == 0);
		assert(preprocessor.paste_depth == 0);
		assert(preprocessor.conditional_count <= preprocess_conditional_limit);
		if (spelling != source) {
			struct pp_lexer lexer;
			struct pp_token raw;

			assert(token.kind != pp_eof && token.location.offset == 0);
			assert(token.length == spelling->length && spelling->data[token.length] == 0);
			pp_lexer_init(&lexer, spelling, &diagnostics);
			raw = pp_lexer_next(&lexer);
			assert(raw.kind != pp_invalid && raw.kind != pp_eof && raw.length == token.length);
			if (token.kind != pp_invalid)
				assert(raw.kind == token.kind);
			assert(pp_lexer_next(&lexer).kind == pp_eof);
		}
		if (token.kind == pp_eof) {
			size_t errors = diagnostics.errors;

			assert(spelling == source && token.length == 0);
			assert(token.location.offset == source->length);
			assert_same_pp_token(token, preprocess_next_pp(&preprocessor));
			assert(diagnostics.errors == errors);
			break;
		}
		assert(token.length > 0);
		previous_offset = token.expansion_location.offset;
	}
	preprocess_destroy(&preprocessor);
}

static void assert_same_language_token(struct token left, struct token right)
{
	assert(left.kind == right.kind);
	assert(left.location.source == right.location.source);
	assert(left.location.offset == right.location.offset);
	assert(left.spelling_location.source == right.spelling_location.source);
	assert(left.spelling_location.offset == right.spelling_location.offset);
	assert(left.length == right.length && left.integer == right.integer);
	assert(left.character == right.character);
	assert(left.string_length == right.string_length);
	assert(left.integer_base == right.integer_base);
	assert(left.integer_long_suffix == right.integer_long_suffix);
	assert(left.integer_unsigned_suffix == right.integer_unsigned_suffix);
}

static void fuzz_integer_spelling(const unsigned char *data, size_t size)
{
	struct integer_spelling spelling;
	struct integer_spelling roundtrip;
	char text[32];
	int length;

	if (parse_integer_spelling(data, size, &spelling))
		return;
	assert(spelling.base == 2 || spelling.base == 8 || spelling.base == 10 || spelling.base == 16);
	assert(spelling.long_suffix <= 2);
	length = snprintf(text, sizeof(text), "%ju", (uintmax_t)spelling.value);
	assert(length > 0 && (size_t)length < sizeof(text));
	assert(!parse_integer_spelling((const unsigned char *)text, (size_t)length, &roundtrip));
	assert(roundtrip.value == spelling.value && !roundtrip.unsigned_suffix && !roundtrip.long_suffix);
}

static void fuzz_character_spelling(const unsigned char *data, size_t size)
{
	int64_t value;
	int64_t roundtrip;
	unsigned byte;
	char text[8];

	if (parse_character_spelling(data, size, &value))
		return;
	assert(value >= -128 && value <= 127);
	byte = (unsigned)(value < 0 ? value + 256 : value);
	assert(snprintf(text, sizeof(text), "'\\%03o'", byte) == 6);
	assert(!parse_character_spelling((const unsigned char *)text, 6, &roundtrip));
	assert(value == roundtrip);
}

static void fuzz_string_spelling(const unsigned char *data, size_t size)
{
	size_t length;
	size_t actual;
	unsigned char *decoded;
	unsigned char *encoded;
	unsigned char *roundtrip;

	if (parse_string_spelling(data, size, NULL, 0, &length))
		return;
	assert(length <= size);
	decoded = malloc(length + 1);
	roundtrip = malloc(length + 1);
	encoded = malloc(length * 4 + 2);
	assert(decoded && roundtrip && encoded);
	decoded[length] = 42;
	assert(!parse_string_spelling(data, size, decoded, length, &actual));
	assert(actual == length && decoded[length] == 42);
	encoded[0] = '"';
	for (size_t i = 0; i < length; i++) {
		/* Fixed three-digit octal prevents greedy-hex boundary ambiguity. */
		encoded[1 + i * 4] = '\\';
		encoded[2 + i * 4] = (unsigned char)('0' + (decoded[i] >> 6));
		encoded[3 + i * 4] = (unsigned char)('0' + ((decoded[i] >> 3) & 7));
		encoded[4 + i * 4] = (unsigned char)('0' + (decoded[i] & 7));
	}
	encoded[1 + length * 4] = '"';
	assert(!parse_string_spelling(encoded, length * 4 + 2, roundtrip, length, &actual));
	assert(actual == length && memcmp(decoded, roundtrip, length) == 0);
	if (length) {
		decoded[length - 1] = 42;
		assert(parse_string_spelling(data, size, decoded, length - 1, &actual));
		assert(decoded[length - 1] == 42);
	}
	free(encoded);
	free(roundtrip);
	free(decoded);
}

/* libFuzzer requires this spelling; compiler identifiers remain snake_case. */
int LLVMFuzzerTestOneInput(const unsigned char *data, size_t size)
{
	struct source source;
	struct preprocessor preprocessor;
	FILE *stream;
	struct diagnostics diagnostics;
	size_t previous_end = 0;

	if (size > 65536)
		return 0;
	fuzz_integer_spelling(data, size);
	fuzz_character_spelling(data, size);
	fuzz_string_spelling(data, size);
	stream = fopen("/dev/null", "w");
	assert(stream);
	diagnostics = (struct diagnostics) { .stream = stream };
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
	check_expanded_stream(&source, stream);
	preprocess_init(&preprocessor, &source, &diagnostics);
	for (size_t steps = 0; ; steps++) {
		struct token peek = preprocess_peek(&preprocessor);
		size_t errors = diagnostics.errors;
		size_t work = preprocessor.expansion_work;
		size_t auxiliary = preprocessor.auxiliary_records;
		size_t spelling_bytes = preprocessor.spelling_bytes;
		bool deferred_space = preprocessor.cursor.deferred_space;
		size_t frames = preprocessor.cursor.frame_count;
		size_t offset = preprocessor.input.offset;
		bool pending = preprocessor.cursor.has_pending;
		struct token token;

		assert_same_language_token(peek, preprocess_peek(&preprocessor));
		token = preprocess_next(&preprocessor);
		assert_same_language_token(peek, token);
		assert(diagnostics.errors == errors);
		assert(preprocessor.expansion_work == work);
		assert(preprocessor.auxiliary_records == auxiliary);
		assert(preprocessor.spelling_bytes == spelling_bytes);
		assert(preprocessor.cursor.deferred_space == deferred_space);
		assert(preprocessor.cursor.frame_count == frames);
		assert(preprocessor.input.offset == offset);
		assert(preprocessor.cursor.has_pending == pending);
		assert(frames <= preprocess_depth_limit && work <= preprocess_work_limit);
		assert(preprocessor.macro_count <= preprocess_macro_limit);
		assert(preprocessor.stored_tokens <= preprocess_storage_limit);
		assert(preprocessor.auxiliary_records <= preprocess_auxiliary_limit);
		assert(preprocessor.prescan_depth == 0);
		assert(preprocessor.optional_depth == 0);
		assert(preprocessor.paste_depth == 0);
		assert(preprocessor.conditional_count <= preprocess_conditional_limit);
		if (pending)
			assert(preprocessor.cursor.pending.token.kind != pp_newline);

		assert(steps <= source.length + preprocess_work_limit + 1);
		assert(peek.kind == token.kind);
		assert(peek.location.offset == token.location.offset);
		assert(peek.length == token.length);
		assert(peek.integer == token.integer);
		assert(source_physical_offset(token.location) <= size);
		assert(token.location.offset >= previous_end);
		assert(token.location.offset <= source.length);
		assert(token.spelling_location.source->prepared);
		assert(token.spelling_location.offset <= token.spelling_location.source->length);
		assert(token.length <= token.spelling_location.source->length - token.spelling_location.offset);
		if (token.spelling_location.source != &source)
			assert(token.kind != token_eof && token.spelling_location.source->data[
				token.spelling_location.source->length] == 0);
		assert(preprocessor.spelling_bytes <= preprocess_spelling_limit);
		if (token.kind == token_eof) {
			assert(token.location.offset == source.length && token.length == 0);
			assert_same_language_token(token, preprocess_next(&preprocessor));
			assert_same_language_token(token, preprocess_peek(&preprocessor));
			assert(diagnostics.errors == errors);
			break;
		}
		assert(token.length > 0);
		previous_end = token.location.offset;
	}
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
	return 0;
}
