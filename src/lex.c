#include "lex.h"

#include <assert.h>
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

static bool is_horizontal_space(unsigned char byte)
{
	return byte == ' ' || byte == '\t' || byte == '\v' || byte == '\f';
}

static struct pp_token make_pp_token(struct pp_lexer *lexer,
	enum pp_token_kind kind, size_t beginning)
{
	struct pp_token token = {
		.kind = kind,
		.location = { lexer->source, beginning },
		.length = lexer->offset - beginning,
		.leading_space = lexer->leading_space,
		.at_line_start = lexer->at_line_start,
		.has_non_directive_space = lexer->has_non_directive_space,
	};

	if (kind == pp_newline) {
		lexer->at_line_start = true;
		lexer->leading_space = false;
		lexer->has_non_directive_space = false;
	} else if (kind != pp_eof) {
		lexer->at_line_start = false;
		lexer->leading_space = false;
		lexer->has_non_directive_space = false;
	}
	return token;
}

static struct pp_token invalid_pp_token(struct pp_lexer *lexer,
	size_t beginning, const char *message)
{
	struct pp_token token = make_pp_token(lexer, pp_invalid, beginning);

	diagnostic_error(lexer->diagnostics, token.location, message);
	return token;
}

/* Comments become one space. Their internal newlines are not directive ends. */
static bool skip_pp_trivia(struct pp_lexer *lexer, struct pp_token *error)
{
	const struct source *source = lexer->source;

	while (lexer->offset < source->length) {
		size_t beginning = lexer->offset;
		unsigned char byte = source->data[beginning];

		if (is_horizontal_space(byte)) {
			lexer->leading_space = true;
			if (byte == '\v' || byte == '\f')
				lexer->has_non_directive_space = true;
			lexer->offset++;
			continue;
		}
		if (byte != '/' || source->length - beginning < 2)
			break;
		if (source->data[beginning + 1] == '/') {
			lexer->leading_space = true;
			lexer->offset += 2;
			while (lexer->offset < source->length &&
				source->data[lexer->offset] != '\n')
				lexer->offset++;
			continue;
		}
		if (source->data[beginning + 1] != '*')
			break;
		lexer->leading_space = true;
		lexer->offset += 2;
		while (source->length - lexer->offset >= 2) {
			if (source->data[lexer->offset] == '*' &&
				source->data[lexer->offset + 1] == '/')
				break;
			lexer->offset++;
		}
		if (source->length - lexer->offset < 2) {
			lexer->offset = source->length;
			*error = invalid_pp_token(lexer, beginning, "unterminated block comment");
			return false;
		}
		lexer->offset += 2;
	}
	return true;
}

static struct pp_token lex_pp_identifier(struct pp_lexer *lexer)
{
	size_t beginning = lexer->offset;

	do
		lexer->offset++;
	while (lexer->offset < lexer->source->length &&
		is_identifier_continue(lexer->source->data[lexer->offset]));
	return make_pp_token(lexer, pp_identifier, beginning);
}

/* pp-number ::= digit | "." digit | pp-number identifier-continue
 *             | pp-number "'" (digit | nondigit) | pp-number "."
 *             | pp-number ("e" | "E" | "p" | "P") ("+" | "-")
 * This recognizes spelling only, not a numeric value or a supported C type.
 */
static struct pp_token lex_pp_number(struct pp_lexer *lexer)
{
	const struct source *source = lexer->source;
	size_t beginning = lexer->offset;

	lexer->offset++;

	while (lexer->offset < source->length) {
		unsigned char byte = source->data[lexer->offset];
		unsigned char previous = source->data[lexer->offset - 1];

		if (is_identifier_continue(byte) || byte == '.') {
			lexer->offset++;
			continue;
		}
		if (byte == '\'' && source->length - lexer->offset >= 2 &&
			is_identifier_continue(source->data[lexer->offset + 1])) {
			lexer->offset += 2;
			continue;
		}
		if ((byte == '+' || byte == '-') &&
			(previous == 'e' || previous == 'E' ||
			previous == 'p' || previous == 'P')) {
			lexer->offset++;
			continue;
		}
		break;
	}
	return make_pp_token(lexer, pp_number, beginning);
}

/* Return the quote offset, or source length if no quoted token starts here. */
static size_t find_quote(const struct pp_lexer *lexer)
{
	const struct source *source = lexer->source;
	size_t offset = lexer->offset;
	unsigned char byte = source->data[offset];

	if (byte == '\'' || byte == '"')
		return offset;
	if (byte == 'u' && source->length - offset >= 3 && source->data[offset + 1] == '8')
		offset += 2;
	else if (byte == 'u' || byte == 'U' || byte == 'L')
		offset++;
	else
		return source->length;
	if (offset < source->length &&
		(source->data[offset] == '\'' || source->data[offset] == '"'))
		return offset;
	return source->length;
}

