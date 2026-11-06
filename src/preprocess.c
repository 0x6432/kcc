#include "preprocess.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

struct include_source {
	struct source source;
	struct include_source *next;
};

/* File names are the successful loader's source.name, not realpath or inode.
 * The retained source outlives this arena-owned record. */
struct pragma_once_file {
	const char *name;
	struct pragma_once_file *next;
};

/* Per-physical-source mappings remain arena-owned for the whole translation. */
struct line_remap {
	const struct source *source;
	size_t physical_start;
	size_t logical_start;
	const char *name;
	struct line_remap *next;
};

struct include_name {
	char path[preprocess_include_path_limit];
	struct pp_token invocation;
	bool angled;
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

static bool is_predefined_location(struct pp_token name)
{
	return name.kind == pp_identifier &&
		(pp_spelling_is(name, "__LINE__") || pp_spelling_is(name, "__FILE__"));
}

static bool is_predefined_clock(struct pp_token name)
{
	return name.kind == pp_identifier &&
		(pp_spelling_is(name, "__DATE__") || pp_spelling_is(name, "__TIME__"));
}

static bool is_predefined_embed_status(struct pp_token name)
{
	return name.kind == pp_identifier &&
		(pp_spelling_is(name, "__STDC_EMBED_NOT_FOUND__") ||
		 pp_spelling_is(name, "__STDC_EMBED_FOUND__") ||
		 pp_spelling_is(name, "__STDC_EMBED_EMPTY__"));
}

static bool macro_is_defined(struct preprocessor *preprocessor, struct pp_token name)
{
	struct macro *macro = find_macro(preprocessor, name);

	return is_predefined_location(name) || is_predefined_clock(name) || is_predefined_embed_status(name) ||
		(name.kind == pp_identifier && (pp_spelling_is(name, "__has_c_attribute") ||
			pp_spelling_is(name, "__has_include") || pp_spelling_is(name, "__has_embed"))) ||
		(macro && macro->defined);
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
	/* Built-in headers may define their own implementation-reserved guards
	 * and compatibility macros, but not the preprocessor's magic operators
	 * or predefined values. Trust is attached to the source, never its name. */
	bool builtin_reserved = name.location.source->compiler_builtin &&
		!pp_spelling_is(name, "defined") && !is_predefined_location(name) &&
		!is_predefined_clock(name) && !is_predefined_embed_status(name) &&
		!pp_spelling_is(name, "__has_c_attribute") && !pp_spelling_is(name, "__has_include") &&
		!pp_spelling_is(name, "__has_embed");
	if (is_protected_name(name) && !builtin_reserved) {
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
	*value = macro_is_defined(preprocessor, operand);
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

static bool once_file_seen(const struct preprocessor *preprocessor, const char *name)
{
	for (const struct pragma_once_file *file = preprocessor->once_files; file; file = file->next)
		if (!strcmp(file->name, name))
			return true;
	return false;
}

/* Unknown pragmas have no effect. Recognized pragmas which require semantic
 * or layout support are rejected instead of silently ignored.
 * The body is consumed as raw preprocessing tokens, without macro expansion.
 */
static bool read_pragma_directive(struct preprocessor *preprocessor,
	struct pp_token marker, struct token *error)
{
	struct pp_token token = pp_lexer_next(&preprocessor->input);
	bool first = true;

	while (!is_directive_end(token)) {
		if (token.kind == pp_invalid || token.has_non_directive_space) {
			*error = reject_directive(preprocessor, marker, token,
				token.kind == pp_invalid ? NULL :
				"only space and tab are allowed in a preprocessing directive");
			return false;
		}
		if (first && token.kind == pp_identifier && pp_spelling_is(token, "once")) {
			struct pp_token end = pp_lexer_next(&preprocessor->input);
			struct pragma_once_file *file;

			if (end.kind == pp_invalid || end.has_non_directive_space || !is_directive_end(end)) {
				*error = reject_directive(preprocessor, marker, end,
					end.kind == pp_invalid ? NULL : "expected end of line after pragma once");
				return false;
			}
			if (once_file_seen(preprocessor, marker.location.source->name))
				return true;
			if (preprocessor->once_file_count == preprocess_include_count_limit + 1) {
				*error = stop_preprocessing(preprocessor, marker, "pragma once file limit exceeded");
				return false;
			}
			file = allocate_auxiliary(preprocessor, 1, sizeof(*file), marker, error);
			if (!file)
				return false;
			*file = (struct pragma_once_file) {
				.name = marker.location.source->name, .next = preprocessor->once_files,
			};
			preprocessor->once_files = file;
			preprocessor->once_file_count++;
			return true;
		}
		if (first && token.kind == pp_identifier &&
			(pp_spelling_is(token, "STDC") || pp_spelling_is(token, "pack"))) {
			*error = reject_directive(preprocessor, marker, token,
				"this pragma is not supported yet");
			return false;
		}
		first = false;
		token = pp_lexer_next(&preprocessor->input);
	}
	if (token.has_non_directive_space) {
		*error = reject_directive(preprocessor, marker, token,
			"only space and tab are allowed in a preprocessing directive");
		return false;
	}
	return true;
}

struct embed_parameters {
	uint64_t limit;
	struct argument_token *prefix, *suffix, *if_empty;
};

static bool expand_include_operand(struct preprocessor *preprocessor,
	struct pp_token marker, struct include_name *header, struct token *error, struct embed_parameters *params);

/* Join bounded path slices without changing the process working directory. */
static bool include_path(struct preprocessor *preprocessor, struct include_name *name,
	const char *directory, size_t directory_length, char *path, struct token *error)
{
	size_t length = strlen(name->path);
	bool slash = directory_length && directory[directory_length - 1] != '/';

	if (directory_length >= preprocess_include_path_limit ||
		length + (size_t)slash >= preprocess_include_path_limit - directory_length) {
		*error = stop_preprocessing(preprocessor, name->invocation, "include path limit exceeded");
		return false;
	}
	memcpy(path, directory, directory_length);
	if (slash)
		path[directory_length++] = '/';
	memcpy(path + directory_length, name->path, length + 1);
	return true;
}

/* Quote: including directory, then configured directories. Angle: configured
 * directories only. Absolute names have one candidate in either form.
 */
static bool load_include_source(struct preprocessor *preprocessor,
	struct pp_token marker, struct include_name *name, struct source *source,
	struct token *error, bool *found, bool builtins)
{
	const char *parent = marker.location.source->name;
	bool absolute = name->path[0] == '/';
	size_t candidates = absolute ? 1 : preprocessor->include_directory_count + !name->angled;
	char path[preprocess_include_path_limit];

	if (found)
		*found = true;
	for (size_t i = 0; i < candidates; i++) {
		const char *directory = "";
		size_t length = 0;

		if (!absolute && !name->angled && i == 0) {
			const char *slash = strrchr(parent, '/');

			directory = parent;
			if (slash)
				length = (size_t)(slash - parent) + 1;
		} else if (!absolute) {
			directory = preprocessor->include_directories[i - !name->angled];
			length = strlen(directory);
		}
		if (!include_path(preprocessor, name, directory, length, path, error))
			return false;
		if (preprocessor->include_loader(preprocessor->include_context, source, path))
			return true;
		source_destroy(source);
	}
	/* Explicit include directories win; provide target headers as fallback. */
	if (builtins && !absolute && strcmp(name->path, "stdarg.h") == 0) {
		static const char header[] =
			"#ifndef __KCC_STDARG_H\n"
			"#define __KCC_STDARG_H 1\n"
			"typedef struct __kcc_va_list_tag { unsigned int __gp; unsigned int __fp; "
			"void *__overflow; void *__save; } va_list[1];\n"
			"#define va_start(ap,...) __kcc_va_start(ap)\n"
			"#define va_arg(ap,T) __kcc_va_arg(ap,T)\n"
			"#define va_copy(dst,src) __kcc_va_copy(dst,src)\n"
			"#define va_end(ap) __kcc_va_end(ap)\n"
			"#endif\n";
		if (source_from_bytes(source, "<kcc/stdarg.h>",
			(const unsigned char *)header, sizeof(header) - 1)) {
			source->compiler_builtin = true;
			return true;
		}
		*error = stop_preprocessing(preprocessor, name->invocation,
			"cannot allocate built-in stdarg.h");
		return false;
	}
	if (builtins && !absolute) {
		static const char uchar_header[] =
			"#ifndef __KCC_UCHAR_H\n#define __KCC_UCHAR_H 1\n"
			"#include <stddef.h>\n"
			"typedef unsigned char char8_t;\n"
			"typedef unsigned short char16_t;\n"
			"typedef unsigned int char32_t;\n"
			"#ifndef __mbstate_t_defined\n#define __mbstate_t_defined 1\n"
			"typedef struct { int __count; union { unsigned int __wch; char __wchb[4]; } __value; } mbstate_t;\n"
			"#endif\n"
			"size_t mbrtoc16(char16_t *,const char *,size_t,mbstate_t *);\n"
			"size_t c16rtomb(char *,char16_t,mbstate_t *);\n"
			"size_t mbrtoc32(char32_t *,const char *,size_t,mbstate_t *);\n"
			"size_t c32rtomb(char *,char32_t,mbstate_t *);\n"
			"#endif\n";
		static const char wchar_header[] =
			"#ifndef __KCC_WCHAR_H\n#define __KCC_WCHAR_H 1\n"
			"#include <stddef.h>\n"
			"#ifndef __mbstate_t_defined\n#define __mbstate_t_defined 1\n"
			"typedef struct { int __count; union { unsigned int __wch; char __wchb[4]; } __value; } mbstate_t;\n"
			"#endif\n"
			"typedef unsigned int wint_t;\n#define WEOF 4294967295U\n"
			"#ifndef WCHAR_MIN\n#define WCHAR_MIN (-2147483647-1)\n#define WCHAR_MAX 2147483647\n#endif\n"
			"size_t wcslen(const wchar_t *);\n"
			"wchar_t *wcscpy(wchar_t *,const wchar_t *); wchar_t *wcsncpy(wchar_t *,const wchar_t *,size_t);\n"
			"wchar_t *wcscat(wchar_t *,const wchar_t *); wchar_t *wcsncat(wchar_t *,const wchar_t *,size_t);\n"
			"int wcscmp(const wchar_t *,const wchar_t *); int wcsncmp(const wchar_t *,const wchar_t *,size_t);\n"
			"wchar_t *wcschr(const wchar_t *,wchar_t); wchar_t *wcsrchr(const wchar_t *,wchar_t);\n"
			"wchar_t *wcsstr(const wchar_t *,const wchar_t *);\n"
			"wchar_t *wmemcpy(wchar_t *,const wchar_t *,size_t); wchar_t *wmemmove(wchar_t *,const wchar_t *,size_t);\n"
			"wchar_t *wmemset(wchar_t *,wchar_t,size_t); int wmemcmp(const wchar_t *,const wchar_t *,size_t);\n"
			"wchar_t *wmemchr(const wchar_t *,wchar_t,size_t);\n"
			"wint_t btowc(int); int wctob(wint_t); int mbsinit(const mbstate_t *);\n"
			"size_t mbrlen(const char *,size_t,mbstate_t *);\n"
			"size_t mbrtowc(wchar_t *,const char *,size_t,mbstate_t *);\n"
			"size_t wcrtomb(char *,wchar_t,mbstate_t *);\n"
			"size_t mbsrtowcs(wchar_t *,const char **,size_t,mbstate_t *);\n"
			"size_t wcsrtombs(char *,const wchar_t **,size_t,mbstate_t *);\n"
			"#endif\n";
		static const char wctype_header[] =
			"#ifndef __KCC_WCTYPE_H\n#define __KCC_WCTYPE_H 1\n"
			"#include <wchar.h>\n"
			"typedef unsigned long wctype_t; typedef const int *wctrans_t;\n"
			"int iswalnum(wint_t); int iswalpha(wint_t); int iswblank(wint_t); int iswcntrl(wint_t);\n"
			"int iswdigit(wint_t); int iswgraph(wint_t); int iswlower(wint_t); int iswprint(wint_t);\n"
			"int iswpunct(wint_t); int iswspace(wint_t); int iswupper(wint_t); int iswxdigit(wint_t);\n"
			"wint_t towlower(wint_t); wint_t towupper(wint_t);\n"
			"wctype_t wctype(const char *); int iswctype(wint_t,wctype_t);\n"
			"wctrans_t wctrans(const char *); wint_t towctrans(wint_t,wctrans_t);\n"
			"#endif\n";
		static const char locale_header[] =
			"#ifndef __KCC_LOCALE_H\n#define __KCC_LOCALE_H 1\n"
			"#define LC_CTYPE 0\n#define LC_NUMERIC 1\n#define LC_TIME 2\n"
			"#define LC_COLLATE 3\n#define LC_MONETARY 4\n#define LC_ALL 6\n"
			"struct lconv { char *decimal_point; char *thousands_sep; char *grouping;\n"
			"char *int_curr_symbol; char *currency_symbol; char *mon_decimal_point;\n"
			"char *mon_thousands_sep; char *mon_grouping; char *positive_sign; char *negative_sign;\n"
			"char int_frac_digits; char frac_digits; char p_cs_precedes; char p_sep_by_space;\n"
			"char n_cs_precedes; char n_sep_by_space; char p_sign_posn; char n_sign_posn;\n"
			"char int_p_cs_precedes; char int_p_sep_by_space; char int_n_cs_precedes;\n"
			"char int_n_sep_by_space; char int_p_sign_posn; char int_n_sign_posn; };\n"
			"char *setlocale(int,const char *); struct lconv *localeconv(void);\n"
			"#endif\n";
		static const char stdbool_header[] =
			"#ifndef __KCC_STDBOOL_H\n#define __KCC_STDBOOL_H 1\n"
			"#define __bool_true_false_are_defined 1\n#endif\n";
		static const char stdnoreturn_header[] =
			"#ifndef __KCC_STDNORETURN_H\n#define __KCC_STDNORETURN_H 1\n"
			"#define noreturn _Noreturn\n#endif\n";
		static const char time_header[] =
			"#ifndef __KCC_TIME_H\n#define __KCC_TIME_H 1\n"
			"#include <stddef.h>\n"
			"typedef long time_t; typedef long clock_t;\n"
			"#ifndef _STRUCT_TIMESPEC\n#define _STRUCT_TIMESPEC 1\n"
			"struct timespec { time_t tv_sec; long tv_nsec; };\n#endif\n"
			"struct tm { int tm_sec,tm_min,tm_hour,tm_mday,tm_mon,tm_year,tm_wday,tm_yday,tm_isdst;"
			" long __kcc_gmtoff; const char *__kcc_zone; };\n"
			"#define CLOCKS_PER_SEC 1000000L\n#define TIME_UTC 1\n"
			"time_t time(time_t *); clock_t clock(void); double difftime(time_t,time_t);\n"
			"time_t mktime(struct tm *); struct tm *gmtime(const time_t *);\n"
			"struct tm *localtime(const time_t *); char *asctime(const struct tm *);\n"
			"char *ctime(const time_t *); size_t strftime(char *,size_t,const char *,const struct tm *);\n"
			"int timespec_get(struct timespec *,int); int timespec_getres(struct timespec *,int);\n"
			"#endif\n";
		static const char errno_header[] =
			"#ifndef __KCC_ERRNO_H\n#define __KCC_ERRNO_H 1\n"
			"int *__errno_location(void);\n#define errno (*__errno_location())\n"
			"#define EDOM 33\n#define ERANGE 34\n#define EILSEQ 84\n"
			"#define ENOENT 2\n#define EIO 5\n#define ENOMEM 12\n#define EINVAL 22\n#define EFBIG 27\n"
			"#endif\n";
		static const char math_header[] =
			"#ifndef __KCC_MATH_H\n#define __KCC_MATH_H 1\n"
			"int __finite(double); int __isinf(double); int __isnan(double); int __signbit(double);\n"
			"#define isfinite(x) __finite(x)\n#define isinf(x) __isinf(x)\n"
			"#define isnan(x) __isnan(x)\n#define signbit(x) __signbit(x)\n"
			"double fabs(double); float fabsf(float);\n"
			"double sqrt(double); float sqrtf(float); double cbrt(double); float cbrtf(float);\n"
			"double sin(double); float sinf(float); double cos(double); float cosf(float);\n"
			"double tan(double); float tanf(float); double asin(double); float asinf(float);\n"
			"double acos(double); float acosf(float); double atan(double); float atanf(float);\n"
			"double atan2(double,double); float atan2f(float,float);\n"
			"double exp(double); float expf(float); double log(double); float logf(float);\n"
			"double log10(double); float log10f(float); double pow(double,double); float powf(float,float);\n"
			"double floor(double); float floorf(float); double ceil(double); float ceilf(float);\n"
			"double trunc(double); float truncf(float); double round(double); float roundf(float);\n"
			"double fmod(double,double); float fmodf(float,float);\n"
			"#endif\n";
		static const char tgmath_header[] =
			"#ifndef __KCC_TGMATH_H\n#define __KCC_TGMATH_H 1\n"
			"#include <math.h>\n"
			"#define fabs(x) _Generic((x),float:fabsf,default:fabs)(x)\n"
			"#define sqrt(x) _Generic((x),float:sqrtf,default:sqrt)(x)\n"
			"#define cbrt(x) _Generic((x),float:cbrtf,default:cbrt)(x)\n"
			"#define sin(x) _Generic((x),float:sinf,default:sin)(x)\n"
			"#define cos(x) _Generic((x),float:cosf,default:cos)(x)\n"
			"#define tan(x) _Generic((x),float:tanf,default:tan)(x)\n"
			"#define asin(x) _Generic((x),float:asinf,default:asin)(x)\n"
			"#define acos(x) _Generic((x),float:acosf,default:acos)(x)\n"
			"#define atan(x) _Generic((x),float:atanf,default:atan)(x)\n"
			"#define exp(x) _Generic((x),float:expf,default:exp)(x)\n"
			"#define log(x) _Generic((x),float:logf,default:log)(x)\n"
			"#define log10(x) _Generic((x),float:log10f,default:log10)(x)\n"
			"#define floor(x) _Generic((x),float:floorf,default:floor)(x)\n"
			"#define ceil(x) _Generic((x),float:ceilf,default:ceil)(x)\n"
			"#define trunc(x) _Generic((x),float:truncf,default:trunc)(x)\n"
			"#define round(x) _Generic((x),float:roundf,default:round)(x)\n"
			"#define atan2(x,y) _Generic((x),float:_Generic((y),float:atan2f,default:atan2),default:atan2)((x),(y))\n"
			"#define pow(x,y) _Generic((x),float:_Generic((y),float:powf,default:pow),default:pow)((x),(y))\n"
			"#define fmod(x,y) _Generic((x),float:_Generic((y),float:fmodf,default:fmod),default:fmod)((x),(y))\n"
			"#endif\n";
		static const char ctype_header[] =
			"#ifndef __KCC_CTYPE_H\n#define __KCC_CTYPE_H 1\n"
			"int isalnum(int); int isalpha(int); int isblank(int); int iscntrl(int);\n"
			"int isdigit(int); int isgraph(int); int islower(int); int isprint(int);\n"
			"int ispunct(int); int isspace(int); int isupper(int); int isxdigit(int);\n"
			"int tolower(int); int toupper(int);\n"
			"#endif\n";
		static const char inttypes_header[] =
			"#ifndef __KCC_INTTYPES_H\n#define __KCC_INTTYPES_H 1\n#include <stdint.h>\n"
			"#define PRId8 \"d\"\n#define PRIi8 \"i\"\n#define PRIu8 \"u\"\n#define PRIx8 \"x\"\n#define PRIX8 \"X\"\n#define PRIo8 \"o\"\n"
			"#define PRId16 \"d\"\n#define PRIi16 \"i\"\n#define PRIu16 \"u\"\n#define PRIx16 \"x\"\n#define PRIX16 \"X\"\n#define PRIo16 \"o\"\n"
			"#define PRId32 \"d\"\n#define PRIi32 \"i\"\n#define PRIu32 \"u\"\n#define PRIx32 \"x\"\n#define PRIX32 \"X\"\n#define PRIo32 \"o\"\n"
			"#define PRId64 \"ld\"\n#define PRIi64 \"li\"\n#define PRIu64 \"lu\"\n#define PRIx64 \"lx\"\n#define PRIX64 \"lX\"\n#define PRIo64 \"lo\"\n"
			"#define PRIdPTR PRId64\n#define PRIiPTR PRIi64\n#define PRIuPTR PRIu64\n"
			"#define PRIxPTR PRIx64\n#define PRIXPTR PRIX64\n#define PRIoPTR PRIo64\n"
			"#define PRIdMAX PRId64\n#define PRIiMAX PRIi64\n#define PRIuMAX PRIu64\n"
			"#define PRIxMAX PRIx64\n#define PRIXMAX PRIX64\n#define PRIoMAX PRIo64\n"
			"#define PRIdLEAST8 PRId8\n"
			"#define PRIiLEAST8 PRIi8\n"
			"#define PRIuLEAST8 PRIu8\n"
			"#define PRIoLEAST8 PRIo8\n"
			"#define PRIxLEAST8 PRIx8\n"
			"#define PRIXLEAST8 PRIX8\n"
			"#define PRIdLEAST16 PRId16\n"
			"#define PRIiLEAST16 PRIi16\n"
			"#define PRIuLEAST16 PRIu16\n"
			"#define PRIoLEAST16 PRIo16\n"
			"#define PRIxLEAST16 PRIx16\n"
			"#define PRIXLEAST16 PRIX16\n"
			"#define PRIdLEAST32 PRId32\n"
			"#define PRIiLEAST32 PRIi32\n"
			"#define PRIuLEAST32 PRIu32\n"
			"#define PRIoLEAST32 PRIo32\n"
			"#define PRIxLEAST32 PRIx32\n"
			"#define PRIXLEAST32 PRIX32\n"
			"#define PRIdLEAST64 PRId64\n"
			"#define PRIiLEAST64 PRIi64\n"
			"#define PRIuLEAST64 PRIu64\n"
			"#define PRIoLEAST64 PRIo64\n"
			"#define PRIxLEAST64 PRIx64\n"
			"#define PRIXLEAST64 PRIX64\n"
			"#define PRIdFAST8 PRId8\n"
			"#define PRIiFAST8 PRIi8\n"
			"#define PRIuFAST8 PRIu8\n"
			"#define PRIoFAST8 PRIo8\n"
			"#define PRIxFAST8 PRIx8\n"
			"#define PRIXFAST8 PRIX8\n"
			"#define PRIdFAST16 PRId64\n"
			"#define PRIiFAST16 PRIi64\n"
			"#define PRIuFAST16 PRIu64\n"
			"#define PRIoFAST16 PRIo64\n"
			"#define PRIxFAST16 PRIx64\n"
			"#define PRIXFAST16 PRIX64\n"
			"#define PRIdFAST32 PRId64\n"
			"#define PRIiFAST32 PRIi64\n"
			"#define PRIuFAST32 PRIu64\n"
			"#define PRIoFAST32 PRIo64\n"
			"#define PRIxFAST32 PRIx64\n"
			"#define PRIXFAST32 PRIX64\n"
			"#define PRIdFAST64 PRId64\n"
			"#define PRIiFAST64 PRIi64\n"
			"#define PRIuFAST64 PRIu64\n"
			"#define PRIoFAST64 PRIo64\n"
			"#define PRIxFAST64 PRIx64\n"
			"#define PRIXFAST64 PRIX64\n"
			"#define SCNd8 \"hhd\"\n"
			"#define SCNi8 \"hhi\"\n"
			"#define SCNu8 \"hhu\"\n"
			"#define SCNo8 \"hho\"\n"
			"#define SCNx8 \"hhx\"\n"
			"#define SCNd16 \"hd\"\n"
			"#define SCNi16 \"hi\"\n"
			"#define SCNu16 \"hu\"\n"
			"#define SCNo16 \"ho\"\n"
			"#define SCNx16 \"hx\"\n"
			"#define SCNd32 \"d\"\n"
			"#define SCNi32 \"i\"\n"
			"#define SCNu32 \"u\"\n"
			"#define SCNo32 \"o\"\n"
			"#define SCNx32 \"x\"\n"
			"#define SCNd64 \"ld\"\n"
			"#define SCNi64 \"li\"\n"
			"#define SCNu64 \"lu\"\n"
			"#define SCNo64 \"lo\"\n"
			"#define SCNx64 \"lx\"\n"
			"#define SCNdLEAST8 \"hhd\"\n"
			"#define SCNiLEAST8 \"hhi\"\n"
			"#define SCNuLEAST8 \"hhu\"\n"
			"#define SCNoLEAST8 \"hho\"\n"
			"#define SCNxLEAST8 \"hhx\"\n"
			"#define SCNdLEAST16 \"hd\"\n"
			"#define SCNiLEAST16 \"hi\"\n"
			"#define SCNuLEAST16 \"hu\"\n"
			"#define SCNoLEAST16 \"ho\"\n"
			"#define SCNxLEAST16 \"hx\"\n"
			"#define SCNdLEAST32 \"d\"\n"
			"#define SCNiLEAST32 \"i\"\n"
			"#define SCNuLEAST32 \"u\"\n"
			"#define SCNoLEAST32 \"o\"\n"
			"#define SCNxLEAST32 \"x\"\n"
			"#define SCNdLEAST64 \"ld\"\n"
			"#define SCNiLEAST64 \"li\"\n"
			"#define SCNuLEAST64 \"lu\"\n"
			"#define SCNoLEAST64 \"lo\"\n"
			"#define SCNxLEAST64 \"lx\"\n"
			"#define SCNdFAST8 \"hhd\"\n"
			"#define SCNiFAST8 \"hhi\"\n"
			"#define SCNuFAST8 \"hhu\"\n"
			"#define SCNoFAST8 \"hho\"\n"
			"#define SCNxFAST8 \"hhx\"\n"
			"#define SCNdFAST16 \"ld\"\n"
			"#define SCNiFAST16 \"li\"\n"
			"#define SCNuFAST16 \"lu\"\n"
			"#define SCNoFAST16 \"lo\"\n"
			"#define SCNxFAST16 \"lx\"\n"
			"#define SCNdFAST32 \"ld\"\n"
			"#define SCNiFAST32 \"li\"\n"
			"#define SCNuFAST32 \"lu\"\n"
			"#define SCNoFAST32 \"lo\"\n"
			"#define SCNxFAST32 \"lx\"\n"
			"#define SCNdFAST64 \"ld\"\n"
			"#define SCNiFAST64 \"li\"\n"
			"#define SCNuFAST64 \"lu\"\n"
			"#define SCNoFAST64 \"lo\"\n"
			"#define SCNxFAST64 \"lx\"\n"
			"#define SCNdPTR \"ld\"\n"
			"#define SCNiPTR \"li\"\n"
			"#define SCNuPTR \"lu\"\n"
			"#define SCNoPTR \"lo\"\n"
			"#define SCNxPTR \"lx\"\n"
			"#define SCNdMAX \"ld\"\n"
			"#define SCNiMAX \"li\"\n"
			"#define SCNuMAX \"lu\"\n"
			"#define SCNoMAX \"lo\"\n"
			"#define SCNxMAX \"lx\"\n"
			"intmax_t imaxabs(intmax_t);\n"
			"intmax_t strtoimax(const char *,char **,int);\n"
			"uintmax_t strtoumax(const char *,char **,int);\n"
			"#endif\n";
		/* assert.h is intentionally re-evaluated on each inclusion for NDEBUG. */
		static const char assert_header[] =
			"#undef assert\n"
			"#ifdef NDEBUG\n#define assert(...) ((void)0)\n#else\n"
			"void __assert_fail(const char *, const char *, unsigned int, const char *);\n"
			"#define assert(...) ((__VA_ARGS__) ? (void)0 : "
			"__assert_fail(#__VA_ARGS__, __FILE__, __LINE__, __func__))\n"
			"#endif\n";
		static const char stdatomic_header[] =
			"#ifndef __KCC_STDATOMIC_H\n#define __KCC_STDATOMIC_H 1\n"
			"typedef _Atomic _Bool atomic_bool;\n"
			"typedef _Atomic char atomic_char;\ntypedef _Atomic signed char atomic_schar;\n"
			"typedef _Atomic unsigned char atomic_uchar;\ntypedef _Atomic short atomic_short;\n"
			"typedef _Atomic unsigned short atomic_ushort;\n"
			"typedef _Atomic int atomic_int;\ntypedef _Atomic unsigned int atomic_uint;\n"
			"typedef _Atomic long atomic_long;\ntypedef _Atomic unsigned long atomic_ulong;\n"
			"typedef _Atomic long long atomic_llong;\ntypedef _Atomic unsigned long long atomic_ullong;\n"
			"typedef atomic_int atomic_wchar_t; typedef atomic_ushort atomic_char16_t; typedef atomic_uint atomic_char32_t;\n"
			"typedef atomic_schar atomic_int_least8_t; typedef atomic_uchar atomic_uint_least8_t;\n"
			"typedef atomic_short atomic_int_least16_t; typedef atomic_ushort atomic_uint_least16_t;\n"
			"typedef atomic_int atomic_int_least32_t; typedef atomic_uint atomic_uint_least32_t;\n"
			"typedef atomic_long atomic_int_least64_t; typedef atomic_ulong atomic_uint_least64_t;\n"
			"typedef atomic_schar atomic_int_fast8_t; typedef atomic_uchar atomic_uint_fast8_t;\n"
			"typedef atomic_long atomic_int_fast16_t; typedef atomic_ulong atomic_uint_fast16_t;\n"
			"typedef atomic_long atomic_int_fast32_t; typedef atomic_ulong atomic_uint_fast32_t;\n"
			"typedef atomic_long atomic_int_fast64_t; typedef atomic_ulong atomic_uint_fast64_t;\n"
			"typedef atomic_long atomic_intptr_t; typedef atomic_ulong atomic_uintptr_t;\n"
			"typedef atomic_ulong atomic_size_t; typedef atomic_long atomic_ptrdiff_t;\n"
			"typedef atomic_long atomic_intmax_t; typedef atomic_ulong atomic_uintmax_t;\n";
		static const char stdatomic_header_tail[] =
			"typedef _Atomic unsigned int atomic_flag;\n"
			"typedef enum { memory_order_relaxed=0, memory_order_consume=1, memory_order_acquire=2,"
			" memory_order_release=3, memory_order_acq_rel=4, memory_order_seq_cst=5 } memory_order;\n"
			"void atomic_thread_fence(memory_order);\n"
			"void atomic_signal_fence(memory_order);\n"
			"#define ATOMIC_VAR_INIT(value) (value)\n"
			"#define ATOMIC_FLAG_INIT 0U\n"
			"#define atomic_init(object,value) ((void)(*(object)=(value)))\n"
			"#define atomic_is_lock_free(object) __kcc_atomic_is_lock_free(object)\n"
			"#define atomic_flag_test_and_set(object) ((_Bool)__kcc_atomic_exchange(object,1U))\n"
			"#define atomic_flag_test_and_set_explicit(object,order) ((_Bool)__kcc_atomic_exchange(object,1U,order))\n"
			"#define atomic_flag_clear(object) ((void)__kcc_atomic_store(object,0U))\n"
			"#define atomic_flag_clear_explicit(object,order) ((void)__kcc_atomic_store(object,0U,order))\n"
			"#define atomic_load(object) __kcc_atomic_load(object)\n"
			"#define atomic_store(object,value) ((void)__kcc_atomic_store(object,value))\n"
			"#define atomic_load_explicit(object,order) __kcc_atomic_load(object,order)\n"
			"#define atomic_store_explicit(object,value,order) ((void)__kcc_atomic_store(object,value,order))\n"
			"#define atomic_fetch_add(object,value) __kcc_atomic_fetch_add(object,value)\n"
			"#define atomic_fetch_sub(object,value) __kcc_atomic_fetch_sub(object,value)\n"
			"#define atomic_fetch_and(object,value) __kcc_atomic_fetch_and(object,value)\n"
			"#define atomic_fetch_or(object,value) __kcc_atomic_fetch_or(object,value)\n"
			"#define atomic_fetch_xor(object,value) __kcc_atomic_fetch_xor(object,value)\n"
			"#define atomic_exchange(object,value) __kcc_atomic_exchange(object,value)\n"
			"#define atomic_compare_exchange_strong(object,expected,desired) __kcc_atomic_compare_exchange(object,expected,desired)\n"
			"#define atomic_compare_exchange_weak(object,expected,desired) __kcc_atomic_compare_exchange(object,expected,desired)\n"
			"#define atomic_fetch_add_explicit(object,value,order) __kcc_atomic_fetch_add(object,value,order)\n"
			"#define atomic_fetch_sub_explicit(object,value,order) __kcc_atomic_fetch_sub(object,value,order)\n"
			"#define atomic_fetch_and_explicit(object,value,order) __kcc_atomic_fetch_and(object,value,order)\n"
			"#define atomic_fetch_or_explicit(object,value,order) __kcc_atomic_fetch_or(object,value,order)\n"
			"#define atomic_fetch_xor_explicit(object,value,order) __kcc_atomic_fetch_xor(object,value,order)\n"
			"#define atomic_exchange_explicit(object,value,order) __kcc_atomic_exchange(object,value,order)\n"
			"#define atomic_compare_exchange_strong_explicit(object,expected,desired,success,failure) __kcc_atomic_compare_exchange(object,expected,desired,success,failure)\n"
			"#define atomic_compare_exchange_weak_explicit(object,expected,desired,success,failure) __kcc_atomic_compare_exchange(object,expected,desired,success,failure)\n"
			"#endif\n";
		static const char stdlib_header[] =
			"#ifndef __KCC_STDLIB_H\n#define __KCC_STDLIB_H 1\n"
			"#include <stddef.h>\n"
			"#define EXIT_SUCCESS 0\n#define EXIT_FAILURE 1\n#define RAND_MAX 2147483647\n"
			"void *malloc(size_t); void *calloc(size_t,size_t); void *realloc(void *,size_t);\n"
			"void free(void *); void abort(void); void exit(int); void _Exit(int);\n"
			"int atoi(const char *); long atol(const char *); long long atoll(const char *);\n"
			"long strtol(const char *,char **,int); unsigned long strtoul(const char *,char **,int);\n"
			"long long strtoll(const char *,char **,int); unsigned long long strtoull(const char *,char **,int);\n"
			"float strtof(const char *,char **); double strtod(const char *,char **);\n"
			"int rand(void); void srand(unsigned int);\n"
			"int abs(int); long labs(long); long long llabs(long long);\n"
			"void qsort(void *,size_t,size_t,int (*)(const void *,const void *));\n"
			"void *bsearch(const void *,const void *,size_t,size_t,int (*)(const void *,const void *));\n"
			"#endif\n";
		static const char string_header[] =
			"#ifndef __KCC_STRING_H\n#define __KCC_STRING_H 1\n"
			"#include <stddef.h>\n"
			"void *memcpy(void *,const void *,size_t); void *memmove(void *,const void *,size_t);\n"
			"void *memset(void *,int,size_t); int memcmp(const void *,const void *,size_t);\n"
			"void *memchr(const void *,int,size_t);\n"
			"size_t strlen(const char *); char *strcpy(char *,const char *);\n"
			"char *strncpy(char *,const char *,size_t); char *strcat(char *,const char *);\n"
			"char *strncat(char *,const char *,size_t); int strcmp(const char *,const char *);\n"
			"int strncmp(const char *,const char *,size_t); char *strchr(const char *,int);\n"
			"char *strrchr(const char *,int); char *strstr(const char *,const char *);\n"
			"char *strerror(int);\n"
			"#endif\n";
		static const char stdio_header[] =
			"#ifndef __KCC_STDIO_H\n#define __KCC_STDIO_H 1\n"
			"#include <stddef.h>\n#include <stdarg.h>\n"
			"typedef struct _IO_FILE FILE;\n"
			"extern FILE *stdin; extern FILE *stdout; extern FILE *stderr;\n"
			"#define EOF (-1)\n#define SEEK_SET 0\n#define SEEK_CUR 1\n#define SEEK_END 2\n"
			"#define BUFSIZ 8192\n"
			"FILE *fopen(const char *,const char *); FILE *freopen(const char *,const char *,FILE *);\n"
			"int fclose(FILE *); int fflush(FILE *);\n"
			"size_t fread(void *,size_t,size_t,FILE *); size_t fwrite(const void *,size_t,size_t,FILE *);\n"
			"int fgetc(FILE *); int getc(FILE *); int getchar(void);\n"
			"int fputc(int,FILE *); int putc(int,FILE *); int putchar(int);\n"
			"char *fgets(char *,int,FILE *); int fputs(const char *,FILE *); int puts(const char *);\n"
			"int printf(const char *,...); int fprintf(FILE *,const char *,...);\n"
			"int sprintf(char *,const char *,...); int snprintf(char *,size_t,const char *,...);\n"
			"int vprintf(const char *,va_list); int vfprintf(FILE *,const char *,va_list);\n"
			"int vsprintf(char *,const char *,va_list); int vsnprintf(char *,size_t,const char *,va_list);\n"
			"int scanf(const char *,...); int fscanf(FILE *,const char *,...); int sscanf(const char *,const char *,...);\n"
			"int fseek(FILE *,long,int); long ftell(FILE *); void rewind(FILE *);\n"
			"int feof(FILE *); int ferror(FILE *); void clearerr(FILE *);\n"
			"int remove(const char *); int rename(const char *,const char *); void perror(const char *);\n"
			"#endif\n";
		static const char stddef_header[] =
			"#ifndef __KCC_STDDEF_H\n#define __KCC_STDDEF_H 1\n"
			"typedef unsigned long size_t;\ntypedef long ptrdiff_t;\n"
			"typedef int wchar_t;\ntypedef typeof(nullptr) nullptr_t;\n"
			"typedef struct { long long __kcc_ll; alignas(16) long long __kcc_ld; } max_align_t;\n"
			"#define NULL ((void *)0)\n"
			"#define offsetof(type,member) __kcc_offsetof(type,member)\n#endif\n";
		static const char limits_header[] =
			"#ifndef __KCC_LIMITS_H\n#define __KCC_LIMITS_H 1\n"
			"#define CHAR_BIT 8\n#define MB_LEN_MAX 16\n"
			"#define SCHAR_MIN (-127-1)\n#define SCHAR_MAX 127\n#define UCHAR_MAX 255\n"
			"#define CHAR_MIN SCHAR_MIN\n#define CHAR_MAX SCHAR_MAX\n"
			"#define SHRT_MIN (-32767-1)\n#define SHRT_MAX 32767\n#define USHRT_MAX 65535\n"
			"#define INT_MIN (-2147483647-1)\n#define INT_MAX 2147483647\n#define UINT_MAX 4294967295U\n"
			"#define LONG_MIN (-9223372036854775807L-1L)\n#define LONG_MAX 9223372036854775807L\n"
			"#define ULONG_MAX 18446744073709551615UL\n"
			"#define LLONG_MIN (-9223372036854775807LL-1LL)\n#define LLONG_MAX 9223372036854775807LL\n"
			"#define ULLONG_MAX 18446744073709551615ULL\n"
			"#define BOOL_WIDTH 1\n#define CHAR_WIDTH 8\n#define SCHAR_WIDTH 8\n#define UCHAR_WIDTH 8\n"
			"#define SHRT_WIDTH 16\n#define USHRT_WIDTH 16\n#define INT_WIDTH 32\n#define UINT_WIDTH 32\n"
			"#define LONG_WIDTH 64\n#define ULONG_WIDTH 64\n#define LLONG_WIDTH 64\n#define ULLONG_WIDTH 64\n"
			"#endif\n";
		static const char float_header[] =
			"#ifndef __KCC_FLOAT_H\n#define __KCC_FLOAT_H 1\n"
			"#define FLT_RADIX 2\n#define FLT_ROUNDS 1\n#define FLT_EVAL_METHOD 0\n"
			"#define FLT_MANT_DIG 24\n#define FLT_DIG 6\n#define FLT_DECIMAL_DIG 9\n"
			"#define FLT_MIN_EXP (-125)\n#define FLT_MIN_10_EXP (-37)\n"
			"#define FLT_MAX_EXP 128\n#define FLT_MAX_10_EXP 38\n"
			"#define FLT_MIN 1.17549435082228750796873653722224568e-38F\n"
			"#define FLT_MAX 3.40282346638528859811704183484516925e+38F\n"
			"#define FLT_EPSILON 1.1920928955078125e-7F\n"
			"#define DBL_MANT_DIG 53\n#define DBL_DIG 15\n#define DBL_DECIMAL_DIG 17\n"
			"#define DBL_MIN_EXP (-1021)\n#define DBL_MIN_10_EXP (-307)\n"
			"#define DBL_MAX_EXP 1024\n#define DBL_MAX_10_EXP 308\n"
			"#define DBL_MIN 2.22507385850720138309023271733240406e-308\n"
			"#define DBL_MAX 1.79769313486231570814527423731704357e+308\n"
			"#define DBL_EPSILON 2.220446049250313080847263336181640625e-16\n"
			"#endif\n";
		static const char stdint_header[] =
			"#ifndef __KCC_STDINT_H\n#define __KCC_STDINT_H 1\n"
			"typedef signed char int8_t;\ntypedef unsigned char uint8_t;\n"
			"typedef short int16_t;\ntypedef unsigned short uint16_t;\n"
			"typedef int int32_t;\ntypedef unsigned int uint32_t;\n"
			"typedef long int64_t;\ntypedef unsigned long uint64_t;\n"
			"typedef long intptr_t;\ntypedef unsigned long uintptr_t;\n"
			"typedef long intmax_t;\ntypedef unsigned long uintmax_t;\n"
			"typedef int8_t int_least8_t;\ntypedef uint8_t uint_least8_t;\n"
			"typedef int16_t int_least16_t;\ntypedef uint16_t uint_least16_t;\n"
			"typedef int32_t int_least32_t;\ntypedef uint32_t uint_least32_t;\n"
			"typedef int64_t int_least64_t;\ntypedef uint64_t uint_least64_t;\n"
			"typedef signed char int_fast8_t;\ntypedef unsigned char uint_fast8_t;\n"
			"typedef long int_fast16_t;\ntypedef unsigned long uint_fast16_t;\n"
			"typedef long int_fast32_t;\ntypedef unsigned long uint_fast32_t;\n"
			"typedef long int_fast64_t;\ntypedef unsigned long uint_fast64_t;\n"
			"#define INT8_MAX 127\n#define INT8_MIN (-127-1)\n#define UINT8_MAX 255\n"
			"#define INT16_MAX 32767\n#define INT16_MIN (-32767-1)\n#define UINT16_MAX 65535\n"
			"#define INT32_MAX 2147483647\n#define INT32_MIN (-2147483647-1)\n#define UINT32_MAX 4294967295U\n"
			"#define INT64_MAX 9223372036854775807L\n"
			"#define INT64_MIN (-9223372036854775807L-1L)\n#define UINT64_MAX 18446744073709551615UL\n"
			"#define INTPTR_MAX INT64_MAX\n#define INTPTR_MIN INT64_MIN\n#define UINTPTR_MAX UINT64_MAX\n"
			"#define INTMAX_MAX INT64_MAX\n#define INTMAX_MIN INT64_MIN\n#define UINTMAX_MAX UINT64_MAX\n"
			"#define SIZE_MAX UINT64_MAX\n#define PTRDIFF_MAX INT64_MAX\n#define PTRDIFF_MIN INT64_MIN\n"
			"#define INT_LEAST8_MIN INT8_MIN\n#define INT_LEAST8_MAX INT8_MAX\n#define UINT_LEAST8_MAX UINT8_MAX\n"
			"#define INT_LEAST16_MIN INT16_MIN\n#define INT_LEAST16_MAX INT16_MAX\n#define UINT_LEAST16_MAX UINT16_MAX\n"
			"#define INT_LEAST32_MIN INT32_MIN\n#define INT_LEAST32_MAX INT32_MAX\n#define UINT_LEAST32_MAX UINT32_MAX\n"
			"#define INT_LEAST64_MIN INT64_MIN\n#define INT_LEAST64_MAX INT64_MAX\n#define UINT_LEAST64_MAX UINT64_MAX\n"
			"#define INT_FAST8_MIN INT8_MIN\n#define INT_FAST8_MAX INT8_MAX\n#define UINT_FAST8_MAX UINT8_MAX\n"
			"#define INT_FAST16_MIN INT64_MIN\n#define INT_FAST16_MAX INT64_MAX\n#define UINT_FAST16_MAX UINT64_MAX\n"
			"#define INT_FAST32_MIN INT64_MIN\n#define INT_FAST32_MAX INT64_MAX\n#define UINT_FAST32_MAX UINT64_MAX\n"
			"#define INT_FAST64_MIN INT64_MIN\n#define INT_FAST64_MAX INT64_MAX\n#define UINT_FAST64_MAX UINT64_MAX\n"
			"#define INT8_C(c) c\n#define UINT8_C(c) c\n#define INT16_C(c) c\n#define UINT16_C(c) c\n"
			"#define INT32_C(c) c\n#define UINT32_C(c) c ## U\n"
			"#ifndef WCHAR_MIN\n#define WCHAR_MIN (-2147483647-1)\n#define WCHAR_MAX 2147483647\n#endif\n"
			"#define WINT_MIN 0U\n#define WINT_MAX 4294967295U\n"
			"#define INT64_C(c) c ## L\n#define UINT64_C(c) c ## UL\n"
			"#define INTMAX_C(c) c ## L\n#define UINTMAX_C(c) c ## UL\n"
			"#endif\n";
		const char *header = NULL, *header_tail = NULL, *source_name = NULL;

		if (strcmp(name->path, "locale.h") == 0) {
			header = locale_header;
			source_name = "<kcc/locale.h>";
		} else if (strcmp(name->path, "wctype.h") == 0) {
			header = wctype_header;
			source_name = "<kcc/wctype.h>";
		} else if (strcmp(name->path, "wchar.h") == 0) {
			header = wchar_header;
			source_name = "<kcc/wchar.h>";
		} else if (strcmp(name->path, "uchar.h") == 0) {
			header = uchar_header;
			source_name = "<kcc/uchar.h>";
		} else if (strcmp(name->path, "stdbool.h") == 0) {
			header = stdbool_header;
			source_name = "<kcc/stdbool.h>";
		} else if (strcmp(name->path, "stdnoreturn.h") == 0) {
			header = stdnoreturn_header;
			source_name = "<kcc/stdnoreturn.h>";
		} else if (strcmp(name->path, "time.h") == 0) {
			header = time_header;
			source_name = "<kcc/time.h>";
		} else if (strcmp(name->path, "errno.h") == 0) {
			header = errno_header;
			source_name = "<kcc/errno.h>";
		} else if (strcmp(name->path, "math.h") == 0) {
			header = math_header;
			source_name = "<kcc/math.h>";
		} else if (strcmp(name->path, "tgmath.h") == 0) {
			header = tgmath_header;
			source_name = "<kcc/tgmath.h>";
		} else if (strcmp(name->path, "ctype.h") == 0) {
			header = ctype_header;
			source_name = "<kcc/ctype.h>";
		} else if (strcmp(name->path, "inttypes.h") == 0) {
			header = inttypes_header;
			source_name = "<kcc/inttypes.h>";
		} else if (strcmp(name->path, "assert.h") == 0) {
			header = assert_header;
			source_name = "<kcc/assert.h>";
		} else if (strcmp(name->path, "stdatomic.h") == 0) {
			header = stdatomic_header;
			header_tail = stdatomic_header_tail;
			source_name = "<kcc/stdatomic.h>";
		} else if (strcmp(name->path, "stdlib.h") == 0) {
			header = stdlib_header;
			source_name = "<kcc/stdlib.h>";
		} else if (strcmp(name->path, "string.h") == 0) {
			header = string_header;
			source_name = "<kcc/string.h>";
		} else if (strcmp(name->path, "stdio.h") == 0) {
			header = stdio_header;
			source_name = "<kcc/stdio.h>";
		} else if (strcmp(name->path, "stddef.h") == 0) {
			header = stddef_header;
			source_name = "<kcc/stddef.h>";
		} else if (strcmp(name->path, "stdint.h") == 0) {
			header = stdint_header;
			source_name = "<kcc/stdint.h>";
		} else if (strcmp(name->path, "limits.h") == 0) {
			header = limits_header;
			source_name = "<kcc/limits.h>";
		} else if (strcmp(name->path, "float.h") == 0) {
			header = float_header;
			source_name = "<kcc/float.h>";
		}
		if (header) {
			bool loaded = false;
			if (header_tail) {
				size_t first = strlen(header), second = strlen(header_tail);
				unsigned char *joined = malloc(first + second);
				if (joined) {
					memcpy(joined, header, first);
					memcpy(joined + first, header_tail, second);
					loaded = source_from_bytes(source, source_name, joined, first + second);
					free(joined);
				}
			} else
				loaded = source_from_bytes(source, source_name, (const unsigned char *)header, strlen(header));
			if (loaded) {
				source->compiler_builtin = true;
				return true;
			}
			*error = stop_preprocessing(preprocessor, name->invocation,
				"cannot allocate built-in standard header");
			return false;
		}
	}

	if (found) {
		*found = false;
		return true;
	}
	{
		char message[preprocess_include_path_limit + 64];

		snprintf(message, sizeof(message), "cannot load %s include '%s'",
			name->angled ? "angle" : "quoted", name->path);
		diagnostic_error(preprocessor->diagnostics, name->invocation.expansion_location, message);
	}
	*error = invalid_token(marker);
	return false;
}

/* include-directive = '#' 'include' include-operand
 * Resolve a validated direct/computed name, retaining every successful source.
 */
static bool read_include_directive(struct preprocessor *preprocessor,
	struct pp_token marker, struct token *error)
{
	struct include_name name;
	struct include_source *child;

	if (!expand_include_operand(preprocessor, marker, &name, error, NULL))
		return false;
	if (!preprocessor->include_loader) {
		diagnostic_error(preprocessor->diagnostics, name.invocation.expansion_location,
			"includes require a configured source loader");
		*error = invalid_token(marker);
		return false;
	}
	if (preprocessor->include_depth == preprocess_include_depth_limit) {
		*error = stop_preprocessing(preprocessor, name.invocation, "include nesting limit (32) exceeded");
		return false;
	}
	if (preprocessor->include_count == preprocess_include_count_limit) {
		*error = stop_preprocessing(preprocessor, name.invocation, "include attempt limit (128) exceeded");
		return false;
	}
	child = allocate_auxiliary(preprocessor, 1, sizeof(*child), name.invocation, error);
	if (!child)
		return false;
	*child = (struct include_source) { 0 };
	preprocessor->include_count++;
	if (!load_include_source(preprocessor, marker, &name, &child->source, error, NULL, true))
		return false;
	if (once_file_seen(preprocessor, child->source.name)) {
		source_destroy(&child->source);
		preprocessor->cursor.deferred_space = true;
		return true;
	}
	if (child->source.length > preprocess_include_bytes_limit - preprocessor->include_bytes) {
		source_destroy(&child->source);
		*error = stop_preprocessing(preprocessor, name.invocation, "include input byte limit exceeded");
		return false;
	}
	preprocessor->include_bytes += child->source.length;
	if (!source_prepare(&child->source)) {
		source_destroy(&child->source);
		*error = stop_preprocessing(preprocessor, name.invocation, "cannot prepare include source");
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

/* control-line = '#' newline | define-directive | undef-directive | diagnostic-directive | pragma
 *              | include-directive | line-directive
 *              | conditional-control
 * Other C23 control lines are recognized but not implemented yet.
 */
static bool read_line_directive(struct preprocessor *preprocessor,
	struct pp_token marker, struct token *error);

static bool read_embed_directive(struct preprocessor *preprocessor,
	struct pp_token marker, struct token *error);

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
	if (pp_spelling_is(token, "embed"))
		return read_embed_directive(preprocessor, marker, error);
	if (pp_spelling_is(token, "line"))
		return read_line_directive(preprocessor, marker, error);
	if (pp_spelling_is(token, "define") || pp_spelling_is(token, "undef"))
		return read_macro_directive(preprocessor, marker,
			pp_spelling_is(token, "define"), error);
	if (pp_spelling_is(token, "error") || pp_spelling_is(token, "warning"))
		return read_diagnostic_directive(preprocessor, marker, token, error);
	if (pp_spelling_is(token, "pragma"))
		return read_pragma_directive(preprocessor, marker, error);
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

	if (*length > remaining || amount > remaining - *length) {
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

/* The stored sites are physical; maps are selected by both source identity and
 * physical line so cached/macro-origin tokens cannot inherit a later mapping. */
static bool logical_position(struct preprocessor *preprocessor, struct source_location site,
	struct pp_token blame, size_t *physical, size_t *logical, const char **name,
	struct token *error)
{
	size_t column, scan;

	if (!site.source || !site.source->name || site.offset > site.source->length) {
		*error = stop_preprocessing(preprocessor, blame, "invalid semantic source location");
		return false;
	}
	scan = source_physical_offset(site);
	if (scan > preprocess_line_scan_limit - preprocessor->line_scan_bytes) {
		*error = stop_preprocessing(preprocessor, blame, "predefined line lookup work limit exceeded");
		return false;
	}
	preprocessor->line_scan_bytes += scan;
	source_line_column(site, physical, &column);
	*logical = *physical;
	*name = site.source->name;
	for (struct line_remap *map = preprocessor->line_remaps; map; map = map->next) {
		if (!spend_expansion_work(preprocessor, blame, error))
			return false;
		if (map->source == site.source && map->physical_start <= *physical) {
			size_t delta = *physical - map->physical_start;

			if (delta > SIZE_MAX - map->logical_start) {
				*error = stop_preprocessing(preprocessor, blame, "logical line number overflow");
				return false;
			}
			*logical = map->logical_start + delta;
			*name = map->name;
			break;
		}
	}
	return true;
}

/* Generate ordinary pp literals without changing diagnostic provenance. The
 * semantic site belongs to the identifier, not its spelling or outer call. */
static bool expand_predefined_location(struct preprocessor *preprocessor,
	struct rescan_token *input, struct token *error)
{
	struct source_location site = input->semantic_location;
	struct source *spelling;
	const char *logical_name;
	size_t length, physical_line, line;

	if (!logical_position(preprocessor, site, input->token, &physical_line, &line,
		&logical_name, error))
		return false;
	if (pp_spelling_is(input->token, "__LINE__")) {
		char buffer[3 * sizeof(size_t) + 2];
		int written;

		written = snprintf(buffer, sizeof(buffer), "%zu", line);
		if (written < 0 || (size_t)written >= sizeof(buffer)) {
			*error = stop_preprocessing(preprocessor, input->token,
				"cannot represent predefined line number");
			return false;
		}
		length = (size_t)written;
		spelling = allocate_spelling(preprocessor, length + 1, input->token, error);
		if (!spelling)
			return false;
		memcpy(spelling->data, buffer, length + 1);
		input->token.kind = pp_number;
	} else {
		const unsigned char *name = (const unsigned char *)logical_name;
		size_t size = 3; /* quotes and NUL */

		for (const unsigned char *p = name; *p; p++) {
			size_t n = (*p < 32 || *p >= 127 || *p == '?') ? 4 :
				(*p == '"' || *p == '\\') ? 2 : 1;
			if (!add_stringizing_bytes(preprocessor, &size, n, input->token, error))
				return false;
		}
		spelling = allocate_spelling(preprocessor, size, input->token, error);
		if (!spelling)
			return false;
		length = 0;
		spelling->data[length++] = '"';
		for (const unsigned char *p = name; *p; p++) {
			unsigned char c = *p;
			if (c < 32 || c >= 127 || c == '?') {
				spelling->data[length++] = '\\';
				spelling->data[length++] = (unsigned char)('0' + (c >> 6));
				spelling->data[length++] = (unsigned char)('0' + ((c >> 3) & 7));
				spelling->data[length++] = (unsigned char)('0' + (c & 7));
			} else {
				if (c == '"' || c == '\\')
					spelling->data[length++] = '\\';
				spelling->data[length++] = c;
			}
		}
		spelling->data[length++] = '"';
		spelling->data[length] = 0;
		input->token.kind = pp_string;
	}
	input->token.location = (struct source_location) { spelling, 0 };
	input->token.length = length;
	return spend_expansion_work(preprocessor, input->token, error);
}

/* Clock values are captured once per translation, with stable macro provenance. */
static bool expand_predefined_clock(struct preprocessor *preprocessor,
	struct rescan_token *input, struct token *error)
{
	const char *value = pp_spelling_is(input->token, "__DATE__") ?
		preprocessor->translation_date : preprocessor->translation_time;
	size_t length;
	struct source *spelling;
	if (preprocessor->invalid_source_date_epoch) {
		*error = stop_preprocessing(preprocessor, input->token, "invalid SOURCE_DATE_EPOCH");
		return false;
	}
	length = strlen(value);
	spelling = allocate_spelling(preprocessor, length + 1, input->token, error);
	if (!spelling)
		return false;
	memcpy(spelling->data, value, length + 1);
	input->token.kind = pp_string;
	input->token.location = (struct source_location) { spelling, 0 };
	input->token.length = length;
	return spend_expansion_work(preprocessor, input->token, error);
}

static bool expand_predefined_embed_status(struct preprocessor *preprocessor,
	struct rescan_token *input, struct token *error)
{
	unsigned char digit = pp_spelling_is(input->token, "__STDC_EMBED_FOUND__") ? '1' :
		pp_spelling_is(input->token, "__STDC_EMBED_EMPTY__") ? '2' : '0';
	struct source *spelling = allocate_spelling(preprocessor, 2, input->token, error);
	if (!spelling)
		return false;
	spelling->data[0] = digit;
	spelling->data[1] = 0;
	input->token.kind = pp_number;
	input->token.location = (struct source_location) { spelling, 0 };
	input->token.length = 1;
	return spend_expansion_work(preprocessor, input->token, error);
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
			*result = (struct rescan_token) { .token = replacement->token, .hide = frame->hide,
				.semantic_location = frame->semantic_location };
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
						.semantic_location = frame->semantic_location,
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
		result->semantic_location = result->token.location;
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
	struct source_location invocation, struct source_location semantic_location,
	struct macro_hide_set hide, bool leading_space,
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
	const struct argument_token *right, struct pp_token operator,
	struct source_location semantic_location, struct token *error)
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
		left->input.semantic_location = semantic_location;
		return true;
	}
	if (right->placemarker) {
		left->input.semantic_location = semantic_location;
		return true;
	}
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
		.semantic_location = semantic_location,
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
			if (!paste_pair(preprocessor, list->tail, next, item->input.token, item->input.semantic_location, error))
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
	struct source_location invocation, struct source_location semantic_location,
	struct macro_hide_set hide, bool leading_space,
	struct substitution_list *list, struct pp_token blame, struct token *error)
{
	bool first_token = true;
	bool paste_before = false;

	for (struct macro_token *item = first; item != end;) {
		struct macro_token *after = item->next;
		struct rescan_token input = { .token = item->token, .semantic_location = semantic_location };

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
			struct expansion_frame frame = { .arguments = arguments, .invocation = invocation,
				.semantic_location = semantic_location, .hide = hide };

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
				item->va_opt_end, arguments, invocation, semantic_location, hide, input.token.leading_space,
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
	struct source_location invocation, struct source_location semantic_location,
	struct macro_hide_set hide, bool leading_space,
	struct substitution_list *list, struct pp_token blame, struct token *error)
{
	bool success;

	if (preprocessor->paste_depth == preprocess_paste_limit) {
		*error = stop_preprocessing(preprocessor, blame, "macro paste substitution depth limit exceeded");
		return false;
	}
	preprocessor->paste_depth++;
	success = substitute_paste_range(preprocessor, first, end, arguments, invocation,
		semantic_location, hide, leading_space, list, blame, error) && resolve_pastes(preprocessor, list, error);
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
			frame->arguments, frame->invocation, frame->semantic_location, frame->hide, false, &list, operator, error))
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
		.semantic_location = frame->semantic_location,
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
		if (is_predefined_location(input.token)) {
			if (!expand_predefined_location(preprocessor, &input, error))
				return false;
			*result = input;
			return true;
		}
		if (is_predefined_clock(input.token)) {
			if (!expand_predefined_clock(preprocessor, &input, error))
				return false;
			*result = input;
			return true;
		}
		if (is_predefined_embed_status(input.token)) {
			if (!expand_predefined_embed_status(preprocessor, &input, error))
				return false;
			*result = input;
			return true;
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
				input.token.expansion_location, input.semantic_location, hide, input.token.leading_space,
				&list, input.token, error))
				return false;
			remove_placemarkers(&list);
			if (!push_frame(preprocessor, cursor, (struct expansion_frame) {
				.argument = list.head, .hide = hide,
				.invocation = input.token.expansion_location,
				.semantic_location = input.semantic_location,
				.first = true, .leading_space = input.token.leading_space,
			}, input.token, error))
				return false;
			continue;
		}
		if (!push_frame(preprocessor, cursor, (struct expansion_frame) {
			.replacement = macro->replacement,
			.arguments = arguments,
			.invocation = input.token.expansion_location,
			.semantic_location = input.semantic_location,
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
	struct rescan_token expanded;
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
	parser->expanded = next;
	if (next.token.kind == pp_invalid)
		parser->failed = true;
}

/* condition-character = ordinary-character
 * Shared spelling decoding; conditional values use intmax_t arithmetic.
 */
static struct condition_value parse_condition_character(struct condition_parser *parser,
	struct pp_token token)
{
	const unsigned char *text = token.location.source->data + token.location.offset;
	int64_t value;
	const char *error = parse_character_spelling(text, token.length, &value);

	if (error) {
		condition_error(parser, token, error);
		return signed_condition(0);
	}
	return signed_condition(value);
}

/* condition-integer = integer-constant
 * Shared spelling decoding precedes this context's intmax/uintmax selection.
 */
static struct condition_value parse_condition_integer(struct condition_parser *parser, struct pp_token token)
{
	const unsigned char *text = token.location.source->data + token.location.offset;
	struct integer_spelling spelling;
	const char *error = parse_integer_spelling(text, token.length, &spelling);

	if (error) {
		condition_error(parser, token, error);
		return signed_condition(0);
	}
	if (spelling.bit_precise_suffix) {
		condition_error(parser, token, "bit-precise integer literals are not supported yet");
		return signed_condition(0);
	}
	if (!spelling.unsigned_suffix && spelling.base == 10 && spelling.value > INT64_MAX) {
		condition_error(parser, token, "conditional integer exceeds signed 64-bit range");
		return signed_condition(0);
	}
	return (struct condition_value) {
		.bits = spelling.value,
		.unsigned_type = spelling.unsigned_suffix || (spelling.base != 10 && spelling.value > INT64_MAX),
	};
}

static struct condition_value parse_condition_expression(struct condition_parser *parser,
	unsigned minimum_power, bool evaluate);

/* Optional bounded C23 limit parameter. The current token is either the
 * parameter name or the caller's closing delimiter; the latter is left alone. */
static bool parse_embed_limit(struct condition_parser *parser, uint64_t *limit)
{
	struct condition_value value;
	if (!(parser->token.kind == pp_identifier &&
		(pp_spelling_is(parser->token, "limit") || pp_spelling_is(parser->token, "__limit__"))))
		return true;
	advance_condition(parser);
	if (!is_punctuator(parser->token, "(")) {
		condition_error(parser, parser->token, "expected '(' after embed limit");
		return false;
	}
	advance_condition(parser);
	value = parse_condition_expression(parser, 0, true);
	if (parser->failed)
		return false;
	if (!is_punctuator(parser->token, ")")) {
		condition_error(parser, parser->token, "expected ')' after embed limit expression");
		return false;
	}
	if (!value.unsigned_type && condition_signed_value(value) < 0) {
		condition_error(parser, parser->token, "embed limit must be nonnegative");
		return false;
	}
	*limit = value.bits;
	advance_condition(parser);
	return !parser->failed;
}

/* Read balanced standard token parameters; retain hide sets for later rescan.
 * Unknown query parameters are parsed but mark the resource unavailable. */
static bool parse_embed_parameters(struct condition_parser *parser,
	struct embed_parameters *params, bool query, bool *supported)
{
	bool seen_limit = false, seen_prefix = false, seen_suffix = false, seen_empty = false;
	while (!parser->failed && parser->token.kind != pp_eof &&
		!(query && is_punctuator(parser->token, ")"))) {
		char expected[preprocess_parentheses_limit];
		size_t depth = 0;
		bool *seen = NULL, known = true;
		struct argument_token **tail = NULL;
		if (parser->token.kind != pp_identifier) {
			condition_error(parser, parser->token, "expected embed parameter name");
			return false;
		}
		if (pp_spelling_is(parser->token, "limit") || pp_spelling_is(parser->token, "__limit__")) {
			if (seen_limit) {
				condition_error(parser, parser->token, "duplicate embed limit parameter");
				return false;
			}
			seen_limit = true;
			if (!parse_embed_limit(parser, &params->limit)) return false;
			continue;
		}
		if (pp_spelling_is(parser->token, "prefix") || pp_spelling_is(parser->token, "__prefix__")) {
			seen = &seen_prefix; tail = &params->prefix;
		} else if (pp_spelling_is(parser->token, "suffix") || pp_spelling_is(parser->token, "__suffix__")) {
			seen = &seen_suffix; tail = &params->suffix;
		} else if (pp_spelling_is(parser->token, "if_empty") || pp_spelling_is(parser->token, "__if_empty__")) {
			seen = &seen_empty; tail = &params->if_empty;
		} else {
			known = false;
			if (!query) {
				condition_error(parser, parser->token, "unsupported embed parameter");
				return false;
			}
			*supported = false;
		}
		if (seen && *seen) {
			condition_error(parser, parser->token, "duplicate embed parameter");
			return false;
		}
		if (seen) *seen = true;
		advance_condition(parser);
		if (!known && is_punctuator(parser->token, "::")) {
			advance_condition(parser);
			if (parser->token.kind != pp_identifier) {
				condition_error(parser, parser->token, "expected scoped embed parameter name");
				return false;
			}
			advance_condition(parser);
		}
		if (!is_punctuator(parser->token, "(")) {
			if (!known) continue;
			condition_error(parser, parser->token, "expected '(' after embed parameter");
			return false;
		}
		expected[depth++] = ')';
		advance_condition(parser);
		while (!parser->failed && depth) {
			struct pp_token token = parser->token;
			char closing = 0;
			if (token.kind == pp_eof) {
				condition_error(parser, token, "unterminated embed parameter");
				return false;
			}
			if (is_punctuator(token, "(")) closing = ')';
			else if (is_punctuator(token, "[") || is_punctuator(token, "<:")) closing = ']';
			else if (is_punctuator(token, "{") || is_punctuator(token, "<%")) closing = '}';
			if (closing) {
				if (depth == sizeof(expected)) {
					condition_error(parser, token, "embed parameter nesting limit exceeded");
					return false;
				}
				expected[depth++] = closing;
			} else if (is_punctuator(token, ")") || is_punctuator(token, "]") ||
				is_punctuator(token, "}") || is_punctuator(token, ":>") || is_punctuator(token, "%>")) {
				char actual = is_punctuator(token, ":>") ? ']' : is_punctuator(token, "%>") ? '}' :
					(char)token.location.source->data[token.location.offset];
				if (actual != expected[depth - 1]) {
					condition_error(parser, token, "mismatched embed parameter delimiter");
					return false;
				}
				depth--;
			}
			if (depth && known && !query) {
				struct argument_token *copy = copy_argument_token(parser->preprocessor,
					parser->expanded, token, parser->error);
				if (!copy) { parser->failed = true; return false; }
				*tail = copy;
				tail = &copy->next;
			}
			advance_condition(parser);
		}
	}
	return !parser->failed;
}

static bool append_include_piece(struct preprocessor *preprocessor,
	struct include_name *name, struct pp_token piece, size_t *length, struct token *error);

/* Preserve a directly written angle header from identifier macro expansion;
 * computed names are expanded using the ordinary conditional cursor. */
static void advance_include_condition(struct condition_parser *parser, bool raw)
{
	struct rescan_token next;
	if (parser->failed)
		return;
	if (!(raw ? read_rescan_token(parser->preprocessor, parser->cursor, &next, parser->error) :
		read_expanded_token(parser->preprocessor, parser->cursor, &next, parser->error))) {
		parser->failed = true;
		return;
	}
	parser->token = next.token;
	parser->expanded = next;
	if (next.token.kind == pp_invalid)
		parser->failed = true;
}

static struct condition_value parse_has_include(struct condition_parser *parser,
	struct pp_token operator, bool evaluate, bool embed)
{
	struct preprocessor *preprocessor = parser->preprocessor;
	struct include_name name = { .invocation = operator };
	struct rescan_token first;
	struct source source = { 0 };
	size_t length = 0;
	bool direct, found = false, supported = true;
	int status = 0;
	struct embed_parameters params = { .limit = UINT64_MAX };

	advance_condition(parser);
	if (!is_punctuator(parser->token, "(")) {
		condition_error(parser, parser->token, "expected '(' after resource availability operator");
		return signed_condition(0);
	}
	if (!read_rescan_token(preprocessor, parser->cursor, &first, parser->error)) {
		parser->failed = true;
		return signed_condition(0);
	}
	direct = is_punctuator(first.token, "<");
	parser->cursor->pending = first;
	parser->cursor->has_pending = true;
	advance_include_condition(parser, direct);
	if (is_punctuator(parser->token, "<")) {
		name.angled = true;
		advance_include_condition(parser, direct);
		while (!parser->failed && !is_punctuator(parser->token, ">")) {
			if (parser->token.kind == pp_eof || is_punctuator(parser->token, ")")) {
				condition_error(parser, parser->token, "expected '>' in resource availability operator");
				return signed_condition(0);
			}
			if (!append_include_piece(preprocessor, &name, parser->token, &length, parser->error)) {
				parser->failed = true;
				return signed_condition(0);
			}
			advance_include_condition(parser, direct);
		}
		if (!length || parser->token.leading_space) {
			condition_error(parser, parser->token, "angle include name must be nonempty with no internal whitespace");
			return signed_condition(0);
		}
	} else {
		struct pp_token token = parser->token;
		const unsigned char *text = token.location.source->data + token.location.offset;
		if (token.kind != pp_string || token.length < 3 || text[0] != '"') {
			condition_error(parser, token, "resource availability operator requires a nonempty name");
			return signed_condition(0);
		}
		length = token.length - 2;
		if (length >= sizeof(name.path)) {
			condition_error(parser, token, "include path limit exceeded");
			return signed_condition(0);
		}
		for (size_t i = 1; i <= length; i++) {
			if (text[i] == '\\') {
				condition_error(parser, token, "backslashes in quoted include names are not supported yet");
				return signed_condition(0);
			}
		}
		memcpy(name.path, text + 1, length);
		name.path[length] = 0;
	}
	advance_condition(parser);
	if (embed && !parse_embed_parameters(parser, &params, true, &supported))
		return signed_condition(0);
	if (!is_punctuator(parser->token, ")")) {
		condition_error(parser, parser->token, "expected ')' after resource name or supported parameters");
		return signed_condition(0);
	}
	if (evaluate && supported) {
		if (!preprocessor->include_loader) {
			condition_error(parser, operator, "includes require a configured source loader");
			return signed_condition(0);
		}
		if (preprocessor->include_count == preprocess_include_count_limit) {
			*parser->error = stop_preprocessing(preprocessor, operator, "include attempt limit (128) exceeded");
			parser->failed = true;
			return signed_condition(0);
		}
		preprocessor->include_count++;
		if (!load_include_source(preprocessor, operator, &name, &source, parser->error, &found, !embed)) {
			parser->failed = true;
			return signed_condition(0);
		}
		if (found) {
			if (source.length > preprocess_include_bytes_limit - preprocessor->include_bytes) {
				source_destroy(&source);
				*parser->error = stop_preprocessing(preprocessor, operator, "include input byte limit exceeded");
				parser->failed = true;
				return signed_condition(0);
			}
			preprocessor->include_bytes += source.length;
			if (embed) {
				uint64_t effective = source.length < params.limit ? source.length : params.limit;
				status = effective > 4096 ? 0 : effective ? 1 : 2;
			} else
				status = 1;
			source_destroy(&source);
		}
	}
	advance_condition(parser);
	return signed_condition(status);
}

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
	if (token.kind == pp_identifier &&
		(pp_spelling_is(token, "__has_include") || pp_spelling_is(token, "__has_embed")))
		return parse_has_include(parser, token, evaluate, pp_spelling_is(token, "__has_embed"));
	if (token.kind == pp_identifier && pp_spelling_is(token, "__has_c_attribute")) {
		advance_condition(parser);
		if (!is_punctuator(parser->token, "(")) {
			condition_error(parser, parser->token, "expected '(' after __has_c_attribute");
			return signed_condition(0);
		}
		advance_condition(parser);
		if (parser->token.kind != pp_identifier) {
			condition_error(parser, parser->token, "expected attribute name in __has_c_attribute");
			return signed_condition(0);
		}
		advance_condition(parser);
		if (is_punctuator(parser->token, "::")) {
			advance_condition(parser);
			if (parser->token.kind != pp_identifier) {
				condition_error(parser, parser->token, "expected scoped attribute name in __has_c_attribute");
				return signed_condition(0);
			}
			advance_condition(parser);
		}
		if (!is_punctuator(parser->token, ")")) {
			condition_error(parser, parser->token, "expected ')' after __has_c_attribute");
			return signed_condition(0);
		}
		advance_condition(parser);
		/* All currently recognized attributes have restricted placements;
		 * do not advertise them as fully supported. */
		return signed_condition(0);
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
	struct pp_token marker, struct pp_token *token, size_t *count, struct token *error,
	bool in_direct_header)
{
	*token = pp_lexer_next(&preprocessor->input);
	if (token->kind == pp_invalid || token->has_non_directive_space) {
		*error = reject_directive(preprocessor, marker, *token,
			token->kind == pp_invalid ? NULL :
			"only space and tab are allowed in a preprocessing directive");
		return false;
	}
	if (!in_direct_header && is_variadic_identifier(*token)) {
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
	struct source *spelling;
	bool parenthesized;

	if (!read_condition_input(preprocessor, marker, &name, count, error, false))
		return false;
	parenthesized = is_punctuator(name, "(");
	if (parenthesized && !read_condition_input(preprocessor, marker, &name, count, error, false))
		return false;
	if (name.kind != pp_identifier) {
		*error = reject_directive(preprocessor, marker, name,
			"expected an identifier after defined");
		return false;
	}
	if (parenthesized) {
		struct pp_token close;

		if (!read_condition_input(preprocessor, marker, &close, count, error, false))
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
	spelling->data[0] = macro_is_defined(preprocessor, name) ? '1' : '0';
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
	unsigned direct_header_state = 0;
	struct condition_value result;

	for (;;) {
		struct argument_token *copy;

		if (!read_condition_input(preprocessor, marker, &token, &count, error, direct_header_state == 3))
			return false;
		if (is_directive_end(token))
			break;
		/* The spelling inside a direct angle header is a header name, not
		 * conditional-expression operators such as the word defined. */
		if (direct_header_state != 3 && token.kind == pp_identifier &&
			pp_spelling_is(token, "defined") &&
			!replace_defined_operand(preprocessor, marker, &token, &count, error))
			return false;
		if (direct_header_state == 3) {
			if (is_punctuator(token, ">"))
				direct_header_state = 0;
		} else if (direct_header_state == 2)
			direct_header_state = is_punctuator(token, "<") ? 3 : 0;
		else if (direct_header_state == 1)
			direct_header_state = is_punctuator(token, "(") ? 2 : 0;
		else if (token.kind == pp_identifier &&
			(pp_spelling_is(token, "__has_include") || pp_spelling_is(token, "__has_embed")))
			direct_header_state = 1;
		/* Directive tokens retain their individual source invocation sites. */
		copy = copy_argument_token(preprocessor, (struct rescan_token) { .token = token, .semantic_location = token.location }, token, error);
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

/* header-name = string-literal | '<' path-token+ '>'
 * The angle subset has no internal whitespace and uses only ASCII path bytes.
 */
static bool append_include_piece(struct preprocessor *preprocessor,
	struct include_name *name, struct pp_token piece, size_t *length, struct token *error)
{
	const unsigned char *text = piece.location.source->data + piece.location.offset;

	if (piece.leading_space) {
		diagnostic_error(preprocessor->diagnostics, piece.expansion_location,
			"whitespace inside angle include names is not supported yet");
		*error = invalid_token(name->invocation);
		return false;
	}
	for (size_t i = 0; i < piece.length; i++) {
		unsigned char c = text[i];

		if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
			(c >= '0' && c <= '9') || c == '_' || c == '.' || c == '/' ||
			c == '-' || c == '+')) {
			diagnostic_error(preprocessor->diagnostics, piece.expansion_location,
				"unsupported byte in angle include name");
			*error = invalid_token(name->invocation);
			return false;
		}
	}
	if (piece.length >= sizeof(name->path) - *length) {
		*error = stop_preprocessing(preprocessor, piece, "include path limit exceeded");
		return false;
	}
	memcpy(name->path + *length, text, piece.length);
	*length += piece.length;
	name->path[*length] = 0;
	return true;
}

/* The same bounded cursor reads raw direct-angle or rescanned computed input. */
static bool read_include_token(struct preprocessor *preprocessor,
	struct expansion_cursor *cursor, bool direct, struct rescan_token *token, struct token *error)
{
	if (!direct)
		return read_expanded_token(preprocessor, cursor, token, error);
	if (!cursor->input) {
		*token = cursor_end(cursor);
		return true;
	}
	*token = cursor->input->input;
	cursor->input = cursor->input->next;
	return true;
}

static bool read_include_name(struct preprocessor *preprocessor,
	struct expansion_cursor *cursor, bool direct, struct include_name *header, struct token *error,
	struct embed_parameters *params)
{
	struct rescan_token input;
	struct pp_token first;
	size_t length = 0;

	if (!read_include_token(preprocessor, cursor, direct, &input, error))
		return false;
	first = input.token;
	*header = (struct include_name) { .invocation = first };
	if (first.kind == pp_punctuator && pp_spelling_is(first, "<")) {
		header->angled = true;
		for (;;) {
			if (!read_include_token(preprocessor, cursor, direct, &input, error))
				return false;
			if (input.token.kind == pp_eof) {
				diagnostic_error(preprocessor->diagnostics, first.expansion_location,
					"expected '>' after angle include name");
				*error = invalid_token(first);
				return false;
			}
			if (input.token.kind == pp_punctuator && pp_spelling_is(input.token, ">")) {
				if (!input.token.leading_space && length)
					break;
				diagnostic_error(preprocessor->diagnostics, input.token.expansion_location,
					"angle include name must be nonempty with no internal whitespace");
				*error = invalid_token(first);
				return false;
			}
			if (!append_include_piece(preprocessor, header, input.token, &length, error))
				return false;
		}
	} else {
		const unsigned char *text = first.location.source->data + first.location.offset;

		if (first.kind != pp_string || first.length < 3 || text[0] != '"') {
			diagnostic_error(preprocessor->diagnostics, first.expansion_location,
				"include operand must expand to one nonempty unprefixed quoted name or angle name");
			*error = invalid_token(first);
			return false;
		}
		length = first.length - 2;
		if (length >= sizeof(header->path)) {
			*error = stop_preprocessing(preprocessor, first, "include path limit exceeded");
			return false;
		}
		for (size_t i = 1; i <= length; i++)
			if (text[i] == '\\') {
				diagnostic_error(preprocessor->diagnostics, first.expansion_location,
					"backslashes in quoted include names are not supported yet");
				*error = invalid_token(first);
				return false;
			}
		memcpy(header->path, text + 1, length);
		header->path[length] = 0;
	}
	if (params) {
		struct condition_parser parser = { .preprocessor = preprocessor, .cursor = cursor, .error = error };
		bool supported = true;
		params->limit = UINT64_MAX;
		advance_condition(&parser);
		if (!parse_embed_parameters(&parser, params, false, &supported) || parser.failed) {
			*error = invalid_token(first);
			return false;
		}
		input.token = parser.token;
	} else if (!read_include_token(preprocessor, cursor, direct, &input, error))
		return false;
	if (input.token.kind != pp_eof) {
		diagnostic_error(preprocessor->diagnostics, input.token.expansion_location,
			"expected end of include or supported embed operand");
		*error = invalid_token(first);
		return false;
	}
	return true;
}

/* include-operand = pp-tokens newline
 * Collect one raw line. Direct angles bypass expansion; other operands rescan
 * in isolation. Validation must never drain the following source line.
 */
static bool expand_include_operand(struct preprocessor *preprocessor,
	struct pp_token marker, struct include_name *header, struct token *error, struct embed_parameters *params)
{
	struct argument_token *head = NULL;
	struct argument_token **tail = &head;
	struct expansion_cursor *cursor;
	struct pp_token token;
	size_t count = 0;
	bool direct = false;
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
		if (count == 1)
			direct = token.kind == pp_punctuator && pp_spelling_is(token, "<");
		if (!direct && is_variadic_identifier(token)) {
			*error = reject_directive(preprocessor, marker, token,
				"variadic identifiers require a variadic macro replacement list");
			return false;
		}
		/* Directive tokens retain their individual source invocation sites. */
		copy = copy_argument_token(preprocessor, (struct rescan_token) { .token = token, .semantic_location = token.location }, token, error);
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
	success = read_include_name(preprocessor, cursor, direct, header, error, params);
	free(cursor);
	if (!success && !preprocessor->stopped)
		*error = invalid_token(marker);
	return success;
}

/* Bounded C23 embed: the resource stays raw binary, never
 * source-prepared; each byte becomes a decimal pp-number separated by commas. */
static bool read_embed_directive(struct preprocessor *preprocessor,
	struct pp_token marker, struct token *error)
{
	struct include_name name;
	struct source resource = { 0 };
	struct source *spelling;
	struct argument_token *head = NULL, **tail = &head;
	bool found;
	size_t offset = 0, effective;
	struct embed_parameters params = { 0 };

	if (!expand_include_operand(preprocessor, marker, &name, error, &params))
		return false;
	if (!preprocessor->include_loader) {
		diagnostic_error(preprocessor->diagnostics, marker.expansion_location,
			"embed requires a configured source loader");
		*error = invalid_token(marker);
		return false;
	}
	if (preprocessor->include_count == preprocess_include_count_limit) {
		*error = stop_preprocessing(preprocessor, marker, "include attempt limit (128) exceeded");
		return false;
	}
	preprocessor->include_count++;
	if (!load_include_source(preprocessor, marker, &name, &resource, error, &found, false))
		return false;
	if (!found) {
		diagnostic_error(preprocessor->diagnostics, marker.expansion_location, "cannot load embed resource");
		*error = invalid_token(marker);
		return false;
	}
	effective = resource.length < params.limit ? resource.length : (size_t)params.limit;
	if (effective > 4096 || resource.length > preprocess_include_bytes_limit - preprocessor->include_bytes) {
		source_destroy(&resource);
		*error = stop_preprocessing(preprocessor, marker, "embed resource byte limit exceeded (4096)");
		return false;
	}
	preprocessor->include_bytes += resource.length;
	if (!effective) {
		source_destroy(&resource);
		if (!params.if_empty) {
			preprocessor->cursor.deferred_space = true;
			return true;
		}
		return push_frame(preprocessor, &preprocessor->cursor, (struct expansion_frame) {
			.argument = params.if_empty, .invocation = marker.expansion_location,
			.semantic_location = marker.location, .first = true, .leading_space = true,
		}, marker, error);
	}
	if (params.prefix) {
		head = params.prefix;
		while (*tail) tail = &(*tail)->next;
	}
	spelling = allocate_spelling(preprocessor, effective * 4 + 1, marker, error);
	if (!spelling) {
		source_destroy(&resource);
		return false;
	}
	for (size_t i = 0; i < effective; i++) {
		for (unsigned part = 0; part < (i ? 2u : 1u); part++) {
			bool comma = i && !part;
			size_t length;
			struct argument_token *copy;
			struct pp_token token = marker;
			if (comma) {
				spelling->data[offset] = ',';
				length = 1;
			} else {
				int written = snprintf((char *)spelling->data + offset,
					effective * 4 + 1 - offset, "%u", (unsigned)resource.data[i]);
				assert(written > 0 && written <= 3);
				length = (size_t)written;
			}
			token.kind = comma ? pp_punctuator : pp_number;
			token.location = (struct source_location) { spelling, offset };
			token.length = length;
			token.at_line_start = false;
			token.leading_space = false;
			copy = copy_argument_token(preprocessor, (struct rescan_token) {
				.token = token, .semantic_location = marker.location,
			}, marker, error);
			if (!copy) {
				source_destroy(&resource);
				return false;
			}
			*tail = copy;
			tail = &copy->next;
			offset += length;
		}
	}
	spelling->data[offset] = 0;
	spelling->length = spelling->physical_length = offset;
	*tail = params.suffix;
	source_destroy(&resource);
	return push_frame(preprocessor, &preprocessor->cursor, (struct expansion_frame) {
		.argument = head, .invocation = marker.expansion_location,
		.semantic_location = marker.location, .first = true, .leading_space = true,
	}, marker, error);
}

/* The directive line is fully collected before rescan, so a malformed or
 * function-like operand cannot consume tokens from the following source line. */
static bool read_line_directive(struct preprocessor *preprocessor,
	struct pp_token marker, struct token *error)
{
	struct argument_token *head = NULL;
	struct argument_token **tail = &head;
	struct expansion_cursor *cursor;
	struct rescan_token result;
	struct pp_token end, number, filename = { 0 };
	struct line_remap *map;
	struct source *name_storage = NULL;
	const char *name, *failure = NULL;
	size_t count = 0, physical, logical, value = 0, decoded = 0;
	bool success = false;

	for (;;) {
		struct argument_token *copy;
		struct pp_token token = pp_lexer_next(&preprocessor->input);

		if (token.kind == pp_invalid || token.has_non_directive_space) {
			*error = reject_directive(preprocessor, marker, token,
				token.kind == pp_invalid ? NULL :
				"only space and tab are allowed in a preprocessing directive");
			return false;
		}
		if (is_directive_end(token)) {
			end = token;
			break;
		}
		if (++count > preprocess_line_directive_token_limit) {
			*error = reject_directive(preprocessor, marker, token,
				"line directive token limit (1024) exceeded");
			return false;
		}
		if (is_variadic_identifier(token)) {
			*error = reject_directive(preprocessor, marker, token,
				"variadic identifiers require a variadic macro replacement list");
			return false;
		}
		copy = copy_argument_token(preprocessor,
			(struct rescan_token) { .token = token, .semantic_location = token.location }, token, error);
		if (!copy)
			return false;
		*tail = copy;
		tail = &copy->next;
	}
	cursor = calloc(1, sizeof(*cursor));
	if (!cursor) {
		*error = stop_preprocessing(preprocessor, marker, "cannot allocate line directive cursor");
		return false;
	}
	cursor->input = head;
	cursor->end = end.location;
	if (!read_expanded_token(preprocessor, cursor, &result, error))
		goto done;
	number = result.token;
	if (number.kind != pp_number || !number.length) {
		failure = "line directive requires a decimal line number";
		goto invalid;
	}
	for (size_t i = 0; i < number.length; i++) {
		unsigned char c = number.location.source->data[number.location.offset + i];

		if (c < '0' || c > '9' || value > (2147483647u - (unsigned)(c - '0')) / 10u) {
			failure = "line directive number must be decimal and between 1 and 2147483647";
			goto invalid;
		}
		value = value * 10 + (size_t)(c - '0');
	}
	if (!value) {
		failure = "line directive number must be decimal and between 1 and 2147483647";
		goto invalid;
	}
	if (!read_expanded_token(preprocessor, cursor, &result, error))
		goto done;
	if (result.token.kind != pp_eof) {
		const char *message;
		const unsigned char *text;

		filename = result.token;
		text = filename.location.source->data + filename.location.offset;
		if (filename.kind != pp_string || !filename.length || text[0] != '"') {
			failure = "line directive filename must be an ordinary string literal";
			goto invalid;
		}
		message = parse_string_spelling(text, filename.length, NULL, 0, &decoded);
		if (message) {
			failure = "unsupported line directive filename string";
			goto invalid;
		}
		if (!read_expanded_token(preprocessor, cursor, &result, error))
			goto done;
		if (result.token.kind != pp_eof) {
			failure = "unexpected token after line directive filename";
			goto invalid;
		}
		name_storage = allocate_spelling(preprocessor, decoded + 1, filename, error);
		if (!name_storage)
			goto done;
		message = parse_string_spelling(text, filename.length, name_storage->data, decoded, &decoded);
		if (message || memchr(name_storage->data, 0, decoded)) {
			failure = "line directive filename cannot contain NUL";
			goto invalid;
		}
		name_storage->data[decoded] = 0;
	}
	if (!logical_position(preprocessor, end.location, marker, &physical, &logical, &name, error))
		goto done;
	if (physical == SIZE_MAX) {
		*error = stop_preprocessing(preprocessor, marker, "line directive physical location overflow");
		goto done;
	}
	map = allocate_auxiliary(preprocessor, 1, sizeof(*map), marker, error);
	if (!map)
		goto done;
	*map = (struct line_remap) {
		.source = marker.location.source, .physical_start = physical + 1,
		.logical_start = value, .name = name_storage ? (const char *)name_storage->data : name,
		.next = preprocessor->line_remaps,
	};
	preprocessor->line_remaps = map;
	success = true;
	goto done;
invalid:
	diagnostic_error(preprocessor->diagnostics, marker.location, failure);
	*error = invalid_token(marker);
done:
	free(cursor);
	return success;
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
	static const char *const months[] = {
		"Jan", "Feb", "Mar", "Apr", "May", "Jun",
		"Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
	};
	const char *epoch = getenv("SOURCE_DATE_EPOCH");
	time_t now;
	struct tm *clock;

	*preprocessor = (struct preprocessor) { .diagnostics = diagnostics };
	now = time(NULL);
	if (epoch) {
		uint64_t seconds = 0;
		const char *p = epoch;
		if (!*p)
			preprocessor->invalid_source_date_epoch = true;
		for (; *p; p++) {
			unsigned digit;
			if (*p < '0' || *p > '9') {
				preprocessor->invalid_source_date_epoch = true;
				break;
			}
			digit = (unsigned)(*p - '0');
			if (seconds > (UINT64_C(253402300799) - digit) / 10) {
				preprocessor->invalid_source_date_epoch = true;
				break;
			}
			seconds = seconds * 10 + digit;
		}
		if (!preprocessor->invalid_source_date_epoch) {
			now = (time_t)seconds;
			if (now < (time_t)0 || (uint64_t)now != seconds)
				preprocessor->invalid_source_date_epoch = true;
		}
	}
	clock = now == (time_t)-1 || preprocessor->invalid_source_date_epoch ? NULL : gmtime(&now);
	memcpy(preprocessor->translation_date, "\"??? ?? ????\"", 14);
	memcpy(preprocessor->translation_time, "\"??:??:??\"", 11);
	if (clock && clock->tm_mon >= 0 && clock->tm_mon < 12 &&
		clock->tm_mday >= 1 && clock->tm_mday <= 31 &&
		clock->tm_year >= -1900 && clock->tm_year <= 8099 &&
		clock->tm_hour >= 0 && clock->tm_hour <= 23 &&
		clock->tm_min >= 0 && clock->tm_min <= 59 &&
		clock->tm_sec >= 0 && clock->tm_sec <= 60) {
		snprintf(preprocessor->translation_date, sizeof(preprocessor->translation_date),
			"\"%s %2d %04d\"", months[clock->tm_mon], clock->tm_mday, clock->tm_year + 1900);
		snprintf(preprocessor->translation_time, sizeof(preprocessor->translation_time),
			"\"%02d:%02d:%02d\"", clock->tm_hour, clock->tm_min, clock->tm_sec);
	}
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

bool preprocess_set_include_directories(struct preprocessor *preprocessor,
	const char *const *directories, size_t count)
{
	assert(!preprocessor->input.offset && !preprocessor->has_lookahead);
	if (count > preprocess_include_directory_limit)
		return false;
	preprocessor->include_directories = directories;
	preprocessor->include_directory_count = count;
	return true;
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
		struct token result = preprocessor->lookahead;
		if (preprocessor->has_second_lookahead) {
			preprocessor->lookahead = preprocessor->second_lookahead;
			preprocessor->has_second_lookahead = false;
		} else {
			preprocessor->has_lookahead = false;
		}
		return result;
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

struct token preprocess_peek_second(struct preprocessor *preprocessor)
{
	(void)preprocess_peek(preprocessor);
	if (!preprocessor->has_second_lookahead) {
		/* Raw expansion requires no pending language-token peek. */
		preprocessor->has_lookahead = false;
		preprocessor->second_lookahead = read_preprocessed_token(preprocessor);
		preprocessor->has_lookahead = true;
		preprocessor->has_second_lookahead = true;
	}
	return preprocessor->second_lookahead;
}
