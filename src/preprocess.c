#include "preprocess.h"

#include <assert.h>
#include <stdlib.h>
#include <string.h>

struct include_source {
	struct source source;
	struct include_source *next;
};

struct macro_token {
	struct pp_token token;
	struct macro_token *next;
	struct macro_token *va_opt_end;
	size_t parameter_index;
	bool va_opt_close;
	bool stringize;
	bool optional_has_paste;
};

struct macro_parameter {
	struct pp_token name;
	struct macro_parameter *next;
	size_t index;
};

struct argument_token {
	struct rescan_token input;
	struct argument_token *next;
	bool placemarker;
	bool paste_operator;
};

struct macro_argument {
	struct argument_token *raw;
	struct argument_token *expanded;
	bool expanded_ready;
	bool trailing_space;
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
	bool variadic;
	bool has_paste;
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

static bool is_variadic_identifier(struct pp_token token)
{
	return token.kind == pp_identifier &&
		(pp_spelling_is(token, "__VA_ARGS__") || pp_spelling_is(token, "__VA_OPT__"));
}

static bool is_directive_marker(struct pp_token token)
{
	return token.kind == pp_punctuator &&
		(pp_spelling_is(token, "#") || pp_spelling_is(token, "%:"));
}

static bool is_paste_operator(struct pp_token token)
{
	return token.kind == pp_punctuator &&
		(pp_spelling_is(token, "##") || pp_spelling_is(token, "%:%:"));
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

/* function-parameters = '(' ')' | '(' '...' ')'
 *                     | '(' identifier (',' identifier)* (',' '...')? ')'
 */
static bool read_parameters(struct preprocessor *preprocessor, struct pp_token marker,
	struct macro_parameter **parameters, size_t *count, bool *variadic, struct token *error)
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
		if (token.kind == pp_punctuator && pp_spelling_is(token, "...")) {
			token = pp_lexer_next(&preprocessor->input);
			if (!check_parameter_token(preprocessor, marker, token, error))
				return false;
			if (token.kind != pp_punctuator || !pp_spelling_is(token, ")")) {
				*error = reject_directive(preprocessor, marker, token,
					"expected ')' after variadic ellipsis");
				return false;
			}
			*variadic = true;
			return true;
		}
		if (token.kind != pp_identifier || is_variadic_identifier(token)) {
			*error = reject_directive(preprocessor, marker, token,
				"expected a macro parameter or final ellipsis");
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

/* va-opt-replacement = '__VA_OPT__' '(' preprocessing-token* ')'
 * Match parentheses iteratively; nested optional regions are a constraint error.
 * Preserve all raw tokens for redefinition comparison and future #/## work.
 */
static bool validate_optional_replacements(struct preprocessor *preprocessor,
	struct pp_token marker, struct macro_token *replacement, struct token *error)
{
	for (struct macro_token *item = replacement; item; item = item->next) {
		struct macro_token *end;
		size_t depth = 1;

		if (!pp_spelling_is(item->token, "__VA_OPT__"))
			continue;
		if (!item->next || item->next->token.kind != pp_punctuator ||
			!pp_spelling_is(item->next->token, "(")) {
			*error = invalid_token(marker);
			diagnostic_error(preprocessor->diagnostics, item->token.location,
				"expected '(' after __VA_OPT__");
			return false;
		}
		for (end = item->next->next; end; end = end->next) {
			if (is_paste_operator(end->token))
				item->optional_has_paste = true;
			if (pp_spelling_is(end->token, "__VA_OPT__")) {
				*error = invalid_token(marker);
				diagnostic_error(preprocessor->diagnostics, end->token.location,
					"nested __VA_OPT__ is not allowed");
				return false;
			}
			if (end->token.kind == pp_punctuator && pp_spelling_is(end->token, "("))
				depth++;
			else if (end->token.kind == pp_punctuator && pp_spelling_is(end->token, ")"))
				depth--;
			if (!depth)
				break;
		}
		if (!end) {
			*error = invalid_token(marker);
			diagnostic_error(preprocessor->diagnostics, item->token.location,
				"unterminated __VA_OPT__ replacement");
			return false;
		}
		item->va_opt_end = end;
		end->va_opt_close = true;
		item = end;
	}
	return true;
}

/* stringizing = ('#' | '%:') (parameter | va-opt-replacement)
 * Optional operands are validated and substituted before ordinary rescanning.
 */
static bool validate_stringizing(struct preprocessor *preprocessor,
	struct pp_token marker, struct macro_token *replacement, struct token *error)
{
	for (struct macro_token *item = replacement; item; item = item->next) {
		if (!is_directive_marker(item->token))
			continue;
		if (!item->next || item->next->parameter_index == SIZE_MAX) {
			diagnostic_error(preprocessor->diagnostics, item->token.location,
				"expected a macro parameter after stringizing operator");
			*error = invalid_token(marker);
			return false;
		}
		item->stringize = true;
		item->parameter_index = item->next->parameter_index;
	}
	return true;
}

/* paste-range = operand ('##' operand | operand)*
 * Optional bodies form independent replacement ranges with the same constraints.
 */
static bool validate_pastes(struct preprocessor *preprocessor, struct pp_token marker,
	struct macro_token *first, struct macro_token *end, struct token *error)
{
	bool operand = false;

	for (struct macro_token *item = first; item != end;) {
		struct macro_token *after = item->next;
		struct macro_token *optional = item->stringize ? item->next : item;

		if (is_paste_operator(item->token)) {
			if (!operand || after == end || is_paste_operator(after->token)) {
				diagnostic_error(preprocessor->diagnostics, item->token.location,
					"token pasting requires an operand on both sides");
				*error = invalid_token(marker);
				return false;
			}
			operand = false;
		} else {
			operand = true;
			if (optional->va_opt_end) {
				if (!validate_pastes(preprocessor, marker, optional->next->next,
					optional->va_opt_end, error))
					return false;
				after = optional->va_opt_end->next;
			} else if (item->stringize)
				after = optional->next;
		}
		item = after;
	}
	return true;
}

/* define-directive = '#' 'define' identifier function-parameters? replacement-list newline
 * undef-directive = '#' 'undef' identifier newline
 * replacement-list = preprocessing-token*
 * Operator results are rescanned only after substitution and paste resolution.
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
	bool variadic = false;
	bool has_paste = false;

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
		if (!read_parameters(preprocessor, marker, &parameters, &parameter_count, &variadic, error))
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
		if (is_variadic_identifier(token) && !variadic) {
			*error = reject_directive(preprocessor, marker, token,
				"variadic identifiers require a variadic macro replacement list");
			return false;
		}
		if (is_paste_operator(token))
			has_paste = true;
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
			.parameter_index = is_variadic_identifier(token) ? parameter_count :
				parameter_index(parameters, token),
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
	if (!validate_optional_replacements(preprocessor, marker, replacement, error) ||
		(function_like && !validate_stringizing(preprocessor, marker, replacement, error)) ||
		!validate_pastes(preprocessor, marker, replacement, NULL, error))
		return false;
	if (macro && macro->defined) {
		if (macro->function_like == function_like && macro->variadic == variadic &&
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
	macro->variadic = variadic;
	macro->has_paste = has_paste;
	macro->replacement = replacement;
	macro->defined = true;
	return true;
}

static bool conditional_active(const struct preprocessor *preprocessor)
{
	return !preprocessor->conditional_count ||
		preprocessor->conditionals[preprocessor->conditional_count - 1].active;
}

static bool is_conditional_directive(struct pp_token name)
{
	static const char *const names[] = {
		"if", "ifdef", "ifndef", "elif", "elifdef", "elifndef", "else", "endif",
	};

	for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); i++)
		if (pp_spelling_is(name, names[i]))
			return true;
	return false;
}

/* macro-condition = identifier newline
 * The identifier is looked up as written, not macro-expanded.
 */
static bool read_macro_condition(struct preprocessor *preprocessor,
	struct pp_token marker, bool negate, bool *value, struct token *error)
{
	struct pp_token operand = pp_lexer_next(&preprocessor->input);
	struct pp_token end;
	struct macro *macro;

	if (operand.kind == pp_invalid || operand.has_non_directive_space) {
		*error = reject_directive(preprocessor, marker, operand,
			operand.kind == pp_invalid ? NULL :
			"only space and tab are allowed in a preprocessing directive");
		return false;
	}
	if (operand.kind != pp_identifier) {
		*error = reject_directive(preprocessor, marker, operand,
			"expected exactly one identifier in macro condition");
		return false;
	}
	end = pp_lexer_next(&preprocessor->input);
	if (end.kind == pp_invalid || end.has_non_directive_space || !is_directive_end(end)) {
		*error = reject_directive(preprocessor, marker, end,
			end.kind == pp_invalid ? NULL :
			"expected end of line after conditional directive");
		return false;
	}
	macro = find_macro(preprocessor, operand);
	*value = macro && macro->defined;
	if (negate)
		*value = !*value;
	return true;
}

static bool read_expression_condition(struct preprocessor *preprocessor,
	struct pp_token marker, bool *value, struct token *error);

/* conditional-control = '#' ('ifdef' | 'ifndef' | 'elifdef' | 'elifndef') macro-condition
 *                     | '#' ('else' | 'endif') newline
 *                     | '#' ('if' | 'elif') expression-condition
 * Excluded conditions are structural only and do not expand their operands.
 */
static bool read_conditional_directive(struct preprocessor *preprocessor,
	struct pp_token marker, struct pp_token name, struct token *error)
{
	bool opening = pp_spelling_is(name, "if") || pp_spelling_is(name, "ifdef") ||
		pp_spelling_is(name, "ifndef");
	bool closing = pp_spelling_is(name, "endif");
	bool otherwise = pp_spelling_is(name, "else");
	bool expression = pp_spelling_is(name, "if") || pp_spelling_is(name, "elif");
	bool negate = pp_spelling_is(name, "ifndef") || pp_spelling_is(name, "elifndef");
	struct conditional_group *group = NULL;
	bool parent_active;
	bool evaluate;
	bool selected = false;

	if (opening) {
		if (preprocessor->conditional_count == preprocess_conditional_limit) {
			*error = stop_preprocessing(preprocessor, marker,
				"conditional nesting limit (128) exceeded");
			return false;
		}
		parent_active = conditional_active(preprocessor);
		evaluate = parent_active;
	} else {
		if (preprocessor->conditional_count == preprocessor->conditional_base) {
			*error = reject_directive(preprocessor, marker, name,
				"conditional directive has no matching opener");
			return false;
		}
		group = &preprocessor->conditionals[preprocessor->conditional_count - 1];
		if (!closing && group->seen_else) {
			*error = reject_directive(preprocessor, marker, name,
				"conditional alternative follows #else");
			return false;
		}
		parent_active = group->parent_active;
		evaluate = parent_active && !group->branch_taken;
	}
	if (closing || otherwise) {
		struct pp_token end = pp_lexer_next(&preprocessor->input);

		if (end.kind == pp_invalid || end.has_non_directive_space || !is_directive_end(end)) {
			*error = reject_directive(preprocessor, marker, end,
				end.kind == pp_invalid ? NULL :
				"expected end of line after conditional directive");
			return false;
		}
		selected = evaluate;
	} else if (!evaluate) {
		finish_directive(preprocessor, pp_lexer_next(&preprocessor->input));
	} else if (expression) {
		if (!read_expression_condition(preprocessor, marker, &selected, error))
			return false;
	} else if (!read_macro_condition(preprocessor, marker, negate, &selected, error))
		return false;
	if (opening) {
		group = &preprocessor->conditionals[preprocessor->conditional_count++];
		*group = (struct conditional_group) {
			.opening = marker.location,
			.parent_active = parent_active,
			.active = parent_active && selected,
			.branch_taken = selected,
		};
	} else if (closing)
		preprocessor->conditional_count--;
	else {
		group->active = parent_active && selected;
		group->branch_taken |= selected;
		group->seen_else = otherwise;
	}
	return true;
}

/* diagnostic-directive = '#' ('error' | 'warning') pp-tokens? newline
 * The body is a raw pp-token sequence, never a macro expansion or C expression.
 */
static bool read_diagnostic_directive(struct preprocessor *preprocessor,
	struct pp_token marker, struct pp_token name, struct token *error)
{
	bool warning = pp_spelling_is(name, "warning");
	const char *prefix = warning ? "#warning:" : "#error:";
	const struct source *source = name.location.source;
	size_t used = strlen(prefix);
	size_t capacity = source->length - name.location.offset + used + 1;
	char *message = malloc(capacity);
	struct pp_token token;

	if (!message) {
		*error = stop_preprocessing(preprocessor, marker,
			"cannot allocate directive diagnostic text");
		return false;
	}
	memcpy(message, prefix, used);
	for (;;) {
		token = pp_lexer_next(&preprocessor->input);
		if (token.kind == pp_invalid || token.has_non_directive_space) {
			free(message);
			*error = reject_directive(preprocessor, marker, token,
				token.kind == pp_invalid ? NULL :
				"only space and tab are allowed in a preprocessing directive");
			return false;
		}
		if (is_directive_end(token))
			break;
		/* Tokens are disjoint source slices; each separator replaces a gap. */
		assert(used + 1 + token.length < capacity);
		if (used == strlen(prefix) || token.leading_space)
			message[used++] = ' ';
		memcpy(message + used, source->data + token.location.offset, token.length);
		used += token.length;
	}
	message[used] = 0;
	if (warning)
		diagnostic_warning(preprocessor->diagnostics, name.location, message);
	else
		diagnostic_error(preprocessor->diagnostics, name.location, message);
	free(message);
	if (warning)
		return true;
	*error = invalid_token(marker);
	return false;
}

static bool expand_include_operand(struct preprocessor *preprocessor,
	struct pp_token marker, struct pp_token *header, struct token *error);

/* include-directive = '#' 'include' include-operand
 * The isolated operand must expand to one quoted name; no escape decoding.
 */
static bool read_include_directive(struct preprocessor *preprocessor,
	struct pp_token marker, struct token *error)
{
	struct pp_token name;
	const struct source *parent = marker.location.source;
	const unsigned char *text;
	struct include_source *child;
	size_t directory_length = 0;
	size_t name_length;
	char path[preprocess_include_path_limit];

	if (!expand_include_operand(preprocessor, marker, &name, error))
		return false;
	text = name.location.source->data + name.location.offset;
	if (name.kind != pp_string || name.length < 3 || text[0] != '"') {
		diagnostic_error(preprocessor->diagnostics, name.expansion_location,
			"include operand must expand to one nonempty unprefixed quoted name");
		*error = invalid_token(marker);
		return false;
	}
	name_length = name.length - 2;
	for (size_t i = 1; i <= name_length; i++)
		if (text[i] == '\\') {
			diagnostic_error(preprocessor->diagnostics, name.expansion_location,
				"backslashes in quoted include names are not supported yet");
			*error = invalid_token(marker);
			return false;
		}
	if (text[1] != '/') {
		const char *slash = strrchr(parent->name, '/');

		if (slash)
			directory_length = (size_t)(slash - parent->name) + 1;
	}
	if (directory_length >= sizeof(path) || name_length >= sizeof(path) - directory_length) {
		*error = stop_preprocessing(preprocessor, name, "quoted include path limit exceeded");
		return false;
	}
	memcpy(path, parent->name, directory_length);
	memcpy(path + directory_length, text + 1, name_length);
	path[directory_length + name_length] = 0;
	if (!preprocessor->include_loader) {
		diagnostic_error(preprocessor->diagnostics, name.expansion_location,
			"quoted includes require a configured source loader");
		*error = invalid_token(marker);
		return false;
	}
	if (preprocessor->include_depth == preprocess_include_depth_limit) {
		*error = stop_preprocessing(preprocessor, name, "include nesting limit (32) exceeded");
		return false;
	}
	if (preprocessor->include_count == preprocess_include_count_limit) {
		*error = stop_preprocessing(preprocessor, name, "include attempt limit (128) exceeded");
		return false;
	}
	child = allocate_auxiliary(preprocessor, 1, sizeof(*child), name, error);
	if (!child)
		return false;
	*child = (struct include_source) { 0 };
	preprocessor->include_count++;
	if (!preprocessor->include_loader(preprocessor->include_context, &child->source, path)) {
		char message[preprocess_include_path_limit + 64];

		snprintf(message, sizeof(message), "cannot load quoted include '%s'", path);
		diagnostic_error(preprocessor->diagnostics, name.expansion_location, message);
		source_destroy(&child->source);
		*error = invalid_token(marker);
		return false;
	}
	if (child->source.length > preprocess_include_bytes_limit - preprocessor->include_bytes) {
		source_destroy(&child->source);
		*error = stop_preprocessing(preprocessor, name, "include input byte limit exceeded");
		return false;
	}
	preprocessor->include_bytes += child->source.length;
	if (!source_prepare(&child->source)) {
		source_destroy(&child->source);
		*error = stop_preprocessing(preprocessor, name, "cannot prepare quoted include source");
		return false;
	}
	child->next = preprocessor->include_sources;
	preprocessor->include_sources = child;
	preprocessor->include_frames[preprocessor->include_depth++] = (struct include_frame) {
		.parent = preprocessor->input,
		.conditional_base = preprocessor->conditional_base,
	};
	preprocessor->conditional_base = preprocessor->conditional_count;
	pp_lexer_init(&preprocessor->input, &child->source, preprocessor->diagnostics);
	preprocessor->cursor.deferred_space = true;
	return true;
}

/* control-line = '#' newline | define-directive | undef-directive | diagnostic-directive
 *              | include-directive
 *              | conditional-control
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
	if (token.kind == pp_identifier && is_conditional_directive(token))
		return read_conditional_directive(preprocessor, marker, token, error);
	if (!conditional_active(preprocessor)) {
		finish_directive(preprocessor, token);
		return true;
	}
	if (token.kind != pp_identifier) {
		*error = reject_directive(preprocessor, marker, token,
			"expected a directive name or end of line after '#'");
		return false;
	}
	if (pp_spelling_is(token, "include"))
		return read_include_directive(preprocessor, marker, error);
	if (pp_spelling_is(token, "define") || pp_spelling_is(token, "undef"))
		return read_macro_directive(preprocessor, marker,
			pp_spelling_is(token, "define"), error);
	if (pp_spelling_is(token, "error") || pp_spelling_is(token, "warning"))
		return read_diagnostic_directive(preprocessor, marker, token, error);
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

/* The byte budget includes quotes and NUL, across all retained spellings. */
static bool add_stringizing_bytes(struct preprocessor *preprocessor, size_t *length,
	size_t amount, struct pp_token blame, struct token *error)
{
	size_t remaining = preprocess_spelling_limit - preprocessor->spelling_bytes;

	if (amount > remaining - *length) {
		*error = stop_preprocessing(preprocessor, blame, "macro synthesized spelling limit exceeded");
		return false;
	}
	*length += amount;
	return true;
}

/* Arena-owned view: callers fill logical bytes and never source_destroy it. */
static struct source *allocate_spelling(struct preprocessor *preprocessor, size_t length,
	struct pp_token blame, struct token *error)
{
	struct source *spelling;
	unsigned char *text;

	if (length > preprocess_spelling_limit - preprocessor->spelling_bytes) {
		*error = stop_preprocessing(preprocessor, blame, "macro synthesized spelling limit exceeded");
		return NULL;
	}
	spelling = allocate_auxiliary(preprocessor, 1, sizeof(*spelling), blame, error);
	if (!spelling)
		return NULL;
	text = arena_alloc(&preprocessor->storage, length);
	if (!text) {
		*error = stop_preprocessing(preprocessor, blame, "cannot allocate synthesized spelling");
		return NULL;
	}
	*spelling = (struct source) {
		.name = "<macro spelling>", .data = text, .length = length - 1,
		.physical_length = length - 1, .prepared = true,
	};
	preprocessor->spelling_bytes += length;
	return spelling;
}

/* Stringize raw tokens, not the prescan cache. Two bounded passes avoid a
 * growing temporary buffer; literal-token quotes/backslashes alone are escaped.
 */
static bool stringize_argument(struct preprocessor *preprocessor,
	const struct macro_argument *argument, struct pp_token operator,
	struct pp_token *result, struct token *error)
{
	size_t length = 0;
	size_t used = 0;
	struct source *spelling;
	unsigned char *text;

	if (!add_stringizing_bytes(preprocessor, &length, 3, operator, error))
		return false;
	for (struct argument_token *item = argument->raw; item; item = item->next) {
		struct pp_token token = item->input.token;
		const unsigned char *bytes = token.location.source->data + token.location.offset;
		bool literal = token.kind == pp_string || token.kind == pp_character;

		if (!spend_expansion_work(preprocessor, operator, error))
			return false;
		if (item != argument->raw && token.leading_space &&
			!add_stringizing_bytes(preprocessor, &length, 1, operator, error))
			return false;
		for (size_t i = 0; i < token.length; i++) {
			bool escape = literal && (bytes[i] == '"' || bytes[i] == '\\');

			if (!literal && bytes[i] == '\\') {
				*error = stop_preprocessing(preprocessor, operator,
					"stringizing a backslash outside a literal is not supported yet");
				return false;
			}
			if (!add_stringizing_bytes(preprocessor, &length, escape ? 2 : 1, operator, error))
				return false;
		}
	}
	spelling = allocate_spelling(preprocessor, length, operator, error);
	if (!spelling)
		return false;
	text = spelling->data;
	text[used++] = '"';
	for (struct argument_token *item = argument->raw; item; item = item->next) {
		struct pp_token token = item->input.token;
		const unsigned char *bytes = token.location.source->data + token.location.offset;
		bool literal = token.kind == pp_string || token.kind == pp_character;

		if (item != argument->raw && token.leading_space)
			text[used++] = ' ';
		for (size_t i = 0; i < token.length; i++) {
			if (literal && (bytes[i] == '"' || bytes[i] == '\\'))
				text[used++] = '\\';
			text[used++] = bytes[i];
		}
	}
	text[used++] = '"';
	text[used++] = 0;
	assert(used == length);
	*result = (struct pp_token) {
		.kind = pp_string,
		.location = { spelling, 0 },
		.expansion_location = operator.expansion_location,
		.length = length - 1,
		.leading_space = operator.leading_space,
	};
	return true;
}

static bool stringize_optional(struct preprocessor *preprocessor,
	struct macro_token *optional, const struct expansion_frame *frame,
	struct pp_token operator, struct pp_token *result, struct token *error);

static void apply_frame_spacing(struct expansion_frame *frame, struct pp_token *token,
	bool preserve_argument_space)
{
	if (frame->first) {
		token->leading_space = frame->leading_space ||
			(preserve_argument_space && token->leading_space);
		frame->first = false;
	}
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
			cursor->frames[cursor->frame_count - 1].replacement ==
				cursor->frames[cursor->frame_count - 1].replacement_end &&
			!cursor->frames[cursor->frame_count - 1].argument) {
			frame = &cursor->frames[cursor->frame_count - 1];
			if ((frame->first && frame->leading_space) || frame->trailing_space)
				cursor->deferred_space = true;
			cursor->frame_count--;
		}
		if (!cursor->frame_count)
			break;
		frame = &cursor->frames[cursor->frame_count - 1];
		if (frame->argument) {
			*result = frame->argument->input;
			frame->argument = frame->argument->next;
			result->hide = hide_union(&result->hide, &frame->hide);
			apply_frame_spacing(frame, &result->token, true);
		} else {
			struct macro_token *replacement = frame->replacement;

			frame->replacement = replacement->next;
			*result = (struct rescan_token) { .token = replacement->token, .hide = frame->hide };
			result->token.expansion_location = frame->invocation;
			if (replacement->va_opt_close) {
				if (frame->first) {
					cursor->deferred_space |= frame->leading_space;
					frame->first = false;
				}
				if (!spend_expansion_work(preprocessor, result->token, error))
					return false;
				continue;
			}
			apply_frame_spacing(frame, &result->token, false);
			if (replacement->stringize) {
				struct macro_token *operand = replacement->next;

				if (operand->va_opt_end) {
					frame->replacement = operand->va_opt_end->next;
					if (!stringize_optional(preprocessor, operand, frame, result->token,
						&result->token, error))
						return false;
				} else {
					frame->replacement = operand->next;
					if (!stringize_argument(preprocessor,
						&frame->arguments[replacement->parameter_index], result->token,
						&result->token, error))
						return false;
				}
			} else if (replacement->va_opt_end) {
				struct macro_argument *variable =
					&frame->arguments[replacement->parameter_index];

				if (!spend_expansion_work(preprocessor, result->token, error) ||
					!prescan_argument(preprocessor, variable, result->token, error))
					return false;
				frame->replacement = variable->expanded ? replacement->next->next :
					replacement->va_opt_end->next;
				if (variable->expanded) {
					frame->first = true;
					frame->leading_space = result->token.leading_space;
				} else
					cursor->deferred_space |= result->token.leading_space;
				continue;
			} else if (replacement->parameter_index != SIZE_MAX) {
				struct macro_argument *argument =
					&frame->arguments[replacement->parameter_index];

				if (!spend_expansion_work(preprocessor, result->token, error) ||
					!prescan_argument(preprocessor, argument, result->token, error))
					return false;
				if (!argument->expanded)
					cursor->deferred_space |= result->token.leading_space || argument->trailing_space;
				if (argument->expanded && !push_frame(preprocessor, cursor,
					(struct expansion_frame) {
						.argument = argument->expanded,
						.invocation = frame->invocation,
						.hide = frame->hide,
						.first = true,
						.leading_space = result->token.leading_space,
						.trailing_space = argument->trailing_space,
					}, result->token, error))
					return false;
				continue;
			}
		}
		result->token.leading_space |= cursor->deferred_space;
		cursor->deferred_space = false;
		result->from_source = false;
		result->token.expansion_location = frame->invocation;
		result->token.at_line_start = false;
		return spend_expansion_work(preprocessor, result->token, error);
	}
	if (cursor->input) {
		*result = cursor->input->input;
		cursor->input = cursor->input->next;
		result->from_source = false;
		result->token.leading_space |= cursor->deferred_space;
		cursor->deferred_space = false;
		return spend_expansion_work(preprocessor, result->token, error);
	}
	if (!cursor->source_input) {
		*result = cursor_end(cursor);
		return true;
	}
	*result = (struct rescan_token) { .from_source = true };
	for (;;) {
		result->token = pp_lexer_next(&preprocessor->input);
		if (result->token.kind != pp_newline)
			break;
		cursor->deferred_space = true;
	}
	result->token.leading_space |= cursor->deferred_space;
	cursor->deferred_space = false;
	return true;
}

struct substitution_list {
	struct argument_token *head;
	struct argument_token *tail;
};

static bool build_paste_range(struct preprocessor *preprocessor,
	struct macro_token *first, struct macro_token *end, struct macro_argument *arguments,
	struct source_location invocation, struct macro_hide_set hide, bool leading_space,
	struct substitution_list *list, struct pp_token blame, struct token *error);

static void append_substitution(struct substitution_list *list, struct argument_token *item)
{
	item->next = NULL;
	if (list->tail)
		list->tail->next = item;
	else
		list->head = item;
	list->tail = item;
}

static void join_substitution(struct substitution_list *list, struct substitution_list body)
{
	if (!body.head)
		return;
	if (list->tail)
		list->tail->next = body.head;
	else
		list->head = body.head;
	list->tail = body.tail;
}

/* Markers are private zero-token operands; they never reach ordinary rescan. */
static void remove_placemarkers(struct substitution_list *list)
{
	struct argument_token *item = list->head;
	bool space = false;

	*list = (struct substitution_list) { 0 };
	while (item) {
		struct argument_token *next = item->next;

		if (item->placemarker)
			space |= item->input.token.leading_space;
		else {
			item->input.token.leading_space |= space;
			space = false;
			append_substitution(list, item);
		}
		item = next;
	}
}

static bool append_operand(struct preprocessor *preprocessor, struct substitution_list *list,
	struct rescan_token input, bool placemarker, bool paste_operator,
	struct pp_token blame, struct token *error)
{
	struct argument_token *copy = copy_argument_token(preprocessor, input, blame, error);

