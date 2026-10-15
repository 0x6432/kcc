#include "codegen.h"
#include "type.h"

#include <assert.h>
#include <stdarg.h>

struct loop_codegen {
	struct loop_codegen *parent;
	const struct ast_statement *statement;
	size_t break_label;
	size_t continue_label;
};

struct codegen {
	FILE *stream;
	struct loop_codegen *loop;
	size_t next_temporary;
	size_t next_label;
	size_t current_label;
	bool output_ok;
};

static void emit(struct codegen *codegen, const char *format, ...)
{
	va_list arguments;

	va_start(arguments, format);
	if (vfprintf(codegen->stream, format, arguments) < 0)
		codegen->output_ok = false;
	va_end(arguments);
}

static size_t new_label(struct codegen *codegen)
{
	return codegen->next_label++;
}

static void emit_label(struct codegen *codegen, size_t label)
{
	emit(codegen, "@b%zu\n", label);
	codegen->current_label = label;
}

static const char *binary_instruction(enum binary_operator operation)
{
	switch (operation) {
	case binary_add: return "add";
	case binary_subtract: return "sub";
	case binary_multiply: return "mul";
	case binary_divide: return "div";
	case binary_remainder: return "rem";
	case binary_equal: return "ceqw";
	case binary_not_equal: return "cnew";
	case binary_less: return "csltw";
	case binary_less_equal: return "cslew";
	case binary_greater: return "csgtw";
	case binary_greater_equal: return "csgew";
	}
	assert(0 && "unknown binary operator");
	return NULL;
}

/* Only names denote objects in this subset; sema supplies the declaration. */
static size_t codegen_local_slot(const struct ast_expression *expression)
{
	const struct ast_name_expression *name;

	assert(expression->kind == expression_name && expression->is_lvalue);
	name = (const struct ast_name_expression *)expression;
	assert(name->declaration && name->declaration->type == &type_int);
	return name->declaration->slot;
}

static size_t codegen_expression(struct codegen *codegen,
	const struct ast_expression *expression);

static size_t codegen_logical(struct codegen *codegen,
	const struct ast_logical_expression *node)
{
	size_t left = codegen_expression(codegen, node->left);
	size_t left_predecessor = codegen->current_label;
	size_t rhs_label = new_label(codegen);
	size_t merge_label = new_label(codegen);
	size_t right;
	size_t normalized;
	size_t right_predecessor;
	size_t result;
	unsigned skipped_value;

	if (node->operation == logical_and) {
		emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n",
			left, rhs_label, merge_label);
		skipped_value = 0;
	} else {
		emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n",
			left, merge_label, rhs_label);
		skipped_value = 1;
	}
	emit_label(codegen, rhs_label);
	right = codegen_expression(codegen, node->right);
	normalized = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =w cnew %%t%zu, 0\n", normalized, right);
	/* Nested RHS logic can end in a different block from rhs_label. */
	right_predecessor = codegen->current_label;
	emit(codegen, "\tjmp @b%zu\n", merge_label);
	emit_label(codegen, merge_label);
	result = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =w phi @b%zu %u, @b%zu %%t%zu\n",
		result, left_predecessor, skipped_value, right_predecessor, normalized);
	return result;
}

/* Return the temporary containing the value; operands are emitted first. */
static size_t codegen_expression(struct codegen *codegen,
	const struct ast_expression *expression)
{
	size_t temporary;

	assert(expression->type == &type_int);
	switch (expression->kind) {
	case expression_integer: {
		const struct ast_integer_expression *node =
			(const struct ast_integer_expression *)expression;

		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =w copy %ju\n", temporary,
			(uintmax_t)node->value);
		return temporary;
	}
	case expression_unary: {
		const struct ast_unary_expression *node =
			(const struct ast_unary_expression *)expression;
		size_t operand = codegen_expression(codegen, node->operand);

		temporary = codegen->next_temporary++;
		switch (node->operation) {
		case unary_plus:
			emit(codegen, "\t%%t%zu =w copy %%t%zu\n", temporary, operand);
			break;
		case unary_minus:
			emit(codegen, "\t%%t%zu =w sub 0, %%t%zu\n", temporary, operand);
			break;
		case unary_not:
			emit(codegen, "\t%%t%zu =w ceqw %%t%zu, 0\n", temporary, operand);
			break;
		}
		return temporary;
	}
	case expression_binary: {
		const struct ast_binary_expression *node =
			(const struct ast_binary_expression *)expression;
		size_t left = codegen_expression(codegen, node->left);
		size_t right = codegen_expression(codegen, node->right);

		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =w %s %%t%zu, %%t%zu\n", temporary,
			binary_instruction(node->operation), left, right);
		return temporary;
	}
	case expression_logical:
		return codegen_logical(codegen,
			(const struct ast_logical_expression *)expression);
	case expression_load: {
		const struct ast_load_expression *node =
			(const struct ast_load_expression *)expression;
		size_t slot = codegen_local_slot(node->operand);

		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =w loadw %%v%zu\n", temporary, slot);
		return temporary;
	}
	case expression_assignment: {
		const struct ast_assignment_expression *node =
			(const struct ast_assignment_expression *)expression;
		size_t value = codegen_expression(codegen, node->right);
		size_t slot = codegen_local_slot(node->left);

		emit(codegen, "\tstorew %%t%zu, %%v%zu\n", value, slot);
		return value;
	}
	case expression_name:
		assert(0 && "missing lvalue-to-rvalue conversion");
		return 0;
	}
	assert(0 && "unknown expression kind");
	return 0;
}

