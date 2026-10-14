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
	}
	assert(0 && "unknown expression kind");
	return 0;
}

bool codegen_translation_unit(FILE *stream, const struct ast_translation_unit *unit)
{
	struct codegen codegen = { .stream = stream, .output_ok = true };
	const struct ast_function *function = unit->function;
	const struct ast_return_statement *statement;
	struct token name = function->name;
	size_t value;

	assert(function->return_type == &type_int);
	assert(function->body->body->kind == statement_return);
	statement = (const struct ast_return_statement *)function->body->body;
	emit(&codegen, "export function w $%.*s() {\n@start\n",
		(int)name.length, (const char *)name.location.source->data + name.location.offset);
	value = codegen_expression(&codegen, statement->value);
	emit(&codegen, "\tret %%t%zu\n}\n", value);
	if (fflush(stream) != 0)
		codegen.output_ok = false;
	return codegen.output_ok;
}
