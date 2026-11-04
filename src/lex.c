#include "lex.h"

#include <errno.h>
#include <float.h>
#include <math.h>
#include <stdlib.h>

#include <assert.h>
#include <stdio.h>
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
		.expansion_location = { lexer->source, beginning },
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
		memcmp(token.spelling_location.source->data + token.spelling_location.offset, spelling, length) == 0;
}
/* Keep unsupported C keywords out of the ordinary identifier namespace. */
static bool is_unsupported_keyword(struct token token)
{
	static const char *const keywords[] = {
		"break", "case", "const", "continue", "default",
		"do", "double", "else", "float", "for", "goto",
		"if", "inline", "restrict",
		"sizeof", "struct", "switch", "union",
		"volatile", "while", "_Alignas", "_Alignof", "_Atomic",
		"_Complex", "_Decimal32", "_Decimal64", "_Decimal128",
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
	{ "__kcc_va_start", token_kcc_va_start }, { "__kcc_va_arg", token_kcc_va_arg },
	{ "__kcc_va_copy", token_kcc_va_copy }, { "__kcc_va_end", token_kcc_va_end },
	{ "__kcc_offsetof", token_kcc_offsetof },
	{ "__kcc_atomic_fetch_add", token_kcc_atomic_fetch_add },
	{ "__kcc_atomic_fetch_sub", token_kcc_atomic_fetch_sub },
	{ "__kcc_atomic_fetch_and", token_kcc_atomic_fetch_and },
	{ "__kcc_atomic_fetch_or", token_kcc_atomic_fetch_or },
	{ "__kcc_atomic_fetch_xor", token_kcc_atomic_fetch_xor },
	{ "__kcc_atomic_exchange", token_kcc_atomic_exchange },
	{ "__kcc_atomic_load", token_kcc_atomic_load }, { "__kcc_atomic_store", token_kcc_atomic_store },
	{ "__kcc_atomic_compare_exchange", token_kcc_atomic_compare_exchange },
	{ "__kcc_atomic_is_lock_free", token_kcc_atomic_is_lock_free },
	{ "struct", token_struct }, { "union", token_union }, { "enum", token_enum },
	{ "char", token_char }, { "short", token_short }, { "_Bool", token_bool },
	{ "nullptr", token_nullptr }, { "bool", token_c23_bool }, { "true", token_true }, { "false", token_false },
	{ "_Generic", token_generic },
	{ "float", token_float }, { "double", token_double },
	{ "int", token_int }, { "signed", token_signed }, { "unsigned", token_unsigned }, { "long", token_long }, { "void", token_void }, { "return", token_return },
	{ "if", token_if }, { "else", token_else }, { "case", token_case }, { "default", token_default }, { "switch", token_switch }, { "while", token_while },
	{ "do", token_do }, { "for", token_for }, { "break", token_break },
	{ "continue", token_continue }, { "goto", token_goto }, { "const", token_const },
	{ "_Atomic", token_atomic },
	{ "_Noreturn", token_noreturn },
	{ "thread_local", token_thread_local }, { "_Thread_local", token_thread_local },
	{ "inline", token_inline }, { "extern", token_extern }, { "static", token_static }, { "auto", token_auto }, { "register", token_register }, { "typedef", token_typedef },
	{ "typeof", token_typeof }, { "typeof_unqual", token_typeof_unqual },
	{ "sizeof", token_sizeof }, { "alignas", token_alignas },
	{ "_Alignas", token_legacy_alignas }, { "alignof", token_alignof },
	{ "_Alignof", token_legacy_alignof },
	{ "static_assert", token_static_assert }, { "_Static_assert", token_legacy_static_assert },
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

static int integer_digit(unsigned char byte)
{
	if (byte >= '0' && byte <= '9')
		return byte - '0';
	if (byte >= 'a' && byte <= 'f')
		return byte - 'a' + 10;
	if (byte >= 'A' && byte <= 'F')
		return byte - 'A' + 10;
	return -1;
}

/* integer-constant = (decimal | octal | hexadecimal | binary) integer-suffix?
 * integer-suffix = unsigned-suffix (long-suffix | bit-precise-suffix)?
 *                | (long-suffix | bit-precise-suffix) unsigned-suffix?
 * long-suffix = 'l' | 'L' | 'll' | 'LL'
 * bit-precise-suffix = 'wb' | 'WB'
 * A separator must have a valid base digit on both sides.
 */
const char *parse_integer_spelling(const unsigned char *text, size_t length,
	struct integer_spelling *result)
{
	size_t offset = 0;
	size_t digits = 0;
	bool previous_digit = false;

	*result = (struct integer_spelling) { .base = 10 };
	if (!length)
		return "expected digits in integer literal";
	if (text[0] == '0') {
		result->base = 8;
		if (length > 1 && (text[1] == 'x' || text[1] == 'X')) {
			result->base = 16;
			offset = 2;
		} else if (length > 1 && (text[1] == 'b' || text[1] == 'B')) {
			result->base = 2;
			offset = 2;
		}
	}
	while (offset < length) {
		int digit = integer_digit(text[offset]);

		if (digit >= 0 && (unsigned)digit < result->base) {
			if (result->value > (UINT64_MAX - (unsigned)digit) / result->base)
				return "integer literal exceeds 64-bit range";
			result->value = result->value * result->base + (unsigned)digit;
			offset++;
			digits++;
			previous_digit = true;
			continue;
		}
		if (text[offset] == '\'') {
			int next = offset + 1 < length ? integer_digit(text[offset + 1]) : -1;

			if (!previous_digit || next < 0 || (unsigned)next >= result->base)
				return "invalid separator in integer literal";
			previous_digit = false;
			offset++;
			continue;
		}
		if (text[offset] >= '0' && text[offset] <= '9')
			return "invalid digit in integer literal";
		break;
	}
	if (!digits)
		return "expected digits in integer literal";
	if (offset < length && (text[offset] == 'u' || text[offset] == 'U')) {
		result->unsigned_suffix = true;
		offset++;
	}
	if (length - offset >= 2 &&
		((text[offset] == 'w' && text[offset + 1] == 'b') ||
		 (text[offset] == 'W' && text[offset + 1] == 'B'))) {
		result->bit_precise_suffix = true;
		offset += 2;
	} else if (offset < length && (text[offset] == 'l' || text[offset] == 'L')) {
		unsigned char first = text[offset++];

		result->long_suffix = 1;
		if (offset < length && text[offset] == first) {
			result->long_suffix = 2;
			offset++;
		}
	}
	if (!result->unsigned_suffix && offset < length && (text[offset] == 'u' || text[offset] == 'U')) {
		result->unsigned_suffix = true;
		offset++;
	}
	if (offset != length)
		return "unsupported integer suffix";
	return NULL;
}

/* Cursor begins immediately after a backslash; end excludes the quote. */
static const char *parse_byte_escape(const unsigned char *text, size_t end,
	size_t *cursor, unsigned *result)
{
	size_t offset = *cursor;
	unsigned value;
	unsigned char escape;

	if (offset == end)
		return "incomplete character escape";
	escape = text[offset++];
	switch (escape) {
	case '\'': case '"': case '?': case '\\':
		value = escape;
		break;
	case 'a': value = 7; break;
	case 'b': value = 8; break;
	case 'f': value = 12; break;
	case 'n': value = 10; break;
	case 'r': value = 13; break;
	case 't': value = 9; break;
	case 'v': value = 11; break;
	case 'x': {
		size_t digits = 0;

		value = 0;
		while (offset < end) {
			int digit = integer_digit(text[offset]);

			if (digit < 0)
				break;
			if (value > (255 - (unsigned)digit) / 16)
				return "character escape exceeds one byte";
			value = value * 16 + (unsigned)digit;
			offset++;
			digits++;
		}
		if (!digits)
			return "expected digits in hexadecimal character escape";
		break;
	}
	default:
		if (escape < '0' || escape > '7')
			return "unsupported character escape";
		value = escape - '0';
		for (size_t digits = 1; digits < 3 && offset < end; digits++) {
			unsigned char next = text[offset];

			if (next < '0' || next > '7')
				break;
			value = value * 8 + next - '0';
			offset++;
		}
		if (value > 255)
			return "character escape exceeds one byte";
		break;
	}

	*cursor = offset;
	*result = value;
	return NULL;
}

/* ordinary-character = "'" (ascii-character | simple-escape | octal-escape
 *                              | hexadecimal-escape) "'"
 * Exactly one target byte, interpreted using target signed plain char.
 */
const char *parse_character_spelling(const unsigned char *text, size_t length,
	int64_t *result)
{
	size_t offset = 1;
	size_t end;
	unsigned value;
	bool utf8 = length >= 3 && text[0] == 'u' && text[1] == '8' && text[2] == '\'';

	if (!length)
		return "expected one character in character constant";
	if (utf8)
		offset = 3;
	else if (text[0] != '\'')
		return "prefixed character constants are not supported yet";
	if (length < (utf8 ? 5u : 3u) || text[length - 1] != '\'')
		return "expected one character in character constant";
	end = length - 1;
	value = text[offset++];
	if (value == '\\') {
		const char *error = parse_byte_escape(text, end, &offset, &value);

		if (error)
			return error;
	} else if (value >= 128) {
		return "non-ASCII character constants are not supported yet";
	} else if (!value || value == '\n' || value == '\r' || value == '\'') {
		return "invalid source character in character constant";
	}
	if (offset != end)
		return "multicharacter constants are not supported yet";
	*result = utf8 || value < 128 ? (int64_t)value : (int64_t)value - 256;
	return NULL;
}

/* ordinary-string ::= '"' { ascii-byte | byte-escape } '"' */
const char *parse_string_spelling(const unsigned char *text, size_t length,
	unsigned char *output, size_t capacity, size_t *decoded_length)
{
	size_t offset = 1;
	size_t count = 0;
	size_t end;
	bool utf8 = length >= 3 && text[0] == 'u' && text[1] == '8' && text[2] == '"';

	*decoded_length = 0;
	if (!length)
		return "expected ordinary string literal";
	if (utf8)
		offset = 3;
	else if (text[0] != '"')
		return "prefixed string literals are not supported yet";
	if (length < (utf8 ? 4u : 2u) || text[length - 1] != '"')
		return "unterminated string literal";
	end = length - 1;
	while (offset < end) {
		unsigned value = text[offset++];

		if (value == '\\' && offset < end && (text[offset] == 'u' || text[offset] == 'U')) {
			unsigned digits = text[offset++] == 'u' ? 4 : 8;
			uint32_t codepoint = 0;
			unsigned char encoded[4];
			unsigned units;
			if (digits > end - offset)
				return "incomplete universal character name";
			for (unsigned i = 0; i < digits; i++) {
				int digit = integer_digit(text[offset++]);
				if (digit < 0)
					return "invalid universal character name";
				codepoint = (codepoint << 4) | (unsigned)digit;
			}
			/* Conservative subset: reject basic-set UCNs and surrogates. */
			if (codepoint < 0xa0 || codepoint > 0x10ffff ||
				(codepoint >= 0xd800 && codepoint <= 0xdfff))
				return "unsupported or invalid universal character name";
			if (codepoint < 0x800) {
				units = 2;
				encoded[0] = (unsigned char)(0xc0 | (codepoint >> 6));
				encoded[1] = (unsigned char)(0x80 | (codepoint & 0x3f));
			} else if (codepoint < 0x10000) {
				units = 3;
				encoded[0] = (unsigned char)(0xe0 | (codepoint >> 12));
				encoded[1] = (unsigned char)(0x80 | ((codepoint >> 6) & 0x3f));
				encoded[2] = (unsigned char)(0x80 | (codepoint & 0x3f));
			} else {
				units = 4;
				encoded[0] = (unsigned char)(0xf0 | (codepoint >> 18));
				encoded[1] = (unsigned char)(0x80 | ((codepoint >> 12) & 0x3f));
				encoded[2] = (unsigned char)(0x80 | ((codepoint >> 6) & 0x3f));
				encoded[3] = (unsigned char)(0x80 | (codepoint & 0x3f));
			}
			if (output && units > capacity - count)
				return "string output buffer is too small";
			if (output)
				memcpy(output + count, encoded, units);
			count += units;
			continue;
		} else if (value == '\\') {
			const char *error = parse_byte_escape(text, end, &offset, &value);

			if (error)
				return error;
		} else if (value >= 128) {
			unsigned continuation;
			unsigned char first = (unsigned char)value;
			if (!utf8)
				return "non-ASCII string bytes are not supported yet";
			if (first >= 0xc2 && first <= 0xdf) continuation = 1;
			else if (first >= 0xe0 && first <= 0xef) continuation = 2;
			else if (first >= 0xf0 && first <= 0xf4) continuation = 3;
			else return "invalid UTF-8 string sequence";
			if (continuation > end - offset)
				return "truncated UTF-8 string sequence";
			for (unsigned i = 0; i < continuation; i++) {
				unsigned char next = text[offset + i];
				if (next < 0x80 || next > 0xbf ||
					(i == 0 && ((first == 0xe0 && next < 0xa0) ||
					(first == 0xed && next > 0x9f) || (first == 0xf0 && next < 0x90) ||
					(first == 0xf4 && next > 0x8f))))
					return "invalid UTF-8 string sequence";
			}
			if (output && continuation + 1 > capacity - count)
				return "string output buffer is too small";
			if (output) {
				output[count] = first;
				memcpy(output + count + 1, text + offset, continuation);
			}
			count += continuation + 1;
			offset += continuation;
			continue;
		} else if (!value || value == '\n' || value == '\r' || value == '"') {
			return "invalid source byte in string literal";
		}
		if (output) {
			if (count == capacity)
				return "string output buffer is too small";
			output[count] = (unsigned char)value;
		}
		count++;
	}
	*decoded_length = count;
	return NULL;
}

static struct token convert_string(struct token token, struct diagnostics *diagnostics)
{
	const unsigned char *text = token.spelling_location.source->data + token.spelling_location.offset;
	const char *error = parse_string_spelling(text, token.length, NULL, 0, &token.string_length);

	if (error)
		return invalid_language_token(token, diagnostics, error);
	token.kind = token_string;
	token.string_utf8 = token.length >= 3 && text[0] == 'u' && text[1] == '8' && text[2] == '"';
	return token;
}

static struct token convert_character(struct token token, struct diagnostics *diagnostics)
{
	const unsigned char *text = token.spelling_location.source->data + token.spelling_location.offset;
	const char *error = parse_character_spelling(text, token.length, &token.character);

	if (error)
		return invalid_language_token(token, diagnostics, error);
	token.kind = token_character;
	token.character_utf8 = token.length >= 3 && text[0] == 'u' && text[1] == '8' && text[2] == '\'';
	return token;
}

/* Parse only C decimal/hex floating forms, avoiding strtod extensions and
 * locale-sensitive spellings. Conversion assumes the host's IEEE formats and
 * C locale; out-of-range results are rejected rather than silently changed. */
static struct token convert_floating(struct token token, struct diagnostics *diagnostics)
{
	const unsigned char *text = token.spelling_location.source->data + token.spelling_location.offset;
	char buf[4097], *end;
	size_t n = token.length, i = 0, digits = 0;
	bool hex = n >= 2 && text[0] == '0' && (text[1] == 'x' || text[1] == 'X');
	bool dot = false, exponent = false, single = false;
	if (n > 4096 || !n)
		return invalid_language_token(token, diagnostics, "floating literal exceeds spelling limit");
	if (hex) i = 2;
	while (i < n) {
		int d = integer_digit(text[i]);
		if (d >= 0 && d < (hex ? 16 : 10)) { digits++; i++; continue; }
		if (text[i] == '\'') {
			int before = i ? integer_digit(text[i - 1]) : -1;
			int after = i + 1 < n ? integer_digit(text[i + 1]) : -1;
			int base = hex ? 16 : 10;
			if (before < 0 || before >= base || after < 0 || after >= base)
				goto invalid;
			i++;
			continue;
		}
		if (text[i] == '.' && !dot) { dot = true; i++; continue; }
		break;
	}
	if (!digits) goto invalid;
	if (i < n && (hex ? (text[i] == 'p' || text[i] == 'P') : (text[i] == 'e' || text[i] == 'E'))) {
		size_t first;
		exponent = true; i++;
		if (i < n && (text[i] == '+' || text[i] == '-')) i++;
		first = i;
		while (i < n) {
			if (text[i] >= '0' && text[i] <= '9') { i++; continue; }
			if (text[i] == '\'' && i > first && i + 1 < n &&
				text[i - 1] >= '0' && text[i - 1] <= '9' &&
				text[i + 1] >= '0' && text[i + 1] <= '9') { i++; continue; }
			break;
		}
		if (first == i) goto invalid;
	}
	if ((hex && !exponent) || (!hex && !dot && !exponent)) goto invalid;
	if (i < n && (text[i] == 'f' || text[i] == 'F')) { single = true; i++; }
	if (i != n) goto invalid;
	/* The host conversion functions do not recognize C23 separators. */
	{
		size_t length = 0;
		for (size_t j = 0; j < n - (single ? 1u : 0u); j++)
			if (text[j] != '\'') buf[length++] = (char)text[j];
		buf[length] = 0;
	}
	errno = 0;
	if (single) {
		float v = strtof(buf, &end);
		uint32_t bits;
		if (errno || *end || !isfinite(v)) goto range;
		memcpy(&bits, &v, sizeof(bits));
		token.floating_bits = bits;
	} else {
		double v = strtod(buf, &end);
		if (errno || *end || !isfinite(v)) goto range;
		memcpy(&token.floating_bits, &v, sizeof(v));
	}
	token.kind = token_floating;
	token.floating_single = single;
	return token;
invalid:
	return invalid_language_token(token, diagnostics, "invalid or unsupported floating literal");
range:
	return invalid_language_token(token, diagnostics, "floating literal outside supported range");
}

_Static_assert(FLT_RADIX == 2 && FLT_MANT_DIG == 24 && DBL_MANT_DIG == 53 &&
	sizeof(float) == 4 && sizeof(double) == 8, "IEEE binary32/binary64 host required");

static struct token convert_number(struct token token, struct diagnostics *diagnostics)
{
	const unsigned char *text = token.spelling_location.source->data + token.spelling_location.offset;
	bool hex = token.length >= 2 && text[0] == '0' && (text[1] == 'x' || text[1] == 'X');
	struct integer_spelling spelling;
	const char *error;
	for (size_t i = 0; i < token.length; i++)
		if (text[i] == '.' || (hex ? (text[i] == 'p' || text[i] == 'P') : (text[i] == 'e' || text[i] == 'E')))
			return convert_floating(token, diagnostics);
	error = parse_integer_spelling(text, token.length, &spelling);
	if (error) {
		char message[128];
		snprintf(message, sizeof(message), "unsupported numeric literal: %s", error);
		return invalid_language_token(token, diagnostics, message);
	}
	if (spelling.bit_precise_suffix)
		return invalid_language_token(token, diagnostics,
			"bit-precise integer literals are not supported yet");
	token.kind = token_integer;
	token.integer = spelling.value;
	token.integer_base = spelling.base;
	token.integer_long_suffix = spelling.long_suffix;
	token.integer_unsigned_suffix = spelling.unsigned_suffix;
	return token;
}

struct language_punctuator {
	const char *spelling;
	enum token_kind kind;
};

static const struct language_punctuator language_punctuators[] = {
	{ ".", token_dot }, { "...", token_ellipsis }, { "->", token_arrow },
	{ "(", token_left_paren }, { ")", token_right_paren },
	{ "[", token_left_bracket }, { "]", token_right_bracket },
	{ "<:", token_left_bracket }, { ":>", token_right_bracket },
	{ "{", token_left_brace }, { "}", token_right_brace },
	{ "<%", token_left_brace }, { "%>", token_right_brace },
	{ ";", token_semicolon }, { ",", token_comma },
	{ "?", token_question }, { ":", token_colon },
	{ "++", token_increment }, { "--", token_decrement },
	{ "+=", token_plus_equal }, { "-=", token_minus_equal },
	{ "*=", token_star_equal },
	{ "/=", token_slash_equal },
	{ "%=", token_percent_equal },
	{ "&=", token_ampersand_equal },
	{ "^=", token_caret_equal },
	{ "|=", token_pipe_equal },
	{ "<<=", token_shift_left_equal },
	{ ">>=", token_shift_right_equal },
	{ "+", token_plus }, { "-", token_minus }, { "*", token_star },
	{ "/", token_slash }, { "%", token_percent }, { "=", token_equal },
	{ "==", token_equal_equal }, { "!=", token_not_equal },
	{ "<", token_less }, { "<=", token_less_equal },
	{ ">", token_greater }, { ">=", token_greater_equal },
	{ "!", token_bang }, { "&&", token_and_and }, { "||", token_or_or },
	{ "~", token_tilde }, { "&", token_ampersand }, { "^", token_caret },
	{ "|", token_pipe }, { "<<", token_shift_left }, { ">>", token_shift_right },
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
		.location = input.expansion_location,
		.spelling_location = input.location,
		.length = input.length,
	};

	switch (input.kind) {
	case pp_eof:
		token.kind = token_eof;
		return token;
	case pp_invalid:
		return token;
	case pp_identifier:
		/* Do not let the parser, type system or ABI mistake this reserved
		 * type keyword for an implemented integer type. Preprocessing itself
		 * still sees the unchanged identifier token. */
		if (spelling_is(token, "_BitInt"))
			return invalid_language_token(token, diagnostics,
				"_BitInt types and their ABI are not supported yet");
		return convert_identifier(token);
	case pp_number:
		return convert_number(token, diagnostics);
	case pp_punctuator:
		return convert_punctuator(token, diagnostics);
	case pp_character:
		return convert_character(token, diagnostics);
	case pp_string:
		return convert_string(token, diagnostics);
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
	case token_floating: return "floating";
	case token_float: return "float";
	case token_double: return "double";
	case token_string: return "string";
	case token_character: return "character";
	case token_int: return "int";
	case token_signed: return "signed";
	case token_unsigned: return "unsigned";
	case token_long: return "long";
	case token_char: return "char";
	case token_short: return "short";
	case token_bool: return "_Bool";
	case token_c23_bool: return "bool";
	case token_true: return "true";
	case token_false: return "false";
	case token_nullptr: return "nullptr";
	case token_void: return "void";
	case token_const: return "const";
	case token_atomic: return "_Atomic";
	case token_typedef: return "typedef";
	case token_register: return "register";
	case token_extern: return "extern";
	case token_static: return "static";
	case token_thread_local: return "thread_local";
	case token_inline: return "inline";
	case token_auto: return "auto";
	case token_typeof: return "typeof";
	case token_typeof_unqual: return "typeof_unqual";
	case token_sizeof: return "sizeof";
	case token_alignas: return "alignas";
	case token_legacy_alignas: return "_Alignas";
	case token_alignof: return "alignof";
	case token_legacy_alignof: return "_Alignof";
	case token_static_assert: return "static_assert";
	case token_legacy_static_assert: return "_Static_assert";
	case token_return: return "return";
	case token_if: return "if";
	case token_else: return "else";
	case token_case: return "case";
	case token_default: return "default";
	case token_switch: return "switch";
	case token_while: return "while";
	case token_do: return "do";
	case token_for: return "for";
	case token_break: return "break";
	case token_continue: return "continue";
	case token_goto: return "goto";
	case token_left_paren: return "(";
	case token_right_paren: return ")";
	case token_left_bracket: return "[";
	case token_right_bracket: return "]";
	case token_left_brace: return "{";
	case token_right_brace: return "}";
	case token_semicolon: return ";";
	case token_comma: return ",";
	case token_question: return "?";
	case token_colon: return ":";
	case token_increment: return "++";
	case token_decrement: return "--";
	case token_star_equal: return "*=";
	case token_slash_equal: return "/=";
	case token_percent_equal: return "%=";
	case token_ampersand_equal: return "&=";
	case token_caret_equal: return "^=";
	case token_pipe_equal: return "|=";
	case token_shift_left_equal: return "<<=";
	case token_shift_right_equal: return ">>=";
	case token_plus_equal: return "+=";
	case token_minus_equal: return "-=";
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
	case token_tilde: return "~";
	case token_ampersand: return "&";
	case token_caret: return "^";
	case token_pipe: return "|";
	case token_shift_left: return "<<";
	case token_shift_right: return ">>";
	case token_and_and: return "&&";
	case token_or_or: return "||";
	case token_struct: return "struct";
	case token_enum: return "enum";
	case token_union: return "union";
	case token_dot: return ".";
	case token_ellipsis: return "...";
	case token_kcc_va_start: return "__kcc_va_start";
	case token_kcc_va_arg: return "__kcc_va_arg";
	case token_kcc_va_copy: return "__kcc_va_copy";
	case token_kcc_va_end: return "__kcc_va_end";
	case token_kcc_offsetof: return "__kcc_offsetof";
	case token_kcc_atomic_fetch_add: return "__kcc_atomic_fetch_add";
	case token_kcc_atomic_fetch_sub: return "__kcc_atomic_fetch_sub";
	case token_kcc_atomic_fetch_and: return "__kcc_atomic_fetch_and";
	case token_kcc_atomic_fetch_or: return "__kcc_atomic_fetch_or";
	case token_kcc_atomic_fetch_xor: return "__kcc_atomic_fetch_xor";
	case token_kcc_atomic_exchange: return "__kcc_atomic_exchange";
	case token_kcc_atomic_load: return "__kcc_atomic_load";
	case token_kcc_atomic_store: return "__kcc_atomic_store";
	case token_kcc_atomic_compare_exchange: return "__kcc_atomic_compare_exchange";
	case token_kcc_atomic_is_lock_free: return "__kcc_atomic_is_lock_free";
	case token_generic: return "_Generic";
	case token_noreturn: return "_Noreturn";
	case token_arrow: return "->";
	}
	return "unknown";
}