	if (!copy)
		return false;
	copy->placemarker = placemarker;
	copy->paste_operator = paste_operator;
	append_substitution(list, copy);
	return true;
}

static bool paste_pair(struct preprocessor *preprocessor, struct argument_token *left,
	const struct argument_token *right, struct pp_token operator, struct token *error)
{
	struct pp_token a = left->input.token;
	struct pp_token b = right->input.token;
	struct source *spelling;
	struct pp_lexer lexer;
	struct pp_token token;
	struct diagnostics quiet = { 0 };
	size_t length;

	if (!spend_expansion_work(preprocessor, operator, error))
		return false;
	if (left->placemarker) {
		left->input = right->input;
		left->input.token.leading_space = a.leading_space;
		left->placemarker = right->placemarker;
		return true;
	}
	if (right->placemarker)
		return true;
	if (a.length > preprocess_spelling_limit || b.length > preprocess_spelling_limit - a.length) {
		*error = stop_preprocessing(preprocessor, operator, "macro synthesized spelling limit exceeded");
		return false;
	}
	length = a.length + b.length;
	spelling = allocate_spelling(preprocessor, length + 1, operator, error);
	if (!spelling)
		return false;
	memcpy(spelling->data, a.location.source->data + a.location.offset, a.length);
	memcpy(spelling->data + a.length, b.location.source->data + b.location.offset, b.length);
	spelling->data[length] = 0;
	/* Logical spelling is already prepared. Never splice it or dispatch directives. */
	pp_lexer_init(&lexer, spelling, &quiet);
	token = pp_lexer_next(&lexer);
	if (token.kind == pp_invalid || token.kind == pp_eof || token.kind == pp_newline ||
		token.location.offset != 0 || token.length != length ||
		pp_lexer_next(&lexer).kind != pp_eof || quiet.errors) {
		*error = stop_preprocessing(preprocessor, operator,
			"token pasting must produce exactly one preprocessing token");
		return false;
	}
	token.expansion_location = operator.expansion_location;
	token.leading_space = a.leading_space;
	left->input = (struct rescan_token) {
		.token = token,
		.hide = hide_intersection(&left->input.hide, &right->input.hide),
	};
	return true;
}

/* Evaluate definition-origin operators left to right, retaining markers. */
static bool resolve_pastes(struct preprocessor *preprocessor, struct substitution_list *list,
	struct token *error)
{
	struct argument_token *item = list->head;

