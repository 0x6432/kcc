#include "parse.h"

#include <assert.h>

struct parser {
	struct lexer *lexer;
	struct arena *arena;
	struct diagnostics *diagnostics;
	unsigned depth;
	unsigned statement_nesting;
	size_t block_items;
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
	unsigned left_binding_power;
	unsigned right_binding_power;
};

/* A higher binding power binds more tightly. Right = left + 1 gives left
 * associativity: a-b-c is (a-b)-c, because the RHS does not consume another
 * operator of equal precedence. Assignment uses equal left/right powers,
 * making a=b=c associate as a=(b=c). Prefix operators bind at 30.
 */
static const struct infix_operator infix_operators[] = {
	{ token_equal, 1, 1 },
	{ token_or_or, 2, 3 },
	{ token_and_and, 3, 4 },
	{ token_equal_equal, 7, 8 },
	{ token_not_equal, 7, 8 },
	{ token_less, 8, 9 },
	{ token_less_equal, 8, 9 },
	{ token_greater, 8, 9 },
	{ token_greater_equal, 8, 9 },
	{ token_plus, 10, 11 },
	{ token_minus, 10, 11 },
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

static struct ast_expression *parse_expression(struct parser *parser,
	unsigned minimum_binding_power);

/* primary-expression ::= integer-expression | identifier | "(" expression ")" */
static struct ast_expression *parse_primary_expression(struct parser *parser)
{
	struct token token = lexer_peek(parser->lexer);
	struct ast_expression *expression;

	if (token.kind == token_identifier) {
		struct ast_name_expression *node;

		lexer_next(parser->lexer);
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

/* prefix-expression ::= primary-expression | ("+" | "-" | "!") prefix-expression */
static struct ast_expression *parse_prefix_expression(struct parser *parser)
{
	struct token token = lexer_peek(parser->lexer);
	struct ast_expression *operand;
	struct ast_unary_expression *node;
	enum unary_operator operation;

	if (token.kind != token_plus && token.kind != token_minus &&
		token.kind != token_bang)
		return parse_primary_expression(parser);
	lexer_next(parser->lexer);
	switch (token.kind) {
	case token_plus: operation = unary_plus; break;
	case token_minus: operation = unary_minus; break;
	case token_bang: operation = unary_not; break;
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
	case token_plus: return binary_add;
	case token_minus: return binary_subtract;
	case token_star: return binary_multiply;
	case token_slash: return binary_divide;
	case token_percent: return binary_remainder;
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

static struct ast_expression *new_infix_expression(struct parser *parser,
	struct token token, struct ast_expression *left, struct ast_expression *right)
{
	if (token.kind == token_equal) {
		struct ast_assignment_expression *node = ast_new_assignment(
			parser->arena, token.location, left, right);

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

/* expression ::= prefix-expression { binary-operator prefix-expression }
 * binary-operator ::= "=" | "+" | "-" | "*" | "/" | "%"
 *                   | "==" | "!=" | "<" | "<=" | ">" | ">=" | "&&" | "||"
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
		struct ast_expression *node;

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
		node = new_infix_expression(parser, token, left, right);
		if (!node)
			goto failure;
		left = node;
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

/* expression-statement ::= expression ";" */
static struct ast_statement *parse_expression_statement(struct parser *parser)
{
	struct ast_expression *value = parse_expression(parser, 0);
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
			lexer_peek(parser->lexer).location,
			"statement nesting exceeds limit (128)");
		return false;
	}
	parser->statement_nesting++;
	return true;
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
	if (lexer_peek(parser->lexer).kind == token_else) {
		lexer_next(parser->lexer);
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

/* statement ::= return-statement | expression-statement | empty-statement
 *             | compound-statement | if-statement
 */
static struct ast_statement *parse_statement(struct parser *parser)
{
	struct token token = lexer_peek(parser->lexer);

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

/* local-declaration ::= "int" identifier [ "=" expression ] ";" */
static struct ast_block_item *parse_local_declaration(struct parser *parser)
{
	struct token beginning;
	struct token name;
	struct ast_expression *initializer = NULL;
	struct ast_local_declaration *node;

	if (!expect_token(parser, token_int, "expected 'int'", &beginning))
		return NULL;
	if (!expect_token(parser, token_identifier, "expected local name", &name))
		return NULL;
	if (lexer_peek(parser->lexer).kind == token_equal) {
		lexer_next(parser->lexer);
		initializer = parse_expression(parser, 0);
		if (!initializer)
			return NULL;
	}
	if (!expect_token(parser, token_semicolon,
		"expected ';' after declaration", NULL))
		return NULL;
	node = ast_new_local(parser->arena, beginning.location, name, initializer);
	if (!node) {
		allocation_error(parser, beginning.location);
		return NULL;
	}
	return &node->item;
}

/* block-item ::= local-declaration | statement */
static struct ast_block_item *parse_block_item(struct parser *parser)
{
	struct ast_statement *statement;
	struct ast_statement_item *node;

	if (lexer_peek(parser->lexer).kind == token_int)
		return parse_local_declaration(parser);
	statement = parse_statement(parser);
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
	while (lexer_peek(parser->lexer).kind != token_right_brace) {
		struct ast_block_item *item;
		struct token token = lexer_peek(parser->lexer);

		if (token.kind == token_eof) {
			diagnostic_error(parser->diagnostics, token.location,
				"expected '}' before end of file");
			return NULL;
		}
		if (parser->block_items == ast_max_block_items) {
			diagnostic_error(parser->diagnostics, token.location,
				"function body exceeds item limit (4096)");
			return NULL;
		}
		parser->block_items++;
		item = parse_block_item(parser);
		if (!item)
			return NULL;
		*tail = item;
		tail = &item->next;
	}
	lexer_next(parser->lexer);
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
