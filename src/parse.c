#include "parse.h"

struct parser {
	struct lexer *lexer;
	struct arena *arena;
	struct diagnostics *diagnostics;
	unsigned depth;
};

static bool expect_token(struct parser *parser, enum token_kind kind,
	const char *message, struct token *result)
{
	struct token token = lexer_next(parser->lexer);

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

/* integer-expression ::= decimal-integer-token */
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

struct infix_operator {
	enum token_kind token;
	enum binary_operator operation;
	unsigned left_binding_power;
	unsigned right_binding_power;
};

/* A higher binding power binds more tightly. Right = left + 1 gives left
 * associativity: a-b-c is (a-b)-c, because the RHS does not consume another
 * operator of equal precedence. Prefix operators bind at 30.
 */
static const struct infix_operator infix_operators[] = {
	{ token_plus, binary_add, 10, 11 },
	{ token_minus, binary_subtract, 10, 11 },
	{ token_star, binary_multiply, 20, 21 },
	{ token_slash, binary_divide, 20, 21 },
	{ token_percent, binary_remainder, 20, 21 },
};

static const struct infix_operator *find_infix_operator(enum token_kind kind)
{
	for (size_t i = 0; i < sizeof(infix_operators) / sizeof(infix_operators[0]); i++)
		if (infix_operators[i].token == kind)
			return &infix_operators[i];
	return NULL;
}

static struct ast_expression *parse_expression(struct parser *parser,
	unsigned minimum_binding_power);

/* primary-expression ::= integer-expression | "(" expression ")" */
static struct ast_expression *parse_primary_expression(struct parser *parser)
{
	struct token token = lexer_peek(parser->lexer);
	struct ast_expression *expression;

	if (token.kind != token_left_paren)
		return parse_integer_expression(parser);
	lexer_next(parser->lexer);
	expression = parse_expression(parser, 0);
	if (!expression)
		return NULL;
	if (!expect_token(parser, token_right_paren, "expected ')'", NULL))
		return NULL;
	return expression;
}

/* prefix-expression ::= primary-expression | ("+" | "-") prefix-expression */
static struct ast_expression *parse_prefix_expression(struct parser *parser)
{
	struct token token = lexer_peek(parser->lexer);
	struct ast_expression *operand;
	struct ast_unary_expression *node;
	enum unary_operator operation;

	if (token.kind != token_plus && token.kind != token_minus)
		return parse_primary_expression(parser);
	lexer_next(parser->lexer);
	operation = token.kind == token_plus ? unary_plus : unary_minus;
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

/* expression ::= prefix-expression { binary-operator prefix-expression }
 * binary-operator ::= "+" | "-" | "*" | "/" | "%"
 * Pratt parsing groups this flat grammar using the binding-power table.
 * Recursive calls parse RHS operators only at or above the requested power.
 */
static struct ast_expression *parse_expression(struct parser *parser,
	unsigned minimum_binding_power)
{
	struct ast_expression *left;

	if (parser->depth == ast_max_expression_depth) {
		diagnostic_error(parser->diagnostics,
			lexer_peek(parser->lexer).location,
			"expression nesting exceeds depth limit (128)");
		return NULL;
	}
	parser->depth++;
	left = parse_prefix_expression(parser);
	if (!left)
		goto failure;

	for (;;) {
		struct token token = lexer_peek(parser->lexer);
		const struct infix_operator *operator = find_infix_operator(token.kind);
		struct ast_expression *right;
		struct ast_binary_expression *node;

		if (!operator || operator->left_binding_power < minimum_binding_power)
			break;
		lexer_next(parser->lexer);
		right = parse_expression(parser, operator->right_binding_power);
		if (!right)
			goto failure;
		if (left->depth >= ast_max_expression_depth ||
			right->depth >= ast_max_expression_depth) {
			diagnostic_error(parser->diagnostics, token.location,
				"expression tree exceeds depth limit (128)");
			goto failure;
		}
		node = ast_new_binary(parser->arena, token.location,
			operator->operation, left, right);
		if (!node) {
			allocation_error(parser, token.location);
			goto failure;
		}
		left = &node->expression;
	}
	parser->depth--;
	return left;

failure:
	parser->depth--;
	return NULL;
}

/* return-statement ::= "return" expression ";" */
static struct ast_return_statement *parse_return_statement(struct parser *parser)
{
	struct token keyword;
	struct ast_expression *value;
	struct ast_return_statement *node;

	if (!expect_token(parser, token_return, "expected 'return'", &keyword))
		return NULL;
	value = parse_expression(parser, 0);
	if (!value)
		return NULL;
	if (!expect_token(parser, token_semicolon, "expected ';' after return", NULL))
		return NULL;
	node = ast_new_return(parser->arena, keyword.location, value);
	if (!node)
		allocation_error(parser, keyword.location);
	return node;
}

/* compound-statement ::= "{" return-statement "}" */
static struct ast_compound_statement *parse_compound_statement(struct parser *parser)
{
	struct token opening;
	struct ast_return_statement *body;
	struct ast_compound_statement *node;

	if (!expect_token(parser, token_left_brace, "expected '{'", &opening))
		return NULL;
	body = parse_return_statement(parser);
	if (!body)
		return NULL;
	if (!expect_token(parser, token_right_brace, "expected '}'", NULL))
		return NULL;
	node = ast_new_compound(parser->arena, opening.location, &body->statement);
	if (!node)
		allocation_error(parser, opening.location);
	return node;
}

/* function-definition ::= "int" identifier "(" "void" ")" compound-statement */
static struct ast_function *parse_function_definition(struct parser *parser)
{
	struct token beginning;
	struct token name;
	struct ast_compound_statement *body;
	struct ast_function *node;

	if (!expect_token(parser, token_int, "expected 'int' return type", &beginning))
		return NULL;
	if (!expect_token(parser, token_identifier, "expected function name", &name))
		return NULL;
	if (!expect_token(parser, token_left_paren, "expected '('", NULL))
		return NULL;
	if (!expect_token(parser, token_void, "expected 'void' parameter list", NULL))
		return NULL;
	if (!expect_token(parser, token_right_paren, "expected ')'", NULL))
		return NULL;
	body = parse_compound_statement(parser);
	if (!body)
		return NULL;
	node = ast_new_function(parser->arena, beginning.location, name, body);
	if (!node)
		allocation_error(parser, beginning.location);
	return node;
}

/* translation-unit ::= function-definition end-of-file */
struct ast_translation_unit *parse_translation_unit(struct lexer *lexer,
	struct arena *arena, struct diagnostics *diagnostics)
{
	struct parser parser = {
		.lexer = lexer,
		.arena = arena,
		.diagnostics = diagnostics,
	};
	struct ast_function *function = parse_function_definition(&parser);
	struct ast_translation_unit *unit;

	if (!function)
		return NULL;
	if (!expect_token(&parser, token_eof, "expected end of file", NULL))
		return NULL;
	unit = ast_new_translation_unit(arena, function);
	if (!unit)
		allocation_error(&parser, function->location);
	return unit;
}
