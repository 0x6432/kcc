#include "preprocess.h"

#include <assert.h>
#include <stdarg.h>
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
	struct diagnostics diagnostics = { .stream = stream };
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
		size_t spelling_bytes = preprocessor.spelling_bytes;
		struct token second = preprocess_peek(&preprocessor);
		struct token next = preprocess_next(&preprocessor);

		assert_same_token(first, second);
		assert_same_token(first, next);
		assert(diagnostics.errors == errors);
		assert(preprocessor.spelling_bytes == spelling_bytes);
		if (next.kind != expected[i].kind || next.length != strlen(expected[i].spelling))
			fprintf(stderr, "stream mismatch at %zu: %s (wanted %s)\n", i, text, expected[i].spelling);
		assert(next.kind == expected[i].kind);
		assert(next.length == strlen(expected[i].spelling));
		assert(next.location.offset >= previous_offset);
		assert(memcmp(next.spelling_location.source->data + next.spelling_location.offset,
			expected[i].spelling, next.length) == 0);
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
		"embed", "line", "pragma",
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
		sizeof(expected) / sizeof(expected[0]), 1, "only direct nonempty quoted includes");
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
	struct diagnostics diagnostics = { .stream = stream };
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
		"#define X+1\nX", "#define X(x,x) 1\nX", "#define X ## 1\nX",
		"#define X 1 %:%: \nX", "#define X\v 1\nX", "#define X 1\f\nX",
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
	struct diagnostics diagnostics = { .stream = stream };
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
	struct diagnostics diagnostics = { .stream = stream };
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
	assert(!preprocessor.optional_depth && !preprocessor.prescan_depth && !preprocessor.paste_depth);
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
		"incompatible macro redefinition");
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
		"#define F(x,x) x\n7", "#define F(...,x) 1\n7", "#define F(,) 1\n7",
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

static void test_fixed_arguments(void)
{
	const struct expected_token number[] = { { token_integer, "7" }, { token_eof, "" } };
	const struct expected_token empty[] = { { token_eof, "" } };
	const struct expected_token sum[] = {
		{ token_integer, "2" }, { token_plus, "+" }, { token_integer, "3" }, { token_eof, "" },
	};
	const struct expected_token repeat[] = {
		{ token_integer, "7" }, { token_integer, "7" }, { token_eof, "" },
	};
	const struct expected_token marker[] = { { token_invalid, "#" }, { token_eof, "" } };

	check_stream("#define ID(x) x\nID(ID(7))", number, 2, 0, NULL);
	check_stream("#define ID(x) x\nID()", empty, 1, 0, NULL);
	check_stream("#define KEEP(a,b) a b\nKEEP(,) KEEP(,)", empty, 1, 0, NULL);
	check_stream("#define F(a,b) a+b\nF(2,3)", sum, 4, 0, NULL);
	check_stream("#define F(a) a a\nF(7)", repeat, 3, 0, NULL);
	check_stream("#define F(x) x\n#define G() 7\nF(G)()", number, 2, 0, NULL);
	check_stream("#define F(x) x\n#define G(x) x\nF(G)(7)", number, 2, 0, NULL);
	check_stream("#define DROP(x) 7\nDROP(BAD(1,2))", number, 2, 0, NULL);
	check_stream("#define BAD(a,b) a+b\n#define DROP(x) 7\nDROP(BAD(1))", number, 2, 0, NULL);
	check_stream("#define DROP(x) 7\n#define F(x) DROP(x)\nF(12u)", number, 2, 0, NULL);
	check_stream("#define DROP(x) 7\nDROP(#)", number, 2, 0, NULL);
	check_stream("#define DROP(a,b) 7\nDROP({1,2})", number, 2, 0, NULL);
	check_stream("#define F(int) int\nF(7)", number, 2, 0, NULL);
	check_stream("#define HASH #\n#define ID(x) x\nID(HASH)", marker, 2, 1,
		"directive marker cannot be converted");
}

static void test_fixed_argument_errors(void)
{
	const struct expected_token call_error[] = { { token_invalid, "F" }, { token_eof, "" } };
	const struct expected_token number[] = { { token_integer, "7" }, { token_eof, "" } };
	const struct expected_token definition_error[] = {
		{ token_invalid, "#" }, { token_integer, "7" }, { token_eof, "" },
	};
	const char *calls[] = {
		"#define F(x) x\nF(1,2)", "#define F(a,b) a\nF()",
		"#define F(x) x\nF((7)", "#define F(a,b,c) a\nF(1,2)",
	};
	const char *definitions[] = {
		"#define F(x,x) x\n7", "#define F(x,) x\n7", "#define F(x y) x\n7",
		"#define F(x...) 1\n7", "#define F(x,...,y) x\n7",
		"#define F(__VA_ARGS__) 1\n7", "#define F(__VA_OPT__) 1\n7",
		"#define F(x\v,y) x\n7",
	};

	for (size_t i = 0; i < sizeof(calls) / sizeof(calls[0]); i++)
		check_stream(calls[i], call_error, 2, 1, NULL);
	for (size_t i = 0; i < sizeof(definitions) / sizeof(definitions[0]); i++)
		check_stream(definitions[i], definition_error, 3, 1, NULL);
	check_stream("#define F(x) 7\n#define F(y) 7\nF(1)", definition_error, 3, 1,
		"incompatible macro redefinition");
	check_stream("#define F(x) 7\n#define F(x,x) 8\nF(1)", definition_error, 3, 1,
		"duplicate macro parameter");
	check_stream("#define F(x) 7\n#define F( x ) 7\nF(1)", number, 2, 0, NULL);
}

/* Generate limit inputs with checked capacity and checked formatting results. */
static void append_test_text(char *text, size_t capacity, size_t *used,
	const char *format, ...)
{
	va_list arguments;
	int written;

	assert(*used < capacity);
	va_start(arguments, format);
	written = vsnprintf(text + *used, capacity - *used, format, arguments);
	va_end(arguments);
	assert(written >= 0 && (size_t)written < capacity - *used);
	*used += (size_t)written;
}

