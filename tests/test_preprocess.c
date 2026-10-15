#include "preprocess.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
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
	assert(left.spelling_location.source == right.spelling_location.source);
	assert(left.spelling_location.offset == right.spelling_location.offset);
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
	size_t previous_offset = 0;

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
		assert(next.location.offset >= previous_offset);
		assert(memcmp(source.data + next.spelling_location.offset, expected[i].spelling,
			next.length) == 0);
		assert(next.kind == token_eof || next.length > 0);
		previous_offset = next.location.offset;
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
	preprocess_destroy(&preprocessor);
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
		"include", "embed", "line", "error", "warning", "pragma",
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
	check_stream("#include X 18446744073709551616\nint", expected,
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
	check_stream("#include X \"bad\nint", unsupported,
		sizeof(unsupported) / sizeof(unsupported[0]), 2, "unterminated quoted");
	check_stream("#\\\r\nunknown X\nint", unsupported,
		sizeof(unsupported) / sizeof(unsupported[0]), 1, ":2:1: error: unknown");
}

static void test_lazy_dispatch(void)
{
	const unsigned char text[] = "int\n#include X 1\n";
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
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_object_expansion(void)
{
	const struct expected_token expected[] = {
		{ token_int, "int" }, { token_integer, "42" }, { token_plus, "+" },
		{ token_integer, "42" }, { token_identifier, "value" }, { token_eof, "" },
	};
	const struct expected_token recursive[] = {
		{ token_identifier, "A" }, { token_identifier, "A" },
		{ token_identifier, "B" }, { token_identifier, "SELF" }, { token_eof, "" },
	};
	const struct expected_token separate[] = {
		{ token_integer, "1" }, { token_integer, "2" },
		{ token_plus, "+" }, { token_plus, "+" }, { token_eof, "" },
	};
	const struct expected_token source_order[] = {
		{ token_integer, "1" }, { token_identifier, "X" },
		{ token_integer, "2" }, { token_integer, "2" }, { token_eof, "" },
	};

	check_stream("#define TYPE int\n#define VALUE N\n#define N 42\n#define EMPTY\n"
		"TYPE EMPTY VALUE + N value\n", expected, sizeof(expected) / sizeof(expected[0]),
		0, NULL);
	check_stream("#define A B\n#define B A\n#define SELF SELF\nA A B SELF\n", recursive,
		sizeof(recursive) / sizeof(recursive[0]), 0, NULL);
	check_stream("#define ONE 1\n#define PLUS +\nONE 2 PLUS+", separate,
		sizeof(separate) / sizeof(separate[0]), 0, NULL);
	check_stream("#define X 1\nX\n#undef X\nX\n#define X 2\nX\n#undef UNKNOWN\nX\n",
		source_order, sizeof(source_order) / sizeof(source_order[0]), 0, NULL);
}

static void test_macro_definition_rules(void)
{
	const struct expected_token parens[] = {
		{ token_left_paren, "(" }, { token_integer, "3" }, { token_right_paren, ")" },
		{ token_eof, "" },
	};
	const struct expected_token empty[] = { { token_eof, "" } };
	const struct expected_token unchanged[] = {
		{ token_invalid, "#" }, { token_integer, "1" }, { token_eof, "" },
	};
	const struct expected_token bad_name[] = {
		{ token_invalid, "#" }, { token_identifier, "X" }, { token_eof, "" },
	};
	const char *invalid[] = {
		"#define\nX", "#define 1\nX", "#undef\nX", "#undef 1\nX",
		"#define X+1\nX", "#define X(x) 1\nX", "#define X ## 1\nX",
		"#define X 1 %:%: 2\nX", "#define X\v 1\nX", "#define X 1\f\nX",
		"#undef X trailing\nX", "#undef X\v\nX", "#define defined 1\nX",
		"#define __LINE__ 1\nX", "#undef _Pragma\nX", "#define X \"bad\nX",
	};

	check_stream("#define X (3)\n#define X /* trivia */ (3) /* tail */\nX", parens,
		sizeof(parens) / sizeof(parens[0]), 0, NULL);
	check_stream("#define X/**/(3)\nX", parens,
		sizeof(parens) / sizeof(parens[0]), 0, NULL);
	check_stream("#define X\n#define X /**/\nX\n#undef X", empty, 1, 0, NULL);
	check_stream("#define X 12u .5 \"unused\"\n#undef X", empty, 1, 0, NULL);
	check_stream("#define X 1\n#define X 2\nX", unchanged, 3, 1,
		"incompatible macro redefinition");
	check_stream("#define X 1\n#undef X extra\nX", unchanged, 3, 1,
		"unexpected token after macro name");
	check_stream("#define X 1\n#define X() 2\nX", unchanged, 3, 1,
		"incompatible macro redefinition");
	for (size_t i = 0; i < sizeof(invalid) / sizeof(invalid[0]); i++)
		check_stream(invalid[i], bad_name, 3, 1, NULL);
}

static void test_rescan_and_redefinition(void)
{
	const struct expected_token last_token[] = {
		{ token_integer, "1" }, { token_integer, "2" }, { token_identifier, "A" },
		{ token_integer, "1" }, { token_integer, "2" }, { token_identifier, "A" },
		{ token_eof, "" },
	};
	const struct expected_token whitespace[] = {
		{ token_invalid, "#" }, { token_integer, "1" }, { token_plus, "+" },
		{ token_integer, "2" }, { token_eof, "" },
	};
	const struct expected_token generated[] = {
		{ token_invalid, "#" }, { token_identifier, "define" },
		{ token_identifier, "X" }, { token_integer, "1" },
		{ token_identifier, "X" }, { token_eof, "" },
	};

	check_stream("#define A 1 B\n#define B 2 A\nA A", last_token, 7, 0, NULL);
	check_stream("#define X 1 +2\n#define X 1+2\nX", whitespace, 5, 1,
		"incompatible macro redefinition");
	check_stream("#define X 1 +2\n#define X 1	+2\n#define X 1/**/+2\n"
		"#define X 1 + 2\nX", whitespace, 5, 1, "incompatible macro redefinition");
	check_stream("#define HASH #\nHASH define X 1\nX", generated, 6, 1,
		"directive marker cannot be converted");
}

static void test_macro_identity_reuse(void)
{
	char text[40000];
	size_t used = 0;
	const struct expected_token expected[] = { { token_integer, "7" }, { token_eof, "" } };

	for (size_t i = 0; i < preprocess_macro_limit + 1; i++)
		used += (size_t)sprintf(text + used, "#define X\n#undef X\n");
	used += (size_t)sprintf(text + used, "#define X 7\nX");
	assert(used < sizeof(text));
	check_stream(text, expected, 2, 0, NULL);
}

static void test_macro_locations(void)
{
	const unsigned char text[] = "#define A B\n#define B missing\nA\n";
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { stream, 0 };
	struct preprocessor preprocessor;
	struct token token;

	assert(stream);
	assert(source_from_bytes(&source, "locations.c", text, sizeof(text) - 1));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	token = preprocess_next(&preprocessor);
	assert(token.kind == token_identifier && token.length == 7);
	assert(token.location.offset == sizeof(text) - 3);
	assert(token.spelling_location.offset == 22);
	assert(preprocess_next(&preprocessor).kind == token_eof);
	assert(!diagnostics.errors);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

/* Resource failures terminate with one invalid token, then stable EOF. */
static void check_resource_failure(const char *text, const char *message,
	size_t minimum_integers, size_t maximum_integers)
{
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { stream, 0 };
	struct preprocessor preprocessor;
	struct token token;
	char buffer[256];
	size_t integers = 0;
	size_t bytes;

	assert(stream);
	assert(source_from_bytes(&source, "limits.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	while ((token = preprocess_next(&preprocessor)).kind != token_invalid) {
		assert(token.kind == token_integer);
		integers++;
		assert(integers <= preprocess_work_limit);
	}
	assert(integers >= minimum_integers && integers <= maximum_integers);
	assert(token.length > 0 && preprocessor.stopped && diagnostics.errors == 1);
	token = preprocess_peek(&preprocessor);
	assert(token.kind == token_eof && token.location.offset == source.length);
	assert_same_token(token, preprocess_peek(&preprocessor));
	assert_same_token(token, preprocess_next(&preprocessor));
	assert_same_token(token, preprocess_next(&preprocessor));
	assert(diagnostics.errors == 1);
	rewind(stream);
	bytes = fread(buffer, 1, sizeof(buffer) - 1, stream);
	buffer[bytes] = 0;
	assert(strstr(buffer, message));
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_macro_limits(void)
{
	char *text = malloc(400000);
	size_t used = 0;

	assert(text);
	for (size_t i = 0; i <= preprocess_macro_limit; i++)
		used += (size_t)sprintf(text + used, "#define M%zu\n", i);
	check_resource_failure(text, "macro name limit exceeded", 0, 0);
	used = (size_t)sprintf(text, "#define X ");
	for (size_t i = 0; i <= preprocess_replacement_limit; i++)
		used += (size_t)sprintf(text + used, "1 ");
	check_resource_failure(text, "macro replacement storage limit exceeded", 0, 0);
	used = 0;
	for (size_t i = 0; i <= preprocess_storage_limit / preprocess_replacement_limit; i++) {
		used += (size_t)sprintf(text + used, "#define X ");
		for (size_t j = 0; j < preprocess_replacement_limit; j++)
			used += (size_t)sprintf(text + used, "1 ");
		used += (size_t)sprintf(text + used, "\n");
	}
	check_resource_failure(text, "macro replacement storage limit exceeded", 0, 0);
	used = 0;
	for (size_t i = 0; i < preprocess_depth_limit; i++)
		used += (size_t)sprintf(text + used, "#define M%zu M%zu\n", i, i + 1);
	used += (size_t)sprintf(text + used, "#define M%u 1\nM0", preprocess_depth_limit);
	check_resource_failure(text, "macro expansion depth limit exceeded", 0, 0);
	used = (size_t)sprintf(text, "#define M0 1\n");
	for (size_t i = 1; i <= 16; i++)
		used += (size_t)sprintf(text + used, "#define M%zu M%zu M%zu\n", i, i - 1, i - 1);
	used += (size_t)sprintf(text + used, "M16\n");
	/* 65536 units stop within the binary expansion, without huge output. */
	check_resource_failure(text, "macro expansion work limit exceeded", 1, preprocess_work_limit);
	used = (size_t)sprintf(text, "#define X ");
	for (size_t i = 0; i < preprocess_replacement_limit; i++)
		used += (size_t)sprintf(text + used, "1 ");
	used += (size_t)sprintf(text + used, "\n");
	for (size_t i = 0; i < 64; i++)
		used += (size_t)sprintf(text + used, "X ");
	/* 63 * (1 push + 1024 visits), then 1 push + 960 visits. */
	check_resource_failure(text, "macro expansion work limit exceeded", 65472, 65472);
	free(text);
}

static void test_empty_function_macros(void)
{
	const struct expected_token basic[] = {
		{ token_integer, "42" }, { token_integer, "42" },
		{ token_identifier, "F" }, { token_eof, "" },
	};
	const struct expected_token empty[] = { { token_eof, "" } };
	const struct expected_token bare[] = { { token_identifier, "F" }, { token_eof, "" } };
	const struct expected_token not_retroactive[] = {
		{ token_identifier, "F" }, { token_left_paren, "(" },
		{ token_right_paren, ")" }, { token_eof, "" },
	};
	const struct expected_token number[] = { { token_integer, "7" }, { token_eof, "" } };

	check_stream("#define F()42\n#define F( /* empty */ ) 42\nF() F (\n) F", basic,
		sizeof(basic) / sizeof(basic[0]), 0, NULL);
	check_stream("#define F()\nF() F/**/(/**/) F\n(\n)", empty, 1, 0, NULL);
	check_stream("#define F() unused\nF", bare, 2, 0, NULL);
	check_stream("#define F() 7\n#define LP (\nF LP )", not_retroactive, 4, 0, NULL);
	check_stream("#define F() 7\n#define EMPTY\nF EMPTY ()", not_retroactive, 4, 0, NULL);
	check_stream("#define ALIAS F\n#define F() 7\nALIAS/**/(\n)", number, 2, 0, NULL);
	check_stream("#define PREFIX F(\n#define F() 7\nPREFIX )", number, 2, 0, NULL);
	check_stream("#define SUFFIX ()\n#define F() 7\n#define CALL F SUFFIX\nCALL",
		not_retroactive, 4, 0, NULL);
	check_stream("%:define F() 7\nF\\\n()", number, 2, 0, NULL);
}

static void test_function_macro_redefinition(void)
{
	const struct expected_token unchanged[] = {
		{ token_invalid, "#" }, { token_integer, "1" }, { token_eof, "" },
	};
	const struct expected_token number[] = { { token_integer, "2" }, { token_eof, "" } };
	const struct expected_token object[] = {
		{ token_left_paren, "(" }, { token_right_paren, ")" },
		{ token_integer, "2" }, { token_eof, "" },
	};

	check_stream("#define F() 1\n#define F 2\nF()", unchanged, 3, 1,
		"incompatible macro redefinition");
	check_stream("#define F() 1\n#define F() 2\nF()", unchanged, 3, 1,
		"incompatible macro redefinition");
	check_stream("#define F() 1\n#define F(x) x\nF()", unchanged, 3, 1,
		"macro parameters are not supported");
	check_stream("#define F() 1\n#undef F\n#define F 2\nF", number, 2, 0, NULL);
	check_stream("#define F 1\n#undef F\n#define F() 2\nF()", number, 2, 0, NULL);
	check_stream("#define F/**/()2\nF", object, 4, 0, NULL);
}

static void test_function_macro_suppression(void)
{
	const struct expected_token recursive[] = {
		{ token_identifier, "F" }, { token_left_paren, "(" },
		{ token_right_paren, ")" }, { token_eof, "" },
	};
	const struct expected_token alias[] = {
		{ token_identifier, "A" }, { token_identifier, "A" }, { token_eof, "" },
	};

	check_stream("#define F() F()\nF()", recursive, 4, 0, NULL);
	check_stream("#define F() G()\n#define G() F()\nF()", recursive, 4, 0, NULL);
	check_stream("#define A F()\n#define F() A\nA A", alias, 3, 0, NULL);
	/* Exercise hide-set word/bit boundaries, including the last identity. */
	for (size_t boundary = 63; boundary <= 1023; boundary += 64) {
		char text[20000];
		size_t used = 0;

		for (size_t i = 0; i < boundary; i++)
			used += (size_t)sprintf(text + used, "#define M%zu\n", i);
		used += (size_t)sprintf(text + used, "#define F() F()\nF()");
		assert(used < sizeof(text));
		check_stream(text, recursive, 4, 0, NULL);
	}
}

static void test_function_definition_errors(void)
{
	const struct expected_token invalid[] = {
		{ token_invalid, "#" }, { token_integer, "7" }, { token_eof, "" },
	};
	const char *inputs[] = {
		"#define F(x) x\n7", "#define F(...) 1\n7", "#define F(,) 1\n7",
		"#define F(1) 1\n7", "#define F(\n7", "#define F(\v) 1\n7",
		"#define F() # X\n7", "#define F() %: X\n7", "#define F() ## X\n7",
	};

	for (size_t i = 0; i < sizeof(inputs) / sizeof(inputs[0]); i++)
		check_stream(inputs[i], invalid, 3, 1, NULL);
}

static void test_function_invocation_errors(void)
{
	const struct expected_token invalid_name[] = {
		{ token_invalid, "F" }, { token_eof, "" },
	};
	const struct expected_token invalid_marker[] = {
		{ token_invalid, "#" }, { token_eof, "" },
	};
	const struct expected_token raw_invalid[] = {
		{ token_invalid, "\"bad" }, { token_eof, "" },
	};

	check_stream("#define F() 7\nF(", invalid_name, 2, 1, "unterminated");
	check_stream("#define F() 7\nF(1)", invalid_name, 2, 1, "requires no arguments");
	check_stream("#define F() 7\n#define E\nF(E)", invalid_name, 2, 1,
		"requires no arguments");
	check_stream("#define F() 7\nF(,)", invalid_name, 2, 1, "requires no arguments");
	check_stream("#define F() 7\nF\n#\n()", invalid_marker, 2, 1,
		"directives during macro invocation lookahead");
	check_stream("#define F() 7\nF(\n#undef F\n)", invalid_marker, 2, 1,
		"directives during macro invocation lookahead");
	check_stream("#define F() 7\nF \"bad", raw_invalid, 2, 1, "unterminated quoted");
}

static void test_function_macro_work_and_stream_depth(void)
{
	char text[20000];
	size_t used = (size_t)sprintf(text, "#define F0() 1\n");
	const struct expected_token number[] = { { token_integer, "1" }, { token_eof, "" } };

	for (size_t i = 1; i <= 16; i++)
		used += (size_t)sprintf(text + used, "#define F%zu() F%zu() F%zu()\n",
			i, i - 1, i - 1);
	used += (size_t)sprintf(text + used, "F16()\n");
	assert(used < sizeof(text));
	check_resource_failure(text, "macro expansion work limit exceeded", 1, preprocess_work_limit);
	used = 0;
	for (size_t i = 0; i < 200; i++)
		used += (size_t)sprintf(text + used, "#define F%zu() F%zu\n", i, i + 1);
	used += (size_t)sprintf(text + used, "#define F200() 1\nF0");
	for (size_t i = 0; i <= 200; i++)
		used += (size_t)sprintf(text + used, "()");
	assert(used < sizeof(text));
	/* Completed streams are popped: 201 successive calls are not 201 frames. */
	check_stream(text, number, 2, 0, NULL);
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
	test_object_expansion();
	test_macro_definition_rules();
	test_rescan_and_redefinition();
	test_macro_locations();
	test_macro_identity_reuse();
	test_macro_limits();
	test_empty_function_macros();
	test_function_macro_redefinition();
	test_function_macro_suppression();
	test_function_definition_errors();
	test_function_invocation_errors();
	test_function_macro_work_and_stream_depth();
	puts("Preprocessor directive and stream tests passed");
	return 0;
}
