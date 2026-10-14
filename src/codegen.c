#include "codegen.h"
#include "type.h"

#include <assert.h>

bool codegen_translation_unit(FILE *stream, const struct ast_translation_unit *unit)
{
	const struct ast_function *function = unit->function;
	const struct ast_return_statement *statement;
	const struct ast_integer_expression *integer;
	struct token name = function->name;
	int written;

	assert(function->return_type == &type_int);
	assert(function->body->body->kind == statement_return);
	statement = (const struct ast_return_statement *)function->body->body;
	assert(statement->value->kind == expression_integer);
	assert(statement->value->type == &type_int);
	integer = (const struct ast_integer_expression *)statement->value;

	written = fprintf(stream,
		"export function w $%.*s() {\n@start\n\tret %ju\n}\n",
		(int)name.length, name.location.source->data + name.location.offset,
		(uintmax_t)integer->value);
	return written >= 0 && fflush(stream) == 0;
}
