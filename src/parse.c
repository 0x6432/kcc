#include "parse.h"
#include "type.h"

#include <assert.h>

struct parser {
	struct preprocessor *preprocessor;
	struct arena *arena;
	struct diagnostics *diagnostics;
	unsigned depth;
	unsigned statement_nesting;
	unsigned declarator_nesting;
	size_t block_items;
	size_t string_bytes;
	size_t string_count;
	size_t string_fragment_count;
};

static struct ast_expression *parse_expression(struct parser *parser,
	unsigned minimum_binding_power);

static bool expect_token(struct parser *parser, enum token_kind kind,
	const char *message, struct token *result)
{
	struct token token = preprocess_next(parser->preprocessor);

	if (token.kind != kind) {
		if (token.kind != token_invalid)
			diagnostic_error(parser->diagnostics, token.location, message);
		return false;
	}
	if (result)
		*result = token;
	return true;
}

static void allocation_error(struct parser *parser, struct source_location location)
{
	diagnostic_error(parser->diagnostics, location, "out of memory building AST");
}

static bool begins_integer_type(enum token_kind kind)
{
	return kind == token_int || kind == token_signed || kind == token_unsigned ||
		kind == token_long || kind == token_char || kind == token_short || kind == token_bool || kind == token_c23_bool;
}

static bool begins_declaration_specifier(enum token_kind kind)
{
	return kind == token_void || kind == token_const || begins_integer_type(kind);
}

/* type-qualifier-list ::= "const" { "const" }
 * Repeats are idempotent; one concrete wrapper preserves this type level.
 */
static struct ast_type_syntax *qualify_type_syntax(struct parser *parser,
	struct ast_type_syntax *base, unsigned qualifiers, struct source_location location)
{
	struct ast_qualified_type_syntax *qualified;

	if (!qualifiers)
		return base;
	qualified = ast_new_qualified_type_syntax(parser->arena, location, base, qualifiers);
	if (!qualified)
		allocation_error(parser, location);
	return qualified ? &qualified->syntax : NULL;
}

/* declaration-specifiers ::= permutation of type-qualifier-list and builtin-type
 * builtin-type ::= integer-type | "void"
 * integer-type ::= permutation of ['signed' | 'unsigned'] ['long' ['long']] ['int']
 *                | permutation of ['signed' | 'unsigned'] 'char'
 *                | permutation of ['signed' | 'unsigned'] 'short' ['int'] | '_Bool' | 'bool'
 * At least one actual type specifier is required; void cannot combine with
 * integer specifiers. Qualifiers do not hide duplicate/conflicting specifiers.
 */
static struct ast_type_syntax *parse_declaration_specifiers(struct parser *parser,
	struct token *beginning)
{
	bool seen_int = false;
	bool seen_void = false;
	bool seen_char = false;
	bool seen_short = false;
	bool seen_bool = false;
	bool seen_sign = false;
	bool unsigned_type = false;
	unsigned long_count = 0;
	unsigned qualifiers = 0;
	enum integer_specifier specifier;
	struct ast_type_syntax *base;
	struct ast_integer_type_syntax *integer;
	struct token qualifier = { 0 };

	*beginning = preprocess_peek(parser->preprocessor);
	if (!begins_declaration_specifier(beginning->kind)) {
		if (beginning->kind != token_invalid)
			diagnostic_error(parser->diagnostics, beginning->location, "expected integer type specifier");
		return NULL;
	}
	while (begins_declaration_specifier(preprocess_peek(parser->preprocessor).kind)) {
		struct token token = preprocess_next(parser->preprocessor);

		if (token.kind == token_const) {
			if (!qualifiers)
				qualifier = token;
			qualifiers |= type_qualifier_const;
			continue;
		}
		if (token.kind == token_void) {
			if (seen_void) {
				diagnostic_error(parser->diagnostics, token.location, "duplicate void type specifier");
				return NULL;
			}
			seen_void = true;
			continue;
		}
		if (token.kind == token_bool || token.kind == token_c23_bool) {
			if (seen_bool) {
				diagnostic_error(parser->diagnostics, token.location, "duplicate _Bool type specifier");
				return NULL;
			}
			seen_bool = true;
		} else if (token.kind == token_char) {
			if (seen_char) {
				diagnostic_error(parser->diagnostics, token.location, "duplicate char type specifier");
				return NULL;
			}
			seen_char = true;
		} else if (token.kind == token_short) {
			if (seen_short) {
				diagnostic_error(parser->diagnostics, token.location, "duplicate short type specifier");
				return NULL;
			}
			seen_short = true;
		} else if (token.kind == token_long) {
			if (long_count == 2) {
				diagnostic_error(parser->diagnostics, token.location, "too many long type specifiers");
				return NULL;
			}
			long_count++;
		} else if (token.kind == token_int) {
			if (seen_int) {
				diagnostic_error(parser->diagnostics, token.location, "duplicate or conflicting integer type specifier");
				return NULL;
			}
			seen_int = true;
		} else {
			if (seen_sign) {
				diagnostic_error(parser->diagnostics, token.location, "duplicate or conflicting integer type specifier");
				return NULL;
			}
			seen_sign = true;
			unsigned_type = token.kind == token_unsigned;
		}
	}
	if (seen_void) {
		struct ast_void_type_syntax *node;

		if (seen_int || seen_char || seen_short || seen_bool || seen_sign || long_count) {
			diagnostic_error(parser->diagnostics, beginning->location, "void cannot combine with other type specifiers");
			return NULL;
		}
		node = ast_new_void_type_syntax(parser->arena, beginning->location);
		if (!node) {
			allocation_error(parser, beginning->location);
			return NULL;
		}
		base = &node->syntax;
		return qualify_type_syntax(parser, base, qualifiers, qualifier.location);
	}
	if (!seen_int && !seen_char && !seen_short && !seen_bool && !seen_sign && !long_count) {
		diagnostic_error(parser->diagnostics, beginning->location, "expected type specifier with qualifier");
		return NULL;
	}
	if (seen_bool && (seen_sign || seen_char || seen_short || seen_int || long_count)) {
		diagnostic_error(parser->diagnostics, beginning->location, "_Bool cannot combine with other type specifiers");
		return NULL;
	}
	if (seen_char && (seen_int || long_count || seen_short)) {
		diagnostic_error(parser->diagnostics, beginning->location, "char cannot combine with int, short or long");
		return NULL;
	}
	if (seen_short && long_count) {
		diagnostic_error(parser->diagnostics, beginning->location, "short cannot combine with long");
		return NULL;
	}
	if (seen_bool)
		specifier = integer_specifier_bool;
	else if (seen_char) {
		if (!seen_sign)
			specifier = integer_specifier_char;
		else
			specifier = unsigned_type ? integer_specifier_unsigned_char : integer_specifier_signed_char;
	} else if (seen_short) {
		specifier = unsigned_type ? integer_specifier_unsigned_short : integer_specifier_short;
	} else if (long_count == 2)
		specifier = unsigned_type ? integer_specifier_unsigned_long_long : integer_specifier_long_long;
	else if (long_count == 1)
		specifier = unsigned_type ? integer_specifier_unsigned_long : integer_specifier_long;
	else
		specifier = unsigned_type ? integer_specifier_unsigned : integer_specifier_int;
	integer = ast_new_integer_type_syntax(parser->arena, beginning->location, specifier);
	if (!integer) {
		allocation_error(parser, beginning->location);
		return NULL;
	}
	base = &integer->syntax;
	return qualify_type_syntax(parser, base, qualifiers, qualifier.location);
}

enum declarator_context {
	declarator_local,
	declarator_external,
	declarator_parameter,
	declarator_cast,
};

/* The base slot is construction state: every published syntax has a base. */
struct parsed_declarator {
	struct ast_type_syntax *syntax;
	struct ast_type_syntax **base_slot;
	struct token name;
	bool has_name;
	size_t pointers;
	size_t dimensions;
	size_t functions;
};

static bool parse_parameters(struct parser *parser,
	struct ast_function_type_syntax *function);

/* function-suffix ::= "(" ("void" | [ parameter-list ]) ")" */
static bool parse_function_suffix(struct parser *parser,
	struct parsed_declarator *declarator, struct token opening)
{
	struct ast_function_type_syntax *function;

	if (declarator->functions == ast_max_function_layers) {
		diagnostic_error(parser->diagnostics, opening.location, "function declarator exceeds layer limit (64)");
		return false;
	}
	function = ast_new_function_type_syntax(parser->arena, opening.location, NULL);
	if (!function) {
		allocation_error(parser, opening.location);
		return false;
	}
	if (!parse_parameters(parser, function) ||
		!expect_token(parser, token_right_paren, "expected ')' after parameter list", NULL))
		return false;
	*declarator->base_slot = &function->syntax;
	declarator->base_slot = &function->return_syntax;
	declarator->functions++;
	return true;
}

/* object-array-suffix ::= "[" [ assignment-expression ] "]"
 * Sema rejects incomplete elements/objects before layout, while a pointer to
 * an unknown-bound array is complete. Append dimensions in source order.
 */
