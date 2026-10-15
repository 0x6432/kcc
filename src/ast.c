#include "ast.h"

struct ast_integer_expression *ast_new_integer(struct arena *arena,
	struct token token)
{
	struct ast_integer_expression *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_integer_expression) {
			.expression = {
				.kind = expression_integer,
				.location = token.location,
				.depth = 1,
			},
			.value = token.integer,
		};
	return node;
}

struct ast_name_expression *ast_new_name(struct arena *arena, struct token name)
{
	struct ast_name_expression *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_name_expression) {
			.expression = {
				.kind = expression_name,
				.location = name.location,
				.depth = 1,
			},
			.name = name,
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
			.expression = {
				.kind = expression_unary,
				.location = location,
				.depth = operand->depth + 1,
			},
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
			.expression = {
				.kind = expression_binary,
				.location = location,
				.depth = depth + 1,
			},
			.operation = operation,
			.left = left,
			.right = right,
		};
	return node;
}

struct ast_logical_expression *ast_new_logical(struct arena *arena,
	struct source_location location, enum logical_operator operation,
	struct ast_expression *left, struct ast_expression *right)
{
	struct ast_logical_expression *node = arena_alloc(arena, sizeof(*node));
	unsigned depth = left->depth > right->depth ? left->depth : right->depth;

	if (node)
		*node = (struct ast_logical_expression) {
			.expression = {
				.kind = expression_logical,
				.location = location,
				.depth = depth + 1,
			},
			.operation = operation,
			.left = left,
			.right = right,
		};
	return node;
}

struct ast_assignment_expression *ast_new_assignment(struct arena *arena,
	struct source_location location, struct ast_expression *left,
	struct ast_expression *right)
{
	struct ast_assignment_expression *node = arena_alloc(arena, sizeof(*node));
	unsigned depth = left->depth > right->depth ? left->depth : right->depth;

	if (node)
		*node = (struct ast_assignment_expression) {
			.expression = {
				.kind = expression_assignment,
				.location = location,
				.depth = depth + 1,
			},
			.left = left,
			.right = right,
		};
	return node;
}

struct ast_load_expression *ast_new_load(struct arena *arena,
	struct ast_expression *operand)
{
	struct ast_load_expression *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_load_expression) {
			.expression = {
				.kind = expression_load,
				.location = operand->location,
				.depth = operand->depth + 1,
			},
			.operand = operand,
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

struct ast_expression_statement *ast_new_expression_statement(struct arena *arena,
	struct source_location location, struct ast_expression *value)
{
	struct ast_expression_statement *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_expression_statement) {
			.statement = { statement_expression, location },
			.value = value,
		};
	return node;
}

struct ast_empty_statement *ast_new_empty_statement(struct arena *arena,
	struct source_location location)
{
	struct ast_empty_statement *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_empty_statement) {
			.statement = { statement_empty, location },
		};
	return node;
}

struct ast_if_statement *ast_new_if(struct arena *arena,
	struct source_location location, struct ast_expression *condition,
	struct ast_statement *then_branch, struct ast_statement *else_branch)
{
	struct ast_if_statement *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_if_statement) {
			.statement = { statement_if, location },
			.condition = condition,
			.then_branch = then_branch,
			.else_branch = else_branch,
		};
	return node;
}

struct ast_local_declaration *ast_new_local(struct arena *arena,
	struct source_location location, struct token name,
	struct ast_expression *initializer)
{
	struct ast_local_declaration *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_local_declaration) {
			.item = { .kind = block_item_declaration, .location = location },
			.name = name,
			.initializer = initializer,
		};
	return node;
}

struct ast_statement_item *ast_new_statement_item(struct arena *arena,
	struct ast_statement *statement)
{
	struct ast_statement_item *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_statement_item) {
			.item = {
				.kind = block_item_statement,
				.location = statement->location,
			},
			.statement = statement,
		};
	return node;
}

struct ast_compound_statement *ast_new_compound(struct arena *arena,
	struct source_location location, struct ast_block_item *items)
{
	struct ast_compound_statement *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_compound_statement) {
			.statement = { statement_compound, location },
			.items = items,
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
