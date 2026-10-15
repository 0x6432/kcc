#include "preprocess.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

struct expected_token {
	enum token_kind kind;
	const char *spelling;
};

static void assert_same_token(struct token left, struct token right)
{
	assert(left.kind == right.kind);
	assert(left.location.source == right.location.source);
	assert(left.location.offset == right.location.offset);
	assert(left.length == right.length && left.integer == right.integer);
}

static void check_stream(const char *text, const struct expected_token *expected,
	size_t count, size_t expected_errors, const char *message)
{
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { stream, 0 };
	struct preprocessor preprocessor;
	struct token last = { 0 };
	size_t previous_end = 0;

	assert(stream);
	assert(source_from_bytes(&source, "directives.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	for (size_t i = 0; i < count; i++) {
		struct token first = preprocess_peek(&preprocessor);
		size_t errors = diagnostics.errors;
		struct token second = preprocess_peek(&preprocessor);
		struct token next = preprocess_next(&preprocessor);

		assert_same_token(first, second);
		assert_same_token(first, next);
		assert(diagnostics.errors == errors);
		assert(next.kind == expected[i].kind);
		assert(next.length == strlen(expected[i].spelling));
		assert(next.location.offset >= previous_end);
		assert(memcmp(source.data + next.location.offset, expected[i].spelling,
			next.length) == 0);
		assert(next.kind == token_eof || next.length > 0);
		previous_end = next.location.offset + next.length;
		last = next;
	}
	assert(last.kind == token_eof && last.location.offset == source.length);
	assert_same_token(last, preprocess_next(&preprocessor));
	assert_same_token(last, preprocess_peek(&preprocessor));
	assert_same_token(last, preprocess_next(&preprocessor));
	assert(diagnostics.errors == expected_errors);
	if (message) {
		char text_buffer[2048];
		size_t bytes;

		rewind(stream);
		bytes = fread(text_buffer, 1, sizeof(text_buffer) - 1, stream);
		assert(!ferror(stream));
		text_buffer[bytes] = 0;
		assert(strstr(text_buffer, message));
	}
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_null_streams(void)
{
	const char *inputs[] = {
		"", "#", "#\n", "%:", "# \t", "%: // EOF",
		"# /* comment */\n#\n", "#/* across\nlines */\n",
		"\v\f#\n", "#/*\v\f*/\n", "#\n%:/*\n*/",
		"# // continued\\\nignored\n", "%\\\n: \t\n",
	};
	const struct expected_token expected[] = { { token_eof, "" } };

	for (size_t i = 0; i < sizeof(inputs) / sizeof(inputs[0]); i++)
		check_stream(inputs[i], expected, sizeof(expected) / sizeof(expected[0]), 0, NULL);
}

static void test_null_directives_in_code(void)
{
	const struct expected_token expected[] = {
		{ token_int, "int" }, { token_identifier, "main" },
		{ token_left_paren, "(" }, { token_void, "void" }, { token_right_paren, ")" },
		{ token_left_brace, "{" }, { token_return, "return" },
		{ token_integer, "42" }, { token_semicolon, ";" },
		{ token_right_brace, "}" }, { token_eof, "" },
	};

	check_stream("#\n %:/**/\nint\n#\nmain(void)\n%:\n{ return\n"
		"# /* null */\n42;\n#\n}\n#", expected,
		sizeof(expected) / sizeof(expected[0]), 0, NULL);
}

static void test_known_and_unknown_directives(void)
{
	const char *names[] = {
		"define", "undef", "include", "embed", "line", "error", "warning", "pragma",
		"if", "ifdef", "ifndef", "elif", "elifdef", "elifndef", "else", "endif",
	};
	const struct expected_token expected[] = {
		{ token_invalid, "#" }, { token_int, "int" }, { token_eof, "" },
	};
	char text[128];

	for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); i++) {
		assert(snprintf(text, sizeof(text), "#%s X 12u .5\nint", names[i]) > 0);
		check_stream(text, expected, sizeof(expected) / sizeof(expected[0]), 1,
			"preprocessing directive is not supported yet");
	}
	check_stream("#unknown @ .5\nint", expected, sizeof(expected) / sizeof(expected[0]),
		1, "unknown preprocessing directive");
	check_stream("#int\nint", expected, sizeof(expected) / sizeof(expected[0]),
		1, "unknown preprocessing directive");
	check_stream("#define X 18446744073709551616\nint", expected,
		sizeof(expected) / sizeof(expected[0]), 1, "not supported yet");
}

