#include "lex.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

struct expected_pp_token {
	enum pp_token_kind kind;
	const char *spelling;
	bool leading_space;
	bool at_line_start;
};

static void assert_same_token(struct pp_token left, struct pp_token right)
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

static void check_raw(const char *text, const struct expected_pp_token *expected,
	size_t count, size_t error_count)
{
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct pp_lexer lexer;
	struct pp_token last = { 0 };

	assert(stream);
	assert(source_from_bytes(&source, "raw.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	pp_lexer_init(&lexer, &source, &diagnostics);
	for (size_t i = 0; i < count; i++) {
		struct pp_token first = pp_lexer_peek(&lexer);
		size_t errors = diagnostics.errors;
		struct pp_token second = pp_lexer_peek(&lexer);
		struct pp_token next = pp_lexer_next(&lexer);

		assert_same_token(first, second);
		assert_same_token(first, next);
		assert(diagnostics.errors == errors);
		assert(next.kind == expected[i].kind);
		assert(next.length == strlen(expected[i].spelling));
		assert(memcmp(source.data + next.location.offset, expected[i].spelling,
			next.length) == 0);
		assert(next.leading_space == expected[i].leading_space);
		assert(next.at_line_start == expected[i].at_line_start);
		last = next;
	}
	assert(last.kind == pp_eof && last.location.offset == source.length);
	assert_same_token(last, pp_lexer_next(&lexer));
	assert_same_token(last, pp_lexer_peek(&lexer));
	assert_same_token(last, pp_lexer_next(&lexer));
	assert(diagnostics.errors == error_count);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_keywords_and_spacing(void)
{
	const struct expected_pp_token expected[] = {
		{ pp_identifier, "int", true, true },
		{ pp_identifier, "x", true, false },
		{ pp_punctuator, "=", false, false },
		{ pp_number, "12u", false, false },
		{ pp_newline, "\n", true, false },
		{ pp_identifier, "return", false, true },
		{ pp_identifier, "if", true, false },
		{ pp_newline, "\n", false, false },
		{ pp_eof, "", true, true },
	};
	const struct expected_pp_token spliced[] = {
		{ pp_identifier, "int", false, true },
		{ pp_identifier, "main", true, false },
		{ pp_eof, "", false, false },
	};
	const struct expected_pp_token empty[] = { { pp_eof, "", false, true } };

	check_raw(" \tint/**/x=12u // comment\nreturn if\n\t", expected,
		sizeof(expected) / sizeof(expected[0]), 0);
	check_raw("in\\\nt ma\\\nin", spliced, sizeof(spliced) / sizeof(spliced[0]), 0);
	check_raw("", empty, sizeof(empty) / sizeof(empty[0]), 0);
}

static void test_comment_lines(void)
{
	const struct expected_pp_token expected[] = {
		{ pp_punctuator, "#", true, true },
		{ pp_identifier, "define", false, false },
		{ pp_identifier, "X", true, false },
		{ pp_number, "1", true, false },
		{ pp_punctuator, "+", true, false },
		{ pp_number, "2", false, false },
		{ pp_newline, "\n", false, false },
		{ pp_identifier, "X", false, true },
		{ pp_punctuator, "#", true, false },
		{ pp_identifier, "end", false, false },
		{ pp_newline, "\n", false, false },
		{ pp_newline, "\n", true, true },
		{ pp_punctuator, "#", true, true },
		{ pp_identifier, "x", false, false },
		{ pp_newline, "\n", false, false },
		{ pp_eof, "", false, true },
	};

	check_raw("/*lead\n*/#define X 1 /* across\n comment */ +2\n"
		"X/*\n*/#end\n//c\n #x\n", expected,
		sizeof(expected) / sizeof(expected[0]), 0);
}

static void test_numbers(void)
{
	const char *spellings[] = {
		"42", "0", "00", "09", "0x10", "12u", "12foo", "1e+2", "1E-foo",
		"0x1p-1", ".5", ".5e+foo", "1...2", "1'000", "1'a", "1._",
		"18446744073709551616", "1'p-2", "2'_x",
	};
	const struct expected_pp_token boundaries[] = {
		{ pp_number, "1e+", false, true },
		{ pp_punctuator, "+", false, false },
		{ pp_number, "2", false, false },
		{ pp_number, "1", true, false },
		{ pp_identifier, "e", true, false },
		{ pp_punctuator, "+", false, false },
		{ pp_number, "2", false, false },
		{ pp_number, "1", true, false },
		{ pp_character, "'+'", false, false },
		{ pp_eof, "", false, false },
	};

	for (size_t i = 0; i < sizeof(spellings) / sizeof(spellings[0]); i++) {
		struct expected_pp_token expected[] = {
			{ pp_number, spellings[i], false, true },
			{ pp_eof, "", false, false },
		};

		check_raw(spellings[i], expected, sizeof(expected) / sizeof(expected[0]), 0);
	}
	check_raw("1e++2 1/**/e+2 1'+'", boundaries,
		sizeof(boundaries) / sizeof(boundaries[0]), 0);
}

static void test_punctuators(void)
{
	const char *spellings[] = {
		"[", "]", "(", ")", "{", "}", ".", "->", "++", "--", "&", "*",
		"+", "-", "~", "!", "/", "%", "<<", ">>", "<", ">", "<=", ">=",
		"==", "!=", "^", "|", "&&", "||", "?", ":", "::", ";", "...",
		"=", "*=", "/=", "%=", "+=", "-=", "<<=", ">>=", "&=", "^=",
		"|=", ",", "#", "##", "<:", ":>", "<%", "%>", "%:", "%:%:",
	};
	const struct expected_pp_token overlapping[] = {
		{ pp_punctuator, "%:%:", false, true },
		{ pp_punctuator, "%:", false, false },
		{ pp_punctuator, "<<=", true, false },
		{ pp_punctuator, "=", false, false },
		{ pp_punctuator, "++", true, false },
		{ pp_punctuator, "++", false, false },
		{ pp_punctuator, "+", false, false },
		{ pp_punctuator, "...", true, false },
		{ pp_number, ".12", true, false },
		{ pp_punctuator, ".", true, false },
		{ pp_punctuator, ".", false, false },
		{ pp_other, "@", true, false },
		{ pp_other, "$", false, false },
		{ pp_eof, "", false, false },
	};

	for (size_t i = 0; i < sizeof(spellings) / sizeof(spellings[0]); i++) {
		struct expected_pp_token expected[] = {
			{ pp_punctuator, spellings[i], false, true },
			{ pp_eof, "", false, false },
		};

		check_raw(spellings[i], expected, sizeof(expected) / sizeof(expected[0]), 0);
	}
	check_raw("%:%:%: <<== +++++ ... .12 .. @$", overlapping,
		sizeof(overlapping) / sizeof(overlapping[0]), 0);
}

static void test_quoted_tokens(void)
{
	const char *prefixes[] = { "", "u8", "u", "U", "L" };
	char text[128];

	for (size_t i = 0; i < sizeof(prefixes) / sizeof(prefixes[0]); i++) {
		struct expected_pp_token expected[] = {
			{ pp_string, text, false, true },
			{ pp_eof, "", false, false },
		};

		assert(snprintf(text, sizeof(text), "%s\"a///*x*/\\\"b\"", prefixes[i]) > 0);
		check_raw(text, expected, sizeof(expected) / sizeof(expected[0]), 0);
		expected[0].kind = pp_character;
		assert(snprintf(text, sizeof(text), "%s'\\''", prefixes[i]) > 0);
		check_raw(text, expected, sizeof(expected) / sizeof(expected[0]), 0);
	}
	{
		const struct expected_pp_token separated[] = {
			{ pp_identifier, "u8", false, true },
			{ pp_string, "\"text\"", true, false },
			{ pp_string, "\"\\\\\"", true, false },
			{ pp_identifier, "u8name", true, false },
			{ pp_eof, "", false, false },
		};

		check_raw("u8 \"text\" \"\\\\\" u8name", separated,
			sizeof(separated) / sizeof(separated[0]), 0);
	}
}

static void test_partial_tokens(void)
{
	const struct expected_pp_token comment[] = {
		{ pp_invalid, "/*x\n", true, true },
		{ pp_eof, "", false, false },
	};
	const struct expected_pp_token quoted[] = {
		{ pp_invalid, "u8\"x", false, true },
		{ pp_newline, "\n", false, false },
		{ pp_identifier, "next", false, true },
		{ pp_eof, "", false, false },
	};
	const struct expected_pp_token ending[] = {
		{ pp_invalid, "'x", false, true },
		{ pp_eof, "", false, false },
	};

	check_raw("/*x\n", comment, sizeof(comment) / sizeof(comment[0]), 1);
	check_raw("u8\"x\nnext", quoted, sizeof(quoted) / sizeof(quoted[0]), 1);
	check_raw("'x", ending, sizeof(ending) / sizeof(ending[0]), 1);
}

static void test_conversion_boundary(void)
{
	const char *spellings[] = { "int", "42", "12u", "#", "\"x\"", "'x'", "'", "<%" };
	const enum token_kind expected[] = {
		token_int, token_integer, token_integer, token_invalid, token_string,
		token_character, token_invalid, token_left_brace,
	};

	for (size_t i = 0; i < sizeof(spellings) / sizeof(spellings[0]); i++) {
		struct source source;
		FILE *stream = tmpfile();
		struct diagnostics diagnostics = { .stream = stream };
		struct pp_lexer lexer;
		struct pp_token raw;
		struct token token;

		assert(stream);
		assert(source_from_bytes(&source, "conversion.c",
			(const unsigned char *)spellings[i], strlen(spellings[i])));
		assert(source_prepare(&source));
		pp_lexer_init(&lexer, &source, &diagnostics);
		raw = pp_lexer_next(&lexer);
		assert(diagnostics.errors == (raw.kind == pp_invalid ? 1u : 0u));
		token = token_from_pp(raw, &diagnostics);
		assert(token.kind == expected[i]);
		assert(diagnostics.errors == (token.kind == token_invalid ? 1u : 0u));
		assert(token.location.offset == raw.location.offset && token.length == raw.length);
		if (token.kind == token_integer)
			assert(token.integer == (i == 2 ? 12u : 42u));
		if (i == 2)
			assert(token.integer_unsigned_suffix);
		source_destroy(&source);
		assert(fclose(stream) == 0);
	}
}

static void test_directive_whitespace_metadata(void)
{
	const unsigned char text[] = "#\vname /*\f*/ next\n\f#x";
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct pp_lexer lexer;
	struct pp_token token;

	assert(stream);
	assert(source_from_bytes(&source, "spacing.c", text, sizeof(text) - 1));
	assert(source_prepare(&source));
	pp_lexer_init(&lexer, &source, &diagnostics);
	token = pp_lexer_next(&lexer);
	assert(token.kind == pp_punctuator && !token.has_non_directive_space);
	token = pp_lexer_next(&lexer);
	assert(token.kind == pp_identifier && token.leading_space);
	assert(token.has_non_directive_space && !token.at_line_start);
	token = pp_lexer_next(&lexer);
	assert(token.kind == pp_identifier && token.leading_space);
	assert(!token.has_non_directive_space);
	token = pp_lexer_next(&lexer);
	assert(token.kind == pp_newline && !token.has_non_directive_space);
	token = pp_lexer_next(&lexer);
	assert(token.kind == pp_punctuator && token.at_line_start);
	assert(token.leading_space && token.has_non_directive_space);
	token = pp_lexer_next(&lexer);
	assert(token.kind == pp_identifier && !token.has_non_directive_space);
	assert(!diagnostics.errors);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_extern_preprocessing_identifier(void)
{
	const struct expected_pp_token tokens[] = {
		{ pp_identifier, "extern", false, true },
		{ pp_identifier, "name", true, false },
		{ pp_eof, "", false, false },
	};

	check_raw("extern name", tokens, sizeof(tokens) / sizeof(tokens[0]), 0);
}

int main(void)
{
	test_extern_preprocessing_identifier();
	test_keywords_and_spacing();
	test_comment_lines();
	test_numbers();
	test_punctuators();
	test_quoted_tokens();
	test_partial_tokens();
	test_conversion_boundary();
	test_directive_whitespace_metadata();
	puts("Raw preprocessing token and conversion tests passed");
	return 0;
}
