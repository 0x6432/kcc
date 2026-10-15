#include "preprocess.h"

#include <stdlib.h>
#include <string.h>

struct macro_token {
	struct pp_token token;
	struct macro_token *next;
	size_t parameter_index;
};

struct macro_parameter {
	struct pp_token name;
	struct macro_parameter *next;
	size_t index;
};

struct argument_token {
	struct rescan_token input;
	struct argument_token *next;
};

struct macro_argument {
	struct argument_token *raw;
	struct argument_token *expanded;
	bool expanded_ready;
};

struct macro {
	struct pp_token name;
	struct macro_token *replacement;
	struct macro_parameter *parameters;
	size_t parameter_count;
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

/* All auxiliary record kinds are bounded together, including abandoned work. */
static void *allocate_auxiliary(struct preprocessor *preprocessor, size_t count,
	size_t size, struct pp_token blame, struct token *error)
{
	void *memory;

	if (count > preprocess_auxiliary_limit - preprocessor->auxiliary_records ||
		(count && size > SIZE_MAX / count)) {
		*error = stop_preprocessing(preprocessor, blame, "macro auxiliary storage limit exceeded");
		return NULL;
	}
	memory = arena_alloc(&preprocessor->storage, count * size);
	if (!memory) {
		*error = stop_preprocessing(preprocessor, blame, "cannot allocate macro argument storage");
		return NULL;
	}
	preprocessor->auxiliary_records += count;
	return memory;
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

static size_t parameter_index(struct macro_parameter *parameters, struct pp_token name)
{
	for (; parameters; parameters = parameters->next)
		if (same_spelling(parameters->name, name))
			return parameters->index;
	return SIZE_MAX;
}

static bool same_parameters(struct macro_parameter *left, struct macro_parameter *right)
{
	while (left && right) {
		if (!same_spelling(left->name, right->name))
			return false;
		left = left->next;
		right = right->next;
	}
	return !left && !right;
}

static bool check_parameter_token(struct preprocessor *preprocessor,
	struct pp_token marker, struct pp_token token, struct token *error)
{
	if (token.kind == pp_invalid || token.has_non_directive_space) {
		*error = reject_directive(preprocessor, marker, token,
			token.kind == pp_invalid ? NULL :
			"only space and tab are allowed in a preprocessing directive");
		return false;
	}
	return true;
}

/* function-parameters = '(' (identifier (',' identifier)*)? ')' */
static bool read_parameters(struct preprocessor *preprocessor, struct pp_token marker,
	struct macro_parameter **parameters, size_t *count, struct token *error)
{
	struct pp_token token = pp_lexer_next(&preprocessor->input);
	struct macro_parameter **tail = parameters;

	if (!check_parameter_token(preprocessor, marker, token, error))
		return false;
	if (token.kind == pp_punctuator && pp_spelling_is(token, ")"))
		return true;
	for (;;) {
		struct macro_parameter *parameter;

		if (!check_parameter_token(preprocessor, marker, token, error))
			return false;
		if (token.kind != pp_identifier || pp_spelling_is(token, "__VA_ARGS__") ||
			pp_spelling_is(token, "__VA_OPT__")) {
			*error = reject_directive(preprocessor, marker, token,
				"expected a fixed macro parameter (variadics are not supported yet)");
			return false;
		}
		if (parameter_index(*parameters, token) != SIZE_MAX) {
			*error = reject_directive(preprocessor, marker, token, "duplicate macro parameter");
			return false;
		}
		if (*count == preprocess_parameter_limit) {
			*error = stop_preprocessing(preprocessor, marker, "macro parameter limit exceeded");
			return false;
		}
		parameter = allocate_auxiliary(preprocessor, 1, sizeof(*parameter), marker, error);
		if (!parameter)
			return false;
		*parameter = (struct macro_parameter) { .name = token, .index = *count };
		*tail = parameter;
		tail = &parameter->next;
		(*count)++;
		token = pp_lexer_next(&preprocessor->input);
		if (!check_parameter_token(preprocessor, marker, token, error))
			return false;
		if (token.kind == pp_punctuator && pp_spelling_is(token, ")"))
			return true;
		if (token.kind != pp_punctuator || !pp_spelling_is(token, ",")) {
			*error = reject_directive(preprocessor, marker, token,
				"expected ',' or ')' after macro parameter");
			return false;
		}
		token = pp_lexer_next(&preprocessor->input);
	}
}

/* define-directive = '#' 'define' identifier function-parameters? replacement-list newline
 * undef-directive = '#' 'undef' identifier newline
 * replacement-list = preprocessing-token*
 * Variadic parameters and token pasting remain deferred.
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
	struct macro_parameter *parameters = NULL;
	size_t parameter_count = 0;
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
		if (!read_parameters(preprocessor, marker, &parameters, &parameter_count, error))
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
		*item = (struct macro_token) {
			.token = token,
			.parameter_index = parameter_index(parameters, token),
		};
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
			same_parameters(macro->parameters, parameters) &&
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
	macro->parameters = parameters;
	macro->parameter_count = parameter_count;
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

static struct macro_hide_set hide_union(const struct macro_hide_set *left,
	const struct macro_hide_set *right)
{
	struct macro_hide_set result;

	for (size_t i = 0; i < sizeof(result.words) / sizeof(result.words[0]); i++)
		result.words[i] = left->words[i] | right->words[i];
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

static bool read_expanded_token(struct preprocessor *preprocessor,
	struct expansion_cursor *cursor, struct rescan_token *result, struct token *error);
static bool prescan_argument(struct preprocessor *preprocessor,
	struct macro_argument *argument, struct pp_token blame, struct token *error);

static struct rescan_token cursor_end(const struct expansion_cursor *cursor)
{
	return (struct rescan_token) {
		.token = {
			.kind = pp_eof,
			.location = cursor->end,
			.expansion_location = cursor->end,
		},
	};
}

static bool push_frame(struct preprocessor *preprocessor, struct expansion_cursor *cursor,
	struct expansion_frame frame, struct pp_token blame, struct token *error)
{
	if (cursor->frame_count == preprocess_depth_limit) {
		*error = stop_preprocessing(preprocessor, blame, "macro expansion depth limit exceeded");
		return false;
	}
	if (!spend_expansion_work(preprocessor, blame, error))
		return false;
	cursor->frames[cursor->frame_count++] = frame;
	return true;
}

static struct argument_token *copy_argument_token(struct preprocessor *preprocessor,
	struct rescan_token input, struct pp_token blame, struct token *error)
{
	struct argument_token *copy;

	if (!spend_expansion_work(preprocessor, blame, error))
		return NULL;
	copy = allocate_auxiliary(preprocessor, 1, sizeof(*copy), blame, error);
	if (!copy)
		return NULL;
	input.from_source = false;
	input.token.expansion_location = blame.expansion_location;
	*copy = (struct argument_token) { .input = input };
	return copy;
}

/* Read one unexpanded token. A parameter occurrence injects its prescanned
 * argument stream, retaining per-token hide bits in addition to the call base.
 */
static bool read_rescan_token(struct preprocessor *preprocessor,
	struct expansion_cursor *cursor, struct rescan_token *result, struct token *error)
{
	if (cursor->has_pending) {
		cursor->has_pending = false;
		*result = cursor->pending;
		return true;
	}
	for (;;) {
		struct expansion_frame *frame;

		while (cursor->frame_count &&
			!cursor->frames[cursor->frame_count - 1].replacement &&
			!cursor->frames[cursor->frame_count - 1].argument)
			cursor->frame_count--;
		if (!cursor->frame_count)
			break;
		frame = &cursor->frames[cursor->frame_count - 1];
		if (frame->argument) {
			*result = frame->argument->input;
			frame->argument = frame->argument->next;
			result->hide = hide_union(&result->hide, &frame->hide);
		} else {
			struct macro_token *replacement = frame->replacement;

			frame->replacement = replacement->next;
			*result = (struct rescan_token) { .token = replacement->token, .hide = frame->hide };
			result->token.expansion_location = frame->invocation;
			if (replacement->parameter_index != SIZE_MAX) {
				struct macro_argument *argument =
					&frame->arguments[replacement->parameter_index];

				if (!spend_expansion_work(preprocessor, result->token, error) ||
					!prescan_argument(preprocessor, argument, result->token, error))
					return false;
				if (argument->expanded && !push_frame(preprocessor, cursor,
					(struct expansion_frame) {
						.argument = argument->expanded,
						.invocation = frame->invocation,
						.hide = frame->hide,
					}, result->token, error))
					return false;
				continue;
			}
		}
		result->from_source = false;
		result->token.expansion_location = frame->invocation;
		result->token.at_line_start = false;
		return spend_expansion_work(preprocessor, result->token, error);
	}
	if (cursor->input) {
		*result = cursor->input->input;
		cursor->input = cursor->input->next;
		result->from_source = false;
		return spend_expansion_work(preprocessor, result->token, error);
	}
	if (!cursor->source_input) {
		*result = cursor_end(cursor);
		return true;
	}
	*result = (struct rescan_token) { .from_source = true };
	do {
		result->token = pp_lexer_next(&preprocessor->input);
	} while (result->token.kind == pp_newline);
	return true;
}

/* Source directives cannot execute speculatively inside invocation probing. */
static bool check_invocation_input(struct preprocessor *preprocessor,
	struct rescan_token input, struct token *error)
{
	if (input.token.kind == pp_invalid) {
		preprocessor->stopped = true;
		*error = invalid_token(input.token);
		return false;
	}
	if (input.from_source && input.token.at_line_start && is_directive_marker(input.token)) {
		*error = stop_preprocessing(preprocessor, input.token,
			"directives during macro invocation lookahead are not supported yet");
		return false;
	}
	return true;
}

static bool is_punctuator(struct pp_token token, const char *spelling)
{
	return token.kind == pp_punctuator && pp_spelling_is(token, spelling);
}

/* invocation = identifier '(' argument-list? ')'
 * argument-list = argument (',' argument)*
 * An argument is raw pp tokens with balanced parentheses. Only parentheses,
 * not braces/brackets or expanded tokens, protect commas during collection.
 */
static bool read_invocation(struct preprocessor *preprocessor, struct expansion_cursor *cursor,
	struct macro *macro, struct rescan_token name, bool *invoked,
	struct macro_argument **arguments, struct macro_hide_set *hide, struct token *error)
{
	struct rescan_token next;
	struct argument_token **tail = NULL;
	size_t index = 0;
	size_t parentheses = 0;

	*invoked = false;
	if (!read_rescan_token(preprocessor, cursor, &next, error) ||
		!check_invocation_input(preprocessor, next, error))
		return false;
	if (!is_punctuator(next.token, "(")) {
		cursor->pending = next;
		cursor->has_pending = true;
		return true;
	}
	if (macro->parameter_count) {
		*arguments = allocate_auxiliary(preprocessor, macro->parameter_count,
			sizeof(**arguments), name.token, error);
		if (!*arguments)
			return false;
		for (size_t i = 0; i < macro->parameter_count; i++)
			(*arguments)[i] = (struct macro_argument) { 0 };
		tail = &(*arguments)[0].raw;
	}
	for (;;) {
		struct argument_token *copy;

		if (!read_rescan_token(preprocessor, cursor, &next, error) ||
			!check_invocation_input(preprocessor, next, error))
			return false;
		if (next.token.kind == pp_eof) {
			*error = stop_preprocessing(preprocessor, name.token,
				"unterminated function-like macro invocation");
			return false;
		}
		if (!spend_expansion_work(preprocessor, name.token, error))
			return false;
		if (is_punctuator(next.token, ")") && !parentheses) {
			/* Empty () is one empty argument only when parameters exist. */
			if (macro->parameter_count && index + 1 != macro->parameter_count) {
				*error = stop_preprocessing(preprocessor, name.token,
					"macro argument count does not match parameters");
				return false;
			}
			*hide = hide_intersection(&name.hide, &next.hide);
			*invoked = true;
			return true;
		}
		if (!macro->parameter_count) {
			*error = stop_preprocessing(preprocessor, name.token,
				"zero-parameter macro invocation requires no arguments");
			return false;
		}
		if (is_punctuator(next.token, ",") && !parentheses) {
			index++;
			if (index == macro->parameter_count) {
				*error = stop_preprocessing(preprocessor, name.token,
					"macro argument count does not match parameters");
				return false;
			}
			tail = &(*arguments)[index].raw;
			continue;
		}
		if (is_punctuator(next.token, "(")) {
			if (parentheses == preprocess_parentheses_limit) {
				*error = stop_preprocessing(preprocessor, name.token,
					"macro argument parentheses limit exceeded");
				return false;
			}
			parentheses++;
		} else if (is_punctuator(next.token, ")"))
			parentheses--;
		copy = copy_argument_token(preprocessor, next, name.token, error);
		if (!copy)
			return false;
		*tail = copy;
		tail = &copy->next;
	}
}

/* Expansion stays in pp tokens, including during isolated argument prescan. */
static bool read_expanded_token(struct preprocessor *preprocessor,
	struct expansion_cursor *cursor, struct rescan_token *result, struct token *error)
{
	for (;;) {
		struct rescan_token input;
		struct macro *macro;
		struct macro_hide_set hide;
		struct macro_argument *arguments = NULL;

		if (!read_rescan_token(preprocessor, cursor, &input, error))
			return false;
		if (input.from_source && is_directive_marker(input.token)) {
			if (!read_directive(preprocessor, input.token, error))
				return false;
			continue;
		}
		macro = input.token.kind == pp_identifier ? find_macro(preprocessor, input.token) : NULL;
		if (!macro || !macro->defined || hide_contains(&input.hide, macro)) {
			*result = input;
			return true;
		}
		hide = input.hide;
		if (macro->function_like) {
			bool invoked;

			if (!read_invocation(preprocessor, cursor, macro, input, &invoked,
				&arguments, &hide, error))
				return false;
			if (!invoked) {
				*result = input;
				return true;
			}
		}
		hide_add(&hide, macro);
		if (!push_frame(preprocessor, cursor, (struct expansion_frame) {
			.replacement = macro->replacement,
			.arguments = arguments,
			.invocation = input.token.expansion_location,
			.hide = hide,
		}, input.token, error))
			return false;
	}
}

/* Prescan sees only this argument, not the source following the invocation.
 * The outer macro's hide bit is added at substitution, NOT before prescan.
 */
static bool prescan_argument(struct preprocessor *preprocessor,
	struct macro_argument *argument, struct pp_token blame, struct token *error)
{
	struct expansion_cursor *cursor;
	struct argument_token **tail = &argument->expanded;
	bool success = false;

	if (argument->expanded_ready)
		return true;
	if (preprocessor->prescan_depth == preprocess_prescan_limit) {
		*error = stop_preprocessing(preprocessor, blame, "macro argument prescan depth limit exceeded");
		return false;
	}
	cursor = malloc(sizeof(*cursor));
	if (!cursor) {
		*error = stop_preprocessing(preprocessor, blame, "cannot allocate macro prescan cursor");
		return false;
	}
	*cursor = (struct expansion_cursor) { .input = argument->raw, .end = blame.expansion_location };
	preprocessor->prescan_depth++;
	for (;;) {
		struct rescan_token input;
		struct argument_token *copy;

		if (!read_expanded_token(preprocessor, cursor, &input, error))
			break;
		if (input.token.kind == pp_eof) {
			argument->expanded_ready = true;
			success = true;
			break;
		}
		copy = copy_argument_token(preprocessor, input, blame, error);
		if (!copy)
			break;
		*tail = copy;
		tail = &copy->next;
	}
	preprocessor->prescan_depth--;
	free(cursor);
	return success;
}

static struct token read_preprocessed_token(struct preprocessor *preprocessor)
{
	struct rescan_token input;
	struct token error;

	if (preprocessor->stopped)
		return end_token(preprocessor);
	if (!read_expanded_token(preprocessor, &preprocessor->cursor, &input, &error))
		return error;
	return token_from_pp(input.token, preprocessor->diagnostics);
}

void preprocess_init(struct preprocessor *preprocessor, const struct source *source,
	struct diagnostics *diagnostics)
{
	*preprocessor = (struct preprocessor) { .diagnostics = diagnostics };
	pp_lexer_init(&preprocessor->input, source, diagnostics);
	preprocessor->cursor.source_input = true;
	preprocessor->cursor.end = (struct source_location) { source, source->length };
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