static void test_malformed_and_misplaced(void)
{
	const struct expected_token malformed[] = {
		{ token_invalid, "#" }, { token_int, "int" }, { token_eof, "" },
	};
	const struct expected_token misplaced[] = {
		{ token_int, "int" }, { token_invalid, "#" },
		{ token_identifier, "main" }, { token_eof, "" },
	};
	const struct expected_token double_hash[] = {
		{ token_invalid, "%:%:" }, { token_int, "int" }, { token_eof, "" },
	};

	check_stream("#12u\nint", malformed, sizeof(malformed) / sizeof(malformed[0]),
		1, "expected a directive name");
	check_stream("#%:%:\nint", malformed, sizeof(malformed) / sizeof(malformed[0]),
		1, "expected a directive name");
	check_stream("int #define main 1\nmain", misplaced,
		sizeof(misplaced) / sizeof(misplaced[0]), 1, "misplaced '#'");
	check_stream("int/*\n*/#\nmain", misplaced,
		sizeof(misplaced) / sizeof(misplaced[0]), 1, ":2:3: error: misplaced");
	check_stream("#/*\n*/int x;\nint", malformed,
		sizeof(malformed) / sizeof(malformed[0]), 1, ":2:3: error: unknown");
	check_stream("%:%:\nint", double_hash, sizeof(double_hash) / sizeof(double_hash[0]),
		1, "punctuator is not supported");
}

static void test_directive_whitespace(void)
{
	const struct expected_token invalid[] = {
		{ token_invalid, "#" }, { token_int, "int" }, { token_eof, "" },
	};
	const struct expected_token invalid_eof[] = {
		{ token_invalid, "#" }, { token_eof, "" },
	};
	const struct expected_token digraph[] = {
		{ token_invalid, "%:" }, { token_int, "int" }, { token_eof, "" },
	};

	check_stream("#\v\nint", invalid, sizeof(invalid) / sizeof(invalid[0]),
		1, "only space and tab");
	check_stream("#\f", invalid_eof, sizeof(invalid_eof) / sizeof(invalid_eof[0]),
		1, "only space and tab");
	check_stream("# \t/**/\v\nint", invalid, sizeof(invalid) / sizeof(invalid[0]),
		1, "only space and tab");
	check_stream("%:\v\nint", digraph, sizeof(digraph) / sizeof(digraph[0]),
		1, "only space and tab");
	check_stream("#\fdefine X 1\nint", invalid, sizeof(invalid) / sizeof(invalid[0]),
		1, "only space and tab");
}

static void test_lexical_errors_and_spliced_locations(void)
{
	const struct expected_token raw_error[] = {
		{ token_invalid, "/* unterminated" }, { token_eof, "" },
	};
	const struct expected_token unsupported[] = {
		{ token_invalid, "#" }, { token_int, "int" }, { token_eof, "" },
	};

	check_stream("#/* unterminated", raw_error, sizeof(raw_error) / sizeof(raw_error[0]),
		1, "unterminated block comment");
	check_stream("#define X \"bad\nint", unsupported,
		sizeof(unsupported) / sizeof(unsupported[0]), 2, "unterminated quoted");
	check_stream("#\\\r\nunknown X\nint", unsupported,
		sizeof(unsupported) / sizeof(unsupported[0]), 1, ":2:1: error: unknown");
}

static void test_lazy_dispatch(void)
{
	const unsigned char text[] = "int\n#define X 1\n";
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { stream, 0 };
	struct preprocessor preprocessor;

	assert(stream);
	assert(source_from_bytes(&source, "lazy.c", text, sizeof(text) - 1));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	assert(!diagnostics.errors);
	assert(preprocess_peek(&preprocessor).kind == token_int);
	assert(preprocess_peek(&preprocessor).kind == token_int);
	assert(!diagnostics.errors);
	assert(preprocess_next(&preprocessor).kind == token_int);
	assert(preprocess_peek(&preprocessor).kind == token_invalid);
	assert(diagnostics.errors == 1);
	assert(preprocess_peek(&preprocessor).kind == token_invalid);
	assert(preprocess_next(&preprocessor).kind == token_invalid);
	assert(preprocess_next(&preprocessor).kind == token_eof);
	assert(preprocess_next(&preprocessor).kind == token_eof);
	assert(diagnostics.errors == 1);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

int main(void)
{
	test_null_streams();
	test_null_directives_in_code();
	test_known_and_unknown_directives();
	test_malformed_and_misplaced();
	test_directive_whitespace();
	test_lexical_errors_and_spliced_locations();
	test_lazy_dispatch();
	puts("Preprocessor directive and stream tests passed");
	return 0;
}