static bool codegen_block_items(struct codegen *codegen,
	const struct ast_block_item *item);

static bool codegen_statement(struct codegen *codegen,
	const struct ast_statement *statement);

static bool codegen_if(struct codegen *codegen, const struct ast_if_statement *node)
{
	size_t condition = codegen_expression(codegen, node->condition);
	size_t then_label = new_label(codegen);
	size_t merge_label = new_label(codegen);
	size_t else_label = node->else_branch ? new_label(codegen) : merge_label;
	bool then_terminated;
	bool else_terminated = false;

	emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n",
		condition, then_label, else_label);
	emit_label(codegen, then_label);
	then_terminated = codegen_statement(codegen, node->then_branch);
	if (!then_terminated)
		emit(codegen, "\tjmp @b%zu\n", merge_label);
	if (node->else_branch) {
		emit_label(codegen, else_label);
		else_terminated = codegen_statement(codegen, node->else_branch);
		if (!else_terminated)
			emit(codegen, "\tjmp @b%zu\n", merge_label);
	}
	if (then_terminated && else_terminated)
		return true;
	emit_label(codegen, merge_label);
	return false;
}

static bool codegen_loop_body(struct codegen *codegen,
	const struct ast_statement *statement, const struct ast_statement *body,
	size_t break_label, size_t continue_label)
{
	struct loop_codegen context = {
		.parent = codegen->loop,
		.statement = statement,
		.break_label = break_label,
		.continue_label = continue_label,
	};
	bool terminated;

	codegen->loop = &context;
	terminated = codegen_statement(codegen, body);
	codegen->loop = context.parent;
	return terminated;
}

static bool codegen_while(struct codegen *codegen,
	const struct ast_while_statement *node)
{
	size_t condition_label = new_label(codegen);
	size_t body_label = new_label(codegen);
	size_t exit_label = new_label(codegen);
	size_t condition;
	bool body_terminated;

	emit(codegen, "\tjmp @b%zu\n", condition_label);
	emit_label(codegen, condition_label);
	condition = codegen_expression(codegen, node->condition);
	emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n",
		condition, body_label, exit_label);
	emit_label(codegen, body_label);
	body_terminated = codegen_loop_body(codegen, &node->statement,
		node->body, exit_label, condition_label);
	if (!body_terminated)
		emit(codegen, "\tjmp @b%zu\n", condition_label);
	emit_label(codegen, exit_label);
	return false;
}

static bool codegen_do(struct codegen *codegen, const struct ast_do_statement *node)
{
	size_t body_label = new_label(codegen);
	size_t condition_label = new_label(codegen);
	size_t exit_label = new_label(codegen);
	size_t condition;
	bool body_terminated;

	emit(codegen, "\tjmp @b%zu\n", body_label);
	emit_label(codegen, body_label);
	body_terminated = codegen_loop_body(codegen, &node->statement,
		node->body, exit_label, condition_label);
	if (!body_terminated)
		emit(codegen, "\tjmp @b%zu\n", condition_label);
	/* Continue may reach this block even when every body path terminates. */
	emit_label(codegen, condition_label);
	condition = codegen_expression(codegen, node->condition);
	emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n",
		condition, body_label, exit_label);
	emit_label(codegen, exit_label);
	return false;
}

static void codegen_local_initializer(struct codegen *codegen,
	const struct ast_local_declaration *local)
{
	if (local->initializer) {
		size_t value = codegen_expression(codegen, local->initializer);

		emit(codegen, "\tstorew %%t%zu, %%v%zu\n", value, local->slot);
	}
}

