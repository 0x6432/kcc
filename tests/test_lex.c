#include "preprocess.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void check_tokens(const char *text, const enum token_kind *kinds,
				size_t count, size_t errors)
{
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;

	assert(stream);
	assert(source_from_bytes(&source, "test.c",
					(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	for (size_t i = 0; i < count; i++) {
		struct token first = preprocess_peek(&preprocessor);
		struct token second = preprocess_peek(&preprocessor);
		struct token next = preprocess_next(&preprocessor);

		assert(first.kind == kinds[i]);
		assert(first.kind == second.kind && first.kind == next.kind);
		assert(first.location.offset == next.location.offset);
		assert(first.length == next.length);
	}
	assert(preprocess_next(&preprocessor).kind == token_eof);
	assert(preprocess_next(&preprocessor).kind == token_eof);
	assert(diagnostics.errors == errors);
	assert(fclose(stream) == 0);
	preprocess_destroy(&preprocessor);
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
	check_tokens("#", NULL, 0, 0);
	check_tokens("%: /* null */\n", NULL, 0, 0);
}

static void test_bracket_tokens(void)
{
	const enum token_kind kinds[] = { token_left_bracket, token_right_bracket,
		token_left_bracket, token_right_bracket };

	check_tokens("[] <: :>", kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_left_bracket), "[") == 0);
	assert(strcmp(token_kind_name(token_right_bracket), "]") == 0);
}

static void test_string_spelling(void)
{
	const char *bad[] = { "", "\"", "\"a", "a\"", "\"\\x\"", "\"\\x100\"",
		"\"\\400\"", "\"\\q\"", "L\"x\"", "u8\"x\"", "\"a\"b\"" };
	const unsigned char nul[] = { '"', 0, '"' };
	const unsigned char high[] = { '"', 128, '"' };
	const unsigned char slice[] = { '"', 'a', '"', 'z' };
	unsigned char output[4];
	size_t length;
	char text[8];

	for (unsigned i = 0; i < 256; i++) {
		assert(snprintf(text, sizeof(text), "\"\\%03o\"", i) == 6);
		assert(!parse_string_spelling((const unsigned char *)text, 6, NULL, 0, &length) && length == 1);
		output[1] = 42;
		assert(!parse_string_spelling((const unsigned char *)text, 6, output, 1, &length));
		assert(length == 1 && output[0] == i && output[1] == 42);
		assert(snprintf(text, sizeof(text), "\"\\x%02x\"", i) == 6);
		assert(!parse_string_spelling((const unsigned char *)text, 6, output, 1, &length));
		assert(length == 1 && output[0] == i && output[1] == 42);
	}
	assert(!parse_string_spelling((const unsigned char *)"\"\"", 2, output, 0, &length) && !length);
	assert(!parse_string_spelling(slice, 3, output, 1, &length) && length == 1 && output[0] == 'a');
	assert(parse_string_spelling(slice, 4, output, sizeof(output), &length));
	output[0] = 42;
	assert(parse_string_spelling(slice, 3, output, 0, &length) && output[0] == 42);
	assert(parse_string_spelling(NULL, 0, output, sizeof(output), &length));
	assert(parse_string_spelling(nul, sizeof(nul), output, sizeof(output), &length));
	assert(parse_string_spelling(high, sizeof(high), output, sizeof(output), &length));
	for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++)
		assert(parse_string_spelling((const unsigned char *)bad[i], strlen(bad[i]), output, sizeof(output), &length));
	assert(!parse_string_spelling((const unsigned char *)"\"\\1234\"", 7, output, 2, &length));
	assert(length == 2 && output[0] == 83 && output[1] == '4');
	assert(!parse_string_spelling((const unsigned char *)"\"\\xffg\"", 7, output, 2, &length));
	assert(length == 2 && output[0] == 255 && output[1] == 'g');
}