static void test_variadic_arguments(void)
{
	const struct expected_token empty[] = { { token_eof, "" } };
	const struct expected_token seven[] = { { token_integer, "7" }, { token_eof, "" } };
	const struct expected_token sum[] = {
		{ token_integer, "3" }, { token_plus, "+" }, { token_integer, "4" }, { token_eof, "" },
	};
	const struct expected_token comma[] = { { token_comma, "," }, { token_eof, "" } };
	const struct expected_token call[] = {
		{ token_identifier, "F" }, { token_left_paren, "(" }, { token_integer, "7" },
		{ token_right_paren, ")" }, { token_eof, "" },
	};

	check_stream("#define F(...) __VA_ARGS__\nF() F(/**/)", empty, 1, 0, NULL);
	check_stream("#define F(...) __VA_ARGS__\nF(,)", comma, 2, 0, NULL);
	check_stream("#define F(x,...) x\nF(7)", seven, 2, 0, NULL);
	check_stream("#define F(x,...) x\nF(7,)", seven, 2, 0, NULL);
	check_stream("#define F(x,y,...) 7\nF(,)", seven, 2, 0, NULL);
	check_stream("#define F(...) 7\n#define BAD(x,y) x\nF(BAD(1))", seven, 2, 0, NULL);
	check_stream("#define F(...) 7\nF(12u,@,#)", seven, 2, 0, NULL);
	check_stream("#define F(...) __VA_OPT__(7)\nF(,)", seven, 2, 0, NULL);
	check_stream("#define F(...) __VA_OPT__(7)\n#define E\nF() F(E)", empty, 1, 0, NULL);
	check_stream("#define F(...) __VA_OPT__(__VA_ARGS__)\nF(7)", seven, 2, 0, NULL);
	check_stream("#define F(...) __VA_OPT__() __VA_OPT__()\nF(7) F()", empty, 1, 0, NULL);
	check_stream("#define F(x,...) x __VA_OPT__(+ __VA_ARGS__)\nF(3,4)", sum, 4, 0, NULL);
	check_stream("#define LP() (\n#define G(x) 7\n"
		"#define F(r,x,...) __VA_OPT__(G r x) )\nF(LP(),0,1)", seven, 2, 0, NULL);
	check_stream("#define F(...) __VA_OPT__(G)\n#define G(x) x\nF(1)(7)", seven, 2, 0, NULL);
	check_stream("#define F(...) __VA_OPT__(G()\n7", (const struct expected_token[]) {
		{ token_invalid, "#" }, { token_integer, "7" }, { token_eof, "" },
	}, 3, 1, "unterminated __VA_OPT__");
	check_stream("#define F(...) F(__VA_ARGS__)\nF(7)", call, 5, 0, NULL);
	check_stream("#define F(...) __VA_ARGS__\n#define G(...) F(__VA_ARGS__)\nG(F(7))",
		seven, 2, 0, NULL);
	check_stream("#define F(...) 7\n#define F( ... ) 7\nF()", seven, 2, 0, NULL);
	check_stream("#define F(x,...) 7\n#define F(x,...) 7\nF()", seven, 2, 0, NULL);
	check_stream("#define F(...) __VA_OPT__(7)\n#undef F\n#define F() 7\nF()",
		seven, 2, 0, NULL);
}

static void test_variadic_errors(void)
{
	const struct expected_token definition_error[] = {
		{ token_invalid, "#" }, { token_integer, "7" }, { token_eof, "" },
	};
	const struct expected_token call_error[] = { { token_invalid, "F" }, { token_eof, "" } };
	const char *definitions[] = {
		"#define F(...,x) 1\n7", "#define F(...,...) 1\n7",
		"#define F(x...) 1\n7", "#define F(x,...,) 1\n7",
		"#define F(x) __VA_ARGS__\n7", "#define F __VA_ARGS__\n7",
		"#define F(x) __VA_OPT__(1)\n7", "#define F __VA_OPT__(1)\n7",
		"#define F(...) __VA_OPT__\n7", "#define F(...) __VA_OPT__ 1\n7",
		"#define F(...) __VA_OPT__((1)\n7",
		"#define F(...) __VA_OPT__(__VA_OPT__(1))\n7",
		"#define F(...) __VA_OPT__(# x)\n7",
		"#define F(...) __VA_OPT__(x ##)\n7",
	};

	for (size_t i = 0; i < sizeof(definitions) / sizeof(definitions[0]); i++)
		check_stream(definitions[i], definition_error, 3, 1, NULL);
	check_stream("#define F(x,y,...) x\nF()", call_error, 2, 1, "argument count");
	check_stream("#define F(...) __VA_ARGS__\nF(", call_error, 2, 1, "unterminated");
	check_stream("#define F() 7\n#define F(...) 7\nF()", definition_error, 3, 1,
		"incompatible macro redefinition");
	check_stream("#define F(x,...) 7\n#define F(x) 7\nF(1)", definition_error, 3, 1,
		"incompatible macro redefinition");
	check_stream("#define F(...) 7\n#define F(...) __VA_OPT__(\nF()", definition_error, 3, 1,
		"unterminated __VA_OPT__");
	check_stream("#define F(...) __VA_OPT__(7)\n#define BAD(x,y) x\nF(BAD(1))",
		(const struct expected_token[]) {
			{ token_invalid, "BAD" }, { token_eof, "" },
		}, 2, 1, "argument count");
	check_stream("#define F(x,...) x\n#define F(x,...) x __VA_OPT__(+)\nF(7)",
		definition_error, 3, 1, "incompatible macro redefinition");
	check_stream("#define F(...) 7\nF(__VA_ARGS__)", (const struct expected_token[]) {
		{ token_invalid, "__VA_ARGS__" }, { token_eof, "" },
	}, 2, 1, "variadic identifiers require");
	check_stream("__VA_OPT__", (const struct expected_token[]) {
		{ token_invalid, "__VA_OPT__" }, { token_eof, "" },
	}, 2, 1, "variadic identifiers require");
}

