#include "codegen.h"
#include "sema.h"
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

static char qbe_type(const struct type *type)
{
	return type_value_width(type) == 64 ? 'l' : 'w';
}

static const char *qbe_abi_type(const struct type *type)
{
	if (type_value_width(type) == 8)
		return type_is_unsigned(type) ? "ub" : "sb";
	if (type_value_width(type) == 16)
		return type_is_unsigned(type) ? "uh" : "sh";
	return type_value_width(type) == 64 ? "l" : "w";
}

static const char *qbe_load_instruction(const struct type *type)
{
	if (type_value_width(type) == 8)
		return type_is_unsigned(type) ? "loadub" : "loadsb";
	if (type_value_width(type) == 16)
		return type_is_unsigned(type) ? "loaduh" : "loadsh";
	return type_value_width(type) == 64 ? "loadl" : "loadw";
}

static char qbe_store_size(const struct type *type)
{
	if (type_value_width(type) == 8)
		return 'b';
	if (type_value_width(type) == 16)
		return 'h';
	return qbe_type(type);
}

/* Sub-word ABI results have unspecified upper bits; normalize before use. */
static size_t codegen_canonicalize(struct codegen *codegen, size_t value,
	const struct type *type)
{
	size_t result;
	const char *instruction;

	if (type_value_width(type) == 8)
		instruction = type_is_unsigned(type) ? "extub" : "extsb";
	else if (type_value_width(type) == 16)
		instruction = type_is_unsigned(type) ? "extuh" : "extsh";
	else
		return value;
	result = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =w %s %%t%zu\n", result, instruction, value);
	return result;
}

static const char *binary_instruction(enum binary_operator operation, const struct type *operand_type)
{
	bool unsigned_operands = type_is_unsigned(operand_type);
	bool wide = type_value_width(operand_type) == 64;

	switch (operation) {
	case binary_add: return "add";
	case binary_subtract: return "sub";
	case binary_multiply: return "mul";
	case binary_divide: return unsigned_operands ? "udiv" : "div";
	case binary_remainder: return unsigned_operands ? "urem" : "rem";
	case binary_bit_and: return "and";
	case binary_bit_xor: return "xor";
	case binary_bit_or: return "or";
	case binary_shift_left: return "shl";
	case binary_shift_right: return unsigned_operands ? "shr" : "sar";
	case binary_equal: return wide ? "ceql" : "ceqw";
	case binary_not_equal: return wide ? "cnel" : "cnew";
	case binary_less:
		if (unsigned_operands)
			return wide ? "cultl" : "cultw";
		return wide ? "csltl" : "csltw";
	case binary_less_equal:
		if (unsigned_operands)
			return wide ? "culel" : "culew";
		return wide ? "cslel" : "cslew";
	case binary_greater:
		if (unsigned_operands)
			return wide ? "cugtl" : "cugtw";
		return wide ? "csgtl" : "csgtw";
	case binary_greater_equal:
		if (unsigned_operands)
			return wide ? "cugel" : "cugew";
		return wide ? "csgel" : "csgew";
	}
	assert(0 && "unknown binary operator");
	return NULL;
}

static size_t codegen_expression(struct codegen *codegen,
	const struct ast_expression *expression);

/* Object lvalues produce addresses; value-context loads are separate nodes. */
static size_t codegen_address(struct codegen *codegen, const struct ast_expression *expression)
{
	assert(expression->is_lvalue);
	switch (expression->kind) {
	case expression_name: {
		const struct ast_name_expression *name = (const struct ast_name_expression *)expression;
		size_t result = codegen->next_temporary++;

		assert(name->declaration && type_is_scalar(name->declaration->type));
		emit(codegen, "\t%%t%zu =l copy %%v%zu\n", result, name->declaration->slot);
		return result;
	}
	case expression_indirection: {
		const struct ast_indirection_expression *node =
			(const struct ast_indirection_expression *)expression;

		return codegen_expression(codegen, node->operand);
	}
	default:
		assert(0 && "unsupported lvalue address");
		return 0;
	}
}