static bool parse_object_array_suffixes(struct parser *parser,
	struct parsed_declarator *declarator)
{
	while (preprocess_peek(parser->preprocessor).kind == token_left_bracket) {
		struct token opening = preprocess_next(parser->preprocessor);
		struct ast_expression *bound = NULL;
		struct ast_array_type_syntax *array;
		bool has_bound = preprocess_peek(parser->preprocessor).kind != token_right_bracket;

		if (declarator->dimensions == ast_max_array_dimensions) {
			diagnostic_error(parser->diagnostics, opening.location,
				"array declarator exceeds dimension limit (64)");
			return false;
		}
		if (has_bound) {
			bound = parse_expression(parser, 1);
			if (!bound)
				return false;
		}
		if (!expect_token(parser, token_right_bracket, "expected ']' after array bound", NULL))
			return false;
		array = ast_new_array_type_syntax(parser->arena, opening.location, NULL, bound);
		if (!array) {
			allocation_error(parser, opening.location);
			return false;
		}
		*declarator->base_slot = &array->syntax;
		declarator->base_slot = &array->element;
		declarator->dimensions++;
	}
	return true;
}

static bool parse_declarator(struct parser *parser,
	struct parsed_declarator *declarator, enum declarator_context context);

/* declarator ::= { "*" [ type-qualifier-list ] } direct-declarator { array-suffix | function-suffix }
 * direct-declarator ::= identifier | "(" declarator ")"
 * Abstract forms omit the identifier. At an abstract opening parenthesis,
 * a specifier/void/closing parenthesis starts a function suffix, not grouping.
 */
static bool parse_declarator_contents(struct parser *parser,
	struct parsed_declarator *declarator, enum declarator_context context)
{
	struct ast_type_syntax *prefix = NULL;
	struct ast_type_syntax **prefix_base = NULL;
	struct token token;

	while (preprocess_peek(parser->preprocessor).kind == token_star) {
		struct token star = preprocess_next(parser->preprocessor);
		struct ast_pointer_type_syntax *pointer;
		unsigned qualifiers = 0;
		struct source_location qualifier_location = star.location;

		if (declarator->pointers == ast_max_pointer_depth) {
			diagnostic_error(parser->diagnostics, star.location, "pointer type exceeds depth limit (64)");
			return false;
		}
		pointer = ast_new_pointer_type_syntax(parser->arena, star.location, prefix);
		if (!pointer) {
			allocation_error(parser, star.location);
			return false;
		}
		if (!prefix)
			prefix_base = &pointer->referent;
		while (preprocess_peek(parser->preprocessor).kind == token_const) {
			struct token qualifier = preprocess_next(parser->preprocessor);

			if (!qualifiers)
				qualifier_location = qualifier.location;
			qualifiers |= type_qualifier_const;
		}
		prefix = qualify_type_syntax(parser, &pointer->syntax, qualifiers, qualifier_location);
		if (!prefix)
			return false;
		declarator->pointers++;
	}
	token = preprocess_peek(parser->preprocessor);
	if (token.kind == token_identifier && context != declarator_cast) {
		declarator->name = preprocess_next(parser->preprocessor);
		declarator->has_name = true;
	} else if (token.kind == token_left_paren) {
		size_t derived_before = declarator->pointers + declarator->dimensions + declarator->functions;
		bool name_before = declarator->has_name;
		struct token next;

		preprocess_next(parser->preprocessor);
		next = preprocess_peek(parser->preprocessor);
		if (begins_declaration_specifier(next.kind) || next.kind == token_right_paren) {
			if (!parse_function_suffix(parser, declarator, token))
				return false;
		} else {
			if (!parse_declarator(parser, declarator, context))
				return false;
			if (derived_before == declarator->pointers + declarator->dimensions + declarator->functions &&
				name_before == declarator->has_name) {
				diagnostic_error(parser->diagnostics, token.location, "expected object declarator inside parentheses");
				return false;
			}
			if (!expect_token(parser, token_right_paren, "expected ')' after object declarator", NULL))
				return false;
		}
	}
	for (;;) {
		token = preprocess_peek(parser->preprocessor);
		if (token.kind == token_left_bracket) {
			if (!parse_object_array_suffixes(parser, declarator))
				return false;
		} else if (token.kind == token_left_paren) {
			preprocess_next(parser->preprocessor);
			if (!parse_function_suffix(parser, declarator, token))
				return false;
		} else {
			break;
		}
	}
	if (prefix) {
		*declarator->base_slot = prefix;
		declarator->base_slot = prefix_base;
	}
	return true;
}

/* Guard grouping AND nested parameter types; the outer declarator is level 0. */
static bool parse_declarator(struct parser *parser,
	struct parsed_declarator *declarator, enum declarator_context context)
{
	bool success;

	if (parser->declarator_nesting > ast_max_declarator_nesting) {
		diagnostic_error(parser->diagnostics, preprocess_peek(parser->preprocessor).location,
			"declarator exceeds nesting limit (64)");
		return false;
	}
	parser->declarator_nesting++;
	success = parse_declarator_contents(parser, declarator, context);
	parser->declarator_nesting--;
	return success;
}

/* derived-type ::= declarator
 * Each declarator gets its own derived chain around the shared specifier base.
 */
static struct ast_type_syntax *parse_derived_type(struct parser *parser,
	struct ast_type_syntax *base, struct token *name, bool *has_name,
	enum declarator_context context)
{
	struct parsed_declarator declarator = { 0 };

	if (!base)
		return NULL;
	declarator.base_slot = &declarator.syntax;
	if (!parse_declarator(parser, &declarator, context))
		return NULL;
	if ((context == declarator_local || context == declarator_external) && !declarator.has_name) {
		diagnostic_error(parser->diagnostics, preprocess_peek(parser->preprocessor).location,
			context == declarator_local ? "expected local name" : "expected function name");
		return NULL;
	}
	*declarator.base_slot = base;
	if (name)
		*name = declarator.name;
	if (has_name)
		*has_name = declarator.has_name;
	return declarator.syntax;
}

/* type-name ::= declaration-specifiers [ declarator ]
 * A local declarator is required; parameter/cast abstract forms may be absent.
 */
static struct ast_type_syntax *parse_type_name(struct parser *parser,
	struct token *beginning, struct token *name, bool *has_name,
	enum declarator_context context)
{
	struct ast_type_syntax *base = parse_declaration_specifiers(parser, beginning);

	return parse_derived_type(parser, base, name, has_name, context);
}

/* integer-expression ::= integer-token (decimal/octal/hex/binary, separators allowed) */
static struct ast_expression *parse_integer_expression(struct parser *parser)
{
	struct token token;
	struct ast_integer_expression *node;

	if (!expect_token(parser, token_integer, "expected integer literal", &token))
		return NULL;
	node = ast_new_integer(parser->arena, token);
	if (!node) {
		allocation_error(parser, token.location);
		return NULL;
	}
	return &node->expression;
}

/* nullptr-constant ::= "nullptr" */
static struct ast_expression *parse_nullptr_expression(struct parser *parser)
{
	struct token token;
	struct ast_nullptr_expression *node;

	if (!expect_token(parser, token_nullptr, "expected nullptr", &token))
		return NULL;
	node = ast_new_nullptr(parser->arena, token.location);
	if (!node) {
		allocation_error(parser, token.location);
		return NULL;
	}
	return &node->expression;
}

/* boolean-constant ::= "true" | "false" */
static struct ast_expression *parse_boolean_expression(struct parser *parser)
{
	struct token token = preprocess_next(parser->preprocessor);
	struct ast_boolean_expression *node = ast_new_boolean(parser->arena, token);

	if (!node) {
		allocation_error(parser, token.location);
		return NULL;
	}
	return &node->expression;
}

/* character-expression ::= ordinary-character-token */
static struct ast_expression *parse_character_expression(struct parser *parser)
{
	struct token token;
	struct ast_character_expression *node;

	if (!expect_token(parser, token_character, "expected character constant", &token))
		return NULL;
	node = ast_new_character(parser->arena, token);
	if (!node) {
		allocation_error(parser, token.location);
		return NULL;
	}
	return &node->expression;
}

/* string-expression ::= ordinary-string-token { ordinary-string-token }
 * Fragments decode independently: greedy escapes never cross closing quotes.
 * Only this bounded sequence is buffered, not the translation unit's tokens.
 */
static struct ast_expression *parse_string_expression(struct parser *parser)
{
	struct string_fragment {
		struct token token;
		struct string_fragment *next;
	};
	struct string_fragment *fragments = NULL;
	struct string_fragment **tail = &fragments;
	struct ast_string_expression *node;
	unsigned char *bytes;
	size_t length = 0;
	size_t offset = 0;
	size_t count = 0;

