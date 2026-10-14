#include "ast.h"

struct ast_integer_expression *ast_new_integer(struct arena *arena,
	struct token token)
{
	struct ast_integer_expression *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_integer_expression) {
			.expression = { expression_integer, token.location, NULL, 1 },
			.value = token.integer,
		};
	return node;
}

struct ast_unary_expression *ast_new_unary(struct arena *arena,
	struct source_location location, enum unary_operator operation,
	struct ast_expression *operand)
{
	struct ast_unary_expression *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_unary_expression) {
			.expression = { expression_unary, location, NULL,
				operand->depth + 1 },
			.operation = operation,
			.operand = operand,
		};
	return node;
}

struct ast_binary_expression *ast_new_binary(struct arena *arena,
	struct source_location location, enum binary_operator operation,
	struct ast_expression *left, struct ast_expression *right)
{
	struct ast_binary_expression *node = arena_alloc(arena, sizeof(*node));
	unsigned depth = left->depth > right->depth ? left->depth : right->depth;

	if (node)
		*node = (struct ast_binary_expression) {
			.expression = { expression_binary, location, NULL, depth + 1 },
			.operation = operation,
			.left = left,
			.right = right,
		};
	return node;
}

struct ast_return_statement *ast_new_return(struct arena *arena,
	struct source_location location, struct ast_expression *value)
{
	struct ast_return_statement *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_return_statement) {
			.statement = { statement_return, location },
			.value = value,
		};
	return node;
}

struct ast_compound_statement *ast_new_compound(struct arena *arena,
	struct source_location location, struct ast_statement *body)
{
	struct ast_compound_statement *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_compound_statement) {
			.statement = { statement_compound, location },
			.body = body,
		};
	return node;
}

struct ast_function *ast_new_function(struct arena *arena,
	struct source_location location, struct token name,
	struct ast_compound_statement *body)
{
	struct ast_function *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_function) {
			.location = location,
			.name = name,
			.body = body,
		};
	return node;
}

struct ast_translation_unit *ast_new_translation_unit(struct arena *arena,
	struct ast_function *function)
{
	struct ast_translation_unit *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_translation_unit) { function };
	return node;
}