/* Value conversion tests the whole source, unlike narrow ABI normalization. */
static size_t codegen_truth_value(struct codegen *codegen, size_t value,
	const struct type *type)
{
	size_t result = codegen->next_temporary++;

	emit(codegen, "\t%%t%zu =w cne%c %%t%zu, 0\n", result, qbe_type(type), value);
	return result;
}

/* Branches always consume a word boolean, never a truncated long value. */
static size_t codegen_truth(struct codegen *codegen, const struct ast_expression *expression)
{
	size_t value = codegen_expression(codegen, expression);

	return codegen_truth_value(codegen, value, expression->type);
}

static size_t codegen_conversion(struct codegen *codegen, const struct ast_expression *operand,
	const struct type *target)
{
	size_t value = codegen_expression(codegen, operand);
	size_t result;
	const char *instruction = "copy";

	if (target->kind == type_kind_bool)
		return codegen_truth_value(codegen, value, operand->type);
	if (type_value_width(target) < 32)
		return codegen_canonicalize(codegen, value, target);
	result = codegen->next_temporary++;
	if (type_value_width(target) == 64 && type_value_width(operand->type) <= 32)
		instruction = type_is_unsigned(operand->type) ? "extuw" : "extsw";
	emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", result, qbe_type(target), instruction, value);
	return result;
}

static size_t codegen_logical(struct codegen *codegen,
	const struct ast_logical_expression *node)
{
	size_t left = codegen_truth(codegen, node->left);
	size_t left_predecessor = codegen->current_label;
	size_t rhs_label = new_label(codegen);
	size_t merge_label = new_label(codegen);
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
	normalized = codegen_truth(codegen, node->right);
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

	assert(type_is_scalar(expression->type));
	switch (expression->kind) {
	case expression_call: {
		const struct ast_call_expression *node =
			(const struct ast_call_expression *)expression;
		struct token name = node->function->name;
		size_t arguments[ast_max_arguments];
		size_t count = 0;
		size_t result;

		/* Finish each argument's IL, including branches, before the call line. */
		for (const struct ast_argument *argument = node->arguments; argument;
			argument = argument->next)
			arguments[count++] = codegen_expression(codegen, argument->value);
		assert(count == node->argument_count && count <= ast_max_arguments);
		result = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%s call $%.*s(", result, qbe_abi_type(expression->type),
			(int)name.length,
			(const char *)name.spelling_location.source->data + name.spelling_location.offset);
		count = 0;
		for (const struct ast_argument *argument = node->arguments; argument; argument = argument->next) {
			emit(codegen, "%s%s %%t%zu", count ? ", " : "", qbe_abi_type(argument->value->type), arguments[count]);
			count++;
		}
		emit(codegen, ")\n");
		return codegen_canonicalize(codegen, result, expression->type);
	}
	case expression_address: {
		const struct ast_address_expression *node = (const struct ast_address_expression *)expression;

		return codegen_address(codegen, node->operand);
	}
	case expression_character: {
		const struct ast_character_expression *node =
			(const struct ast_character_expression *)expression;

		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =w copy %jd\n", temporary, (intmax_t)node->value);
		return temporary;
	}
	case expression_integer: {
		const struct ast_integer_expression *node =
			(const struct ast_integer_expression *)expression;

		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c copy %ju\n", temporary, qbe_type(expression->type),
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
			emit(codegen, "\t%%t%zu =%c copy %%t%zu\n", temporary, qbe_type(expression->type), operand);
			break;
		case unary_minus:
			emit(codegen, "\t%%t%zu =%c sub 0, %%t%zu\n", temporary, qbe_type(expression->type), operand);
			break;
		case unary_complement:
			emit(codegen, "\t%%t%zu =%c xor %%t%zu, -1\n", temporary, qbe_type(expression->type), operand);
			break;
		case unary_not:
			emit(codegen, "\t%%t%zu =w ceq%c %%t%zu, 0\n", temporary, qbe_type(node->operand->type), operand);
			break;
		}
		return temporary;
	}
	case expression_binary: {
		const struct ast_binary_expression *node =
			(const struct ast_binary_expression *)expression;
		size_t left = codegen_expression(codegen, node->left);
		size_t right = codegen_expression(codegen, node->right);

		if ((node->operation == binary_shift_left || node->operation == binary_shift_right) &&
			type_value_width(node->right->type) == 64) {
			size_t count = codegen->next_temporary++;

			/* QBE shift counts are words; valid C counts 0..63 are preserved. */
			emit(codegen, "\t%%t%zu =w copy %%t%zu\n", count, right);
			right = count;
		}
		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c %s %%t%zu, %%t%zu\n", temporary, qbe_type(expression->type),
			binary_instruction(node->operation, node->left->type), left, right);
		return temporary;
	}
	case expression_cast: {
		const struct ast_cast_expression *node = (const struct ast_cast_expression *)expression;

		return codegen_conversion(codegen, node->operand, expression->type);
	}
	case expression_conversion: {
		const struct ast_conversion_expression *node =
			(const struct ast_conversion_expression *)expression;

		return codegen_conversion(codegen, node->operand, expression->type);
	}
	case expression_logical:
		return codegen_logical(codegen,
			(const struct ast_logical_expression *)expression);
	case expression_load: {
		const struct ast_load_expression *node =
			(const struct ast_load_expression *)expression;
		size_t address = codegen_address(codegen, node->operand);

		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", temporary,
			qbe_type(expression->type), qbe_load_instruction(expression->type), address);
		return temporary;
	}
	case expression_assignment: {
		const struct ast_assignment_expression *node =
			(const struct ast_assignment_expression *)expression;
		size_t value = codegen_expression(codegen, node->right);
		size_t address = codegen_address(codegen, node->left);

		emit(codegen, "\tstore%c %%t%zu, %%t%zu\n", qbe_store_size(node->left->type), value, address);
		return value;
	}
	case expression_name:
	case expression_indirection:
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
	size_t condition = codegen_truth(codegen, node->condition);
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
	condition = codegen_truth(codegen, node->condition);
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
	condition = codegen_truth(codegen, node->condition);
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

		emit(codegen, "\tstore%c %%t%zu, %%v%zu\n", qbe_store_size(local->type), value, local->slot);
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
		size_t condition = codegen_truth(codegen, node->condition);

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