static void test_variadic_limits(void)
{
	const size_t capacity = 200000;
	char *text = malloc(capacity);
	size_t used = 0;
	const struct expected_token one[] = { { token_integer, "1" }, { token_eof, "" } };

	assert(text);
	/* The variadic slot does not reduce the named-parameter allowance. */
	append_test_text(text, capacity, &used, "#define F(");
	for (size_t i = 0; i < preprocess_parameter_limit; i++)
		append_test_text(text, capacity, &used, "%sp%zu", i ? "," : "", i);
	append_test_text(text, capacity, &used, ",...) __VA_ARGS__\nF(");
	for (size_t i = 0; i < preprocess_parameter_limit; i++)
		append_test_text(text, capacity, &used, "%s0", i ? "," : "");
	append_test_text(text, capacity, &used, ",1)\n");
	check_stream(text, one, 2, 0, NULL);
	for (size_t extra = 0; extra < 2; extra++) {
		used = 0;
		append_test_text(text, capacity, &used,
			"#define V(...) __VA_OPT__(__VA_ARGS__)\n");
		for (size_t i = 0; i < preprocess_prescan_limit + extra; i++)
			append_test_text(text, capacity, &used, "V(");
		append_test_text(text, capacity, &used, "1");
		for (size_t i = 0; i < preprocess_prescan_limit + extra; i++)
			append_test_text(text, capacity, &used, ")");
		if (extra)
			check_resource_failure(text, "macro argument prescan depth limit exceeded", 0, 0);
		else
			check_stream(text, one, 2, 0, NULL);
	}
	/* Delimiters and inactive content all consume definition-token storage. */
	for (size_t extra = 0; extra < 2; extra++) {
		used = 0;
		append_test_text(text, capacity, &used, "#define V(...) __VA_OPT__(");
		for (size_t i = 0; i < preprocess_replacement_limit - 3 + extra; i++)
			append_test_text(text, capacity, &used, "1 ");
		append_test_text(text, capacity, &used, ")\nV() 1\n");
		if (extra)
			check_resource_failure(text, "macro replacement storage limit exceeded", 0, 0);
		else
			check_stream(text, one, 2, 0, NULL);
	}
	used = 0;
	append_test_text(text, capacity, &used, "#define DROP(...) 1\nDROP(");
	for (size_t i = 0; i < preprocess_auxiliary_limit; i++)
		append_test_text(text, capacity, &used, ",");
	append_test_text(text, capacity, &used, ")");
	/* Collection/copy work reaches its cap before this raw stream fills storage. */
	check_resource_failure(text, "macro expansion work limit exceeded", 0, 0);
	free(text);
}

static void test_fixed_argument_limits(void)
{
	const size_t capacity = 400000;
	char *text = malloc(capacity);
	size_t used;
	const struct expected_token last[] = { { token_integer, "127" }, { token_eof, "" } };
	const struct expected_token one[] = { { token_integer, "1" }, { token_eof, "" } };
	const struct expected_token seven[] = { { token_integer, "7" }, { token_eof, "" } };

	assert(text);
	used = 0;
	append_test_text(text, capacity, &used, "#define F(");
	for (size_t i = 0; i <= preprocess_parameter_limit; i++)
		append_test_text(text, capacity, &used, "%sp%zu", i ? "," : "", i);
	append_test_text(text, capacity, &used, ") 1\n");
	check_resource_failure(text, "macro parameter limit exceeded", 0, 0);
	used = 0;
	append_test_text(text, capacity, &used, "#define F(");
	for (size_t i = 0; i < preprocess_parameter_limit; i++)
		append_test_text(text, capacity, &used, "%sp%zu", i ? "," : "", i);
	append_test_text(text, capacity, &used, ") p127\nF(");
	for (size_t i = 0; i < preprocess_parameter_limit; i++)
		append_test_text(text, capacity, &used, "%s%zu", i ? "," : "", i);
	append_test_text(text, capacity, &used, ")\n");
	check_stream(text, last, 2, 0, NULL);
	used = 0;
	for (size_t i = 0; i <= preprocess_auxiliary_limit / preprocess_parameter_limit; i++) {
		append_test_text(text, capacity, &used, "#define F(");
		for (size_t j = 0; j < preprocess_parameter_limit; j++)
			append_test_text(text, capacity, &used, "%sp%zu", j ? "," : "", j);
		append_test_text(text, capacity, &used, ") 1\n");
	}
	assert(used < capacity);
	check_resource_failure(text, "macro auxiliary storage limit exceeded", 0, 0);
	used = 0;
	append_test_text(text, capacity, &used, "#define ID(x) x\n");
	for (size_t i = 0; i < preprocess_prescan_limit; i++)
		append_test_text(text, capacity, &used, "ID(");
	append_test_text(text, capacity, &used, "1");
	for (size_t i = 0; i < preprocess_prescan_limit; i++)
		append_test_text(text, capacity, &used, ")");
	check_stream(text, one, 2, 0, NULL);
	/* Add one more outer invocation without changing the nested arguments. */
	used = 0;
	append_test_text(text, capacity, &used, "#define ID(x) x\n");
	for (size_t i = 0; i <= preprocess_prescan_limit; i++)
		append_test_text(text, capacity, &used, "ID(");
	append_test_text(text, capacity, &used, "1");
	for (size_t i = 0; i <= preprocess_prescan_limit; i++)
		append_test_text(text, capacity, &used, ")");
	check_resource_failure(text, "macro argument prescan depth limit exceeded", 0, 0);
	for (size_t extra = 0; extra < 2; extra++) {
		used = 0;
		append_test_text(text, capacity, &used, "#define DROP(x) 7\nDROP(");
		for (size_t i = 0; i < preprocess_parentheses_limit + extra; i++)
			append_test_text(text, capacity, &used, "(");
		append_test_text(text, capacity, &used, "1");
		for (size_t i = 0; i < preprocess_parentheses_limit + extra; i++)
			append_test_text(text, capacity, &used, ")");
		append_test_text(text, capacity, &used, ")");
		if (extra)
			check_resource_failure(text, "macro argument parentheses limit exceeded", 0, 0);
		else
			check_stream(text, seven, 2, 0, NULL);
	}
	free(text);
}

