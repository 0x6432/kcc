#include "lex.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void check_tokens(const char *text, const enum token_kind *kinds,
				size_t count, size_t errors)
{
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { stream, 0 };
	struct lexer lexer;

	assert(stream);
	assert(source_from_bytes(&source, "test.c",
					(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	lexer_init(&lexer, &source, &diagnostics);
	for (size_t i = 0; i < count; i++) {
		struct token first = lexer_peek(&lexer);
		struct token second = lexer_peek(&lexer);
		struct token next = lexer_next(&lexer);

		assert(first.kind == kinds[i]);
		assert(first.kind == second.kind && first.kind == next.kind);
		assert(first.location.offset == next.location.offset);
		assert(first.length == next.length);
	}
	assert(lexer_next(&lexer).kind == token_eof);
	assert(lexer_next(&lexer).kind == token_eof);
	assert(diagnostics.errors == errors);
	assert(fclose(stream) == 0);
	source_destroy(&source);
}

static void test_basic(void)
{
	const enum token_kind kinds[] = {
		token_int, token_identifier, token_left_paren, token_void,
		token_right_paren, token_left_brace, token_return, token_integer,
		token_semicolon, token_right_brace,
	};

	check_tokens("int main(void) { return 0; }", kinds,
			sizeof(kinds) / sizeof(kinds[0]), 0);
	check_tokens("/* leading */ int // line\n main(void){return 0;}",
			kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	check_tokens(" \t\r\n\v\f", NULL, 0, 0);
	check_tokens("// EOF", NULL, 0, 0);
	check_tokens("/**/", NULL, 0, 0);
}

static void test_errors(void)
{
	const enum token_kind invalid[] = { token_invalid };
	const enum token_kind separate[] = { token_identifier };
	const char *cases[] = {
		"/*", "/* *", "09", "00", "0x10", "12u", "3.5", "@", "#",
		"18446744073709551616", "++", "--", "->", "+=", "*=", "/=", "%=", "<<", ">>=",
	};

	for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++)
		check_tokens(cases[i], invalid, 1, 1);
	check_tokens("integer", separate, 1, 0);
	{
		const enum token_kind keyword[] = { token_unsupported_keyword };
		const enum token_kind equal[] = { token_equal };

		check_tokens("switch", keyword, 1, 0);
		check_tokens("constexpr", keyword, 1, 0);
		check_tokens("=", equal, 1, 0);
	}
}

static void test_condition_tokens(void)
{
	const enum token_kind kinds[] = {
		token_if, token_else, token_less, token_less_equal, token_greater,
		token_greater_equal, token_equal_equal, token_not_equal, token_equal,
		token_bang, token_and_and, token_or_or,
		token_while, token_break, token_continue, token_do, token_for, token_comma,
	};

	check_tokens("if else < <= > >= == != = ! && || while break continue do for ,", kinds,
		sizeof(kinds) / sizeof(kinds[0]), 0);
}

static void test_binary_and_values(void)
{
	const unsigned char bytes[] = { 0, 255, '0', ' ', '4', '2' };
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { stream, 0 };
	struct lexer lexer;
	struct token token;

	assert(stream);
	assert(source_from_bytes(&source, "binary.c", bytes, sizeof(bytes)));
	assert(source_prepare(&source));
	lexer_init(&lexer, &source, &diagnostics);
	assert(lexer_next(&lexer).kind == token_invalid);
	assert(lexer_next(&lexer).kind == token_invalid);
	token = lexer_next(&lexer);
	assert(token.kind == token_integer && token.integer == 0);
	token = lexer_next(&lexer);
	assert(token.kind == token_integer && token.integer == 42);
	assert(token.location.offset == 4 && token.length == 2);
	assert(lexer_next(&lexer).kind == token_eof);
	assert(diagnostics.errors == 2);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_phase_ordering(void)
{
	const enum token_kind kinds[] = {
		token_int, token_identifier, token_left_paren, token_void,
		token_right_paren, token_left_brace, token_return, token_integer,
		token_semicolon, token_right_brace,
	};
	const enum token_kind names[] = { token_identifier, token_identifier };

	check_tokens("in\\\nt ma\\\nin(vo\\\nid){ret\\\nurn 4\\\n2;}", kinds,
		sizeof(kinds) / sizeof(kinds[0]), 0);
	check_tokens("int main(void){/\\\r\n* hidden *\\\r/return 0;}", kinds,
		sizeof(kinds) / sizeof(kinds[0]), 0);
	check_tokens("int main(void){// hidden\\\nreturn 99;\nreturn 0;}", kinds,
		sizeof(kinds) / sizeof(kinds[0]), 0);
	check_tokens("ab/**/cd", names, sizeof(names) / sizeof(names[0]), 0);
}

int main(void)
{
	test_phase_ordering();
	test_basic();
	test_errors();
	test_binary_and_values();
	test_condition_tokens();
	puts("Lexer tests passed");
	return 0;
}