	*list = (struct substitution_list) { 0 };
	while (item) {
		struct argument_token *next = item->next;

		if (item->paste_operator) {
			assert(list->tail && next && !next->paste_operator);
			if (!paste_pair(preprocessor, list->tail, next, item->input.token, error))
				return false;
			item = next->next;
		} else {
			append_substitution(list, item);
			item = next;
		}
	}
	return true;
}

static bool substitute_paste_range(struct preprocessor *preprocessor,
	struct macro_token *first, struct macro_token *end, struct macro_argument *arguments,
	struct source_location invocation, struct macro_hide_set hide, bool leading_space,
	struct substitution_list *list, struct pp_token blame, struct token *error)
{
	bool first_token = true;
	bool paste_before = false;

	for (struct macro_token *item = first; item != end;) {
		struct macro_token *after = item->next;
		struct rescan_token input = { .token = item->token };

		if (!spend_expansion_work(preprocessor, blame, error))
			return false;
		input.token.expansion_location = invocation;
		input.token.at_line_start = false;
		if (first_token) {
			input.token.leading_space = leading_space;
			first_token = false;
		}
		if (is_paste_operator(item->token)) {
			if (!append_operand(preprocessor, list, input, false, true, blame, error))
				return false;
			paste_before = true;
			item = after;
			continue;
		}
		if (item->stringize) {
			struct macro_token *operand = item->next;
			struct expansion_frame frame = { .arguments = arguments, .invocation = invocation, .hide = hide };

			if (operand->va_opt_end) {
				after = operand->va_opt_end->next;
				if (!stringize_optional(preprocessor, operand, &frame, input.token, &input.token, error))
					return false;
			} else {
				after = operand->next;
				if (!stringize_argument(preprocessor, &arguments[item->parameter_index],
					input.token, &input.token, error))
					return false;
			}
			if (!append_operand(preprocessor, list, input, false, false, blame, error))
				return false;
		} else if (item->va_opt_end) {
			struct macro_argument *variable = &arguments[item->parameter_index];
			struct substitution_list body = { 0 };

			after = item->va_opt_end->next;
			if (!prescan_argument(preprocessor, variable, input.token, error))
				return false;
			if (variable->expanded && !build_paste_range(preprocessor, item->next->next,
				item->va_opt_end, arguments, invocation, hide, input.token.leading_space,
				&body, blame, error))
				return false;
			if (body.head)
				join_substitution(list, body);
			else if (!append_operand(preprocessor, list, input, true, false, blame, error))
				return false;
		} else if (item->parameter_index != SIZE_MAX) {
			struct macro_argument *argument = &arguments[item->parameter_index];
			bool raw = paste_before || (after != end && is_paste_operator(after->token));
			struct argument_token *tokens;
			bool first_argument = true;

			if (!raw && !prescan_argument(preprocessor, argument, input.token, error))
				return false;
			tokens = raw ? argument->raw : argument->expanded;
			if (!tokens) {
				input.token.leading_space |= !raw && argument->trailing_space;
				if (!append_operand(preprocessor, list, input, true, false, blame, error))
					return false;
			}
			for (; tokens; tokens = tokens->next) {
				struct rescan_token token = tokens->input;

				if (first_argument) {
					token.token.leading_space |= input.token.leading_space;
					first_argument = false;
				}
				if (!append_operand(preprocessor, list, token, false, false, blame, error))
					return false;
			}
			if (!raw && argument->expanded && argument->trailing_space) {
				input.token.leading_space = true;
				if (!append_operand(preprocessor, list, input, true, false, blame, error))
					return false;
			}
		} else if (!append_operand(preprocessor, list, input, false, false, blame, error))
			return false;
		paste_before = false;
		item = after;
	}
	return true;
}

static bool build_paste_range(struct preprocessor *preprocessor,
	struct macro_token *first, struct macro_token *end, struct macro_argument *arguments,
	struct source_location invocation, struct macro_hide_set hide, bool leading_space,
	struct substitution_list *list, struct pp_token blame, struct token *error)
{
	bool success;

