#include "codegen.h"
#include "type.h"

#include <assert.h>
#include <stdarg.h>

struct codegen {
	FILE *stream;
	size_t next_temporary;
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

static const char *binary_instruction(enum binary_operator operation)
{
	switch (operation) {
	case binary_add: return "add";
	case binary_subtract: return "sub";
	case binary_multiply: return "mul";
	case binary_divide: return "div";
	case binary_remainder: return "rem";
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
		if (node->operation == unary_plus)
			emit(codegen, "\t%%t%zu =w copy %%t%zu\n", temporary, operand);
		else
			emit(codegen, "\t%%t%zu =w sub 0, %%t%zu\n", temporary, operand);
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

			if (local->initializer) {
				size_t value = codegen_expression(codegen, local->initializer);

				emit(codegen, "\tstorew %%t%zu, %%v%zu\n", value, local->slot);
			}
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
	struct codegen codegen = { .stream = stream, .output_ok = true };
	const struct ast_function *function = unit->function;
	const struct ast_local_declaration *local = function->locals;
	struct token name = function->name;

	assert(function->return_type == &type_int);
	emit(&codegen, "export function w $%.*s() {\n@start\n",
		(int)name.length,
		(const char *)name.location.source->data + name.location.offset);
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