	if (parser->string_count == ast_max_string_literals) {
		diagnostic_error(parser->diagnostics, preprocess_peek(parser->preprocessor).location,
			"string literal storage/count limit exceeded");
		return NULL;
	}
	do {
		struct token token = preprocess_peek(parser->preprocessor);
		struct string_fragment *fragment;

		if (count == ast_max_string_fragments ||
			parser->string_fragment_count == ast_max_total_string_fragments) {
			diagnostic_error(parser->diagnostics, token.location, "string fragment limit exceeded");
			return NULL;
		}
		if (token.string_length > ast_max_string_length - length) {
			diagnostic_error(parser->diagnostics, token.location, "string literal storage/count limit exceeded");
			return NULL;
		}
		length += token.string_length;
		if (length >= ast_max_string_storage - parser->string_bytes) {
			diagnostic_error(parser->diagnostics, token.location, "string literal storage/count limit exceeded");
			return NULL;
		}
		preprocess_next(parser->preprocessor);
		fragment = arena_alloc(parser->arena, sizeof(*fragment));
		if (!fragment) {
			allocation_error(parser, token.location);
			return NULL;
		}
		*fragment = (struct string_fragment) { .token = token };
		*tail = fragment;
		tail = &fragment->next;
		count++;
		parser->string_fragment_count++;
	} while (preprocess_peek(parser->preprocessor).kind == token_string);

	bytes = arena_alloc(parser->arena, length + 1);
	if (!bytes) {
		allocation_error(parser, fragments->token.location);
		return NULL;
	}
	for (struct string_fragment *fragment = fragments; fragment; fragment = fragment->next) {
		struct token token = fragment->token;
		const unsigned char *spelling = token.spelling_location.source->data + token.spelling_location.offset;
		size_t decoded_length;
		const char *error = parse_string_spelling(spelling, token.length,
			bytes + offset, length - offset, &decoded_length);

		if (error) {
			diagnostic_error(parser->diagnostics, token.location, error);
			return NULL;
		}
		assert(decoded_length == token.string_length);
		offset += decoded_length;
	}
	assert(offset == length);
	bytes[length] = 0;
	node = ast_new_string(parser->arena, fragments->token.location, bytes, length);
	if (!node) {
		allocation_error(parser, fragments->token.location);
		return NULL;
	}
	parser->string_bytes += length + 1;
	parser->string_count++;
	return &node->expression;
}

struct infix_operator {
	enum token_kind token;
	unsigned left_binding_power;
	unsigned right_binding_power;
};

/* A higher binding power binds more tightly. Right = left + 1 gives left
 * associativity: a-b-c is (a-b)-c, because the RHS does not consume another
 * operator of equal precedence. Assignment uses equal left/right powers,
 * making a=b=c associate as a=(b=c). Comma binds below assignment at 0/1.
 * Conditional ?: uses power 2 and its own three-operand helper; logical-or is 3.
 * Assignment-expression contexts use floor 1; full expressions use floor 0.
 * Prefix operators bind at 30.
 */
static const struct infix_operator infix_operators[] = {
	{ token_comma, 0, 1 },
	{ token_equal, 1, 1 },
	{ token_plus_equal, 1, 1 },
	{ token_minus_equal, 1, 1 },
	{ token_star_equal, 1, 1 },
	{ token_slash_equal, 1, 1 },
	{ token_percent_equal, 1, 1 },
	{ token_ampersand_equal, 1, 1 },
	{ token_caret_equal, 1, 1 },
	{ token_pipe_equal, 1, 1 },
	{ token_shift_left_equal, 1, 1 },
	{ token_shift_right_equal, 1, 1 },
	{ token_question, 2, 2 },
	{ token_or_or, 3, 4 },
	{ token_and_and, 4, 5 },
	{ token_pipe, 5, 6 },
	{ token_caret, 6, 7 },
	{ token_ampersand, 7, 8 },
	{ token_equal_equal, 8, 9 },
	{ token_not_equal, 8, 9 },
	{ token_less, 9, 10 },
	{ token_less_equal, 9, 10 },
	{ token_greater, 9, 10 },
	{ token_greater_equal, 9, 10 },
	{ token_shift_left, 10, 11 },
	{ token_shift_right, 10, 11 },
	{ token_plus, 11, 12 },
	{ token_minus, 11, 12 },
	{ token_star, 20, 21 },
	{ token_slash, 20, 21 },
	{ token_percent, 20, 21 },
};

static const struct infix_operator *find_infix_operator(enum token_kind kind)
{
	for (size_t i = 0; i < sizeof(infix_operators) / sizeof(infix_operators[0]); i++)
		if (infix_operators[i].token == kind)
			return &infix_operators[i];
	return NULL;
}

/* primary-atom ::= integer-expression | boolean-constant | nullptr-constant | character-expression | string-expression | identifier
 * Parenthesized primaries share cast disambiguation after one opening parenthesis.
 */
static struct ast_expression *parse_primary_expression(struct parser *parser)
{
	struct token token = preprocess_peek(parser->preprocessor);

	if (token.kind == token_nullptr)
		return parse_nullptr_expression(parser);
	if (token.kind == token_true || token.kind == token_false)
		return parse_boolean_expression(parser);
	if (token.kind == token_string)
		return parse_string_expression(parser);
	if (token.kind == token_character)
		return parse_character_expression(parser);
	if (token.kind == token_identifier) {
		struct ast_name_expression *node;

		preprocess_next(parser->preprocessor);
		node = ast_new_name(parser->arena, token);
		if (!node) {
			allocation_error(parser, token.location);
			return NULL;
		}
		return &node->expression;
	}
	if (token.kind == token_unsupported_keyword) {
		diagnostic_error(parser->diagnostics, token.location,
			"keyword is not supported in this expression");
		return NULL;
	}
	return parse_integer_expression(parser);
}

/* argument-expression-list ::= assignment-expression
 *                              { "," assignment-expression }
 * Separator commas stay here; grouped comma expressions are parsed inside parentheses.
 */
static bool parse_call_arguments(struct parser *parser,
	struct ast_argument **arguments, size_t *count)
{
	struct ast_argument **tail = arguments;

	if (preprocess_peek(parser->preprocessor).kind == token_right_paren)
		return true;
	for (;;) {
		struct ast_expression *value;
		struct ast_argument *argument;

		if (*count == ast_max_arguments) {
			diagnostic_error(parser->diagnostics,
				preprocess_peek(parser->preprocessor).location,
				"call exceeds argument limit (128)");
			return false;
		}
		value = parse_expression(parser, 1);
		if (!value)
			return false;
		argument = ast_new_argument(parser->arena, value);
		if (!argument) {
			allocation_error(parser, value->location);
			return false;
		}
		*tail = argument;
		tail = &argument->next;
		(*count)++;
		if (preprocess_peek(parser->preprocessor).kind != token_comma)
			return true;
		preprocess_next(parser->preprocessor);
	}
}

/* call-suffix ::= "(" [ argument-expression-list ] ")" */
static struct ast_expression *parse_call_suffix(struct parser *parser,
	struct ast_expression *callee)
{
	struct ast_call_expression *node;
	struct ast_argument *arguments = NULL;
	size_t count = 0;

	preprocess_next(parser->preprocessor);
	if (!parse_call_arguments(parser, &arguments, &count))
		return NULL;
	if (!expect_token(parser, token_right_paren, "expected ')' after call", NULL))
		return NULL;
	node = ast_new_call(parser->arena, callee, arguments, count);
	if (!node) {
		allocation_error(parser, callee->location);
		return NULL;
	}
	return &node->expression;
}

/* subscript-suffix ::= "[" expression "]"
 * Full expressions include comma; parse_expression shares the recursive
 * nesting budget for each index expression.
 */
static struct ast_expression *parse_subscript_suffix(struct parser *parser,
	struct ast_expression *left)
{
	struct token opening = preprocess_next(parser->preprocessor);
	struct ast_expression *right = parse_expression(parser, 0);
	struct ast_subscript_expression *node;

	if (!right)
		return NULL;
	if (!expect_token(parser, token_right_bracket, "expected ']' after subscript", NULL))
		return NULL;
	node = ast_new_subscript(parser->arena, opening.location, left, right);
	if (!node) {
		allocation_error(parser, opening.location);
		return NULL;
	}
	return &node->expression;
}

/* postfix-update-suffix ::= "++" | "--" */
static struct ast_expression *parse_postfix_update_suffix(struct parser *parser,
	struct ast_expression *operand)
{
	struct token token = preprocess_next(parser->preprocessor);
	enum update_operator operation = token.kind == token_increment ? update_increment : update_decrement;
	struct ast_postfix_update_expression *node;

	node = ast_new_postfix_update(parser->arena, token.location, operation, operand);
	if (!node)
		allocation_error(parser, token.location);
	return node ? &node->expression : NULL;
}

/* postfix-suffix ::= { call-suffix | subscript-suffix | postfix-update-suffix }
 * Shared by atoms and parenthesized primary expressions. A suffix binds more
 * tightly than prefix/infix operators; chains associate left to right.
 */
