#include "preprocess.h"

#include <string.h>

static bool pp_spelling_is(struct pp_token token, const char *spelling)
{
	size_t length = strlen(spelling);

	return token.length == length &&
		memcmp(token.location.source->data + token.location.offset, spelling, length) == 0;
}

static bool is_directive_marker(struct pp_token token)
{
	return token.kind == pp_punctuator &&
		(pp_spelling_is(token, "#") || pp_spelling_is(token, "%:"));
}

static bool is_known_directive(struct pp_token token)
{
	static const char *const names[] = {
		"define", "undef", "include", "embed", "line", "error", "warning", "pragma",
		"if", "ifdef", "ifndef", "elif", "elifdef", "elifndef", "else", "endif",
	};

	for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); i++)
		if (pp_spelling_is(token, names[i]))
			return true;
	return false;
}

static bool is_directive_end(struct pp_token token)
{
	return token.kind == pp_newline || token.kind == pp_eof;
}

/* Drain raw tokens, never converting a rejected directive body into C tokens. */
static void finish_directive(struct preprocessor *preprocessor, struct pp_token token)
{
	while (!is_directive_end(token))
		token = pp_lexer_next(&preprocessor->input);
}

static struct token reject_directive(struct preprocessor *preprocessor,
	struct pp_token marker, struct pp_token token, const char *message)
{
	/* Keep a nonempty error token even when bad trivia is followed by EOF. */
	struct token invalid = {
		.kind = token_invalid,
		.location = marker.location,
		.length = marker.length,
	};

	diagnostic_error(preprocessor->diagnostics, token.location, message);
	finish_directive(preprocessor, token);
	return invalid;
}

/* Return a language token, skipping raw trivia and supported null directives. */
static struct token read_preprocessed_token(struct preprocessor *preprocessor)
{
	for (;;) {
		struct pp_token token = pp_lexer_next(&preprocessor->input);
		struct pp_token marker;

		if (token.kind == pp_newline)
			continue;
		if (!is_directive_marker(token))
			return token_from_pp(token, preprocessor->diagnostics);
		marker = token;
		if (!token.at_line_start)
			return reject_directive(preprocessor, marker, token,
				"misplaced '#' outside a preprocessing directive");

		token = pp_lexer_next(&preprocessor->input);
		if (token.kind == pp_invalid) {
			/* Raw lexing already diagnosed this token. */
			finish_directive(preprocessor, token);
			return token_from_pp(token, preprocessor->diagnostics);
		}
		if (token.has_non_directive_space)
			return reject_directive(preprocessor, marker, token,
				"only space and tab are allowed in a preprocessing directive");
		if (is_directive_end(token)) {
			if (token.kind == pp_eof)
				return token_from_pp(token, preprocessor->diagnostics);
			continue;
		}
		if (token.kind != pp_identifier)
			return reject_directive(preprocessor, marker, token,
				"expected a directive name or end of line after '#'");
		if (is_known_directive(token))
			return reject_directive(preprocessor, marker, token,
				"preprocessing directive is not supported yet");
		return reject_directive(preprocessor, marker, token,
			"unknown preprocessing directive");
	}
}

void preprocess_init(struct preprocessor *preprocessor, const struct source *source,
	struct diagnostics *diagnostics)
{
	*preprocessor = (struct preprocessor) { .diagnostics = diagnostics };
	pp_lexer_init(&preprocessor->input, source, diagnostics);
}

struct token preprocess_next(struct preprocessor *preprocessor)
{
	if (preprocessor->has_lookahead) {
		preprocessor->has_lookahead = false;
		return preprocessor->lookahead;
	}
	return read_preprocessed_token(preprocessor);
}

struct token preprocess_peek(struct preprocessor *preprocessor)
{
	if (!preprocessor->has_lookahead) {
		preprocessor->lookahead = read_preprocessed_token(preprocessor);
		preprocessor->has_lookahead = true;
	}
	return preprocessor->lookahead;
}
