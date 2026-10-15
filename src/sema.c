#include "sema.h"
#include "type.h"

#include <assert.h>
#include <string.h>

struct binding {
	struct ast_local_declaration *declaration;
	struct binding *next;
};

struct scope {
	struct scope *parent;
	struct binding *bindings;
};

struct sema {
	struct arena *arena;
	struct diagnostics *diagnostics;
	struct ast_function *function;
	struct scope *scope;
	size_t local_count;
};

static bool same_name(struct token left, struct token right)
{
	return left.length == right.length &&
		memcmp(left.location.source->data + left.location.offset,
			right.location.source->data + right.location.offset,
			left.length) == 0;
}

static struct ast_local_declaration *find_in_scope(struct scope *scope,
	struct token name)
{
	struct binding *binding = scope->bindings;

	while (binding) {
		if (same_name(binding->declaration->name, name))
			return binding->declaration;
		binding = binding->next;
	}
	return NULL;
}

static struct ast_local_declaration *find_local(struct sema *sema,
	struct token name)
{
	struct scope *scope = sema->scope;

	while (scope) {
		struct ast_local_declaration *local = find_in_scope(scope, name);

		if (local)
			return local;
		scope = scope->parent;
	}
	return NULL;
}

static bool check_expression_depth(struct sema *sema,
	struct ast_expression *expression)
{
	if (expression->depth > ast_max_expression_depth) {
		diagnostic_error(sema->diagnostics, expression->location,
			"typed expression exceeds depth limit (128)");
		return false;
	}
	return true;
}

/* Resolve/types are independent of parsing. Value contexts explicitly load
 * lvalues; assignment's left operand must remain an object, not a loaded value.
 */
static bool sema_expression(struct sema *sema,
	struct ast_expression **expression_slot, bool value_required)
{
	struct ast_expression *expression = *expression_slot;

	switch (expression->kind) {
	case expression_integer: {
		struct ast_integer_expression *node =
			(struct ast_integer_expression *)expression;

		if (node->value > INT32_MAX) {
			diagnostic_error(sema->diagnostics, expression->location,
				"literal does not fit the supported int type");
			return false;
		}
		break;
	}
	case expression_name: {
		struct ast_name_expression *node =
			(struct ast_name_expression *)expression;

		node->declaration = find_local(sema, node->name);
		if (!node->declaration) {
			diagnostic_error(sema->diagnostics, expression->location,
				"use of undeclared identifier");
			return false;
		}
		expression->is_lvalue = true;
		break;
	}
	case expression_unary: {
		struct ast_unary_expression *node =
			(struct ast_unary_expression *)expression;

		if (!sema_expression(sema, &node->operand, true))
			return false;
		expression->depth = node->operand->depth + 1;
		break;
	}
	case expression_binary: {
		struct ast_binary_expression *node =
			(struct ast_binary_expression *)expression;
		unsigned depth;

		if (!sema_expression(sema, &node->left, true))
			return false;
		if (!sema_expression(sema, &node->right, true))
			return false;
		depth = node->left->depth > node->right->depth ?
			node->left->depth : node->right->depth;
		expression->depth = depth + 1;
		break;
	}
	case expression_assignment: {
		struct ast_assignment_expression *node =
			(struct ast_assignment_expression *)expression;
		unsigned depth;

		if (!sema_expression(sema, &node->left, false))
			return false;
		if (!node->left->is_lvalue) {
			diagnostic_error(sema->diagnostics, node->left->location,
				"assignment requires a modifiable lvalue");
			return false;
		}
		if (!sema_expression(sema, &node->right, true))
			return false;
		depth = node->left->depth > node->right->depth ?
			node->left->depth : node->right->depth;
		expression->depth = depth + 1;
		break;
	}
	case expression_load:
		/* Conversion nodes are introduced below; sema is a single pass. */
		assert(0 && "load node before semantic analysis");
		return false;
	}
	expression->type = &type_int;
	if (!check_expression_depth(sema, expression))
		return false;

	if (value_required && expression->is_lvalue) {
		struct ast_load_expression *load = ast_new_load(sema->arena, expression);

		if (!load) {
			diagnostic_error(sema->diagnostics, expression->location,
				"out of memory inserting lvalue conversion");
			return false;
		}
		load->expression.type = &type_int;
		if (!check_expression_depth(sema, &load->expression))
			return false;
		*expression_slot = &load->expression;
	}
	return true;
}

static bool sema_local(struct sema *sema, struct ast_local_declaration *local)
{
	struct binding *binding;

	if (find_in_scope(sema->scope, local->name)) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"redeclaration of local in this scope");
		return false;
	}
	if (sema->local_count == ast_max_locals) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"function exceeds local limit (256)");
		return false;
	}

	binding = arena_alloc(sema->arena, sizeof(*binding));
	if (!binding) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"out of memory creating scope binding");
		return false;
	}
	*binding = (struct binding) { local, sema->scope->bindings };
	sema->scope->bindings = binding;

	/* C's point of declaration is before the initializer is analyzed. */
	local->type = &type_int;
	local->slot = sema->local_count++;
	local->next_local = sema->function->locals;
	sema->function->locals = local;
	if (local->initializer)
		return sema_expression(sema, &local->initializer, true);
	return true;
}

static bool sema_compound(struct sema *sema, struct ast_compound_statement *node);

static bool sema_statement(struct sema *sema, struct ast_statement *statement)
{
	switch (statement->kind) {
	case statement_return: {
		struct ast_return_statement *node =
			(struct ast_return_statement *)statement;

		return sema_expression(sema, &node->value, true);
	}
	case statement_expression: {
		struct ast_expression_statement *node =
			(struct ast_expression_statement *)statement;

		return sema_expression(sema, &node->value, true);
	}
	case statement_empty:
		return true;
	case statement_compound:
		return sema_compound(sema, (struct ast_compound_statement *)statement);
	}
	assert(0 && "unknown statement kind");
	return false;
}

static bool sema_block_items(struct sema *sema, struct ast_block_item *item)
{
	while (item) {
		switch (item->kind) {
		case block_item_declaration:
			if (!sema_local(sema, (struct ast_local_declaration *)item))
				return false;
			break;
		case block_item_statement: {
			struct ast_statement_item *node = (struct ast_statement_item *)item;

			if (!sema_statement(sema, node->statement))
				return false;
			break;
		}
		}
		item = item->next;
	}
	return true;
}

static bool sema_compound(struct sema *sema, struct ast_compound_statement *node)
{
	struct scope scope = { .parent = sema->scope };
	bool success;

	sema->scope = &scope;
	success = sema_block_items(sema, node->items);
	sema->scope = scope.parent;
	return success;
}

bool sema_translation_unit(struct ast_translation_unit *unit, struct arena *arena,
	struct diagnostics *diagnostics)
{
	struct ast_function *function = unit->function;
	struct token name = function->name;
	struct sema sema = {
		.arena = arena,
		.diagnostics = diagnostics,
		.function = function,
	};

	if (name.length != 4 || memcmp(name.location.source->data +
		name.location.offset, "main", 4) != 0) {
		diagnostic_error(diagnostics, name.location,
			"only a function named main is supported");
		return false;
	}
	function->return_type = &type_int;
	return sema_compound(&sema, function->body);
}