static struct ast_expression *parse_postfix_suffix(struct parser *parser,
	struct ast_expression *expression)
{
	while (expression) {
		struct token token = preprocess_peek(parser->preprocessor);

		if (token.kind == token_left_paren)
			expression = parse_call_suffix(parser, expression);
		else if (token.kind == token_left_bracket)
			expression = parse_subscript_suffix(parser, expression);
		else if (token.kind == token_increment || token.kind == token_decrement)
			expression = parse_postfix_update_suffix(parser, expression);
		else
			break;
		if (!expression)
			return NULL;
		if (expression->depth > ast_max_expression_depth) {
			diagnostic_error(parser->diagnostics, expression->location,
				"expression tree exceeds depth limit (128)");
			return NULL;
		}
	}
	return expression;
}

/* postfix-expression ::= primary-atom postfix-suffix */
static struct ast_expression *parse_postfix_expression(struct parser *parser)
{
	return parse_postfix_suffix(parser, parse_primary_expression(parser));
}

/* parenthesized-or-cast ::= '(' expression ')' postfix-suffix
 *                        | '(' type-name ')' cast-expression
 * One opening token is consumed before choosing from the current token.
 * Cast operands bind at prefix power, including postfix calls but no infix.
 */
static struct ast_expression *parse_parenthesized_or_cast(struct parser *parser)
{
	struct token opening = preprocess_next(parser->preprocessor);
	struct ast_expression *operand;
	struct ast_cast_expression *node;
	struct ast_type_syntax *type_syntax;
	struct token beginning;

	if (!begins_declaration_specifier(preprocess_peek(parser->preprocessor).kind)) {
		operand = parse_expression(parser, 0);
		if (!operand || !expect_token(parser, token_right_paren, "expected ')'", NULL))
			return NULL;
		return parse_postfix_suffix(parser, operand);
	}
	type_syntax = parse_type_name(parser, &beginning, NULL, NULL, declarator_cast);
	if (!type_syntax ||
		!expect_token(parser, token_right_paren, "expected ')' after cast type", NULL))
		return NULL;
	operand = parse_expression(parser, 30);
	if (!operand)
		return NULL;
	if (operand->depth >= ast_max_expression_depth) {
		diagnostic_error(parser->diagnostics, opening.location,
			"expression tree exceeds depth limit (128)");
		return NULL;
	}
	node = ast_new_cast(parser->arena, opening.location, type_syntax, operand);
	if (!node) {
		allocation_error(parser, opening.location);
		return NULL;
	}
	return &node->expression;
}

/* sizeof-expression ::= "sizeof" unary-expression | "sizeof" "(" type-name ")"
 * An already-consumed '(' is classified with one on-demand token, without rewind.
 */
static struct ast_expression *parse_sizeof_expression(struct parser *parser)
{
	struct token keyword = preprocess_next(parser->preprocessor);
	struct ast_expression *operand;
	struct ast_sizeof_expression *node;

	if (preprocess_peek(parser->preprocessor).kind == token_left_paren) {
		preprocess_next(parser->preprocessor);
		if (begins_declaration_specifier(preprocess_peek(parser->preprocessor).kind)) {
			struct token beginning;
			struct ast_type_syntax *type_syntax = parse_type_name(parser, &beginning, NULL, NULL, declarator_cast);
			struct ast_sizeof_type_expression *type_node;

			if (!type_syntax || !expect_token(parser, token_right_paren, "expected ')' after sizeof type", NULL))
				return NULL;
			type_node = ast_new_sizeof_type(parser->arena, keyword.location, type_syntax);
			if (!type_node)
				allocation_error(parser, keyword.location);
			return type_node ? &type_node->expression : NULL;
		}
		operand = parse_expression(parser, 0);
		if (!operand || !expect_token(parser, token_right_paren, "expected ')' after sizeof operand", NULL))
			return NULL;
		operand = parse_postfix_suffix(parser, operand);
	} else {
		operand = parse_expression(parser, 30);
	}
	if (!operand)
		return NULL;
	if (operand->depth >= ast_max_expression_depth) {
		diagnostic_error(parser->diagnostics, keyword.location, "expression tree exceeds depth limit (128)");
		return NULL;
	}
	node = ast_new_sizeof(parser->arena, keyword.location, operand);
	if (!node)
		allocation_error(parser, keyword.location);
	return node ? &node->expression : NULL;
}

/* alignof-expression ::= ("alignof" | "_Alignof") "(" type-name ")" */
static struct ast_expression *parse_alignof_expression(struct parser *parser)
{
	struct token keyword = preprocess_next(parser->preprocessor);
	struct token beginning;
	struct ast_type_syntax *type_syntax;
	struct ast_alignof_expression *node;

	if (!expect_token(parser, token_left_paren, "expected '(' after alignof", NULL))
		return NULL;
	type_syntax = parse_type_name(parser, &beginning, NULL, NULL, declarator_cast);
	if (!type_syntax || !expect_token(parser, token_right_paren, "expected ')' after alignof type", NULL))
		return NULL;
	node = ast_new_alignof(parser->arena, keyword.location, type_syntax);
	if (!node)
		allocation_error(parser, keyword.location);
	return node ? &node->expression : NULL;
}

/* pointer-unary-expression ::= ("&" | "*") cast-expression */
static struct ast_expression *parse_pointer_unary_expression(struct parser *parser)
{
	struct token token = preprocess_next(parser->preprocessor);
	struct ast_expression *operand = parse_expression(parser, 30);
	struct ast_expression *expression;

	if (!operand)
		return NULL;
	if (operand->depth >= ast_max_expression_depth) {
		diagnostic_error(parser->diagnostics, token.location,
			"expression tree exceeds depth limit (128)");
		return NULL;
	}
	if (token.kind == token_ampersand) {
		struct ast_address_expression *node = ast_new_address(parser->arena, token.location, operand);

		expression = node ? &node->expression : NULL;
	} else {
		struct ast_indirection_expression *node;

		assert(token.kind == token_star);
		node = ast_new_indirection(parser->arena, token.location, operand);
		expression = node ? &node->expression : NULL;
	}
	if (!expression)
		allocation_error(parser, token.location);
	return expression;
}

/* prefix-update-expression ::= ("++" | "--") unary-expression */
static struct ast_expression *parse_prefix_update_expression(struct parser *parser)
{
	struct token token = preprocess_next(parser->preprocessor);
	struct ast_expression *operand = parse_expression(parser, 30);
	struct ast_prefix_update_expression *node;
	enum update_operator operation;

	if (!operand)
		return NULL;
	if (operand->depth >= ast_max_expression_depth) {
		diagnostic_error(parser->diagnostics, token.location,
			"expression tree exceeds depth limit (128)");
		return NULL;
	}
	operation = token.kind == token_increment ? update_increment : update_decrement;
	node = ast_new_prefix_update(parser->arena, token.location, operation, operand);
	if (!node)
		allocation_error(parser, token.location);
	return node ? &node->expression : NULL;
}

/* prefix-expression ::= postfix-expression | parenthesized-or-cast | prefix-update-expression
 *                     | pointer-unary-expression | sizeof-expression | alignof-expression
 *                     | ("+" | "-" | "!" | "~") cast-expression
 * cast-expression ::= prefix-expression (casts are selected after an opening paren)
 */
static struct ast_expression *parse_prefix_expression(struct parser *parser)
{
	struct token token = preprocess_peek(parser->preprocessor);
	struct ast_expression *operand;
	struct ast_unary_expression *node;
	enum unary_operator operation;

	if (token.kind == token_increment || token.kind == token_decrement)
		return parse_prefix_update_expression(parser);
	if (token.kind == token_sizeof)
		return parse_sizeof_expression(parser);
	if (token.kind == token_alignof || token.kind == token_legacy_alignof)
		return parse_alignof_expression(parser);
	if (token.kind == token_left_paren)
		return parse_parenthesized_or_cast(parser);
	if (token.kind == token_ampersand || token.kind == token_star)
		return parse_pointer_unary_expression(parser);
	if (token.kind != token_plus && token.kind != token_minus &&
		token.kind != token_bang && token.kind != token_tilde)
		return parse_postfix_expression(parser);
	preprocess_next(parser->preprocessor);
	switch (token.kind) {
	case token_plus: operation = unary_plus; break;
	case token_minus: operation = unary_minus; break;
	case token_bang: operation = unary_not; break;
	case token_tilde: operation = unary_complement; break;
	default:
		assert(0 && "unknown prefix operator");
		return NULL;
	}
	operand = parse_expression(parser, 30);
	if (!operand)
		return NULL;
	if (operand->depth >= ast_max_expression_depth) {
		diagnostic_error(parser->diagnostics, token.location,
			"expression tree exceeds depth limit (128)");
		return NULL;
	}
	node = ast_new_unary(parser->arena, token.location, operation, operand);
	if (!node) {
		allocation_error(parser, token.location);
		return NULL;
	}
	return &node->expression;
}

