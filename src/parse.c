#include "parse.h"

struct parser {
	struct lexer *lexer;
	struct arena *arena;
	struct diagnostics *diagnostics;
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

/* return-statement ::= "return" integer-expression ";" */
static struct ast_return_statement *parse_return_statement(struct parser *parser)
{
	struct token keyword;
	struct ast_expression *value;
	struct ast_return_statement *node;

	if (!expect_token(parser, token_return, "expected 'return'", &keyword))
		return NULL;
	value = parse_integer_expression(parser);
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
	struct parser parser = { lexer, arena, diagnostics };
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
