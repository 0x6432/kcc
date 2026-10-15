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

struct loop_context {
	struct loop_context *parent;
	struct ast_statement *statement;
};

struct sema {
	struct arena *arena;
	struct diagnostics *diagnostics;
	struct ast_function *function;
	struct scope *scope;
	struct loop_context *loop;
	size_t local_count;
	struct function_symbol *functions;
	size_t function_count;
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

static struct function_symbol *find_function(struct sema *sema, struct token name)
{
	struct function_symbol *symbol = sema->functions;

	while (symbol) {
		if (same_name(symbol->name, name))
			return symbol;
		symbol = symbol->next;
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
	case expression_call: {
		struct ast_call_expression *node = (struct ast_call_expression *)expression;
		struct ast_name_expression *callee;

		if (node->callee->kind != expression_name) {
			diagnostic_error(sema->diagnostics, node->callee->location,
				"only direct calls to named functions are supported");
			return false;
		}
		callee = (struct ast_name_expression *)node->callee;
		if (find_local(sema, callee->name)) {
			diagnostic_error(sema->diagnostics, node->callee->location,
				"called identifier denotes a local object, not a function");
			return false;
		}
		node->function = find_function(sema, callee->name);
		if (!node->function) {
			diagnostic_error(sema->diagnostics, node->callee->location,
				"call to undeclared function");
			return false;
		}
		node->callee->type = &node->function->type->type;
		if (node->argument_count != node->function->type->parameter_count) {
			diagnostic_error(sema->diagnostics, expression->location,
				"argument count does not match function signature");
			return false;
		}
		expression->depth = node->callee->depth + 1;
		for (struct ast_argument *argument = node->arguments; argument;
			argument = argument->next) {
			if (!sema_expression(sema, &argument->value, true))
				return false;
			if (argument->value->depth + 1 > expression->depth)
				expression->depth = argument->value->depth + 1;
		}
		break;
	}
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
	case expression_logical: {
		struct ast_logical_expression *node =
			(struct ast_logical_expression *)expression;
		unsigned depth;

		/* Even a constant-skipped RHS must obey C's constraints. */
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

static bool sema_statement(struct sema *sema, struct ast_statement *statement);

static bool sema_substatement(struct sema *sema, struct ast_statement *statement)
{
	struct scope scope = { .parent = sema->scope };
	bool success;

	sema->scope = &scope;
	success = sema_statement(sema, statement);
	sema->scope = scope.parent;
	return success;
}

static bool sema_if(struct sema *sema, struct ast_if_statement *node)
{
	struct scope scope = { .parent = sema->scope };
	bool success;

	sema->scope = &scope;
	success = sema_expression(sema, &node->condition, true);
	if (success)
		success = sema_substatement(sema, node->then_branch);
	if (success && node->else_branch)
		success = sema_substatement(sema, node->else_branch);
	sema->scope = scope.parent;
	return success;
}

static bool sema_loop_body(struct sema *sema, struct ast_statement *loop,
	struct ast_statement *body)
{
	struct loop_context context = { sema->loop, loop };
	bool success;

	sema->loop = &context;
	success = sema_substatement(sema, body);
	sema->loop = context.parent;
	return success;
}

static bool sema_while(struct sema *sema, struct ast_while_statement *node)
{
	struct scope scope = { .parent = sema->scope };
	bool success;

	sema->scope = &scope;
	success = sema_expression(sema, &node->condition, true);
	if (success)
		success = sema_loop_body(sema, &node->statement, node->body);
	sema->scope = scope.parent;
	return success;
}

static bool sema_do(struct sema *sema, struct ast_do_statement *node)
{
	struct scope scope = { .parent = sema->scope };
	bool success;

	sema->scope = &scope;
	success = sema_loop_body(sema, &node->statement, node->body);
	if (success)
		success = sema_expression(sema, &node->condition, true);
	sema->scope = scope.parent;
	return success;
}

static bool sema_for(struct sema *sema, struct ast_for_statement *node)
{
	struct scope scope = { .parent = sema->scope };
	bool success = true;

	sema->scope = &scope;
	if (node->initializer_declaration)
		success = sema_local(sema, node->initializer_declaration);
	if (success && node->initializer_expression)
		success = sema_expression(sema, &node->initializer_expression, true);
	if (success && node->condition)
		success = sema_expression(sema, &node->condition, true);
	if (success && node->step)
		success = sema_expression(sema, &node->step, true);
	if (success)
		success = sema_loop_body(sema, &node->statement, node->body);
	sema->scope = scope.parent;
	return success;
}

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
	case statement_for:
		return sema_for(sema, (struct ast_for_statement *)statement);
	case statement_do:
		return sema_do(sema, (struct ast_do_statement *)statement);
	case statement_while:
		return sema_while(sema, (struct ast_while_statement *)statement);
	case statement_break: {
		struct ast_break_statement *node = (struct ast_break_statement *)statement;

		if (!sema->loop) {
			diagnostic_error(sema->diagnostics, statement->location,
				"break is only supported inside a loop");
			return false;
		}
		node->target = sema->loop->statement;
		return true;
	}
	case statement_continue: {
		struct ast_continue_statement *node =
			(struct ast_continue_statement *)statement;

		if (!sema->loop) {
			diagnostic_error(sema->diagnostics, statement->location,
				"continue requires an enclosing loop");
			return false;
		}
		node->target = sema->loop->statement;
		return true;
	}
	case statement_if:
		return sema_if(sema, (struct ast_if_statement *)statement);
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

static bool sema_parameter_names(struct sema *sema,
	struct ast_function_declaration *declaration, bool is_definition)
{
	for (struct ast_parameter *parameter = declaration->parameters; parameter;
		parameter = parameter->next) {
		if (!parameter->has_name) {
			if (!is_definition)
				continue;
			diagnostic_error(sema->diagnostics, parameter->location,
				"unnamed definition parameters are not supported yet");
			return false;
		}
		for (struct ast_parameter *prior = declaration->parameters; prior != parameter;
			prior = prior->next) {
			if (prior->has_name && same_name(prior->name, parameter->name)) {
				diagnostic_error(sema->diagnostics, parameter->name.location,
					"duplicate parameter name");
				return false;
			}
		}
	}
	return true;
}

static bool sema_function_body(struct sema *sema, struct ast_function *definition)
{
	struct scope scope = { 0 };
	bool success = false;

	assert(!sema->scope && !sema->loop);
	sema->function = definition;
	sema->local_count = 0;
	sema->scope = &scope;
	for (struct ast_parameter *parameter = definition->declaration->parameters; parameter;
		parameter = parameter->next) {
		parameter->local = ast_new_local(sema->arena, parameter->location,
			parameter->name, NULL);
		if (!parameter->local) {
			diagnostic_error(sema->diagnostics, parameter->location,
				"out of memory creating parameter local");
			goto done;
		}
		if (!sema_local(sema, parameter->local))
			goto done;
	}
	/* Parameters and outermost body declarations inhabit the same scope. */
	success = sema_block_items(sema, definition->body->items);
done:
	sema->scope = NULL;
	sema->function = NULL;
	return success;
}

static bool sema_function_declaration(struct sema *sema,
	struct ast_function_declaration *declaration, struct ast_function *definition)
{
	struct function_symbol *symbol = find_function(sema, declaration->name);
	struct function_type *type;
	struct token main_name = declaration->name;

	if (!sema_parameter_names(sema, declaration, definition != NULL))
		return false;
	if (main_name.length == 4 && memcmp(main_name.location.source->data +
		main_name.location.offset, "main", 4) == 0 && declaration->parameter_count) {
		diagnostic_error(sema->diagnostics, main_name.location,
			"only zero-parameter main is supported yet");
		return false;
	}
	type = type_new_int_function(sema->arena, declaration->parameter_count);
	if (!type) {
		diagnostic_error(sema->diagnostics, declaration->name.location,
			"out of memory creating function type");
		return false;
	}
	if (symbol && !type_compatible(&symbol->type->type, &type->type)) {
		diagnostic_error(sema->diagnostics, declaration->name.location,
			"incompatible function declaration");
		return false;
	}

	if (!symbol) {
		if (sema->function_count == ast_max_functions) {
			diagnostic_error(sema->diagnostics, declaration->name.location,
				"translation unit exceeds function limit (256)");
			return false;
		}
		symbol = arena_alloc(sema->arena, sizeof(*symbol));
		if (!symbol) {
			diagnostic_error(sema->diagnostics, declaration->name.location,
				"out of memory creating function symbol");
			return false;
		}
		*symbol = (struct function_symbol) {
			.name = declaration->name,
			.type = type,
			.next = sema->functions,
		};
		sema->functions = symbol;
		sema->function_count++;
	}
	if (definition && symbol->definition) {
		diagnostic_error(sema->diagnostics, declaration->name.location,
			"redefinition of function");
		return false;
	}
	declaration->symbol = symbol;
	if (!definition)
		return true;
	/* Install the definition before its body: direct recursion is visible. */
	symbol->definition = definition;
	definition->return_type = symbol->type->return_type;
	return sema_function_body(sema, definition);
}

bool sema_translation_unit(struct ast_translation_unit *unit, struct arena *arena,
	struct diagnostics *diagnostics)
{
	struct sema sema = { .arena = arena, .diagnostics = diagnostics };
	struct ast_external_declaration *external = unit->declarations;

	while (external) {
		struct ast_function *definition = NULL;
		struct ast_function_declaration *declaration;

		if (external->kind == external_function_definition) {
			definition = (struct ast_function *)external;
			declaration = definition->declaration;
		} else {
			declaration = (struct ast_function_declaration *)external;
		}
		if (!sema_function_declaration(&sema, declaration, definition))
			return false;
		external = external->next;
	}
	return true;
}
