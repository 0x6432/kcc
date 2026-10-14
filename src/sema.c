#include "sema.h"
#include "type.h"

#include <assert.h>
#include <string.h>

static bool sema_expression(struct ast_expression *expression,
	struct diagnostics *diagnostics)
{
	switch (expression->kind) {
	case expression_integer: {
		struct ast_integer_expression *integer =
			(struct ast_integer_expression *)expression;

		/* Target int is 32 bits, independent of the compiler host. */
		if (integer->value > INT32_MAX) {
			diagnostic_error(diagnostics, expression->location,
				"literal does not fit the supported int type");
			return false;
		}
		expression->type = &type_int;
		return true;
	}
	case expression_unary: {
		struct ast_unary_expression *node =
			(struct ast_unary_expression *)expression;

		if (!sema_expression(node->operand, diagnostics))
			return false;
		expression->type = &type_int;
		return true;
	}
	case expression_binary: {
		struct ast_binary_expression *node =
			(struct ast_binary_expression *)expression;

		if (!sema_expression(node->left, diagnostics))
			return false;
		if (!sema_expression(node->right, diagnostics))
			return false;
		expression->type = &type_int;
		return true;
	}
	}
	assert(0 && "unknown expression kind");
	return false;
}

static bool sema_statement(struct ast_statement *statement,
	struct diagnostics *diagnostics)
{
	switch (statement->kind) {
	case statement_return: {
		struct ast_return_statement *node =
			(struct ast_return_statement *)statement;

		return sema_expression(node->value, diagnostics);
	}
	case statement_compound: {
		struct ast_compound_statement *node =
			(struct ast_compound_statement *)statement;

		return sema_statement(node->body, diagnostics);
	}
	}
	assert(0 && "unknown statement kind");
	return false;
}

bool sema_translation_unit(struct ast_translation_unit *unit,
	struct diagnostics *diagnostics)
{
	struct ast_function *function = unit->function;
	struct token name = function->name;

	if (name.length != 4 ||
		memcmp(name.location.source->data + name.location.offset, "main", 4) != 0) {
		diagnostic_error(diagnostics, name.location,
			"only a function named main is supported");
		return false;
	}
	function->return_type = &type_int;
	return sema_statement(&function->body->statement, diagnostics);
}
