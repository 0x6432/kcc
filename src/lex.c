#include "lex.h"

#include <string.h>

static bool is_digit(unsigned char byte)
{
	return byte >= '0' && byte <= '9';
}

static bool is_identifier_start(unsigned char byte)
{
	return (byte >= 'a' && byte <= 'z') ||
		(byte >= 'A' && byte <= 'Z') || byte == '_';
}

static bool is_identifier_continue(unsigned char byte)
{
	return is_identifier_start(byte) || is_digit(byte);
}

static bool is_space(unsigned char byte)
{
	return byte == ' ' || byte == '\t' || byte == '\n' ||
		byte == '\r' || byte == '\v' || byte == '\f';
}

static struct token make_token(struct lexer *lexer, enum token_kind kind,
				size_t beginning)
{
	return (struct token) {
		.kind = kind,
		.location = { lexer->source, beginning },
		.length = lexer->offset - beginning,
	};
}

static struct token invalid_token(struct lexer *lexer, size_t beginning,
					const char *message)
{
	struct token token = make_token(lexer, token_invalid, beginning);

	diagnostic_error(lexer->diagnostics, token.location, message);
	return token;
}

/* Skip trivia. On an unterminated comment, leave one invalid token to return. */
static bool skip_trivia(struct lexer *lexer, struct token *error)
{
	const struct source *source = lexer->source;

	while (lexer->offset < source->length) {
		size_t beginning = lexer->offset;
		unsigned char byte = source->data[beginning];

		if (is_space(byte)) {
			lexer->offset++;
			continue;
		}
		if (byte != '/' || source->length - beginning < 2)
			break;
		if (source->data[beginning + 1] == '/') {
			lexer->offset += 2;
			while (lexer->offset < source->length &&
				source->data[lexer->offset] != '\n')
				lexer->offset++;
			continue;
		}
		if (source->data[beginning + 1] != '*')
			break;

		lexer->offset += 2;
		while (source->length - lexer->offset >= 2) {
			if (source->data[lexer->offset] == '*' &&
				source->data[lexer->offset + 1] == '/')
				break;
			lexer->offset++;
		}
		if (source->length - lexer->offset < 2) {
			lexer->offset = source->length;
			*error = invalid_token(lexer, beginning,
						"unterminated block comment");
			return false;
		}
		lexer->offset += 2;
	}
	return true;
}

static bool spelling_is(struct token token, const char *spelling)
{
	size_t length = strlen(spelling);

	return token.length == length &&
		memcmp(token.location.source->data + token.location.offset,
			spelling, length) == 0;
}

/* Keep unsupported C keywords out of the ordinary identifier namespace. */
static bool is_unsupported_keyword(struct token token)
{
	static const char *const keywords[] = {
		"auto", "break", "case", "char", "const", "continue", "default",
		"do", "double", "else", "enum", "extern", "float", "for", "goto",
		"if", "inline", "long", "register", "restrict", "short", "signed",
		"sizeof", "static", "struct", "switch", "typedef", "union",
		"unsigned", "volatile", "while", "_Alignas", "_Alignof", "_Atomic",
		"_Bool", "_Complex", "_Decimal32", "_Decimal64", "_Decimal128",
		"_Generic", "_Imaginary", "_Noreturn", "_Static_assert",
		"_Thread_local", "_BitInt", "alignas", "alignof", "bool",
		"constexpr", "false", "nullptr", "static_assert", "thread_local",
		"true", "typeof", "typeof_unqual",
	};

	for (size_t i = 0; i < sizeof(keywords) / sizeof(keywords[0]); i++)
		if (spelling_is(token, keywords[i]))
			return true;
	return false;
}

static struct token lex_identifier(struct lexer *lexer)
{
	size_t beginning = lexer->offset;
	struct token token;

	do
		lexer->offset++;
	while (lexer->offset < lexer->source->length &&
			is_identifier_continue(lexer->source->data[lexer->offset]));

	token = make_token(lexer, token_identifier, beginning);
	if (spelling_is(token, "int"))
		token.kind = token_int;
	else if (spelling_is(token, "void"))
		token.kind = token_void;
	else if (spelling_is(token, "return"))
		token.kind = token_return;
	else if (spelling_is(token, "if"))
		token.kind = token_if;
	else if (spelling_is(token, "else"))
		token.kind = token_else;
	else if (spelling_is(token, "while"))
		token.kind = token_while;
	else if (spelling_is(token, "break"))
		token.kind = token_break;
	else if (spelling_is(token, "continue"))
		token.kind = token_continue;
	else if (spelling_is(token, "do"))
		token.kind = token_do;
	else if (spelling_is(token, "for"))
		token.kind = token_for;
	else if (is_unsupported_keyword(token))
		token.kind = token_unsupported_keyword;
	return token;
}

static struct token lex_integer(struct lexer *lexer)
{
	size_t beginning = lexer->offset;
	uint64_t value = 0;
	bool overflow = false;
	struct token token;

	while (lexer->offset < lexer->source->length &&
		is_digit(lexer->source->data[lexer->offset])) {
		unsigned digit = lexer->source->data[lexer->offset] - '0';

		if (value > (UINT64_MAX - digit) / 10)
			overflow = true;
		else if (!overflow)
			value = value * 10 + digit;
		lexer->offset++;
	}