static enum binary_operator binary_operator_for_token(enum token_kind kind)
{
	switch (kind) {
	case token_plus_equal:
	case token_plus: return binary_add;
	case token_minus_equal:
	case token_minus: return binary_subtract;
	case token_star_equal:
	case token_star: return binary_multiply;
	case token_slash_equal:
	case token_slash: return binary_divide;
	case token_percent_equal:
	case token_percent: return binary_remainder;
	case token_ampersand_equal:
	case token_ampersand: return binary_bit_and;
	case token_caret_equal:
	case token_caret: return binary_bit_xor;
	case token_pipe_equal:
	case token_pipe: return binary_bit_or;
	case token_shift_left_equal:
	case token_shift_left: return binary_shift_left;
	case token_shift_right_equal:
	case token_shift_right: return binary_shift_right;
	case token_equal_equal: return binary_equal;
	case token_not_equal: return binary_not_equal;
	case token_less: return binary_less;
	case token_less_equal: return binary_less_equal;
	case token_greater: return binary_greater;
	case token_greater_equal: return binary_greater_equal;
	default:
		assert(0 && "unknown arithmetic token");
		return binary_add;
	}
}

static bool is_compound_assignment(enum token_kind kind)
{
	switch (kind) {
	case token_plus_equal:
	case token_minus_equal:
	case token_star_equal:
	case token_slash_equal:
	case token_percent_equal:
	case token_ampersand_equal:
	case token_caret_equal:
	case token_pipe_equal:
	case token_shift_left_equal:
	case token_shift_right_equal:
		return true;
	default:
		return false;
	}
}

static struct ast_expression *new_infix_expression(struct parser *parser,
	struct token token, struct ast_expression *left, struct ast_expression *right)
{
	if (token.kind == token_comma) {
		struct ast_comma_expression *node = ast_new_comma(parser->arena,
			token.location, left, right);

		if (node)
			return &node->expression;
	} else if (token.kind == token_equal) {
		struct ast_assignment_expression *node = ast_new_assignment(
			parser->arena, token.location, left, right);

		if (node)
			return &node->expression;
	} else if (is_compound_assignment(token.kind)) {
		enum binary_operator operation = binary_operator_for_token(token.kind);
		struct ast_compound_assignment_expression *node = ast_new_compound_assignment(
			parser->arena, token.location, operation, left, right);

		if (node)
			return &node->expression;
	} else if (token.kind == token_and_and || token.kind == token_or_or) {
		enum logical_operator operation = token.kind == token_and_and ?
			logical_and : logical_or;
		struct ast_logical_expression *node = ast_new_logical(parser->arena,
			token.location, operation, left, right);

		if (node)
			return &node->expression;
	} else {
		struct ast_binary_expression *node = ast_new_binary(parser->arena,
			token.location, binary_operator_for_token(token.kind), left, right);

		if (node)
			return &node->expression;
	}
	allocation_error(parser, token.location);
	return NULL;
}

/* conditional-expression ::= logical-OR-expression
 *                          | logical-OR-expression "?" expression ":" conditional-expression
 * The condition and question mark have already been consumed by Pratt parsing.
 * Only the middle operand admits an unparenthesized comma or assignment.
 */
static struct ast_expression *parse_conditional_expression(struct parser *parser,
	struct token question, struct ast_expression *condition)
{
	struct ast_expression *then_value = parse_expression(parser, 0);
	struct ast_expression *else_value;
	struct ast_conditional_expression *node;

	if (!then_value || !expect_token(parser, token_colon, "expected ':' in conditional expression", NULL))
		return NULL;
	else_value = parse_expression(parser, 2);
	if (!else_value)
		return NULL;
	if (condition->depth >= ast_max_expression_depth ||
		then_value->depth >= ast_max_expression_depth || else_value->depth >= ast_max_expression_depth) {
		diagnostic_error(parser->diagnostics, question.location,
			"expression tree exceeds depth limit (128)");
		return NULL;
	}
	node = ast_new_conditional(parser->arena, question.location, condition, then_value, else_value);
	if (!node)
		allocation_error(parser, question.location);
	return node ? &node->expression : NULL;
}

/* infix-suffix ::= { infix-operator right-operand }
 * Continue the Pratt tiers at the supplied floor after one parsed left operand.
 * The caller owns the recursion-depth frame, also for consumed identifiers.
 */
static struct ast_expression *parse_infix_suffix(struct parser *parser,
	struct ast_expression *left, unsigned minimum_binding_power)
{
	for (;;) {
		struct token token = preprocess_peek(parser->preprocessor);
		const struct infix_operator *operator = find_infix_operator(token.kind);
		struct ast_expression *right;
		struct ast_expression *node;

		if (!operator || operator->left_binding_power < minimum_binding_power)
			break;
		preprocess_next(parser->preprocessor);
		if (token.kind == token_question) {
			node = parse_conditional_expression(parser, token, left);
			if (!node)
				return NULL;
			left = node;
			continue;
		}
		right = parse_expression(parser, operator->right_binding_power);
		if (!right)
			return NULL;
		if (left->depth >= ast_max_expression_depth ||
			right->depth >= ast_max_expression_depth) {
			diagnostic_error(parser->diagnostics, token.location,
				"expression tree exceeds depth limit (128)");
			return NULL;
		}
		node = new_infix_expression(parser, token, left, right);
		if (!node)
			return NULL;
		left = node;
	}
	return left;
}

/* expression ::= assignment-expression { "," assignment-expression }
 * assignment-expression ::= conditional-expression
 *                         | unary-expression assignment-operator assignment-expression
 * assignment-operator ::= "=" | "+=" | "-=" | "*=" | "/=" | "%=" | "&=" | "^=" | "|=" | "<<=" | ">>="
 * conditional-expression ::= logical-OR-expression [ "?" expression ":" conditional-expression ]
 * logical-OR-expression ::= logical-AND-expression { "||" logical-AND-expression }
 * logical-AND-expression ::= bitwise-OR-expression { "&&" bitwise-OR-expression }
 * bitwise-OR-expression ::= bitwise-XOR-expression { "|" bitwise-XOR-expression }
 * bitwise-XOR-expression ::= bitwise-AND-expression { "^" bitwise-AND-expression }
 * bitwise-AND-expression ::= equality-expression { "&" equality-expression }
 * equality-expression ::= relational-expression { ("==" | "!=") relational-expression }
 * relational-expression ::= shift-expression { ("<" | "<=" | ">" | ">=") shift-expression }
 * shift-expression ::= additive-expression { ("<<" | ">>") additive-expression }
 * additive-expression ::= multiplicative-expression { ("+" | "-") multiplicative-expression }
 * multiplicative-expression ::= cast-expression { ("*" | "/" | "%") cast-expression }
 * Pratt powers implement these precedence levels. Assignment's unary-expression
 * left constraint is checked as a modifiable lvalue by sema. Other recursive
 * calls consume RHS operators only at or above the requested binding power.
 */
static struct ast_expression *parse_expression(struct parser *parser,
	unsigned minimum_binding_power)
{
	struct ast_expression *left;

	if (parser->depth == ast_max_expression_depth) {
		diagnostic_error(parser->diagnostics,
			preprocess_peek(parser->preprocessor).location,
			"expression nesting exceeds depth limit (128)");
		return NULL;
	}
	parser->depth++;
	left = parse_prefix_expression(parser);

	if (left)
		left = parse_infix_suffix(parser, left, minimum_binding_power);
	parser->depth--;
	return left;
}

/* return-statement ::= "return" [ expression ] ";" */
static struct ast_return_statement *parse_return_statement(struct parser *parser)
{
	struct token keyword;
	struct ast_expression *value = NULL;
	struct ast_return_statement *node;

	if (!expect_token(parser, token_return, "expected 'return'", &keyword))
		return NULL;
	if (preprocess_peek(parser->preprocessor).kind != token_semicolon) {
		value = parse_expression(parser, 0);
		if (!value)
			return NULL;
	}
	if (!expect_token(parser, token_semicolon, "expected ';' after return", NULL))
		return NULL;
	node = ast_new_return(parser->arena, keyword.location, value);
	if (!node)
		allocation_error(parser, keyword.location);
	return node;
}

/* expression-statement-tail ::= ";"; the expression was already parsed. */
static struct ast_statement *parse_expression_statement_tail(struct parser *parser,
	struct ast_expression *value)
{
	struct ast_expression_statement *node;

	if (!value)
		return NULL;
	if (!expect_token(parser, token_semicolon,
		"expected ';' after expression", NULL))
		return NULL;
	node = ast_new_expression_statement(parser->arena, value->location, value);
	if (!node) {
		allocation_error(parser, value->location);
		return NULL;
	}
	return &node->statement;
}

/* expression-statement ::= expression ";" */
static struct ast_statement *parse_expression_statement(struct parser *parser)
{
	return parse_expression_statement_tail(parser, parse_expression(parser, 0));
}

/* identifier-expression-statement ::= identifier postfix-suffix infix-suffix ";"
 * The identifier has been consumed to distinguish a colon with one peek only.
 */