static void test_errors(void)
{
	const enum token_kind invalid[] = { token_invalid };
	const enum token_kind separate[] = { token_identifier };
	const char *cases[] = {
		"/*", "/* *", "09", "0xg", "0b2", "12.5", "3.5", "@",
		"18446744073709551616", "->",
	};

	for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++)
		check_tokens(cases[i], invalid, 1, 1);
	check_tokens("integer", separate, 1, 0);
	{
		const enum token_kind keyword[] = { token_unsupported_keyword };
		const enum token_kind equal[] = { token_equal };

		check_tokens("struct", keyword, 1, 0);
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

static void test_bitwise_tokens(void)
{
	const enum token_kind kinds[] = {
		token_tilde, token_ampersand, token_caret, token_pipe,
		token_shift_left, token_shift_right,
	};

	check_tokens("~ & ^ | << >>", kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	check_tokens("#define C(a,b) a##b\n~ & ^ | C(<,<) C(>,>)",
		kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
}

static void test_binary_and_values(void)
{
	const unsigned char bytes[] = { 0, 255, '0', ' ', '4', '2' };
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct token token;

	assert(stream);
	assert(source_from_bytes(&source, "binary.c", bytes, sizeof(bytes)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	assert(preprocess_next(&preprocessor).kind == token_invalid);
	assert(preprocess_next(&preprocessor).kind == token_invalid);
	token = preprocess_next(&preprocessor);
	assert(token.kind == token_integer && token.integer == 0);
	token = preprocess_next(&preprocessor);
	assert(token.kind == token_integer && token.integer == 42);
	assert(token.location.offset == 4 && token.length == 2);
	assert(preprocess_next(&preprocessor).kind == token_eof);
	assert(diagnostics.errors == 2);
	preprocess_destroy(&preprocessor);
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

static void test_integer_spellings(void)
{
	const char *bases[] = { "42", "052", "0x2a", "0B101010", "4'2", "0x2'a" };
	const char *suffixes[] = { "", "u", "U", "l", "L", "ll", "LL", "ul", "uL", "Ull",
		"ULL", "lu", "LU", "llU", "LLu" };
	const char *bad[] = { "", "0x", "0b", "08", "0b2", "0x'1", "1''2", "1'",
		"1'u", "1uu", "1lL", "1Ll", "1LLL", "1wb", "1.0", "1e2",
		"18446744073709551616", "0x10000000000000000" };
	const unsigned char slice[] = { '4', '2', 'u' };
	struct integer_spelling spelling;
	char text[64];

	for (size_t i = 0; i < sizeof(bases) / sizeof(bases[0]); i++)
		for (size_t j = 0; j < sizeof(suffixes) / sizeof(suffixes[0]); j++) {
			unsigned longs = 0;

			assert(snprintf(text, sizeof(text), "%s%s", bases[i], suffixes[j]) > 0);
			assert(!parse_integer_spelling((const unsigned char *)text, strlen(text), &spelling));
			for (const char *p = suffixes[j]; *p; p++)
				if (*p == 'l' || *p == 'L')
					longs++;
			assert(spelling.value == 42 && spelling.long_suffix == longs);
			assert(spelling.unsigned_suffix == (strchr(suffixes[j], 'u') != NULL ||
				strchr(suffixes[j], 'U') != NULL));
			assert(spelling.base == (i == 1 ? 8u : i == 2 || i == 5 ? 16u : i == 3 ? 2u : 10u));
		}
	for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++)
		assert(parse_integer_spelling((const unsigned char *)bad[i], strlen(bad[i]), &spelling));
	assert(parse_integer_spelling(NULL, 0, &spelling));
	assert(!parse_integer_spelling(slice, 2, &spelling));
	assert(spelling.value == 42 && !spelling.unsigned_suffix);
	assert(!parse_integer_spelling(slice, 3, &spelling));
	assert(spelling.value == 42 && spelling.unsigned_suffix);
	assert(!parse_integer_spelling((const unsigned char *)"18446744073709551615", 20, &spelling));
	assert(spelling.value == UINT64_MAX);
	assert(!parse_integer_spelling((const unsigned char *)"0xffffffffffffffffULL", 21, &spelling));
	assert(spelling.value == UINT64_MAX && spelling.unsigned_suffix && spelling.long_suffix == 2);
	{
		const enum token_kind kinds[] = {
			token_integer, token_integer, token_integer, token_integer, token_integer,
		};

		check_tokens("00 052 0x2a 0b101010 4'2", kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	}
}

static void test_character_spellings(void)
{
	const char *bad[] = { "", "'", "''", "'''", "'ab'", "'a", "a'", "'\\'",
		"'\\x'", "'\\x100'", "'\\400'", "'\\1234'", "'\\q'", "'\\u0041'",
		"L'a'", "u'a'", "U'a'", "u8'a'", "'\n'", "'\r'", "'\200'" };
	const unsigned char slice[] = { '\'', 'a', '\'', 'z' };
	const unsigned char nul[] = { '\'', 0, '\'' };
	int64_t value;
	char text[16];

	for (unsigned byte = 0; byte <= 255; byte++) {
		int64_t expected = byte < 128 ? (int64_t)byte : (int64_t)byte - 256;

		assert(snprintf(text, sizeof(text), "'\\%03o'", byte) == 6);
		assert(!parse_character_spelling((const unsigned char *)text, 6, &value));
		assert(value == expected);
		assert(snprintf(text, sizeof(text), "'\\x%02x'", byte) == 6);
		assert(!parse_character_spelling((const unsigned char *)text, 6, &value));
		assert(value == expected);
	}
	for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++)
		assert(parse_character_spelling((const unsigned char *)bad[i], strlen(bad[i]), &value));
	assert(parse_character_spelling(NULL, 0, &value));
	assert(parse_character_spelling(nul, sizeof(nul), &value));
	assert(!parse_character_spelling(slice, 3, &value) && value == 97);
	assert(parse_character_spelling(slice, 4, &value));
	{
		const enum token_kind kinds[] = { token_character, token_character, token_character };

		check_tokens("'A' '\\xff' '\\0'", kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	}
}

static void test_const_tokens(void)
{
	const enum token_kind kinds[] = { token_const, token_identifier, token_const };

	check_tokens("#define READONLY const\nconst constness READONLY", kinds,
		sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_const), "const") == 0);
}

static void test_boolean_keywords(void)
{
	const enum token_kind kinds[] = { token_c23_bool, token_true, token_false,
		token_identifier, token_identifier, token_identifier, token_bool };

	check_tokens("#define FLAG bool\n#define YES true\n#define CAT(a,b) a##b\n"
		"FLAG YES CAT(fal,se) boolish trueish falsehood _Bool", kinds,
		sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_c23_bool), "bool") == 0);
	assert(strcmp(token_kind_name(token_true), "true") == 0);
	assert(strcmp(token_kind_name(token_false), "false") == 0);
}


static void test_conditional_punctuation(void)
{
	const enum token_kind kinds[] = { token_question, token_colon,
		token_question, token_colon };

	check_tokens("#define Q ?\n#define C :\n?: Q C", kinds,
		sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_question), "?") == 0);
	assert(strcmp(token_kind_name(token_colon), ":") == 0);
}