static bool codegen_for(struct codegen *codegen, const struct ast_for_statement *node)
{
	size_t condition_label = new_label(codegen);
	size_t body_label = new_label(codegen);
	size_t step_label = new_label(codegen);
	size_t exit_label = new_label(codegen);
	bool body_terminated;

	if (node->initializer_declaration)
		codegen_local_initializer(codegen, node->initializer_declaration);
	if (node->initializer_expression)
		codegen_expression(codegen, node->initializer_expression);
	emit(codegen, "\tjmp @b%zu\n", condition_label);
	emit_label(codegen, condition_label);
	if (node->condition) {
		size_t condition = codegen_expression(codegen, node->condition);

		emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n",
			condition, body_label, exit_label);
	} else {
		/* Omitted condition is true; no synthetic literal AST is needed. */
		emit(codegen, "\tjmp @b%zu\n", body_label);
	}
	emit_label(codegen, body_label);
	body_terminated = codegen_loop_body(codegen, &node->statement,
		node->body, exit_label, step_label);
	if (!body_terminated)
		emit(codegen, "\tjmp @b%zu\n", step_label);
	emit_label(codegen, step_label);
	if (node->step)
		codegen_expression(codegen, node->step);
	emit(codegen, "\tjmp @b%zu\n", condition_label);
	emit_label(codegen, exit_label);
	return false;
}

/* True means the current block has terminated, not an I/O success flag. */
static bool codegen_statement(struct codegen *codegen,
	const struct ast_statement *statement)
{
	switch (statement->kind) {
	case statement_return: {
		const struct ast_return_statement *node =
			(const struct ast_return_statement *)statement;
		size_t value = codegen_expression(codegen, node->value);

		emit(codegen, "\tret %%t%zu\n", value);
		return true;
	}
	case statement_expression: {
		const struct ast_expression_statement *node =
			(const struct ast_expression_statement *)statement;

		codegen_expression(codegen, node->value);
		return false;
	}
	case statement_empty:
		return false;
	case statement_for:
		return codegen_for(codegen, (const struct ast_for_statement *)statement);
	case statement_do:
		return codegen_do(codegen, (const struct ast_do_statement *)statement);
	case statement_while:
		return codegen_while(codegen, (const struct ast_while_statement *)statement);
	case statement_break: {
		const struct ast_break_statement *node =
			(const struct ast_break_statement *)statement;

		assert(codegen->loop && node->target == codegen->loop->statement);
		emit(codegen, "\tjmp @b%zu\n", codegen->loop->break_label);
		return true;
	}
	case statement_continue: {
		const struct ast_continue_statement *node =
			(const struct ast_continue_statement *)statement;

		assert(codegen->loop && node->target == codegen->loop->statement);
		emit(codegen, "\tjmp @b%zu\n", codegen->loop->continue_label);
		return true;
	}
	case statement_if:
		return codegen_if(codegen, (const struct ast_if_statement *)statement);
	case statement_compound: {
		const struct ast_compound_statement *node =
			(const struct ast_compound_statement *)statement;

		return codegen_block_items(codegen, node->items);
	}
	}
	assert(0 && "unknown statement kind");
	return false;
}

static bool codegen_block_items(struct codegen *codegen,
	const struct ast_block_item *item)
{
	while (item) {
		switch (item->kind) {
		case block_item_declaration: {
			const struct ast_local_declaration *local =
				(const struct ast_local_declaration *)item;

			codegen_local_initializer(codegen, local);
			break;
		}
		case block_item_statement: {
			const struct ast_statement_item *node =
				(const struct ast_statement_item *)item;

			if (codegen_statement(codegen, node->statement))
				return true;
			break;
		}
		}
		item = item->next;
	}
	return false;
}

bool codegen_translation_unit(FILE *stream, const struct ast_translation_unit *unit)
{
	struct codegen codegen = {
		.stream = stream,
		.next_label = 1,
		.output_ok = true,
	};
	const struct ast_function *function = unit->function;
	const struct ast_local_declaration *local = function->locals;
	struct token name = function->name;

	assert(function->return_type == &type_int);
	emit(&codegen, "export function w $%.*s() {\n",
		(int)name.length,
		(const char *)name.location.source->data + name.location.offset);
	emit_label(&codegen, 0);
	while (local) {
		/* Slots are allocated at entry; initialization is in source order. */
		assert(local->type == &type_int);
		emit(&codegen, "\t%%v%zu =l alloc4 4\n", local->slot);
		local = local->next_local;
	}
	if (!codegen_block_items(&codegen, function->body->items))
		emit(&codegen, "\tret 0\n");
	emit(&codegen, "}\n");
	if (fflush(stream) != 0)
		codegen.output_ok = false;
	return codegen.output_ok;
}