static struct ast_statement *parse_identifier_expression_statement(struct parser *parser,
	struct token name)
{
	struct ast_name_expression *node;
	struct ast_expression *value;

	if (parser->depth == ast_max_expression_depth) {
		diagnostic_error(parser->diagnostics, name.location,
			"expression nesting exceeds depth limit (128)");
		return NULL;
	}
	parser->depth++;
	node = ast_new_name(parser->arena, name);
	if (!node)
		allocation_error(parser, name.location);
	value = node ? parse_postfix_suffix(parser, &node->expression) : NULL;
	if (value)
		value = parse_infix_suffix(parser, value, 0);
	parser->depth--;
	return parse_expression_statement_tail(parser, value);
}

/* empty-statement ::= ";" */
static struct ast_statement *parse_empty_statement(struct parser *parser)
{
	struct token token;
	struct ast_empty_statement *node;

	if (!expect_token(parser, token_semicolon, "expected ';'", &token))
		return NULL;
	node = ast_new_empty_statement(parser->arena, token.location);
	if (!node) {
		allocation_error(parser, token.location);
		return NULL;
	}
	return &node->statement;
}

static struct ast_compound_statement *parse_compound_statement(struct parser *parser);

static struct ast_statement *parse_statement(struct parser *parser);

static bool begin_nested_statement(struct parser *parser)
{
	if (parser->statement_nesting == ast_max_statement_nesting) {
		diagnostic_error(parser->diagnostics,
			preprocess_peek(parser->preprocessor).location,
			"statement nesting exceeds limit (128)");
		return false;
	}
	parser->statement_nesting++;
	return true;
}

/* label-tail ::= ":"; the identifier was consumed exactly once. */
static struct ast_label *parse_label_tail(struct parser *parser, struct token name)
{
	struct ast_label *label;

	if (!expect_token(parser, token_colon, "expected ':' after label", NULL))
		return NULL;
	label = ast_new_label(parser->arena, name);
	if (!label)
		allocation_error(parser, name.location);
	return label;
}

/* labeled-statement ::= identifier ":" statement
 * Unlike standalone block labels, this form requires a following statement.
 */
static struct ast_statement *parse_labeled_statement(struct parser *parser, struct token name)
{
	struct ast_label *label = parse_label_tail(parser, name);
	struct ast_statement *body;
	struct ast_labeled_statement *node;

	if (!label || !begin_nested_statement(parser))
		return NULL;
	body = parse_statement(parser);
	parser->statement_nesting--;
	if (!body)
		return NULL;
	node = ast_new_labeled_statement(parser->arena, label, body);
	if (!node)
		allocation_error(parser, name.location);
	return node ? &node->statement : NULL;
}

/* if-statement ::= "if" "(" expression ")" statement [ "else" statement ]
 * Parsing the then-statement recursively attaches else to the nearest if.
 */
static struct ast_if_statement *parse_if_contents(struct parser *parser)
{
	struct token keyword;
	struct ast_expression *condition;
	struct ast_statement *then_branch;
	struct ast_statement *else_branch = NULL;
	struct ast_if_statement *node;

	if (!expect_token(parser, token_if, "expected 'if'", &keyword))
		return NULL;
	if (!expect_token(parser, token_left_paren, "expected '(' after if", NULL))
		return NULL;
	condition = parse_expression(parser, 0);
	if (!condition)
		return NULL;
	if (!expect_token(parser, token_right_paren, "expected ')' after condition", NULL))
		return NULL;
	then_branch = parse_statement(parser);
	if (!then_branch)
		return NULL;
	if (preprocess_peek(parser->preprocessor).kind == token_else) {
		preprocess_next(parser->preprocessor);
		else_branch = parse_statement(parser);
		if (!else_branch)
			return NULL;
	}
	node = ast_new_if(parser->arena, keyword.location, condition,
		then_branch, else_branch);
	if (!node)
		allocation_error(parser, keyword.location);
	return node;
}

/* if-statement ::= "if" "(" expression ")" statement [ "else" statement ] */
static struct ast_if_statement *parse_if_statement(struct parser *parser)
{
	struct ast_if_statement *node;

	if (!begin_nested_statement(parser))
		return NULL;
	node = parse_if_contents(parser);
	parser->statement_nesting--;
	return node;
}

/* switch-statement ::= "switch" "(" expression ")" statement */
static struct ast_switch_statement *parse_switch_contents(struct parser *parser)
{
	struct token keyword;
	struct ast_expression *control;
	struct ast_statement *body;
	struct ast_switch_statement *node;

	if (!expect_token(parser, token_switch, "expected 'switch'", &keyword))
		return NULL;
	if (!expect_token(parser, token_left_paren, "expected '(' after switch", NULL))
		return NULL;
	control = parse_expression(parser, 0);
	if (!control)
		return NULL;
	if (!expect_token(parser, token_right_paren, "expected ')' after switch control", NULL))
		return NULL;
	body = parse_statement(parser);
	if (!body)
		return NULL;
	node = ast_new_switch(parser->arena, keyword.location, control, body);
	if (!node)
		allocation_error(parser, keyword.location);
	return node;
}

/* switch-statement ::= "switch" "(" expression ")" statement; guard nesting. */
static struct ast_switch_statement *parse_switch_statement(struct parser *parser)
{
	struct ast_switch_statement *node;

	if (!begin_nested_statement(parser))
		return NULL;
	node = parse_switch_contents(parser);
	parser->statement_nesting--;
	return node;
}

/* while-statement ::= "while" "(" expression ")" statement */
static struct ast_while_statement *parse_while_contents(struct parser *parser)
{
	struct token keyword;
	struct ast_expression *condition;
	struct ast_statement *body;
	struct ast_while_statement *node;

	if (!expect_token(parser, token_while, "expected 'while'", &keyword))
		return NULL;
	if (!expect_token(parser, token_left_paren, "expected '(' after while", NULL))
		return NULL;
	condition = parse_expression(parser, 0);
	if (!condition)
		return NULL;
	if (!expect_token(parser, token_right_paren, "expected ')' after condition", NULL))
		return NULL;
	body = parse_statement(parser);
	if (!body)
		return NULL;
	node = ast_new_while(parser->arena, keyword.location, condition, body);
	if (!node)
		allocation_error(parser, keyword.location);
	return node;
}

/* while-statement ::= "while" "(" expression ")" statement; guard nesting. */
static struct ast_while_statement *parse_while_statement(struct parser *parser)
{
	struct ast_while_statement *node;

	if (!begin_nested_statement(parser))
		return NULL;
	node = parse_while_contents(parser);
	parser->statement_nesting--;
	return node;
}

/* do-statement ::= "do" statement "while" "(" expression ")" ";" */
static struct ast_do_statement *parse_do_contents(struct parser *parser)
{
	struct token keyword;
	struct ast_statement *body;
	struct ast_expression *condition;
	struct ast_do_statement *node;

	if (!expect_token(parser, token_do, "expected 'do'", &keyword))
		return NULL;
	body = parse_statement(parser);
	if (!body)
		return NULL;
	if (!expect_token(parser, token_while, "expected 'while' after do body", NULL))
		return NULL;
	if (!expect_token(parser, token_left_paren, "expected '(' after while", NULL))
		return NULL;
	condition = parse_expression(parser, 0);
	if (!condition)
		return NULL;
	if (!expect_token(parser, token_right_paren, "expected ')' after condition", NULL))
		return NULL;
	if (!expect_token(parser, token_semicolon, "expected ';' after do/while", NULL))
		return NULL;
	node = ast_new_do(parser->arena, keyword.location, body, condition);
	if (!node)
		allocation_error(parser, keyword.location);
	return node;
}

/* do-statement ::= "do" statement "while" "(" expression ")" ";"; guard nesting. */
static struct ast_do_statement *parse_do_statement(struct parser *parser)
{
	struct ast_do_statement *node;

	if (!begin_nested_statement(parser))
		return NULL;
	node = parse_do_contents(parser);
	parser->statement_nesting--;
	return node;
}

static struct ast_block_item *parse_local_declaration(struct parser *parser);
static struct ast_block_item *parse_block_item(struct parser *parser);
static bool begins_static_assertion(enum token_kind kind);
static bool count_block_item(struct parser *parser, struct source_location location);

/* for-statement ::= "for" "(" for-initializer [ expression ] ";"
 *                   [ expression ] ")" statement
 * for-initializer ::= local-declaration | static-assert-declaration | [ expression ] ";"
 * local-declaration already consumes its semicolon; consume it exactly once.
 */
static struct ast_for_statement *parse_for_contents(struct parser *parser)
{
	struct token keyword;
	struct ast_block_item *initializer_declarations = NULL;
	struct ast_expression *initializer_expression = NULL;
	struct ast_expression *condition = NULL;
	struct ast_expression *step = NULL;
	struct ast_statement *body;
	struct ast_for_statement *node;

