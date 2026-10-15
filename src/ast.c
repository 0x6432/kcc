#include "ast.h"

#include <assert.h>

struct ast_integer_type_syntax *ast_new_integer_type_syntax(struct arena *arena,
	struct source_location location, enum integer_specifier specifier)
{
	struct ast_integer_type_syntax *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_integer_type_syntax) {
			.syntax = { .kind = type_syntax_integer, .location = location },
			.specifier = specifier,
		};
	return node;
}

struct ast_pointer_type_syntax *ast_new_pointer_type_syntax(struct arena *arena,
	struct source_location location, struct ast_type_syntax *referent)
{
	struct ast_pointer_type_syntax *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_pointer_type_syntax) {
			.syntax = { .kind = type_syntax_pointer, .location = location },
			.referent = referent,
		};
	return node;
}

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
			.base = token.integer_base,
			.long_suffix = token.integer_long_suffix,
			.unsigned_suffix = token.integer_unsigned_suffix,
		};
	return node;
}

struct ast_character_expression *ast_new_character(struct arena *arena,
	struct token token)
{
	struct ast_character_expression *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_character_expression) {
			.expression = {
				.kind = expression_character,
				.location = token.location,
				.depth = 1,
			},
			.value = token.character,
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

struct ast_cast_expression *ast_new_cast(struct arena *arena,
	struct source_location location, struct ast_type_syntax *type_syntax,
	struct ast_expression *operand)
{
	struct ast_cast_expression *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_cast_expression) {
			.expression = {
				.kind = expression_cast,
				.location = location,
				.depth = operand->depth + 1,
			},
			.type_syntax = type_syntax,
			.operand = operand,
		};
	return node;
}

struct ast_conversion_expression *ast_new_conversion(struct arena *arena,
	struct ast_expression *operand, const struct type *target)
{
	struct ast_conversion_expression *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_conversion_expression) {
			.expression = {
				.kind = expression_conversion,
				.location = operand->location,
				.type = target,
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

struct ast_while_statement *ast_new_while(struct arena *arena,
	struct source_location location, struct ast_expression *condition,
	struct ast_statement *body)
{
	struct ast_while_statement *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_while_statement) {
			.statement = { statement_while, location },
			.condition = condition,
			.body = body,
		};
	return node;
}

struct ast_do_statement *ast_new_do(struct arena *arena,
	struct source_location location, struct ast_statement *body,
	struct ast_expression *condition)
{
	struct ast_do_statement *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_do_statement) {
			.statement = { statement_do, location },
			.body = body,
			.condition = condition,
		};
	return node;
}

struct ast_for_statement *ast_new_for(struct arena *arena,
	struct source_location location,
	struct ast_local_declaration *initializer_declaration,
	struct ast_expression *initializer_expression, struct ast_expression *condition,
	struct ast_expression *step, struct ast_statement *body)
{
	struct ast_for_statement *node = arena_alloc(arena, sizeof(*node));

	assert(!initializer_declaration || !initializer_expression);
	if (node)
		*node = (struct ast_for_statement) {
			.statement = { statement_for, location },
			.initializer_declaration = initializer_declaration,
			.initializer_expression = initializer_expression,
			.condition = condition,
			.step = step,
			.body = body,
		};
	return node;
}

struct ast_break_statement *ast_new_break(struct arena *arena,
	struct source_location location)
{
	struct ast_break_statement *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_break_statement) {
			.statement = { statement_break, location },
		};
	return node;
}

struct ast_continue_statement *ast_new_continue(struct arena *arena,
	struct source_location location)
{
	struct ast_continue_statement *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_continue_statement) {
			.statement = { statement_continue, location },
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

struct ast_argument *ast_new_argument(struct arena *arena, struct ast_expression *value)
{
	struct ast_argument *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_argument) { .value = value };
	return node;
}

struct ast_parameter *ast_new_parameter(struct arena *arena,
	struct source_location location, struct token name, bool has_name)
{
	struct ast_parameter *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_parameter) {
			.location = location,
			.name = name,
			.has_name = has_name,
		};
	return node;
}

struct ast_call_expression *ast_new_call(struct arena *arena,
	struct ast_expression *callee, struct ast_argument *arguments, size_t argument_count)
{
	struct ast_call_expression *node = arena_alloc(arena, sizeof(*node));
	unsigned depth = callee->depth;

	for (struct ast_argument *argument = arguments; argument; argument = argument->next)
		if (argument->value->depth > depth)
			depth = argument->value->depth;

	if (node)
		*node = (struct ast_call_expression) {
			.expression = {
				.kind = expression_call,
				.location = callee->location,
				.depth = depth + 1,
			},
			.callee = callee,
			.arguments = arguments,
			.argument_count = argument_count,
		};
	return node;
}

struct ast_function_declaration *ast_new_function_declaration(struct arena *arena,
	struct source_location location, struct token name)
{
	struct ast_function_declaration *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_function_declaration) {
			.external = { .kind = external_function_declaration,
				.location = location },
			.name = name,
		};
	return node;
}

struct ast_function *ast_new_function(struct arena *arena,
	struct ast_function_declaration *declaration, struct ast_compound_statement *body)
{
	struct ast_function *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_function) {
			.external = { .kind = external_function_definition,
				.location = declaration->external.location },
			.declaration = declaration,
			.body = body,
		};
	return node;
}

struct ast_translation_unit *ast_new_translation_unit(struct arena *arena,
	struct ast_external_declaration *declarations)
{
	struct ast_translation_unit *node = arena_alloc(arena, sizeof(*node));

	if (node)
		*node = (struct ast_translation_unit) { declarations };
	return node;
}