/* quoted-token ::= [ "u8" | "u" | "U" | "L" ] quoted-spelling
 * Keep escapes opaque, but protect delimiters and reject partial tokens.
 */
static struct pp_token lex_pp_quoted(struct pp_lexer *lexer, size_t quote_offset)
{
	const struct source *source = lexer->source;
	size_t beginning = lexer->offset;
	unsigned char quote = source->data[quote_offset];
	enum pp_token_kind kind = quote == '"' ? pp_string : pp_character;

	lexer->offset = quote_offset + 1;
	while (lexer->offset < source->length) {
		unsigned char byte = source->data[lexer->offset];

		if (byte == '\n')
			break;
		lexer->offset++;
		if (!byte)
			return invalid_pp_token(lexer, beginning,
				"NUL in quoted preprocessing token");
		if (byte == quote)
			return make_pp_token(lexer, kind, beginning);
		if (byte == '\\' && lexer->offset < source->length &&
			source->data[lexer->offset] != '\n') {
			unsigned char escaped = source->data[lexer->offset];

			lexer->offset++;
			if (!escaped)
				return invalid_pp_token(lexer, beginning,
					"NUL in quoted preprocessing token");
		}
	}
	return invalid_pp_token(lexer, beginning, "unterminated quoted preprocessing token");
}

/* Longest spellings first; same-length entries cannot prefix one another. */
static const char *const pp_punctuators[] = {
	"%:%:",
	"<<=", ">>=", "...",
	"->", "++", "--", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||",
	"*=", "/=", "%=", "+=", "-=", "&=", "^=", "|=", "##", "::",
	"<:", ":>", "<%", "%>", "%:",
	"[", "]", "(", ")", "{", "}", ".", "&", "*", "+", "-", "~", "!",
	"/", "%", "<", ">", "^", "|", "?", ":", ";", "=", ",", "#",
};

static struct pp_token lex_pp_punctuator(struct pp_lexer *lexer)
{
	const struct source *source = lexer->source;
	size_t beginning = lexer->offset;

	for (size_t i = 0; i < sizeof(pp_punctuators) / sizeof(pp_punctuators[0]); i++) {
		size_t length = strlen(pp_punctuators[i]);

		if (length <= source->length - beginning &&
			memcmp(source->data + beginning, pp_punctuators[i], length) == 0) {
			lexer->offset += length;
			return make_pp_token(lexer, pp_punctuator, beginning);
		}
	}
	lexer->offset++;
	if (!source->data[beginning] || source->data[beginning] >= 128)
		return invalid_pp_token(lexer, beginning, "unsupported source byte");
	return make_pp_token(lexer, pp_other, beginning);
}

static struct pp_token read_pp_token(struct pp_lexer *lexer)
{
	struct pp_token error;
	const struct source *source = lexer->source;
	size_t beginning;
	size_t quote_offset;
	unsigned char byte;

	if (!skip_pp_trivia(lexer, &error))
		return error;
	beginning = lexer->offset;
	if (beginning == source->length)
		return make_pp_token(lexer, pp_eof, beginning);
	byte = source->data[beginning];
	if (byte == '\n') {
		lexer->offset++;
		return make_pp_token(lexer, pp_newline, beginning);
	}
	quote_offset = find_quote(lexer);
	if (quote_offset != source->length)
		return lex_pp_quoted(lexer, quote_offset);
	if (is_identifier_start(byte))
		return lex_pp_identifier(lexer);
	if (is_digit(byte) || (byte == '.' && source->length - beginning >= 2 &&
		is_digit(source->data[beginning + 1])))
		return lex_pp_number(lexer);
	return lex_pp_punctuator(lexer);
}

void pp_lexer_init(struct pp_lexer *lexer, const struct source *source,
	struct diagnostics *diagnostics)
{
	assert(source->prepared);
	*lexer = (struct pp_lexer) {
		.source = source,
		.diagnostics = diagnostics,
		.at_line_start = true,
	};
}

struct pp_token pp_lexer_next(struct pp_lexer *lexer)
{
	if (lexer->has_lookahead) {
		lexer->has_lookahead = false;
		return lexer->lookahead;
	}
	return read_pp_token(lexer);
}

struct pp_token pp_lexer_peek(struct pp_lexer *lexer)
{
	if (!lexer->has_lookahead) {
		lexer->lookahead = read_pp_token(lexer);
		lexer->has_lookahead = true;
	}
	return lexer->lookahead;
}