	if (!expect_token(parser, token_for, "expected 'for'", &keyword))
		return NULL;
	if (!expect_token(parser, token_left_paren, "expected '(' after for", NULL))
		return NULL;
	if (begins_static_assertion(preprocess_peek(parser->preprocessor).kind)) {
		if (!count_block_item(parser, preprocess_peek(parser->preprocessor).location))
			return NULL;
		initializer_declarations = parse_block_item(parser);
		if (!initializer_declarations)
			return NULL;
	} else if (begins_declaration_specifier(preprocess_peek(parser->preprocessor).kind)) {
		initializer_declarations = parse_local_declaration(parser);
		if (!initializer_declarations)
			return NULL;
	} else {
		if (preprocess_peek(parser->preprocessor).kind != token_semicolon) {
			initializer_expression = parse_expression(parser, 0);
			if (!initializer_expression)
				return NULL;
		}
		if (!expect_token(parser, token_semicolon,
			"expected ';' after for initializer", NULL))
			return NULL;
	}
	if (preprocess_peek(parser->preprocessor).kind != token_semicolon) {
		condition = parse_expression(parser, 0);
		if (!condition)
			return NULL;
	}
	if (!expect_token(parser, token_semicolon,
		"expected ';' after for condition", NULL))
		return NULL;
	if (preprocess_peek(parser->preprocessor).kind != token_right_paren) {
		step = parse_expression(parser, 0);
		if (!step)
			return NULL;
	}
	if (!expect_token(parser, token_right_paren, "expected ')' after for step", NULL))
		return NULL;
	body = parse_statement(parser);
	if (!body)
		return NULL;
	node = ast_new_for(parser->arena, keyword.location, initializer_declarations,
		initializer_expression, condition, step, body);
	if (!node)
		allocation_error(parser, keyword.location);
	return node;
}

/* for-statement ::= "for" "(" for-initializer [ expression ] ";"
 *                   [ expression ] ")" statement; guard nesting.
 */
static struct ast_for_statement *parse_for_statement(struct parser *parser)
{
	struct ast_for_statement *node;

	if (!begin_nested_statement(parser))
		return NULL;
	node = parse_for_contents(parser);
	parser->statement_nesting--;
	return node;
}

/* goto-statement ::= "goto" identifier ";" */
static struct ast_statement *parse_goto_statement(struct parser *parser)
{
	struct token keyword;
	struct token name;
	struct ast_goto_statement *node;

	if (!expect_token(parser, token_goto, "expected 'goto'", &keyword) ||
		!expect_token(parser, token_identifier, "expected label identifier after goto", &name) ||
		!expect_token(parser, token_semicolon, "expected ';' after goto", NULL))
		return NULL;
	node = ast_new_goto(parser->arena, keyword.location, name);
	if (!node)
		allocation_error(parser, keyword.location);
	return node ? &node->statement : NULL;
}

/* break-statement ::= "break" ";" */
static struct ast_statement *parse_break_statement(struct parser *parser)
{
	struct token keyword;
	struct ast_break_statement *node;

	if (!expect_token(parser, token_break, "expected 'break'", &keyword))
		return NULL;
	if (!expect_token(parser, token_semicolon, "expected ';' after break", NULL))
		return NULL;
	node = ast_new_break(parser->arena, keyword.location);
	if (!node) {
		allocation_error(parser, keyword.location);
		return NULL;
	}
	return &node->statement;
}

/* continue-statement ::= "continue" ";" */
static struct ast_statement *parse_continue_statement(struct parser *parser)
{
	struct token keyword;
	struct ast_continue_statement *node;

	if (!expect_token(parser, token_continue, "expected 'continue'", &keyword))
		return NULL;
	if (!expect_token(parser, token_semicolon, "expected ';' after continue", NULL))
		return NULL;
	node = ast_new_continue(parser->arena, keyword.location);
	if (!node) {
		allocation_error(parser, keyword.location);
		return NULL;
	}
	return &node->statement;
}

/* statement ::= return-statement | expression-statement | empty-statement
 *             | compound-statement | if-statement | while-statement
 *             | break-statement | continue-statement | do-statement
 *             | for-statement | labeled-statement | goto-statement | switch-statement
 */
static struct ast_statement *parse_statement(struct parser *parser)
{
	struct token token = preprocess_peek(parser->preprocessor);

	if (token.kind == token_identifier) {
		preprocess_next(parser->preprocessor);
		if (preprocess_peek(parser->preprocessor).kind == token_colon)
			return parse_labeled_statement(parser, token);
		return parse_identifier_expression_statement(parser, token);
	}

	if (begins_static_assertion(token.kind)) {
		diagnostic_error(parser->diagnostics, token.location,
			"static assertion is a declaration, not a statement");
		return NULL;
	}

	if (token.kind == token_for) {
		struct ast_for_statement *node = parse_for_statement(parser);

		if (!node)
			return NULL;
		return &node->statement;
	}
	if (token.kind == token_do) {
		struct ast_do_statement *node = parse_do_statement(parser);

		if (!node)
			return NULL;
		return &node->statement;
	}
	if (token.kind == token_switch) {
		struct ast_switch_statement *node = parse_switch_statement(parser);

		if (!node)
			return NULL;
		return &node->statement;
	}
	if (token.kind == token_while) {
		struct ast_while_statement *node = parse_while_statement(parser);

		if (!node)
			return NULL;
		return &node->statement;
	}
	if (token.kind == token_goto)
		return parse_goto_statement(parser);
	if (token.kind == token_break)
		return parse_break_statement(parser);
	if (token.kind == token_continue)
		return parse_continue_statement(parser);
	if (token.kind == token_if) {
		struct ast_if_statement *node = parse_if_statement(parser);

		if (!node)
			return NULL;
		return &node->statement;
	}
	if (token.kind == token_return) {
		struct ast_return_statement *node = parse_return_statement(parser);

		if (!node)
			return NULL;
		return &node->statement;
	}
	if (token.kind == token_left_brace) {
		struct ast_compound_statement *node = parse_compound_statement(parser);

		if (!node)
			return NULL;
		return &node->statement;
	}
	if (token.kind == token_semicolon)
		return parse_empty_statement(parser);
	return parse_expression_statement(parser);
}

static bool count_block_item(struct parser *parser, struct source_location location)
{
	if (parser->block_items == ast_max_block_items) {
		diagnostic_error(parser->diagnostics, location, "function body exceeds item limit (4096)");
		return false;
	}
	parser->block_items++;
	return true;
}

/* local-declaration ::= declaration-specifiers init-declarator
 *                       { "," init-declarator } ";"
 * init-declarator ::= declarator [ "=" assignment-expression ]
 * Array initializers are diagnosed by sema (braced lists are not parsed yet).
 * Assignment expressions stop before a declarator comma, not call-argument commas.
 */
static struct ast_block_item *parse_local_declaration(struct parser *parser)
{
	struct token beginning;
	struct ast_type_syntax *base = parse_declaration_specifiers(parser, &beginning);
	struct ast_block_item *items = NULL;
	struct ast_block_item **tail = &items;

	if (!base)
		return NULL;
	for (;;) {
		struct token name;
		struct ast_type_syntax *type_syntax;
		struct ast_expression *initializer = NULL;
		struct ast_local_declaration *node;

		if (!count_block_item(parser, preprocess_peek(parser->preprocessor).location))
			return NULL;
		type_syntax = parse_derived_type(parser, base, &name, NULL, declarator_local);
		if (!type_syntax)
			return NULL;
		if (preprocess_peek(parser->preprocessor).kind == token_equal) {
			preprocess_next(parser->preprocessor);
			initializer = parse_expression(parser, 1);
			if (!initializer)
				return NULL;
		}
		node = ast_new_local(parser->arena, beginning.location, name, initializer);
		if (!node) {
			allocation_error(parser, name.location);
			return NULL;
		}
		node->type_syntax = type_syntax;
		*tail = &node->item;
		tail = &node->item.next;
		if (preprocess_peek(parser->preprocessor).kind != token_comma)
			break;
		preprocess_next(parser->preprocessor);
	}
	if (!expect_token(parser, token_semicolon, "expected ';' after declaration", NULL))
		return NULL;
	return items;
}

static bool begins_static_assertion(enum token_kind kind)
{
	return kind == token_static_assert || kind == token_legacy_static_assert;
}

/* static-assert-declaration ::= ("static_assert" | "_Static_assert") "("
 *     conditional-expression [ "," ordinary-string-token { ordinary-string-token } ] ")" ";"
 * The message separator is not the comma operator; parenthesized expressions
 * still parse at floor zero and are checked for ICE form by sema.
 */
static struct ast_static_assertion *parse_static_assertion(struct parser *parser)
{
	struct token keyword = preprocess_next(parser->preprocessor);
	struct ast_expression *condition;
	struct ast_string_expression *message = NULL;
	struct ast_static_assertion *node;

