#include "preprocess.h"

#include <string.h>

struct macro_token {
	struct pp_token token;
	struct macro_token *next;
};

struct macro {
	struct pp_token name;
	struct macro_token *replacement;
	struct macro *next;
	size_t identity;
	bool defined;
	bool function_like;
};

static bool same_spelling(struct pp_token left, struct pp_token right)
{
	return left.kind == right.kind && left.length == right.length &&
		memcmp(left.location.source->data + left.location.offset,
			right.location.source->data + right.location.offset, left.length) == 0;
}

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
		"include", "embed", "line", "error", "warning", "pragma",
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

static struct token invalid_token(struct pp_token token)
{
	return (struct token) {
		.kind = token_invalid,
		.location = token.expansion_location,
		.spelling_location = token.location,
		.length = token.length,
	};
}

static struct token end_token(const struct preprocessor *preprocessor)
{
	const struct source *source = preprocessor->input.source;
	struct source_location location = { source, source->length };

	return (struct token) {
		.kind = token_eof,
		.location = location,
		.spelling_location = location,
	};
}

static struct token stop_preprocessing(struct preprocessor *preprocessor,
	struct pp_token token, const char *message)
{
	diagnostic_error(preprocessor->diagnostics, token.expansion_location, message);
	preprocessor->stopped = true;
	return invalid_token(token);
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
	if (message)
		diagnostic_error(preprocessor->diagnostics, token.location, message);
	finish_directive(preprocessor, token);
	return invalid_token(marker);
}

static struct macro *find_macro(struct preprocessor *preprocessor, struct pp_token name)
{
	for (struct macro *macro = preprocessor->macros; macro; macro = macro->next)
		if (same_spelling(macro->name, name))
			return macro;
	return NULL;
}

/* Reserved implementation names are deliberately outside this milestone. */
static bool is_protected_name(struct pp_token name)
{
	const unsigned char *text = name.location.source->data + name.location.offset;

	return pp_spelling_is(name, "defined") || (name.length >= 2 && text[0] == '_' &&
		(text[1] == '_' || (text[1] >= 'A' && text[1] <= 'Z')));
}

static bool same_replacement(struct macro_token *left, struct macro_token *right)
{
	bool first = true;

	while (left && right) {
		if (!same_spelling(left->token, right->token) || (!first &&
			left->token.leading_space != right->token.leading_space))
			return false;
		first = false;
		left = left->next;
		right = right->next;
	}
	return !left && !right;
}

/* function-parameters = '(' ')' (named/variadic parameters are deferred). */
static bool read_empty_parameters(struct preprocessor *preprocessor,
	struct pp_token marker, struct token *error)
{
	struct pp_token token = pp_lexer_next(&preprocessor->input);

	if (token.kind == pp_invalid) {
		*error = reject_directive(preprocessor, marker, token, NULL);
		return false;
	}
	if (token.has_non_directive_space) {
		*error = reject_directive(preprocessor, marker, token,
			"only space and tab are allowed in a preprocessing directive");
		return false;
	}
	if (token.kind == pp_punctuator && pp_spelling_is(token, ")"))
		return true;
	*error = reject_directive(preprocessor, marker, token,
		"expected ')' (macro parameters are not supported yet)");
	return false;
}

/* define-directive = '#' 'define' identifier function-parameters? replacement-list newline
 * undef-directive = '#' 'undef' identifier newline
 * replacement-list = preprocessing-token*
 * Only empty function-parameters are supported; token pasting is deferred.
 */
static bool read_macro_directive(struct preprocessor *preprocessor,
	struct pp_token marker, bool define, struct token *error)
{
	struct pp_token name = pp_lexer_next(&preprocessor->input);
	struct pp_token token;
	struct macro *macro;
	struct macro_token *replacement = NULL;
	struct macro_token **tail = &replacement;
	size_t count = 0;
	bool function_like = false;