static bool codegen_function(FILE *stream, const struct ast_function *function)
{
	struct codegen codegen = {
		.stream = stream,
		.next_label = 1,
		.output_ok = true,
	};
	const struct ast_local_declaration *local = function->locals;
	struct token name = function->declaration->name;
	size_t parameter_index = 0;

	assert(type_is_scalar(function->return_type));

	emit(&codegen, "export function %s $%.*s(", qbe_abi_type(function->return_type),
		(int)name.length,
		(const char *)name.spelling_location.source->data + name.spelling_location.offset);
	for (const struct ast_parameter *parameter = function->declaration->parameters; parameter;
		parameter = parameter->next) {
		emit(&codegen, "%s%s %%p%zu", parameter_index ? ", " : "",
			qbe_abi_type(parameter->local->type), parameter_index);
		parameter_index++;
	}
	emit(&codegen, ") {\n");
	emit_label(&codegen, 0);
	while (local) {
		/* Slots are allocated at entry; initialization is in source order. */
		unsigned bytes = type_value_width(local->type) / 8;
		unsigned alignment = bytes < 4 ? 4 : bytes;

		assert(type_is_scalar(local->type));
		emit(&codegen, "\t%%v%zu =l alloc%u %u\n", local->slot, alignment, bytes);
		local = local->next_local;
	}
	parameter_index = 0;
	for (const struct ast_parameter *parameter = function->declaration->parameters; parameter;
		parameter = parameter->next) {
		emit(&codegen, "\tstore%c %%p%zu, %%v%zu\n",
			qbe_store_size(parameter->local->type), parameter_index, parameter->local->slot);
		parameter_index++;
	}
	if (!codegen_block_items(&codegen, function->body->items))
		emit(&codegen, "\tret 0\n");
	emit(&codegen, "}\n");
	if (fflush(stream) != 0)
		codegen.output_ok = false;
	return codegen.output_ok;
}

bool codegen_translation_unit(FILE *stream, const struct ast_translation_unit *unit)
{
	const struct ast_external_declaration *external = unit->declarations;

	while (external) {
		if (external->kind == external_function_definition &&
			!codegen_function(stream, (const struct ast_function *)external))
			return false;
		external = external->next;
	}
	return fflush(stream) == 0;
}