static void test_layout_keywords(void)
{
	const enum token_kind kinds[] = { token_sizeof, token_alignof,
		token_legacy_alignof, token_sizeof, token_identifier };

	check_tokens("#define SIZE sizeof\nsizeof alignof _Alignof SIZE sizeofish", kinds,
		sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_sizeof), "sizeof") == 0);
	assert(strcmp(token_kind_name(token_alignof), "alignof") == 0);
	assert(strcmp(token_kind_name(token_legacy_alignof), "_Alignof") == 0);
}


static void test_assertion_keywords(void)
{
	const enum token_kind kinds[] = { token_static_assert, token_legacy_static_assert,
		token_static_assert, token_identifier };

	check_tokens("#define CHECK static_assert\nstatic_assert _Static_assert CHECK static_assertion",
		kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_static_assert), "static_assert") == 0);
	assert(strcmp(token_kind_name(token_legacy_static_assert), "_Static_assert") == 0);
}

static void test_nullptr_keyword(void)
{
	const enum token_kind kinds[] = { token_nullptr, token_nullptr, token_identifier, token_integer, token_nullptr };

	check_tokens("#define N nullptr\nnullptr N nullptr_t\n#define nullptr 42\nnullptr\n#undef nullptr\nnullptr",
		kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_nullptr), "nullptr") == 0);
}


static void test_update_tokens(void)
{
	const enum token_kind kinds[] = {
		token_increment, token_increment, token_identifier,
		token_plus, token_plus, token_identifier,
		token_decrement, token_identifier, token_minus, token_minus, token_identifier,
		token_increment, token_identifier,
	};

	check_tokens("++++x + +x --x - -x\n#define JOIN(a,b) a##b\nJOIN(+,+)x", kinds,
		sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_increment), "++") == 0);
	assert(strcmp(token_kind_name(token_decrement), "--") == 0);
}


static void test_compound_assignment_tokens(void)
{
	const enum token_kind kinds[] = {
		token_plus_equal, token_minus_equal, token_increment, token_equal,
		token_plus, token_equal, token_minus, token_equal,
		token_plus_equal, token_minus_equal,
	};

	check_tokens("+= -= ++= + = - =\n#define JOIN(a,b) a##b\nJOIN(+,=) JOIN(-,=)", kinds,
		sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_plus_equal), "+=") == 0);
	assert(strcmp(token_kind_name(token_minus_equal), "-=") == 0);
}