	if (name.kind == pp_invalid) {
		*error = reject_directive(preprocessor, marker, name, NULL);
		return false;
	}
	if (name.has_non_directive_space) {
		*error = reject_directive(preprocessor, marker, name,
			"only space and tab are allowed in a preprocessing directive");
		return false;
	}
	if (name.kind != pp_identifier) {
		*error = reject_directive(preprocessor, marker, name, "expected a macro name");
		return false;
	}
	if (is_protected_name(name)) {
		*error = reject_directive(preprocessor, marker, name,
			"reserved macro names are not supported yet");
		return false;
	}
	macro = find_macro(preprocessor, name);
	token = pp_lexer_next(&preprocessor->input);
	if (define && token.kind == pp_punctuator && !token.leading_space &&
		pp_spelling_is(token, "(")) {
		function_like = true;
		if (!read_empty_parameters(preprocessor, marker, error))
			return false;
		token = pp_lexer_next(&preprocessor->input);
	} else if (define && !is_directive_end(token) && !token.leading_space &&
		token.kind != pp_invalid) {
		*error = reject_directive(preprocessor, marker, token,
			"expected whitespace before an object-like replacement list");
		return false;
	}
	for (;;) {
		struct macro_token *item;

		if (token.kind == pp_invalid) {
			*error = reject_directive(preprocessor, marker, token, NULL);
			return false;
		}
		if (token.has_non_directive_space) {
			*error = reject_directive(preprocessor, marker, token,
				"only space and tab are allowed in a preprocessing directive");
			return false;
		}
		if (is_directive_end(token))
			break;
		if (!define) {
			*error = reject_directive(preprocessor, marker, token,
				"unexpected token after macro name in #undef");
			return false;
		}
		if (token.kind == pp_punctuator &&
			(pp_spelling_is(token, "##") || pp_spelling_is(token, "%:%:"))) {
			*error = reject_directive(preprocessor, marker, token,
				"macro token pasting is not supported yet");
			return false;
		}
		if (function_like && is_directive_marker(token)) {
			*error = reject_directive(preprocessor, marker, token,
				"macro stringizing is not supported yet");
			return false;
		}
		if (count == preprocess_replacement_limit ||
			preprocessor->stored_tokens == preprocess_storage_limit) {
			*error = stop_preprocessing(preprocessor, marker,
				"macro replacement storage limit exceeded");
			return false;
		}
		item = arena_alloc(&preprocessor->storage, sizeof(*item));
		if (!item) {
			*error = stop_preprocessing(preprocessor, marker,
				"cannot allocate macro replacement token");
			return false;
		}
		*item = (struct macro_token) { .token = token };
		*tail = item;
		tail = &item->next;
		count++;
		preprocessor->stored_tokens++;
		token = pp_lexer_next(&preprocessor->input);
	}
	if (!define) {
		if (macro)
			macro->defined = false;
		return true;
	}
	if (macro && macro->defined) {
		if (macro->function_like == function_like &&
			same_replacement(macro->replacement, replacement))
			return true;
		diagnostic_error(preprocessor->diagnostics, name.location,
			"incompatible macro redefinition");
		*error = invalid_token(marker);
		return false;
	}
	if (!macro) {
		if (preprocessor->macro_count == preprocess_macro_limit) {
			*error = stop_preprocessing(preprocessor, marker, "macro name limit exceeded");
			return false;
		}
		macro = arena_alloc(&preprocessor->storage, sizeof(*macro));
		if (!macro) {
			*error = stop_preprocessing(preprocessor, marker, "cannot allocate macro");
			return false;
		}
		*macro = (struct macro) {
			.name = name,
			.next = preprocessor->macros,
			.identity = preprocessor->macro_count,
		};
		preprocessor->macros = macro;
		preprocessor->macro_count++;
	}
	macro->function_like = function_like;
	macro->replacement = replacement;
	macro->defined = true;
	return true;
}