/* Expanded-pp tests do not imply support for C string expressions. */
static void check_stringizing(const char *text, const char *const *expected, size_t count)
{
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct pp_token first = { 0 };

	assert(stream);
	assert(source_from_bytes(&source, "stringizing.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	for (size_t i = 0; i < count; i++) {
		struct pp_token token = preprocess_next_pp(&preprocessor);
		struct pp_lexer lexer;
		struct pp_token raw;

		assert(token.kind == pp_string && token.length == strlen(expected[i]));
		assert(!preprocessor.optional_depth && !preprocessor.prescan_depth && !preprocessor.paste_depth);
		assert(token.location.source != &source && token.location.offset == 0);
		assert(token.location.source->prepared);
		assert(token.length == token.location.source->length);
		assert(token.expansion_location.source == &source);
		assert(token.expansion_location.offset < source.length && !token.at_line_start);
		assert(memcmp(token.location.source->data, expected[i], token.length) == 0);
		assert(token.location.source->data[token.length] == 0);
		/* Every generated spelling re-lexes as exactly one string token. */
		pp_lexer_init(&lexer, token.location.source, &diagnostics);
		raw = pp_lexer_next(&lexer);
		assert(raw.kind == pp_string && raw.length == token.length);
		assert(pp_lexer_next(&lexer).kind == pp_eof);
		if (!i)
			first = token;
	}
	assert(preprocess_next_pp(&preprocessor).kind == pp_eof);
	assert(preprocess_next_pp(&preprocessor).kind == pp_eof);
	assert(!diagnostics.errors);
	if (count)
		assert(memcmp(first.location.source->data, expected[0], first.length) == 0);
	assert(preprocessor.spelling_bytes <= preprocess_spelling_limit);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_stringizing(void)
{
	const char *const raw[] = { "\"A\"", "\"a + b\"", "\"\"", "\"ab\"" };
	const char *const nested[] = { "\"7\"", "\"\\\"a\\\"\"" };
	const char *const variadic[] = { "\"\"", "\",\"", "\"a, b\"" };
	const char *const discarded[] = { "\"BAD(1)\"", "\"12u\"", "\"@\"" };
	const char *const optional[] = { "\"7\"", "\"a,b\"" };
	const char *const spacing[] = { "\"a+ b\"", "\"a+ b\"", "\"a+b\"", "\"a +b\"" };

	check_stringizing("#define A 7\n#define S(x) #x\nS(A) S( a\t+\n b ) S() S(a\\\nb)",
		raw, 4);
	check_stringizing("#define A 7\n#define S(x) #x\n#define X(x) S(x)\nX(A) X(S(a))",
		nested, 2);
	check_stringizing("#define S(...) %: __VA_ARGS__\nS() S(,) S(a, b)", variadic, 3);
	check_stringizing("#define BAD(x,y) x\n#define S(x) #x\nS(BAD(1)) S(12u) S(@)",
		discarded, 3);
	check_stringizing("#define S(x,...) __VA_OPT__(#x)\nS(7) S(7,1)\n"
		"#define V(...) __VA_OPT__(#__VA_ARGS__)\n#define E\nV(E) V(a,b)", optional, 2);
	check_stringizing("#define S(x) #x\n#define X(x) S(x)\n"
		"#define V(...) a+__VA_OPT__() b\nX(V(1)) X(V())\n"
		"#define F(x) a+x\nX(F( b))\n#undef F\n#define F(x) a x+b\nX(F())", spacing, 4);
}

static void test_stringizing_errors(void)
{
	const struct expected_token definition[] = {
		{ token_invalid, "#" }, { token_integer, "7" }, { token_eof, "" },
	};
	const struct expected_token literal[] = {
		{ token_invalid, "\"a\"" }, { token_eof, "" },
	};

	check_stream("#define S(x) #\n7", definition, 3, 1, "expected a macro parameter");
	check_stream("#define S(x) %: 1\n7", definition, 3, 1, "expected a macro parameter");
	check_stream("#define S(x) #x\n#define S(x) #1\n#define DROP(x) 7\nDROP(S(a))",
		definition, 3, 1, "expected a macro parameter");
	check_stream("#define S(...) #__VA_OPT__(#1)\n7", definition, 3, 1,
		"expected a macro parameter");
	check_stream("#define S(x) #x\nS(a)", literal, 2, 1, "string literals are not supported yet");
	check_stream("#define S(x) #x\nS(\\)", (const struct expected_token[]) {
		{ token_invalid, "#" }, { token_eof, "" },
	}, 2, 1, "backslash outside a literal");
}

/* The cumulative byte cap counts quotes and terminating NUL for each view. */
static void test_stringizing_limits(void)
{
	const char *prefix = "#define S(x) #x\nS(";
	size_t prefix_length = strlen(prefix);
	char *text = malloc(preprocess_spelling_limit + prefix_length + 4);

	assert(text);
	for (size_t extra = 0; extra < 2; extra++) {
		struct source source;
		FILE *stream = tmpfile();
		struct diagnostics diagnostics = { .stream = stream };
		struct preprocessor preprocessor;
		struct pp_token token;
		size_t argument_length = preprocess_spelling_limit - 3 + extra;

		assert(stream);
		memcpy(text, prefix, prefix_length);
		memset(text + prefix_length, 'a', argument_length);
		memcpy(text + prefix_length + argument_length, ")", 2);
		assert(source_from_bytes(&source, "stringizing-limit.c",
			(const unsigned char *)text, strlen(text)));
		assert(source_prepare(&source));
		preprocess_init(&preprocessor, &source, &diagnostics);
		token = preprocess_next_pp(&preprocessor);
		if (extra) {
			assert(token.kind == pp_invalid && preprocessor.stopped);
			assert(diagnostics.errors == 1 && !preprocessor.spelling_bytes);
		} else {
			assert(token.kind == pp_string && !diagnostics.errors);
			assert(token.length == preprocess_spelling_limit - 1);
			assert(preprocessor.spelling_bytes == preprocess_spelling_limit);
		}
		assert(preprocess_next_pp(&preprocessor).kind == pp_eof);
		assert(preprocess_next_pp(&preprocessor).kind == pp_eof);
		preprocess_destroy(&preprocessor);
		source_destroy(&source);
		assert(fclose(stream) == 0);
	}
	free(text);
}

static void test_stringizing_cumulative_limit(void)
{
	const char *prefix = "#define S(x) #x #x\nS(";
	size_t prefix_length = strlen(prefix);
	size_t half_budget = preprocess_spelling_limit / 2;
	char *text = malloc(prefix_length + half_budget + 4);

	assert(text);
	for (size_t extra = 0; extra < 2; extra++) {
		struct source source;
		FILE *stream = tmpfile();
		struct diagnostics diagnostics = { .stream = stream };
		struct preprocessor preprocessor;
		struct pp_token first;
		struct pp_token second;
		size_t argument_length = half_budget - 3 + extra;

		assert(stream);
		memcpy(text, prefix, prefix_length);
		memset(text + prefix_length, 'a', argument_length);
		memcpy(text + prefix_length + argument_length, ")", 2);
		assert(source_from_bytes(&source, "cumulative-stringizing.c",
			(const unsigned char *)text, strlen(text)));
		assert(source_prepare(&source));
		preprocess_init(&preprocessor, &source, &diagnostics);
		first = preprocess_next_pp(&preprocessor);
		assert(first.kind == pp_string && first.length == argument_length + 2);
		second = preprocess_next_pp(&preprocessor);
		if (extra) {
			assert(second.kind == pp_invalid && preprocessor.stopped);
			assert(diagnostics.errors == 1);
			assert(preprocessor.spelling_bytes == half_budget + extra);
		} else {
			assert(second.kind == pp_string && !diagnostics.errors);
			assert(preprocessor.spelling_bytes == preprocess_spelling_limit);
			assert(first.location.source != second.location.source);
		}
		assert(first.location.source->data[0] == '\"');
		assert(first.location.source->data[first.length] == 0);
		assert(preprocess_next_pp(&preprocessor).kind == pp_eof);
		assert(preprocess_next_pp(&preprocessor).kind == pp_eof);
		preprocess_destroy(&preprocessor);
		source_destroy(&source);
		assert(fclose(stream) == 0);
	}
	free(text);
}

static void test_optional_stringizing(void)
{
	const char *const presence[] = { "\"\"", "\"\"", "\"a\"", "\"a\"" };
	const char *const substituted[] = { "\"7 BAD(7) A\"", "\"\"" };
	const char *const inner[] = { "\"\\\"A\\\"\"", "\"a,b\"" };
	const char *const empty[] = { "\"\"" };

	check_stringizing("#define V(...) #__VA_OPT__(a)\n#define E\nV() V(E) V(1) V(,)",
		presence, 4);
	check_stringizing("#define A 7\n#define BAD(a,b) a+b\n"
		"#define V(x,...) #__VA_OPT__(x BAD(x) A)\nV(A,1) V(A)", substituted, 2);
	check_stringizing("#define A 7\n#define V(x,...) %: __VA_OPT__(#x)\nV(A,1)\n"
		"#define W(...) #__VA_OPT__(__VA_ARGS__)\nW(a,b)", inner, 2);
	/* Intentional lazy policy: GCC diagnoses this inactive argument, Clang does not. */
	check_stringizing("#define BAD(a,b) a+b\n#define E\n"
		"#define V(x,...) #__VA_OPT__(x)\nV(BAD(1),E)", empty, 1);
	check_stream("#define BAD(a,b) a+b\n#define V(x,...) #__VA_OPT__(x)\nV(1,BAD(1))",
		(const struct expected_token[]) {
			{ token_invalid, "BAD" }, { token_eof, "" },
		}, 2, 1, "macro argument count");
	check_stream("#define BAD(a,b) a+b\n#define V(x,...) #__VA_OPT__(x)\nV(BAD(1),1)",
		(const struct expected_token[]) {
			{ token_invalid, "BAD" }, { token_eof, "" },
		}, 2, 1, "macro argument count");
}

static void test_optional_stringizing_recovery(void)
{
	const char *text = "#define V(...) #__VA_OPT__(7)\n"
		"#define V(...) #__VA_OPT__(#1)\nV(1)";
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct pp_token token;

	assert(stream);
	assert(source_from_bytes(&source, "optional-recovery.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	token = preprocess_next_pp(&preprocessor);
	assert(token.kind == pp_invalid && diagnostics.errors == 1 && !preprocessor.stopped);
	token = preprocess_next_pp(&preprocessor);
	assert(token.kind == pp_string && token.length == 3);
	assert(memcmp(token.location.source->data, "\"7\"", 3) == 0);
	assert(!preprocessor.optional_depth && !preprocessor.prescan_depth && !preprocessor.paste_depth);
	assert(preprocess_next_pp(&preprocessor).kind == pp_eof);
	assert(preprocess_next_pp(&preprocessor).kind == pp_eof && diagnostics.errors == 1);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_optional_stringizing_limits(void)
{
	const size_t capacity = preprocess_spelling_limit + 1024;
	char *text = malloc(capacity);
	size_t used;
	const char *const seven[] = { "\"7\"" };

	assert(text);
	for (size_t extra = 0; extra < 2; extra++) {
		used = 0;
		append_test_text(text, capacity, &used, "#define DROP(x) 7\n"
			"#define PASS(x) DROP(x)\n#define V(x,...) #__VA_OPT__(x)\n");
		/* PASS must prescan the nested call before DROP discards its string.
		 * This keeps spellings small while optional helper cursors nest.
		 */
		for (size_t i = 0; i < preprocess_optional_limit + extra; i++)
			append_test_text(text, capacity, &used, "V(PASS(");
		append_test_text(text, capacity, &used, "7");
		for (size_t i = 0; i < preprocess_optional_limit + extra; i++)
			append_test_text(text, capacity, &used, "),1)");
		if (extra)
			check_resource_failure(text, "macro optional substitution depth limit exceeded", 0, 0);
		else
			check_stringizing(text, seven, 1);
	}
	used = 0;
	append_test_text(text, capacity, &used, "#define V(x,...) #__VA_OPT__(x)\nV(");
	memset(text + used, 'a', preprocess_spelling_limit);
	used += preprocess_spelling_limit;
	append_test_text(text, capacity, &used, ",1)");
	check_resource_failure(text, "macro synthesized spelling limit exceeded", 0, 0);
	free(text);
}

static void test_token_pasting(void)
{
	const struct expected_token tokens[] = {
		{ token_int, "int" }, { token_integer, "42" }, { token_identifier, "ab" },
		{ token_identifier, "a" }, { token_identifier, "bc" }, { token_identifier, "d" },
		{ token_eof, "" },
	};
	const struct expected_token empty[] = { { token_eof, "" } };
	const struct expected_token standard[] = {
		{ token_identifier, "a" }, { token_identifier, "b" }, { token_eof, "" },
	};
	const char *const quoted[] = { "\"\"", "\"aa aa\"" };

	check_stream("#define C(a,b) a##b\nC(in,t) C(4,2) C(a,b) C(a b,c d)", tokens, 7, 0, NULL);
	check_stream("#define C(a,b,c) a##b##c\nC(,,)", empty, 1, 0, NULL);
	check_stream("#define F(x,...) __VA_OPT__(a x##x) ## b\nF(,1)", standard, 3, 0, NULL);
	check_stringizing("#define F(x,...) #__VA_OPT__(x##x x##x)\nF(,1) F(a,1)", quoted, 2);
	check_stream("#define C(a,b) a##b\nC(/,*)", (const struct expected_token[]) {
		{ token_invalid, "##" }, { token_eof, "" },
	}, 2, 1, "exactly one preprocessing token");
	check_stream("#define C(a,b) a##b\nC(+,*)", (const struct expected_token[]) {
		{ token_invalid, "##" }, { token_eof, "" },
	}, 2, 1, "exactly one preprocessing token");
	check_stream("#define C(a,b) a##b\nC(x,+)", (const struct expected_token[]) {
		{ token_invalid, "##" }, { token_eof, "" },
	}, 2, 1, "exactly one preprocessing token");
	check_stream("#define C(a,b) a##b\nC(1,u)", (const struct expected_token[]) {
		{ token_invalid, "1u" }, { token_eof, "" },
	}, 2, 1, "unsupported numeric");
	check_stream("#define C(a,b) a##b\n#define C(a,b) ##a\nC(4,2)",
		(const struct expected_token[]) {
			{ token_invalid, "#" }, { token_integer, "42" }, { token_eof, "" },
		}, 3, 1, "operand on both sides");
	check_stream("#define F(...) __VA_OPT__(##x)\n7", (const struct expected_token[]) {
		{ token_invalid, "#" }, { token_integer, "7" }, { token_eof, "" },
	}, 3, 1, "operand on both sides");
}

static void test_pasting_limits(void)
{
	const size_t capacity = preprocess_spelling_limit + 1024;
	char *text = malloc(capacity);
	size_t used;

	assert(text);
	for (size_t extra = 0; extra < 2; extra++) {
		struct source source;
		FILE *stream = tmpfile();
		struct diagnostics diagnostics = { .stream = stream };
		struct preprocessor preprocessor;
		struct pp_token token;

		assert(stream);
		used = 0;
		append_test_text(text, capacity, &used, "#define C(a,b) a##b\nC(");
		memset(text + used, 'a', preprocess_spelling_limit - 2 + extra);
		used += preprocess_spelling_limit - 2 + extra;
		append_test_text(text, capacity, &used, ",b)");
		assert(source_from_bytes(&source, "pasting-limit.c", (const unsigned char *)text, used));
		assert(source_prepare(&source));
		preprocess_init(&preprocessor, &source, &diagnostics);
		token = preprocess_next_pp(&preprocessor);
		if (extra) {
			assert(token.kind == pp_invalid && preprocessor.stopped && diagnostics.errors == 1);
		} else {
			assert(token.kind == pp_identifier && !diagnostics.errors);
			assert(token.length == preprocess_spelling_limit - 1);
			assert(preprocessor.spelling_bytes == preprocess_spelling_limit);
		}
		assert(!preprocessor.paste_depth && !preprocessor.prescan_depth && !preprocessor.optional_depth);
		assert(preprocess_next_pp(&preprocessor).kind == pp_eof);
		assert(preprocess_next_pp(&preprocessor).kind == pp_eof);
		preprocess_destroy(&preprocessor);
		source_destroy(&source);
		assert(fclose(stream) == 0);
	}
	for (size_t extra = 0; extra < 2; extra++) {
		used = 0;
		append_test_text(text, capacity, &used, "#define V(x) x+a##b\n");
		for (size_t i = 0; i < preprocess_paste_limit + extra; i++)
			append_test_text(text, capacity, &used, "V(");
		append_test_text(text, capacity, &used, "7");
		for (size_t i = 0; i < preprocess_paste_limit + extra; i++)
			append_test_text(text, capacity, &used, ")");
		if (extra)
			check_resource_failure(text, "macro paste substitution depth limit exceeded", 0, 0);
		else {
			struct source source;
			struct diagnostics diagnostics = { 0 };
			struct preprocessor preprocessor;
			size_t count = 0;

			assert(source_from_bytes(&source, "paste-depth.c", (const unsigned char *)text, used));
			assert(source_prepare(&source));
			preprocess_init(&preprocessor, &source, &diagnostics);
			while (preprocess_next_pp(&preprocessor).kind != pp_eof)
				assert(++count <= 1 + 2 * preprocess_paste_limit);
			assert(count == 1 + 2 * preprocess_paste_limit && !diagnostics.errors);
			assert(!preprocessor.paste_depth && !preprocessor.prescan_depth);
			preprocess_destroy(&preprocessor);
			source_destroy(&source);
		}
	}
	free(text);
}

static void test_diagnostic_directives(void)
{
	const struct expected_token errors[] = {
		{ token_invalid, "#" }, { token_int, "int" }, { token_eof, "" },
	};
	const struct expected_token warning[] = {
		{ token_int, "int" }, { token_eof, "" },
	};
	const struct expected_token digraph[] = {
		{ token_invalid, "%:" }, { token_int, "int" }, { token_eof, "" },
	};
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	const char *text = "#define X 42\n#warning X+12u /**/ .5\nint";
	char message[256];

	check_stream("#error\nint", errors, 3, 1, "error: #error:");
	check_stream("#error a+b /**/ c\nint", errors, 3, 1, "#error: a+b c");
	check_stream("#error \"text\" 12u\nint", errors, 3, 1, "#error: \"text\" 12u");
	check_stream("%:error no\nint", digraph, 3, 1, "#error: no");
	check_stream("#warning\nint", warning, 2, 0, "warning: #warning:");
	check_stream("#war\\\nning hello\nint", warning, 2, 0,
		"directives.c:1:2: warning: #warning: hello");
	check_stream("#warning a\v b\nint", errors, 3, 1, "only space and tab");
	check_stream("#warning \"unterminated\nint", errors, 3, 1, "unterminated");
	{
		const struct expected_token eof_error[] = {
			{ token_invalid, "#" }, { token_eof, "" },
		};

		check_stream("#error", eof_error, 2, 1, "#error:");
	}
	assert(stream);
	assert(source_from_bytes(&source, "message.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	assert(preprocess_peek(&preprocessor).kind == token_int);
	assert(diagnostics.warnings == 1 && !diagnostics.errors);
	assert(preprocess_peek(&preprocessor).kind == token_int);
	assert(preprocess_next(&preprocessor).kind == token_int);
	assert(preprocess_next(&preprocessor).kind == token_eof);
	assert(preprocess_next(&preprocessor).kind == token_eof);
	assert(diagnostics.warnings == 1 && !diagnostics.errors);
	assert(!preprocessor.spelling_bytes);
	rewind(stream);
	assert(fgets(message, sizeof(message), stream));
	assert(strcmp(message, "message.c:2:2: warning: #warning: X+12u .5\n") == 0);
	assert(!fgets(message, sizeof(message), stream));
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_macro_conditions(void)
{
	const struct expected_token integer[] = {
		{ token_integer, "42" }, { token_eof, "" },
	};
	const struct expected_token keyword[] = {
		{ token_int, "int" }, { token_eof, "" },
	};
	const struct expected_token rejected[] = {
		{ token_invalid, "#" }, { token_int, "int" }, { token_eof, "" },
	};
	const struct expected_token empty[] = { { token_eof, "" } };
	char *text = malloc(8192);
	size_t used = 0;

	check_stream("#define X 0\n#ifdef X\n42\n#else\n#error bad\n#endif\n",
		integer, 2, 0, NULL);
	check_stream("#define X Y\n#ifdef Y\n#error expanded\n#elifdef X\n42\n"
		"#elifndef X\n#error taken\n#else\n#error bad\n#endif\n", integer, 2, 0, NULL);
	check_stream("#ifndef X\n#define X 42\n#endif\n#ifdef X\nX\n#endif\n#undef X\n"
		"#ifdef X\n#error stale\n#endif\n", integer, 2, 0, NULL);
	check_stream("%:ifdef X\n#define X 7\n#unknown whatever\n#include <none>\n"
		"#warning hidden\n12u __VA_ARGS__ # not_a_directive\n#if bad(\n"
		"#ifdef missing more tokens\n#endif\n#else\n#endif\n"
		"%:else\nint\n%:endif\n", keyword, 2, 0, NULL);
	check_stream("#define X\n#ifdef X\nint\n#elif no(expression)\n#error hidden\n#endif\n",
		keyword, 2, 0, NULL);
	check_stream("#ifdef X\n#error hidden\n#endif\n", empty, 1, 0, NULL);
	check_stream("#else\nint", rejected, 3, 1, "no matching opener");
	check_stream("#elifdef X\nint", rejected, 3, 1, "no matching opener");
	check_stream("#endif\nint", rejected, 3, 1, "no matching opener");
	check_stream("#ifdef X Y\nint", rejected, 3, 1, "expected end of line");
	check_stream("#ifdef\nint", rejected, 3, 1, "expected exactly one identifier");
	check_stream("#ifdef 12u\nint", rejected, 3, 1, "expected exactly one identifier");
	check_stream("#ifndef X\n#else\n#else\n#endif\nint", rejected, 3, 1,
		"alternative follows #else");
	check_stream("#ifndef X\n#else\n#elifdef X\n#endif\nint", rejected, 3, 1,
		"alternative follows #else");
	check_stream("#ifndef X\n#endif junk\n#endif\nint", rejected, 3, 1,
		"expected end of line");
	check_stream("#ifdef X\n", empty, 1, 1, "directives.c:1:1: error: unterminated");
	check_stream("#ifndef X\nint", keyword, 2, 1, "unterminated conditional");
	check_stream("#if 1uu\nint", rejected, 3, 1, "unsupported conditional integer suffix");
	assert(text);
	for (size_t i = 0; i < preprocess_conditional_limit; i++)
		used += (size_t)sprintf(text + used, "#ifndef missing\n");
	used += (size_t)sprintf(text + used, "int\n");
	for (size_t i = 0; i < preprocess_conditional_limit; i++)
		used += (size_t)sprintf(text + used, "#endif\n");
	check_stream(text, keyword, 2, 0, NULL);
	used = 0;
	for (size_t i = 0; i <= preprocess_conditional_limit; i++)
		used += (size_t)sprintf(text + used, "#ifndef missing\n");
	{
		const struct expected_token limit[] = {
			{ token_invalid, "#" }, { token_eof, "" },
		};

		check_stream(text, limit, 2, 1, "conditional nesting limit (128)");
	}
	free(text);
}

static void test_expression_conditions(void)
{
	const struct expected_token integer[] = {
		{ token_integer, "42" }, { token_eof, "" },
	};
	const struct expected_token rejected[] = {
		{ token_invalid, "#" }, { token_int, "int" }, { token_eof, "" },
	};
	const char *bad[] = {
		"", "defined", "defined()", "defined(7)", "defined(X", "defined(X,Y)",
		"1 +", "(1", "1 2", "1/0", "1%0", "9223372036854775808",
		"9223372036854775807+1", "(-9223372036854775807-1)-1",
		"-(-9223372036854775807-1)", "(-9223372036854775807-1)/-1",
		"(-9223372036854775807-1)%-1", "9223372036854775807*2",
		"0 && (1+)", "1 || (1+)", "__VA_ARGS__", "defined(__VA_OPT__)", "1uu", "0x", "08", "'ab'", "1 ? 2", "1 ? : 2", "1 ? 2 :",
	};
	char text[8192];
	size_t used;

	check_stream("#define X missing\n#if defined(X) && !defined missing && X==0\n42\n"
		"#else\n#error bad\n#endif\n", integer, 2, 0, NULL);
	check_stream("#define C(a,b) a##b\n#define F(x) x+2\n"
		"#if F(C(4,0)) == 42 && (1 || 1/0)\n42\n#endif\n", integer, 2, 0, NULL);
	check_stream("#if 0 && 1/0\n#error bad\n#elif 1 || (9223372036854775807*2)\n42\n"
		"#elif bad(\n#error bad\n#endif\n", integer, 2, 0, NULL);
	check_stream("#if true && !false\n42\n#endif\n", integer, 2, 0, NULL);
	for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++) {
		assert(snprintf(text, sizeof(text), "#if %s\nint", bad[i]) > 0);
		check_stream(text, rejected, 3, 1, NULL);
	}
	check_stream("#define D defined\n#if D(X)\nint", rejected, 3, 1,
		"defined produced by macro expansion");
	used = (size_t)sprintf(text, "#if ");
	for (size_t i = 1; i < preprocess_condition_depth_limit; i++)
		text[used++] = '(';
	text[used++] = '1';
	for (size_t i = 1; i < preprocess_condition_depth_limit; i++)
		text[used++] = ')';
	sprintf(text + used, "\n42\n#endif\n");
	check_stream(text, integer, 2, 0, NULL);
	used = (size_t)sprintf(text, "#if ");
	for (size_t i = 0; i < preprocess_condition_depth_limit; i++)
		text[used++] = '(';
	sprintf(text + used, "1\nint");
	check_stream(text, rejected, 3, 1, "conditional expression nesting limit (128)");
	used = (size_t)sprintf(text, "#if +1");
	for (size_t i = 2; i < preprocess_condition_token_limit; i += 2)
		used += (size_t)sprintf(text + used, "+0");
	sprintf(text + used, "\n42\n#endif\n");
	check_stream(text, integer, 2, 0, NULL);
	used = (size_t)sprintf(text, "#if + +1");
	for (size_t i = 2; i < preprocess_condition_token_limit; i += 2)
		used += (size_t)sprintf(text + used, "+0");
	sprintf(text + used, "\nint");
	check_stream(text, rejected, 3, 1, "conditional expression token limit (1024)");
}


static void test_conditional_operator_depth(void)
{
	const struct expected_token integer[] = {
		{ token_integer, "42" }, { token_eof, "" },
	};
	const struct expected_token rejected[] = {
		{ token_invalid, "#" }, { token_int, "int" }, { token_eof, "" },
	};
	char text[4096];
	size_t used;

	for (size_t depth = preprocess_condition_depth_limit - 1;
		depth <= preprocess_condition_depth_limit; depth++) {
		used = (size_t)sprintf(text, "#if ");
		for (size_t i = 0; i < depth; i++)
			used += (size_t)sprintf(text + used, "0?0:");
		if (depth < preprocess_condition_depth_limit) {
			sprintf(text + used, "1\n42\n#endif\n");
			check_stream(text, integer, 2, 0, NULL);
		} else {
			sprintf(text + used, "1\nint");
			check_stream(text, rejected, 3, 1, "conditional expression nesting limit (128)");
		}
	}
}


struct test_include_context {
	const char *text;
	size_t calls;
	size_t recursive;
	size_t path_length;
};

static bool load_test_include(void *context, struct source *source, const char *path)
{
	struct test_include_context *input = context;
	const char *text = input->text;

	input->calls++;
	input->path_length = strlen(path);
	if (!text)
		return false;
	if (input->recursive)
		text = input->calls < input->recursive ? "#include \"h\"\n" : "42";
	return source_from_bytes(source, path, (const unsigned char *)text, strlen(text));
}

static void check_include_stream(const char *text, struct test_include_context *context,
	size_t expected_calls, size_t expected_errors, bool number)
{
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct token token;
	size_t numbers = 0;

	assert(source_from_bytes(&source, "root.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	preprocess_set_include_loader(&preprocessor, load_test_include, context);
	for (size_t steps = 0; ; steps++) {
		assert(steps < 256);
		token = preprocess_peek(&preprocessor);
		assert_same_token(token, preprocess_peek(&preprocessor));
		assert_same_token(token, preprocess_next(&preprocessor));
		assert(preprocessor.include_depth <= preprocess_include_depth_limit);
		assert(preprocessor.include_count <= preprocess_include_count_limit);
		assert(preprocessor.include_bytes <= preprocess_include_bytes_limit);
		if (token.kind == token_eof)
			break;
		assert(token.kind == token_invalid || token.kind == token_integer);
		if (token.kind == token_integer) {
			assert(token.integer == 42);
			assert(memcmp(token.spelling_location.source->data + token.spelling_location.offset,
				"42", 2) == 0);
			numbers++;
		}
	}
	assert(token.location.source == &source && token.location.offset == source.length);
	assert(numbers == (number ? 1u : 0u));
	assert(context->calls == expected_calls && diagnostics.errors == expected_errors);
	assert_same_token(token, preprocess_next(&preprocessor));
	assert(diagnostics.errors == expected_errors);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_quoted_includes(void)
{
	struct test_include_context context = { .text = "#define VALUE 42\n" };
	char text[preprocess_include_path_limit + 64];
	size_t used;

	check_include_stream("#include \"h\"\nVALUE", &context, 1, 0, true);
	context = (struct test_include_context) { .text = "42" };
	check_include_stream("%:include \"h\"", &context, 1, 0, true);
	context = (struct test_include_context) { .text = "" };
	check_include_stream("#if 0\n#include \"missing\"\n#endif\n42", &context, 0, 0, true);
	context = (struct test_include_context) { 0 };
	check_include_stream("#include \"missing\"\n42", &context, 1, 1, true);
	context = (struct test_include_context) { .text = "#endif\n" };
	check_include_stream("#if 1\n#include \"h\"\n#endif\n42", &context, 1, 1, true);
	context = (struct test_include_context) { .text = "#if 1\n42" };
	check_include_stream("#include \"h\"\n99", &context, 1, 1, true);
	context = (struct test_include_context) { .text = "", .recursive = 32 };
	check_include_stream("#include \"h\"", &context, 32, 0, true);
	context = (struct test_include_context) { .text = "", .recursive = 33 };
	check_include_stream("#include \"h\"", &context, 32, 1, false);
	used = 0;
	for (size_t i = 0; i < preprocess_include_count_limit; i++)
		used += (size_t)sprintf(text + used, "#include \"h\"\n");
	context = (struct test_include_context) { .text = "" };
	check_include_stream(text, &context, 128, 0, false);
	sprintf(text + used, "#include \"h\"\n");
	context = (struct test_include_context) { .text = "" };
	check_include_stream(text, &context, 128, 1, false);
	used = (size_t)sprintf(text, "#include \"");
	memset(text + used, 'a', preprocess_include_path_limit - 1);
	strcpy(text + used + preprocess_include_path_limit - 1, "\"");
	context = (struct test_include_context) { .text = "" };
	check_include_stream(text, &context, 1, 0, false);
	assert(context.path_length == preprocess_include_path_limit - 1);
	text[used + preprocess_include_path_limit - 1] = 'a';
	strcpy(text + used + preprocess_include_path_limit, "\"");
	context = (struct test_include_context) { .text = "" };
	check_include_stream(text, &context, 0, 1, false);
}


static void test_include_macro_boundary(void)
{
	const char *text = "#include \"h\"\n()";
	struct test_include_context context = { .text = "#define F() 42\nF" };
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };

	assert(source_from_bytes(&source, "root.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	preprocess_set_include_loader(&preprocessor, load_test_include, &context);
	assert(preprocess_next(&preprocessor).kind == token_identifier);
	assert(preprocess_next(&preprocessor).kind == token_left_paren);
	assert(preprocess_next(&preprocessor).kind == token_right_paren);
	assert(preprocess_next(&preprocessor).kind == token_eof);
	assert(!diagnostics.errors && !preprocessor.include_depth);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	context = (struct test_include_context) { .text = "#define F(a) a\nF(" };
	check_include_stream("#include \"h\"\n)42", &context, 1, 1, false);
}

static void test_include_byte_budget(void)
{
	size_t length = 16 * 1024 * 1024;
	char *body = malloc(length + 1);
	char text[128];
	size_t used = 0;
	struct test_include_context context;

	assert(body);
	memset(body, ' ', length);
	body[length] = 0;
	for (size_t i = 0; i < 4; i++)
		used += (size_t)sprintf(text + used, "#include \"h\"\n");
	context = (struct test_include_context) { .text = body };
	check_include_stream(text, &context, 4, 0, false);
	sprintf(text + used, "#include \"h\"\n");
	context = (struct test_include_context) { .text = body };
	check_include_stream(text, &context, 5, 1, false);
	free(body);
}

int main(void)
{
	test_include_byte_budget();
	test_include_macro_boundary();
	test_quoted_includes();
	test_conditional_operator_depth();
	test_expression_conditions();
	test_macro_conditions();
	test_diagnostic_directives();
	test_token_pasting();
	test_pasting_limits();
	test_optional_stringizing();
	test_optional_stringizing_recovery();
	test_optional_stringizing_limits();
	test_stringizing();
	test_stringizing_errors();
	test_stringizing_limits();
	test_stringizing_cumulative_limit();
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
	test_variadic_limits();
	test_variadic_arguments();
	test_variadic_errors();
	test_fixed_arguments();
	test_fixed_argument_errors();
	test_fixed_argument_limits();
	test_empty_function_macros();
	test_function_macro_redefinition();
	test_function_macro_suppression();
	test_function_definition_errors();
	test_function_invocation_errors();
	test_function_macro_work_and_stream_depth();
	puts("Preprocessor directive and stream tests passed");
	return 0;
}