static void test_integer_compound_tokens(void)
{
	const enum token_kind kinds[] = {
		token_star_equal,
		token_slash_equal,
		token_percent_equal,
		token_ampersand_equal,
		token_caret_equal,
		token_pipe_equal,
		token_shift_left_equal,
		token_shift_right_equal,
		token_shift_left_equal, token_greater, token_greater_equal,
		token_star, token_equal,
	};

	check_tokens("*= /= %= &= ^= |= <<= >>=\n#define JOIN(a,b) a##b\nJOIN(<<,=) > >= * =", kinds,
		sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_star_equal), "*=") == 0);
	assert(strcmp(token_kind_name(token_slash_equal), "/=") == 0);
	assert(strcmp(token_kind_name(token_percent_equal), "%=") == 0);
	assert(strcmp(token_kind_name(token_ampersand_equal), "&=") == 0);
	assert(strcmp(token_kind_name(token_caret_equal), "^=") == 0);
	assert(strcmp(token_kind_name(token_pipe_equal), "|=") == 0);
	assert(strcmp(token_kind_name(token_shift_left_equal), "<<=") == 0);
	assert(strcmp(token_kind_name(token_shift_right_equal), ">>=") == 0);
}

static void test_goto_keyword(void)
{
	const enum token_kind kinds[] = { token_goto, token_identifier, token_semicolon };

	check_tokens("#define JUMP goto\nJUMP target;", kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_goto), "goto") == 0);
}

static void test_switch_keyword(void)
{
	const enum token_kind kinds[] = { token_switch, token_left_paren, token_integer, token_right_paren, token_semicolon };

	check_tokens("#define SELECT switch\nSELECT(1);", kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_switch), "switch") == 0);
}

static void test_case_keywords(void)
{
	const enum token_kind kinds[] = { token_case, token_integer, token_colon, token_default, token_colon };

	check_tokens("#define ARM case\n#define FALLBACK default\nARM 1: FALLBACK:", kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_case), "case") == 0);
	assert(strcmp(token_kind_name(token_default), "default") == 0);
}

static void test_typeof_keywords(void)
{
	const enum token_kind kinds[] = { token_typeof, token_typeof_unqual };

	check_tokens("#define QUERY typeof\nQUERY typeof_unqual", kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	assert(strcmp(token_kind_name(token_typeof), "typeof") == 0);
	assert(strcmp(token_kind_name(token_typeof_unqual), "typeof_unqual") == 0);
}

static void test_typedef_keyword(void)
{
	const enum token_kind kinds[] = { token_typedef, token_identifier };

	check_tokens("#define DECL typedef\nDECL name", kinds, 2, 0);
	assert(strcmp(token_kind_name(token_typedef), "typedef") == 0);
}

static void test_register_keyword(void)
{
	const enum token_kind kinds[] = { token_register, token_identifier, token_int };

	check_tokens("#define STORE register\nSTORE name\n#define register int\nregister", kinds, 3, 0);
	assert(strcmp(token_kind_name(token_register), "register") == 0);
}

static void test_auto_keyword(void)
{
	const enum token_kind kinds[] = { token_auto, token_identifier, token_int };

	check_tokens("#define STORE auto\nSTORE name\n#define auto int\nauto", kinds, 3, 0);
	assert(strcmp(token_kind_name(token_auto), "auto") == 0);
}

int main(void)
{
	test_auto_keyword();
	test_register_keyword();
	test_typedef_keyword();
	test_typeof_keywords();
	test_case_keywords();
	test_switch_keyword();
	test_goto_keyword();
	test_integer_compound_tokens();
	test_compound_assignment_tokens();
	test_update_tokens();
	test_nullptr_keyword();
	test_assertion_keywords();
	test_layout_keywords();
	test_conditional_punctuation();
	test_boolean_keywords();
	test_const_tokens();
	test_character_spellings();
	test_integer_spellings();
	{
		const enum token_kind kinds[] = { token_bool, token_c23_bool, token_true, token_false };

		check_tokens("_Bool bool true false", kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	}
	{
		const enum token_kind kinds[] = { token_short, token_signed, token_short, token_unsigned, token_short };

		check_tokens("short signed short unsigned short", kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	}
	{
		const enum token_kind kinds[] = { token_char, token_signed, token_char, token_unsigned, token_char };

		check_tokens("char signed char unsigned char", kinds, sizeof(kinds) / sizeof(kinds[0]), 0);
	}
	test_bitwise_tokens();
	test_phase_ordering();
	test_string_spelling();
	test_basic();
	test_bracket_tokens();
	test_errors();
	test_binary_and_values();
	test_condition_tokens();
	puts("Lexer tests passed");
	return 0;
}