/* control-line = '#' newline | define-directive | undef-directive
 * Other C23 control lines are recognized but not implemented yet.
 */
static bool read_directive(struct preprocessor *preprocessor,
	struct pp_token marker, struct token *error)
{
	struct pp_token token;

	if (!marker.at_line_start) {
		*error = reject_directive(preprocessor, marker, marker,
			"misplaced '#' outside a preprocessing directive");
		return false;
	}
	token = pp_lexer_next(&preprocessor->input);
	if (token.kind == pp_invalid) {
		finish_directive(preprocessor, token);
		*error = token_from_pp(token, preprocessor->diagnostics);
		return false;
	}
	if (token.has_non_directive_space) {
		*error = reject_directive(preprocessor, marker, token,
			"only space and tab are allowed in a preprocessing directive");
		return false;
	}
	if (is_directive_end(token))
		return true;
	if (token.kind != pp_identifier) {
		*error = reject_directive(preprocessor, marker, token,
			"expected a directive name or end of line after '#'");
		return false;
	}
	if (pp_spelling_is(token, "define") || pp_spelling_is(token, "undef"))
		return read_macro_directive(preprocessor, marker,
			pp_spelling_is(token, "define"), error);
	*error = reject_directive(preprocessor, marker, token,
		is_known_directive(token) ? "preprocessing directive is not supported yet" :
		"unknown preprocessing directive");
	return false;
}

static bool hide_contains(const struct macro_hide_set *hide, const struct macro *macro)
{
	size_t word = macro->identity / 64;
	uint64_t bit = UINT64_C(1) << (macro->identity % 64);

	return (hide->words[word] & bit) != 0;
}

static void hide_add(struct macro_hide_set *hide, const struct macro *macro)
{
	size_t word = macro->identity / 64;
	uint64_t bit = UINT64_C(1) << (macro->identity % 64);

	hide->words[word] |= bit;
}

static struct macro_hide_set hide_intersection(const struct macro_hide_set *left,
	const struct macro_hide_set *right)
{
	struct macro_hide_set result;

	for (size_t i = 0; i < sizeof(result.words) / sizeof(result.words[0]); i++)
		result.words[i] = left->words[i] & right->words[i];
	return result;
}

/* Each push and replacement-token visit consumes one unit, even without output. */
static bool spend_expansion_work(struct preprocessor *preprocessor,
	struct pp_token token, struct token *error)
{
	if (preprocessor->expansion_work == preprocess_work_limit) {
		*error = stop_preprocessing(preprocessor, token, "macro expansion work limit exceeded");
		return false;
	}
	preprocessor->expansion_work++;
	return true;
}

/* Read ONE unexpanded token across source/replacement stream boundaries.
 * A pending lookahead token was already visited, so never charge it twice.
 */
static bool read_rescan_token(struct preprocessor *preprocessor,
	struct rescan_token *result, struct token *error)
{
	if (preprocessor->has_pending) {
		preprocessor->has_pending = false;
		*result = preprocessor->pending;
		return true;
	}
	while (preprocessor->frame_count &&
		!preprocessor->frames[preprocessor->frame_count - 1].next)
		preprocessor->frame_count--;
	if (preprocessor->frame_count) {
		struct expansion_frame *frame =
			&preprocessor->frames[preprocessor->frame_count - 1];

		*result = (struct rescan_token) { .token = frame->next->token, .hide = frame->hide };
		frame->next = frame->next->next;
		result->token.expansion_location = frame->invocation;
		result->token.at_line_start = false;
		return spend_expansion_work(preprocessor, result->token, error);
	}
	*result = (struct rescan_token) { .from_source = true };
	do {
		result->token = pp_lexer_next(&preprocessor->input);
	} while (result->token.kind == pp_newline);
	return true;
}