	assert(begins_static_assertion(keyword.kind));
	if (!expect_token(parser, token_left_paren, "expected '(' after static assertion", NULL))
		return NULL;
	condition = parse_expression(parser, 2);
	if (!condition)
		return NULL;
	if (preprocess_peek(parser->preprocessor).kind == token_comma) {
		struct ast_expression *string;

		preprocess_next(parser->preprocessor);
		if (preprocess_peek(parser->preprocessor).kind != token_string) {
			diagnostic_error(parser->diagnostics, preprocess_peek(parser->preprocessor).location,
				"expected string literal in static assertion");
			return NULL;
		}
		string = parse_string_expression(parser);
		if (!string)
			return NULL;
		message = (struct ast_string_expression *)string;
	}
	if (!expect_token(parser, token_right_paren, "expected ')' after static assertion", NULL) ||
		!expect_token(parser, token_semicolon, "expected ';' after static assertion", NULL))
		return NULL;
	node = ast_new_static_assertion(parser->arena, keyword.location, condition, message);
	if (!node)
		allocation_error(parser, keyword.location);
	return node;
}

/* block-item ::= local-declaration | static-assert-declaration | unlabeled-statement | identifier ":" */
static struct ast_block_item *parse_block_item(struct parser *parser)
{
	struct ast_statement *statement;
	struct ast_statement_item *node;
	struct token token = preprocess_peek(parser->preprocessor);

	if (token.kind == token_identifier) {
		preprocess_next(parser->preprocessor);
		if (preprocess_peek(parser->preprocessor).kind == token_colon) {
			struct ast_label *label = parse_label_tail(parser, token);
			struct ast_block_label *block;

			if (!label)
				return NULL;
			block = ast_new_block_label(parser->arena, label);
			if (!block)
				allocation_error(parser, token.location);
			return block ? &block->item : NULL;
		}
		statement = parse_identifier_expression_statement(parser, token);
	} else if (begins_static_assertion(token.kind)) {
		struct ast_static_assertion *declaration = parse_static_assertion(parser);
		struct ast_block_static_assertion *assertion;

		if (!declaration)
			return NULL;
		assertion = ast_new_block_static_assertion(parser->arena, declaration);
		if (!assertion)
			allocation_error(parser, declaration->location);
		return assertion ? &assertion->item : NULL;
	} else if (begins_declaration_specifier(token.kind)) {
		return parse_local_declaration(parser);
	} else {
		statement = parse_statement(parser);
	}
	if (!statement)
		return NULL;
	node = ast_new_statement_item(parser->arena, statement);
	if (!node) {
		allocation_error(parser, statement->location);
		return NULL;
	}
	return &node->item;
}

/* compound-statement ::= "{" { block-item } "}" */
static struct ast_compound_statement *parse_compound_contents(struct parser *parser)
{
	struct token opening;
	struct ast_block_item *items = NULL;
	struct ast_block_item **tail = &items;
	struct ast_compound_statement *node;

	if (!expect_token(parser, token_left_brace, "expected '{'", &opening))
		return NULL;
	while (preprocess_peek(parser->preprocessor).kind != token_right_brace) {
		struct ast_block_item *item;
		struct token token = preprocess_peek(parser->preprocessor);

		if (token.kind == token_eof) {
			diagnostic_error(parser->diagnostics, token.location,
				"expected '}' before end of file");
			return NULL;
		}
		/* Declaration groups charge each concrete declaration themselves. */
		if (!begins_declaration_specifier(token.kind) && !count_block_item(parser, token.location))
			return NULL;
		item = parse_block_item(parser);
		if (!item)
			return NULL;
		*tail = item;
		while (*tail)
			tail = &(*tail)->next;
	}
	preprocess_next(parser->preprocessor);
	node = ast_new_compound(parser->arena, opening.location, items);
	if (!node)
		allocation_error(parser, opening.location);
	return node;
}

/* compound-statement ::= "{" { block-item } "}"; guard recursive blocks. */
static struct ast_compound_statement *parse_compound_statement(struct parser *parser)
{
	struct ast_compound_statement *node;

	if (!begin_nested_statement(parser))
		return NULL;
	node = parse_compound_contents(parser);
	parser->statement_nesting--;
	return node;
}

/* parameter-list ::= "void" | [ parameter-declaration { "," parameter-declaration } ]
 * parameter-declaration ::= declaration-specifiers [ declarator ]
 * C23's empty list specifies zero parameters, just like (void).
 */
static bool parse_parameters(struct parser *parser,
	struct ast_function_type_syntax *function)
{
	struct ast_parameter **tail = &function->parameters;

	if (preprocess_peek(parser->preprocessor).kind == token_right_paren)
		return true;
	for (;;) {
		struct token beginning;
		struct token name = { 0 };
		struct ast_parameter *parameter;
		struct ast_type_syntax *type_syntax;
		bool has_name = false;

		if (function->parameter_count == ast_max_parameters) {
			diagnostic_error(parser->diagnostics,
				preprocess_peek(parser->preprocessor).location,
				"function exceeds parameter limit (128)");
			return false;
		}
		type_syntax = parse_type_name(parser, &beginning, &name, &has_name, declarator_parameter);
		if (!type_syntax)
			return false;
		/* Only a sole unnamed, underived void is the empty-list marker. */
		if (!function->parameter_count && !has_name && type_syntax->kind == type_syntax_void &&
			preprocess_peek(parser->preprocessor).kind == token_right_paren)
			return true;
		parameter = ast_new_parameter(parser->arena, beginning.location, name, has_name);
		if (!parameter) {
			allocation_error(parser, beginning.location);
			return false;
		}
		parameter->type_syntax = type_syntax;
		*tail = parameter;
		tail = &parameter->next;
		function->parameter_count++;
		if (preprocess_peek(parser->preprocessor).kind != token_comma)
			return true;
		preprocess_next(parser->preprocessor);
	}
}

/* external-declaration ::= static-assert-declaration |
 *     declaration-specifiers declarator (";" | compound-statement)
 */
static struct ast_external_declaration *parse_external_declaration(struct parser *parser)
{
	struct ast_type_syntax *type_syntax;
	struct token beginning;
	struct token name;
	struct ast_function_declaration *declaration;
	struct ast_compound_statement *body;
	struct ast_function *function;

	if (begins_static_assertion(preprocess_peek(parser->preprocessor).kind)) {
		struct ast_static_assertion *assertion = parse_static_assertion(parser);
		struct ast_external_static_assertion *external;

		if (!assertion)
			return NULL;
		external = ast_new_external_static_assertion(parser->arena, assertion);
		if (!external)
			allocation_error(parser, assertion->location);
		return external ? &external->external : NULL;
	}
	type_syntax = parse_type_name(parser, &beginning, &name, NULL, declarator_external);
	if (!type_syntax)
		return NULL;
	if (type_syntax->kind != type_syntax_function) {
		diagnostic_error(parser->diagnostics, name.location, "file-scope object declarations are not supported yet");
		return NULL;
	}
	declaration = ast_new_function_declaration(parser->arena, beginning.location, name);
	if (!declaration) {
		allocation_error(parser, beginning.location);
		return NULL;
	}
	declaration->type_syntax = (struct ast_function_type_syntax *)type_syntax;
	/* These are views of the one outer function syntax, not reparsed copies. */
	declaration->return_syntax = declaration->type_syntax->return_syntax;
	declaration->parameters = declaration->type_syntax->parameters;
	declaration->parameter_count = declaration->type_syntax->parameter_count;
	if (preprocess_peek(parser->preprocessor).kind == token_semicolon) {
		preprocess_next(parser->preprocessor);
		return &declaration->external;
	}
	parser->block_items = 0;
	body = parse_compound_statement(parser);
	if (!body)
		return NULL;
	function = ast_new_function(parser->arena, declaration, body);
	if (!function) {
		allocation_error(parser, beginning.location);
		return NULL;
	}
	return &function->external;
}

/* translation-unit ::= external-declaration { external-declaration } end-of-file */
struct ast_translation_unit *parse_translation_unit(struct preprocessor *preprocessor,
	struct arena *arena, struct diagnostics *diagnostics)
{
	struct parser parser = {
		.preprocessor = preprocessor,
		.arena = arena,
		.diagnostics = diagnostics,
	};
	struct ast_external_declaration *declarations = NULL;
	struct ast_external_declaration **tail = &declarations;
	struct ast_translation_unit *unit;
	size_t count = 0;

	do {
		struct ast_external_declaration *declaration;

		if (count == ast_max_external_declarations) {
			diagnostic_error(diagnostics, preprocess_peek(preprocessor).location,
				"translation unit exceeds declaration limit (512)");
			return NULL;
		}
		declaration = parse_external_declaration(&parser);
		if (!declaration)
			return NULL;
		*tail = declaration;
		tail = &declaration->next;
		count++;
	} while (preprocess_peek(preprocessor).kind != token_eof);
	/* EOF can carry a deferred preprocessor diagnostic without a C token. */
	if (diagnostics->errors)
		return NULL;
	unit = ast_new_translation_unit(arena, declarations);
	if (!unit)
		allocation_error(&parser, declarations->location);
	return unit;
}