	if (preprocessor->paste_depth == preprocess_paste_limit) {
		*error = stop_preprocessing(preprocessor, blame, "macro paste substitution depth limit exceeded");
		return false;
	}
	preprocessor->paste_depth++;
	success = substitute_paste_range(preprocessor, first, end, arguments, invocation,
		hide, leading_space, list, blame, error) && resolve_pastes(preprocessor, list, error);
	preprocessor->paste_depth--;
	return success;
}

/* A stringized optional body gets parameter substitution and inner #, but
 * not ordinary macro rescan. Its exclusive range end cannot read the suffix.
 */
static bool stringize_optional(struct preprocessor *preprocessor,
	struct macro_token *optional, const struct expansion_frame *frame,
	struct pp_token operator, struct pp_token *result, struct token *error)
{
	struct macro_argument *variable = &frame->arguments[optional->parameter_index];
	struct macro_argument body = { 0 };
	struct argument_token **tail = &body.raw;
	struct expansion_cursor *cursor;
	bool success = false;

	if (preprocessor->optional_depth == preprocess_optional_limit) {
		*error = stop_preprocessing(preprocessor, operator,
			"macro optional substitution depth limit exceeded");
		return false;
	}
	if (!prescan_argument(preprocessor, variable, operator, error))
		return false;
	if (!variable->expanded)
		return stringize_argument(preprocessor, &body, operator, result, error);
	if (optional->optional_has_paste) {
		struct substitution_list list = { 0 };

		if (!build_paste_range(preprocessor, optional->next->next, optional->va_opt_end,
			frame->arguments, frame->invocation, frame->hide, false, &list, operator, error))
			return false;
		remove_placemarkers(&list);
		body.raw = list.head;
		return stringize_argument(preprocessor, &body, operator, result, error);
	}
	cursor = malloc(sizeof(*cursor));
	if (!cursor) {
		*error = stop_preprocessing(preprocessor, operator,
			"cannot allocate macro optional substitution cursor");
		return false;
	}
	*cursor = (struct expansion_cursor) { .end = operator.expansion_location };
	preprocessor->optional_depth++;
	if (!push_frame(preprocessor, cursor, (struct expansion_frame) {
		.replacement = optional->next->next,
		.replacement_end = optional->va_opt_end,
		.arguments = frame->arguments,
		.invocation = frame->invocation,
		.hide = frame->hide,
		.first = true,
	}, operator, error))
		goto done;
	for (;;) {
		struct rescan_token token;
		struct argument_token *copy;

		/* Deliberately do not call read_expanded_token here. */
		if (!read_rescan_token(preprocessor, cursor, &token, error))
			break;
		if (token.token.kind == pp_eof) {
			success = stringize_argument(preprocessor, &body, operator, result, error);
			break;
		}
		copy = copy_argument_token(preprocessor, token, operator, error);
		if (!copy)
			break;
		*tail = copy;
		tail = &copy->next;
	}
done:
	preprocessor->optional_depth--;
	free(cursor);
	return success;
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
	if (input.from_source && is_variadic_identifier(input.token)) {
		*error = stop_preprocessing(preprocessor, input.token,
			"variadic identifiers require a variadic macro replacement list");
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
	size_t argument_count = macro->parameter_count + (macro->variadic ? 1 : 0);

	*invoked = false;
	if (!read_rescan_token(preprocessor, cursor, &next, error) ||
		!check_invocation_input(preprocessor, next, error))
		return false;
	if (!is_punctuator(next.token, "(")) {
		cursor->pending = next;
		cursor->has_pending = true;
		return true;
	}
	if (argument_count) {
		*arguments = allocate_auxiliary(preprocessor, argument_count,
			sizeof(**arguments), name.token, error);
		if (!*arguments)
			return false;
		for (size_t i = 0; i < argument_count; i++)
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
			if ((macro->variadic && index + 1 < macro->parameter_count) ||
				(!macro->variadic && macro->parameter_count &&
				index + 1 != macro->parameter_count)) {
				*error = stop_preprocessing(preprocessor, name.token,
					"macro argument count does not match parameters");
				return false;
			}
			*hide = hide_intersection(&name.hide, &next.hide);
			*invoked = true;
			return true;
		}
		if (!argument_count) {
			*error = stop_preprocessing(preprocessor, name.token,
				"zero-parameter macro invocation requires no arguments");
			return false;
		}
		/* Separators after the named arguments belong to the variable slot. */
		if (is_punctuator(next.token, ",") && !parentheses &&
			(!macro->variadic || index < macro->parameter_count)) {
			index++;
			if (index == argument_count) {
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
		if (!(*arguments)[index].raw)
			copy->input.token.leading_space = false;
		*tail = copy;
		tail = &copy->next;
	}
}

/* File EOF is visible to macro invocation lookahead. Only ordinary expansion
 * resumes the parent: a function-like macro cannot acquire '(' from that file.
 */
static bool finish_include(struct preprocessor *preprocessor)
{
	struct include_frame *frame;

	if (preprocessor->conditional_count != preprocessor->conditional_base) {
		struct conditional_group *group =
			&preprocessor->conditionals[preprocessor->conditional_count - 1];

		diagnostic_error(preprocessor->diagnostics, group->opening,
			"unterminated conditional group in included source");
		preprocessor->conditional_count = 0;
		preprocessor->stopped = true;
		return false;
	}
	frame = &preprocessor->include_frames[--preprocessor->include_depth];
	preprocessor->input = frame->parent;
	preprocessor->conditional_base = frame->conditional_base;
	preprocessor->cursor.deferred_space = true;
	return true;
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
		if (input.from_source && input.token.kind == pp_eof && preprocessor->include_depth) {
			if (!finish_include(preprocessor)) {
				*result = cursor_end(cursor);
				return true;
			}
			continue;
		}
		if (input.from_source && input.token.kind == pp_eof &&
			preprocessor->conditional_count) {
			struct conditional_group *group =
				&preprocessor->conditionals[preprocessor->conditional_count - 1];

			diagnostic_error(preprocessor->diagnostics, group->opening,
				"unterminated conditional group");
			preprocessor->conditional_count = 0;
			preprocessor->stopped = true;
			*result = input;
			return true;
		}
		if (input.from_source && !conditional_active(preprocessor) &&
			!(input.token.at_line_start && is_directive_marker(input.token))) {
			if (input.token.kind == pp_invalid) {
				*result = input;
				return true;
			}
			continue;
		}
		if (input.from_source && is_variadic_identifier(input.token)) {
			*error = stop_preprocessing(preprocessor, input.token,
				"variadic identifiers require a variadic macro replacement list");
			return false;
		}
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
		if (macro->has_paste) {
			struct substitution_list list = { 0 };

			if (!build_paste_range(preprocessor, macro->replacement, NULL, arguments,
				input.token.expansion_location, hide, input.token.leading_space,
				&list, input.token, error))
				return false;
			remove_placemarkers(&list);
			if (!push_frame(preprocessor, cursor, (struct expansion_frame) {
				.argument = list.head, .hide = hide,
				.invocation = input.token.expansion_location,
				.first = true, .leading_space = input.token.leading_space,
			}, input.token, error))
				return false;
			continue;
		}
		if (!push_frame(preprocessor, cursor, (struct expansion_frame) {
			.replacement = macro->replacement,
			.arguments = arguments,
			.invocation = input.token.expansion_location,
			.hide = hide,
			.first = true,
			.leading_space = input.token.leading_space,
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
			argument->trailing_space = cursor->deferred_space;
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

/* A preprocessing integer has target intmax_t or uintmax_t semantics. */
struct condition_value {
	uint64_t bits;
	bool unsigned_type;
};

static struct condition_value signed_condition(int64_t value)
{
	return (struct condition_value) { .bits = (uint64_t)value };
}

/* Decode mathematically, without an implementation-defined large unsigned cast. */
static int64_t condition_signed_value(struct condition_value value)
{
	if (value.bits <= INT64_MAX)
		return (int64_t)value.bits;
	return -1 - (int64_t)(UINT64_MAX - value.bits);
}

enum condition_operation {
	condition_multiply, condition_divide, condition_remainder,
	condition_add, condition_subtract, condition_shift_left, condition_shift_right,
	condition_less, condition_less_equal, condition_greater, condition_greater_equal,
	condition_equal, condition_not_equal, condition_bit_and, condition_bit_xor,
	condition_bit_or, condition_and, condition_or,
};

struct condition_operator {
	const char *spelling;
	unsigned binding_power;
	enum condition_operation operation;
};

static const struct condition_operator condition_operators[] = {
	{ "*", 60, condition_multiply }, { "/", 60, condition_divide },
	{ "%", 60, condition_remainder },
	{ "+", 50, condition_add }, { "-", 50, condition_subtract },
	{ "<<", 45, condition_shift_left }, { ">>", 45, condition_shift_right },
	{ "<", 40, condition_less }, { "<=", 40, condition_less_equal },
	{ ">", 40, condition_greater }, { ">=", 40, condition_greater_equal },
	{ "==", 30, condition_equal }, { "!=", 30, condition_not_equal },
	{ "&", 27, condition_bit_and }, { "^", 25, condition_bit_xor },
	{ "|", 23, condition_bit_or },
	{ "&&", 20, condition_and }, { "||", 10, condition_or },
};

struct condition_parser {
	struct preprocessor *preprocessor;
	struct expansion_cursor *cursor;
	struct pp_token token;
	struct token *error;
	size_t depth;
	bool failed;
};

static void condition_error(struct condition_parser *parser,
	struct pp_token token, const char *message)
{
	if (!parser->failed)
		diagnostic_error(parser->preprocessor->diagnostics, token.expansion_location, message);
	parser->failed = true;
}

static void advance_condition(struct condition_parser *parser)
{
	struct rescan_token next;

	if (parser->failed)
		return;
	if (!read_expanded_token(parser->preprocessor, parser->cursor, &next, parser->error)) {
		parser->failed = true;
		return;
	}
	parser->token = next.token;
	if (next.token.kind == pp_invalid)
		parser->failed = true;
}

static int condition_digit(unsigned char byte)
{
	if (byte >= '0' && byte <= '9')
		return byte - '0';
	if (byte >= 'a' && byte <= 'f')
		return byte - 'a' + 10;
	if (byte >= 'A' && byte <= 'F')
		return byte - 'A' + 10;
	return -1;
}

/* condition-character = "'" (ascii-character | simple-escape | octal-escape
 *                         | hexadecimal-escape) "'"
 * One target byte only; prefixed/Unicode/multicharacter forms are separate work.
 */
static struct condition_value parse_condition_character(struct condition_parser *parser,
	struct pp_token token)
{
	const unsigned char *text = token.location.source->data + token.location.offset;
	size_t offset = 1;
	unsigned value;

	if (text[0] != '\'') {
		condition_error(parser, token, "prefixed conditional characters are not supported yet");
		return signed_condition(0);
	}
	if (token.length < 3) {
		condition_error(parser, token, "expected one character in conditional constant");
		return signed_condition(0);
	}
	value = text[offset++];
	if (value == '\\') {
		unsigned char escape = text[offset++];

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
			while (offset < token.length - 1) {
				int digit = condition_digit(text[offset]);

				if (digit < 0)
					break;
				if (value > (255 - (unsigned)digit) / 16) {
					condition_error(parser, token, "conditional character escape exceeds one byte");
					return signed_condition(0);
				}
				value = value * 16 + (unsigned)digit;
				offset++;
				digits++;
			}
			if (!digits) {
				condition_error(parser, token, "expected digits in hexadecimal character escape");
				return signed_condition(0);
			}
			break;
		}
		default:
			if (escape < '0' || escape > '7') {
				condition_error(parser, token, "unsupported conditional character escape");
				return signed_condition(0);
			}
			value = escape - '0';
			for (size_t digits = 1; digits < 3 && offset < token.length - 1; digits++) {
				unsigned char next = text[offset];

				if (next < '0' || next > '7')
					break;
				value = value * 8 + next - '0';
				offset++;
			}
			if (value > 255) {
				condition_error(parser, token, "conditional character escape exceeds one byte");
				return signed_condition(0);
			}
			break;
		}
	} else if (value >= 128) {
		condition_error(parser, token, "non-ASCII conditional characters are not supported yet");
		return signed_condition(0);
	}
	if (offset != token.length - 1) {
		condition_error(parser, token, "multicharacter conditional constants are not supported yet");
		return signed_condition(0);
	}
	/* Target signed plain char; conversion is independent of host char signedness. */
	return signed_condition(value < 128 ? (int64_t)value : (int64_t)value - 256);
}

/* condition-integer = (decimal | octal | hexadecimal | binary) integer-suffix?
 * Separators occur only between valid base digits. This increment accepts only
 * signed-intmax values, with no suffix or a signed l/L/ll/LL suffix.
 */
static struct condition_value parse_condition_integer(struct condition_parser *parser, struct pp_token token)
{
	const unsigned char *text = token.location.source->data + token.location.offset;
	size_t offset = 0;
	size_t digits = 0;
	unsigned base = 10;
	uint64_t value = 0;
	bool previous_digit = false;
	bool unsigned_suffix = false;

	if (text[0] == '0') {
		base = 8;
		if (token.length > 1 && (text[1] == 'x' || text[1] == 'X')) {
			base = 16;
			offset = 2;
		} else if (token.length > 1 && (text[1] == 'b' || text[1] == 'B')) {
			base = 2;
			offset = 2;
		}
	}
	while (offset < token.length) {
		int digit = condition_digit(text[offset]);

		if (digit >= 0 && (unsigned)digit < base) {
			if (value > (UINT64_MAX - (unsigned)digit) / base) {
				condition_error(parser, token, "conditional integer exceeds 64-bit range");
				return signed_condition(0);
			}
			value = value * base + (unsigned)digit;
			offset++;
			digits++;
			previous_digit = true;
			continue;
		}
		if (text[offset] == '\'') {
			int next = offset + 1 < token.length ? condition_digit(text[offset + 1]) : -1;

			if (!previous_digit || next < 0 || (unsigned)next >= base) {
				condition_error(parser, token, "invalid separator in conditional integer");
				return signed_condition(0);
			}
			previous_digit = false;
			offset++;
			continue;
		}
		if (text[offset] >= '0' && text[offset] <= '9') {
			condition_error(parser, token, "invalid digit in conditional integer");
			return signed_condition(0);
		}
		break;
	}
	if (!digits) {
		condition_error(parser, token, "expected digits in conditional integer");
		return signed_condition(0);
	}
	if (offset < token.length && (text[offset] == 'u' || text[offset] == 'U')) {
		unsigned_suffix = true;
		offset++;
	}
	if (offset < token.length && (text[offset] == 'l' || text[offset] == 'L')) {
		unsigned char first = text[offset++];

		if (offset < token.length && text[offset] == first)
			offset++;
	}
	if (!unsigned_suffix && offset < token.length && (text[offset] == 'u' || text[offset] == 'U')) {
		unsigned_suffix = true;
		offset++;
	}
	if (offset != token.length) {
		condition_error(parser, token, "unsupported conditional integer suffix");
		return signed_condition(0);
	}
	if (!unsigned_suffix && base == 10 && value > INT64_MAX) {
		condition_error(parser, token, "conditional integer exceeds signed 64-bit range");
		return signed_condition(0);
	}
	return (struct condition_value) {
		.bits = value,
		.unsigned_type = unsigned_suffix || (base != 10 && value > INT64_MAX),
	};
}

static struct condition_value parse_condition_expression(struct condition_parser *parser,
	unsigned minimum_power, bool evaluate);

/* condition-operand = condition-integer | condition-character | identifier | '(' condition-expression ')'
 *                   | ('+' | '-' | '!' | '~') condition-operand
 * defined was handled before expansion; other identifiers are zero (C23 true is 1).
 */
static struct condition_value parse_condition_operand(struct condition_parser *parser, bool evaluate)
{
	struct pp_token token = parser->token;
	struct condition_value value = signed_condition(0);

	if (parser->failed)
		return signed_condition(0);
	if (is_punctuator(token, "+") || is_punctuator(token, "-") ||
		is_punctuator(token, "!") || is_punctuator(token, "~")) {
		advance_condition(parser);
		value = parse_condition_expression(parser, 70, evaluate);
		if (parser->failed)
			return signed_condition(0);
		if (is_punctuator(token, "!"))
			return signed_condition(evaluate && !value.bits);
		if (!evaluate) {
			value.bits = 0;
			return value;
		}
		if (is_punctuator(token, "~")) {
			value.bits = ~value.bits;
			return value;
		}
		if (is_punctuator(token, "+"))
			return value;
		if (!value.unsigned_type && condition_signed_value(value) == INT64_MIN) {
			condition_error(parser, token, "signed overflow in conditional expression");
			return signed_condition(0);
		}
		value.bits = UINT64_C(0) - value.bits;
		return value;
	}
	if (is_punctuator(token, "(")) {
		advance_condition(parser);
		value = parse_condition_expression(parser, 0, evaluate);
		if (!parser->failed && !is_punctuator(parser->token, ")"))
			condition_error(parser, parser->token, "expected ')' in conditional expression");
		advance_condition(parser);
		return value;
	}
	if (token.kind == pp_number) {
		value = parse_condition_integer(parser, token);
	} else if (token.kind == pp_character) {
		value = parse_condition_character(parser, token);
	} else if (token.kind == pp_identifier) {
		if (pp_spelling_is(token, "defined"))
			condition_error(parser, token, "defined produced by macro expansion is not supported");
		value = signed_condition(pp_spelling_is(token, "true"));
	} else {
		condition_error(parser, token, "expected an operand in conditional expression");
	}
	advance_condition(parser);
	return value;
}

static bool condition_multiply_overflows(int64_t left, int64_t right)
{
	if (left > 0)
		return (right > 0 && left > INT64_MAX / right) ||
			(right < 0 && right < INT64_MIN / left);
	if (left < 0)
		return (right > 0 && left < INT64_MIN / right) ||
			(right < 0 && left < INT64_MAX / right);
	return false;
}

static bool condition_result_unsigned(enum condition_operation operation,
	struct condition_value left, struct condition_value right)
{
	switch (operation) {
	case condition_less:
	case condition_less_equal:
	case condition_greater:
	case condition_greater_equal:
	case condition_equal:
	case condition_not_equal:
	case condition_and:
	case condition_or:
		return false;
	case condition_shift_left:
	case condition_shift_right:
		return left.unsigned_type;
	default:
		return left.unsigned_type || right.unsigned_type;
	}
}

static struct condition_value evaluate_condition_operator(struct condition_parser *parser,
	struct pp_token token, enum condition_operation operation,
	struct condition_value left, struct condition_value right)
{
	bool unsigned_type = left.unsigned_type || right.unsigned_type;
	struct condition_value result = { .unsigned_type = unsigned_type };
	int64_t a = condition_signed_value(left);
	int64_t b = condition_signed_value(right);

	switch (operation) {
	case condition_add:
		if (!unsigned_type && ((b > 0 && a > INT64_MAX - b) ||
			(b < 0 && a < INT64_MIN - b)))
			break;
		result.bits = left.bits + right.bits;
		return result;
	case condition_subtract:
		if (!unsigned_type && ((b > 0 && a < INT64_MIN + b) ||
			(b < 0 && a > INT64_MAX + b)))
			break;
		result.bits = left.bits - right.bits;
		return result;
	case condition_multiply:
		if (!unsigned_type && condition_multiply_overflows(a, b))
			break;
		result.bits = left.bits * right.bits;
		return result;
	case condition_divide:
	case condition_remainder:
		if (!right.bits) {
			condition_error(parser, token, "division by zero in conditional expression");
			return signed_condition(0);
		}
		if (unsigned_type) {
			result.bits = operation == condition_divide ?
				left.bits / right.bits : left.bits % right.bits;
			return result;
		}
		if (a == INT64_MIN && b == -1)
			break;
		return signed_condition(operation == condition_divide ? a / b : a % b);
	case condition_shift_left:
	case condition_shift_right:
		if ((!right.unsigned_type && b < 0) || right.bits >= 64) {
			condition_error(parser, token, "conditional shift count must be between 0 and 63");
			return signed_condition(0);
		}
		result.unsigned_type = left.unsigned_type;
		if (operation == condition_shift_right) {
			if (!left.unsigned_type && a < 0)
				return signed_condition(-1 - ((-1 - a) >> right.bits));
			result.bits = left.bits >> right.bits;
			return result;
		}
		if (!left.unsigned_type) {
			if (a < 0) {
				condition_error(parser, token, "negative left operand in conditional shift");
				return signed_condition(0);
			}
			if (a > (INT64_MAX >> right.bits))
				break;
		}
		result.bits = left.bits << right.bits;
		return result;
	case condition_bit_and:
		result.bits = left.bits & right.bits;
		return result;
	case condition_bit_xor:
		result.bits = left.bits ^ right.bits;
		return result;
	case condition_bit_or:
		result.bits = left.bits | right.bits;
		return result;
	case condition_less:
		return signed_condition(unsigned_type ? left.bits < right.bits : a < b);
	case condition_less_equal:
		return signed_condition(unsigned_type ? left.bits <= right.bits : a <= b);
	case condition_greater:
		return signed_condition(unsigned_type ? left.bits > right.bits : a > b);
	case condition_greater_equal:
		return signed_condition(unsigned_type ? left.bits >= right.bits : a >= b);
	case condition_equal:
		return signed_condition(left.bits == right.bits);
	case condition_not_equal:
		return signed_condition(left.bits != right.bits);
	case condition_and:
		return signed_condition(left.bits && right.bits);
	case condition_or:
		return signed_condition(left.bits || right.bits);
	}
	condition_error(parser, token, "signed overflow in conditional expression");
	return signed_condition(0);
}

/* condition-expression = condition-operand { binary-operator condition-expression }
 *                        [ '?' condition-expression ':' condition-expression ]
 * Binary operators associate left; ?: associates right below logical-or.
 * Short circuit suppresses arithmetic only, not parsing or macro expansion.
 */
static struct condition_value parse_condition_expression(struct condition_parser *parser,
	unsigned minimum_power, bool evaluate)
{
	struct condition_value value;

	if (parser->failed)
		return signed_condition(0);
	if (parser->depth == preprocess_condition_depth_limit) {
		condition_error(parser, parser->token, "conditional expression nesting limit (128) exceeded");
		return signed_condition(0);
	}
	parser->depth++;
	value = parse_condition_operand(parser, evaluate);
	while (!parser->failed) {
		const struct condition_operator *operator = NULL;
		struct pp_token token = parser->token;
		bool evaluate_right = evaluate;
		struct condition_value right;

		if (is_punctuator(token, "?") && minimum_power <= 5) {
			struct condition_value condition = value;
			struct condition_value yes;
			struct condition_value no;

			advance_condition(parser);
			yes = parse_condition_expression(parser, 0, evaluate && condition.bits != 0);
			if (!parser->failed && !is_punctuator(parser->token, ":"))
				condition_error(parser, parser->token, "expected ':' in conditional expression");
			advance_condition(parser);
			no = parse_condition_expression(parser, 5, evaluate && condition.bits == 0);
			value.bits = evaluate ? (condition.bits ? yes.bits : no.bits) : 0;
			value.unsigned_type = yes.unsigned_type || no.unsigned_type;
			continue;
		}
		if (token.kind != pp_punctuator)
			break;
		for (size_t i = 0; i < sizeof(condition_operators) / sizeof(condition_operators[0]); i++)
			if (pp_spelling_is(token, condition_operators[i].spelling)) {
				operator = &condition_operators[i];
				break;
			}
		if (!operator || operator->binding_power < minimum_power)
			break;
		if (operator->operation == condition_and && !value.bits)
			evaluate_right = false;
		if (operator->operation == condition_or && value.bits)
			evaluate_right = false;
		advance_condition(parser);
		right = parse_condition_expression(parser, operator->binding_power + 1, evaluate_right);
		if (evaluate && !parser->failed)
			value = evaluate_condition_operator(parser, token, operator->operation, value, right);
		else {
			value.unsigned_type = condition_result_unsigned(operator->operation, value, right);
			value.bits = 0;
		}
	}
	parser->depth--;
	return value;
}

/* A raw directive is bounded independently of its expanded macro stream. */
static bool read_condition_input(struct preprocessor *preprocessor,
	struct pp_token marker, struct pp_token *token, size_t *count, struct token *error)
{
	*token = pp_lexer_next(&preprocessor->input);
	if (token->kind == pp_invalid || token->has_non_directive_space) {
		*error = reject_directive(preprocessor, marker, *token,
			token->kind == pp_invalid ? NULL :
			"only space and tab are allowed in a preprocessing directive");
		return false;
	}
	if (is_variadic_identifier(*token)) {
		*error = reject_directive(preprocessor, marker, *token,
			"variadic identifiers require a variadic macro replacement list");
		return false;
	}
	if (!is_directive_end(*token) && ++*count > preprocess_condition_token_limit) {
		*error = reject_directive(preprocessor, marker, *token,
			"conditional expression token limit (1024) exceeded");
		return false;
	}
	return true;
}

/* defined-operand = 'defined' identifier | 'defined' '(' identifier ')'
 * Consumed before rescanning; never expand the macro name being tested.
 */
static bool replace_defined_operand(struct preprocessor *preprocessor,
	struct pp_token marker, struct pp_token *token, size_t *count, struct token *error)
{
	struct pp_token operator = *token;
	struct pp_token name;
	struct macro *macro;
	struct source *spelling;
	bool parenthesized;

	if (!read_condition_input(preprocessor, marker, &name, count, error))
		return false;
	parenthesized = is_punctuator(name, "(");
	if (parenthesized && !read_condition_input(preprocessor, marker, &name, count, error))
		return false;
	if (name.kind != pp_identifier) {
		*error = reject_directive(preprocessor, marker, name,
			"expected an identifier after defined");
		return false;
	}
	if (parenthesized) {
		struct pp_token close;

		if (!read_condition_input(preprocessor, marker, &close, count, error))
			return false;
		if (!is_punctuator(close, ")")) {
			*error = reject_directive(preprocessor, marker, close,
				"expected ')' after defined operand");
			return false;
		}
	}
	spelling = allocate_spelling(preprocessor, 2, operator, error);
	if (!spelling)
		return false;
	macro = find_macro(preprocessor, name);
	spelling->data[0] = macro && macro->defined ? '1' : '0';
	spelling->data[1] = 0;
	*token = (struct pp_token) {
		.kind = pp_number,
		.location = { spelling, 0 },
		.expansion_location = operator.expansion_location,
		.length = 1,
		.leading_space = operator.leading_space,
	};
	return true;
}

/* expression-condition = pp-tokens newline
 * Isolated rescanning prevents macro lookahead from consuming the following line.
 */
static bool read_expression_condition(struct preprocessor *preprocessor,
	struct pp_token marker, bool *value, struct token *error)
{
	struct argument_token *head = NULL;
	struct argument_token **tail = &head;
	struct pp_token token;
	struct expansion_cursor *cursor;
	struct condition_parser parser;
	size_t count = 0;
	struct condition_value result;

	for (;;) {
		struct argument_token *copy;

		if (!read_condition_input(preprocessor, marker, &token, &count, error))
			return false;
		if (is_directive_end(token))
			break;
		if (token.kind == pp_identifier && pp_spelling_is(token, "defined") &&
			!replace_defined_operand(preprocessor, marker, &token, &count, error))
			return false;
		/* Directive tokens retain their individual source invocation sites. */
		copy = copy_argument_token(preprocessor, (struct rescan_token) { .token = token }, token, error);
		if (!copy)
			return false;
		*tail = copy;
		tail = &copy->next;
	}
	cursor = calloc(1, sizeof(*cursor));
	if (!cursor) {
		*error = stop_preprocessing(preprocessor, marker, "cannot allocate conditional macro cursor");
		return false;
	}
	cursor->input = head;
	cursor->end = token.location;
	parser = (struct condition_parser) {
		.preprocessor = preprocessor,
		.cursor = cursor,
		.error = error,
	};
	advance_condition(&parser);
	result = parse_condition_expression(&parser, 0, true);
	if (!parser.failed && parser.token.kind != pp_eof)
		condition_error(&parser, parser.token, "unsupported or trailing token in conditional expression");
	free(cursor);
	if (parser.failed) {
		*error = invalid_token(marker);
		return false;
	}
	*value = result.bits != 0;
	return true;
}

/* include-operand = pp-tokens newline
 * Collect one raw line, then rescan in isolation. Validation must not drain
 * source again: the next directive or C token already follows this operand.
 */
static bool expand_include_operand(struct preprocessor *preprocessor,
	struct pp_token marker, struct pp_token *header, struct token *error)
{
	struct argument_token *head = NULL;
	struct argument_token **tail = &head;
	struct expansion_cursor *cursor;
	struct rescan_token first;
	struct rescan_token end;
	struct pp_token token;
	size_t count = 0;
	bool success;

	for (;;) {
		struct argument_token *copy;

		token = pp_lexer_next(&preprocessor->input);
		if (token.kind == pp_invalid || token.has_non_directive_space) {
			*error = reject_directive(preprocessor, marker, token,
				token.kind == pp_invalid ? NULL :
				"only space and tab are allowed in a preprocessing directive");
			return false;
		}
		if (is_directive_end(token))
			break;
		if (++count > preprocess_header_token_limit) {
			*error = reject_directive(preprocessor, marker, token,
				"include operand token limit (1024) exceeded");
			return false;
		}
		if (is_variadic_identifier(token)) {
			*error = reject_directive(preprocessor, marker, token,
				"variadic identifiers require a variadic macro replacement list");
			return false;
		}
		/* Directive tokens retain their individual source invocation sites. */
		copy = copy_argument_token(preprocessor, (struct rescan_token) { .token = token }, token, error);
		if (!copy)
			return false;
		*tail = copy;
		tail = &copy->next;
	}
	cursor = calloc(1, sizeof(*cursor));
	if (!cursor) {
		*error = stop_preprocessing(preprocessor, marker, "cannot allocate include macro cursor");
		return false;
	}
	cursor->input = head;
	cursor->end = token.location;
	success = read_expanded_token(preprocessor, cursor, &first, error) &&
		read_expanded_token(preprocessor, cursor, &end, error);
	free(cursor);
	if (!success)
		return false;
	if (end.token.kind != pp_eof) {
		diagnostic_error(preprocessor->diagnostics, end.token.expansion_location,
			"expected exactly one quoted include name after macro expansion");
		*error = invalid_token(marker);
		return false;
	}
	*header = first.token;
	return true;
}

struct pp_token preprocess_next_pp(struct preprocessor *preprocessor)
{
	struct rescan_token input;
	struct token error;

	assert(!preprocessor->has_lookahead);
	if (preprocessor->stopped)
		return cursor_end(&preprocessor->cursor).token;
	if (!read_expanded_token(preprocessor, &preprocessor->cursor, &input, &error))
		return (struct pp_token) {
			.kind = pp_invalid,
			.location = error.spelling_location,
			.expansion_location = error.location,
			.length = error.length,
		};
	if (input.token.kind == pp_eof)
		return cursor_end(&preprocessor->cursor).token;
	return input.token;
}

static struct token read_preprocessed_token(struct preprocessor *preprocessor)
{
	return token_from_pp(preprocess_next_pp(preprocessor), preprocessor->diagnostics);
}

void preprocess_init(struct preprocessor *preprocessor, const struct source *source,
	struct diagnostics *diagnostics)
{
	*preprocessor = (struct preprocessor) { .diagnostics = diagnostics };
	pp_lexer_init(&preprocessor->input, source, diagnostics);
	preprocessor->cursor.source_input = true;
	preprocessor->cursor.end = (struct source_location) { source, source->length };
}

void preprocess_set_include_loader(struct preprocessor *preprocessor,
	bool (*loader)(void *context, struct source *source, const char *path), void *context)
{
	assert(!preprocessor->input.offset && !preprocessor->has_lookahead);
	preprocessor->include_loader = loader;
	preprocessor->include_context = context;
}

void preprocess_destroy(struct preprocessor *preprocessor)
{
	for (struct include_source *child = preprocessor->include_sources; child; child = child->next)
		source_destroy(&child->source);
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