	/* Never reinterpret unsupported 12u or 0x10 as separate valid tokens. */
	if (lexer->offset < lexer->source->length &&
		(is_identifier_continue(lexer->source->data[lexer->offset]) ||
		lexer->source->data[lexer->offset] == '.')) {
		while (lexer->offset < lexer->source->length &&
			(is_identifier_continue(lexer->source->data[lexer->offset]) ||
			lexer->source->data[lexer->offset] == '.'))
			lexer->offset++;
		return invalid_token(lexer, beginning,
					"unsupported numeric literal");
	}
	if (lexer->offset - beginning > 1 &&
		lexer->source->data[beginning] == '0')
		return invalid_token(lexer, beginning,
					"nondecimal integer literals are not supported");
	if (overflow)
		return invalid_token(lexer, beginning,
					"integer literal exceeds 64 bits");
	token = make_token(lexer, token_integer, beginning);
	token.integer = value;
	return token;
}

static struct token read_token(struct lexer *lexer)
{
	struct token error;
	size_t beginning;
	unsigned char byte;
	enum token_kind kind;

	if (!skip_trivia(lexer, &error))
		return error;
	beginning = lexer->offset;
	if (beginning == lexer->source->length)
		return make_token(lexer, token_eof, beginning);

	byte = lexer->source->data[beginning];
	if (is_identifier_start(byte))
		return lex_identifier(lexer);
	if (is_digit(byte))
		return lex_integer(lexer);

	/* Preserve maximal munch for compound operators outside this subset. */
	if (lexer->source->length - beginning >= 2) {
		unsigned char next = lexer->source->data[beginning + 1];
		bool compound = (byte == '+' && (next == '+' || next == '=')) ||
			(byte == '-' && (next == '-' || next == '=' || next == '>')) ||
			((byte == '*' || byte == '/' || byte == '%') && next == '=');

		if ((byte == '&' || byte == '|') && next == byte) {
			kind = byte == '&' ? token_and_and : token_or_or;
			lexer->offset += 2;
			return make_token(lexer, kind, beginning);
		}
		if (next == '=' &&
			(byte == '=' || byte == '!' || byte == '<' || byte == '>')) {
			switch (byte) {
			case '=': kind = token_equal_equal; break;
			case '!': kind = token_not_equal; break;
			case '<': kind = token_less_equal; break;
			case '>': kind = token_greater_equal; break;
			default: kind = token_invalid; break;
			}
			lexer->offset += 2;
			return make_token(lexer, kind, beginning);
		}
		if ((byte == '<' || byte == '>') && next == byte) {
			lexer->offset += 2;
			if (lexer->offset < lexer->source->length &&
				lexer->source->data[lexer->offset] == '=')
				lexer->offset++;
			return invalid_token(lexer, beginning,
				"shift operator is not supported");
		}
		if (compound) {
			lexer->offset += 2;
			return invalid_token(lexer, beginning,
				"compound operator is not supported");
		}
	}
	lexer->offset++;
	switch (byte) {
	case '(':
		kind = token_left_paren;
		break;
	case ')':
		kind = token_right_paren;
		break;
	case '{':
		kind = token_left_brace;
		break;
	case '}':
		kind = token_right_brace;
		break;
	case ',':
		kind = token_comma;
		break;
	case ';':
		kind = token_semicolon;
		break;
	case '+':
		kind = token_plus;
		break;
	case '-':
		kind = token_minus;
		break;
	case '*':
		kind = token_star;
		break;
	case '/':
		kind = token_slash;
		break;
	case '%':
		kind = token_percent;
		break;
	case '!':
		kind = token_bang;
		break;
	case '<':
		kind = token_less;
		break;
	case '>':
		kind = token_greater;
		break;
	case '=':
		kind = token_equal;
		break;
	case '#':
		return invalid_token(lexer, beginning,
					"preprocessing directives are not supported");
	default:
		return invalid_token(lexer, beginning,
					"unsupported source byte");
	}
	return make_token(lexer, kind, beginning);
}

void lexer_init(struct lexer *lexer, const struct source *source,
		struct diagnostics *diagnostics)
{
	*lexer = (struct lexer) {
		.source = source,
		.diagnostics = diagnostics,
	};
}

struct token lexer_next(struct lexer *lexer)
{
	if (lexer->has_lookahead) {
		lexer->has_lookahead = false;
		return lexer->lookahead;
	}
	return read_token(lexer);
}

struct token lexer_peek(struct lexer *lexer)
{
	if (!lexer->has_lookahead) {
		lexer->lookahead = read_token(lexer);
		lexer->has_lookahead = true;
	}
	return lexer->lookahead;
}

const char *token_kind_name(enum token_kind kind)
{
	switch (kind) {
	case token_eof: return "eof";
	case token_invalid: return "invalid";
	case token_identifier: return "identifier";
	case token_unsupported_keyword: return "unsupported-keyword";
	case token_integer: return "integer";
	case token_int: return "int";
	case token_void: return "void";
	case token_return: return "return";
	case token_if: return "if";
	case token_else: return "else";
	case token_while: return "while";
	case token_do: return "do";
	case token_for: return "for";
	case token_break: return "break";
	case token_continue: return "continue";
	case token_left_paren: return "(";
	case token_right_paren: return ")";
	case token_left_brace: return "{";
	case token_right_brace: return "}";
	case token_semicolon: return ";";
	case token_comma: return ",";
	case token_plus: return "+";
	case token_minus: return "-";
	case token_star: return "*";
	case token_slash: return "/";
	case token_percent: return "%";
	case token_equal: return "=";
	case token_equal_equal: return "==";
	case token_not_equal: return "!=";
	case token_less: return "<";
	case token_less_equal: return "<=";
	case token_greater: return ">";
	case token_greater_equal: return ">=";
	case token_bang: return "!";
	case token_and_and: return "&&";
	case token_or_or: return "||";
	}
	return "unknown";
}