const char *pp_token_kind_name(enum pp_token_kind kind)
{
	switch (kind) {
	case pp_eof: return "eof";
	case pp_invalid: return "invalid";
	case pp_identifier: return "identifier";
	case pp_number: return "pp-number";
	case pp_character: return "character";
	case pp_string: return "string";
	case pp_punctuator: return "punctuator";
	case pp_other: return "other";
	case pp_newline: return "newline";
	}
	return "unknown";
}

static bool spelling_is(struct token token, const char *spelling)
{
	size_t length = strlen(spelling);

	return token.length == length &&
		memcmp(token.location.source->data + token.location.offset, spelling, length) == 0;
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

struct keyword {
	const char *spelling;
	enum token_kind kind;
};

static const struct keyword keywords[] = {
	{ "int", token_int }, { "void", token_void }, { "return", token_return },
	{ "if", token_if }, { "else", token_else }, { "while", token_while },
	{ "do", token_do }, { "for", token_for }, { "break", token_break },
	{ "continue", token_continue },
};

static struct token convert_identifier(struct token token)
{
	for (size_t i = 0; i < sizeof(keywords) / sizeof(keywords[0]); i++)
		if (spelling_is(token, keywords[i].spelling)) {
			token.kind = keywords[i].kind;
			return token;
		}
	if (is_unsupported_keyword(token))
		token.kind = token_unsupported_keyword;
	else
		token.kind = token_identifier;
	return token;
}

static struct token invalid_language_token(struct token token,
	struct diagnostics *diagnostics, const char *message)
{
	token.kind = token_invalid;
	diagnostic_error(diagnostics, token.location, message);
	return token;
}

static struct token convert_number(struct token token, struct diagnostics *diagnostics)
{
	const unsigned char *spelling = token.location.source->data + token.location.offset;
	uint64_t value = 0;
	bool overflow = false;

	for (size_t i = 0; i < token.length; i++) {
		unsigned digit;

		if (!is_digit(spelling[i]))
			return invalid_language_token(token, diagnostics,
				"unsupported numeric literal");
		digit = spelling[i] - '0';
		if (value > (UINT64_MAX - digit) / 10)
			overflow = true;
		else if (!overflow)
			value = value * 10 + digit;
	}
	if (token.length > 1 && spelling[0] == '0')
		return invalid_language_token(token, diagnostics,
			"nondecimal integer literals are not supported");
	if (overflow)
		return invalid_language_token(token, diagnostics,
			"integer literal exceeds 64 bits");
	token.kind = token_integer;
	token.integer = value;
	return token;
}

struct language_punctuator {
	const char *spelling;
	enum token_kind kind;
};

static const struct language_punctuator language_punctuators[] = {
	{ "(", token_left_paren }, { ")", token_right_paren },
	{ "{", token_left_brace }, { "}", token_right_brace },
	{ "<%", token_left_brace }, { "%>", token_right_brace },
	{ ";", token_semicolon }, { ",", token_comma },
	{ "+", token_plus }, { "-", token_minus }, { "*", token_star },
	{ "/", token_slash }, { "%", token_percent }, { "=", token_equal },
	{ "==", token_equal_equal }, { "!=", token_not_equal },
	{ "<", token_less }, { "<=", token_less_equal },
	{ ">", token_greater }, { ">=", token_greater_equal },
	{ "!", token_bang }, { "&&", token_and_and }, { "||", token_or_or },
};

static struct token convert_punctuator(struct token token, struct diagnostics *diagnostics)
{
	for (size_t i = 0; i < sizeof(language_punctuators) / sizeof(language_punctuators[0]); i++)
		if (spelling_is(token, language_punctuators[i].spelling)) {
			token.kind = language_punctuators[i].kind;
			return token;
		}
	if (spelling_is(token, "#") || spelling_is(token, "%:"))
		return invalid_language_token(token, diagnostics,
			"directive marker cannot be converted to a language token");
	return invalid_language_token(token, diagnostics, "punctuator is not supported yet");
}

struct token token_from_pp(struct pp_token input, struct diagnostics *diagnostics)
{
	struct token token = {
		.kind = token_invalid,
		.location = input.location,
		.length = input.length,
	};

	switch (input.kind) {
	case pp_eof:
		token.kind = token_eof;
		return token;
	case pp_invalid:
		return token;
	case pp_identifier:
		return convert_identifier(token);
	case pp_number:
		return convert_number(token, diagnostics);
	case pp_punctuator:
		return convert_punctuator(token, diagnostics);
	case pp_character:
		return invalid_language_token(token, diagnostics,
			"character constants are not supported yet");
	case pp_string:
		return invalid_language_token(token, diagnostics,
			"string literals are not supported yet");
	case pp_other:
		return invalid_language_token(token, diagnostics, "unsupported source byte");
	case pp_newline:
		assert(0 && "newline is not a language token");
		return token;
	}
	assert(0 && "unknown preprocessing token kind");
	return token;
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