/* Do not execute directives speculatively while deciding whether to invoke. */
static bool check_invocation_input(struct preprocessor *preprocessor,
	struct rescan_token input, struct token *error)
{
	if (input.token.kind == pp_invalid) {
		preprocessor->stopped = true;
		*error = invalid_token(input.token);
		return false;
	}
	if (input.from_source && is_directive_marker(input.token)) {
		*error = stop_preprocessing(preprocessor, input.token,
			"directives during macro invocation lookahead are not supported yet");
		return false;
	}
	return true;
}

/* function-invocation = identifier '(' ')'
 * Inspect the next UNEXPANDED token. A later expansion producing '(' cannot
 * retroactively invoke a bare name. Delimiters may cross replacement frames.
 */
static bool read_empty_invocation(struct preprocessor *preprocessor,
	struct rescan_token name, bool *invoked, struct macro_hide_set *hide,
	struct token *error)
{
	struct rescan_token next;

	*invoked = false;
	if (!read_rescan_token(preprocessor, &next, error) ||
		!check_invocation_input(preprocessor, next, error))
		return false;
	if (next.token.kind != pp_punctuator || !pp_spelling_is(next.token, "(")) {
		preprocessor->pending = next;
		preprocessor->has_pending = true;
		return true;
	}
	if (!read_rescan_token(preprocessor, &next, error) ||
		!check_invocation_input(preprocessor, next, error))
		return false;
	if (next.token.kind != pp_punctuator || !pp_spelling_is(next.token, ")")) {
		*error = stop_preprocessing(preprocessor, name.token,
			next.token.kind == pp_eof ? "unterminated function-like macro invocation" :
			"zero-parameter macro invocation requires no arguments");
		return false;
	}
	*invoked = true;
	/* Only identities hidden at BOTH ends of the invocation remain hidden. */
	*hide = hide_intersection(&name.hide, &next.hide);
	return true;
}

/* Rescan pp tokens before the single language conversion. Availability travels
 * with tokens even after lookahead consumes and pops their original frames.
 */
static struct token read_preprocessed_token(struct preprocessor *preprocessor)
{
	for (;;) {
		struct rescan_token input;
		struct macro *macro;
		struct macro_hide_set hide;
		struct token error;

		if (preprocessor->stopped)
			return end_token(preprocessor);
		if (!read_rescan_token(preprocessor, &input, &error))
			return error;
		if (input.from_source && is_directive_marker(input.token)) {
			if (!read_directive(preprocessor, input.token, &error))
				return error;
			continue;
		}
		macro = input.token.kind == pp_identifier ? find_macro(preprocessor, input.token) : NULL;
		if (!macro || !macro->defined || hide_contains(&input.hide, macro))
			return token_from_pp(input.token, preprocessor->diagnostics);
		hide = input.hide;
		if (macro->function_like) {
			bool invoked;

			if (!read_empty_invocation(preprocessor, input, &invoked, &hide, &error))
				return error;
			if (!invoked)
				return token_from_pp(input.token, preprocessor->diagnostics);
		}
		if (preprocessor->frame_count == preprocess_depth_limit)
			return stop_preprocessing(preprocessor, input.token,
				"macro expansion depth limit exceeded");
		if (!spend_expansion_work(preprocessor, input.token, &error))
			return error;
		hide_add(&hide, macro);
		preprocessor->frames[preprocessor->frame_count++] = (struct expansion_frame) {
			.next = macro->replacement,
			.invocation = input.token.expansion_location,
			.hide = hide,
		};
	}
}

void preprocess_init(struct preprocessor *preprocessor, const struct source *source,
	struct diagnostics *diagnostics)
{
	*preprocessor = (struct preprocessor) { .diagnostics = diagnostics };
	pp_lexer_init(&preprocessor->input, source, diagnostics);
}

void preprocess_destroy(struct preprocessor *preprocessor)
{
	arena_destroy(&preprocessor->storage);
	*preprocessor = (struct preprocessor) { 0 };
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
