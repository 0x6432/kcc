#include "codegen.h"
#include "sema.h"
#include "type.h"

#include <assert.h>
#include <stdarg.h>

struct control_codegen {
	struct control_codegen *parent;
	const struct ast_statement *statement;
	size_t break_label;
	size_t continue_label;
};

struct codegen {
	FILE *stream;
	struct control_codegen *control;
	size_t next_temporary;
	size_t next_label;
	size_t current_label;
	size_t named_label_count;
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
	bool unsigned_operands;
	bool wide = type_value_width(operand_type) == 64;

	if (operand_type->kind == type_kind_pointer) {
		switch (operation) {
		case binary_equal: return "ceql";
		case binary_not_equal: return "cnel";
		case binary_less: return "cultl";
		case binary_less_equal: return "culel";
		case binary_greater: return "cugtl";
		case binary_greater_equal: return "cugel";
		default:
			assert(0 && "noncomparison pointer operator was not lowered");
			return NULL;
		}
	}
	unsigned_operands = type_is_unsigned(operand_type);
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

/* Extend the promoted integer index for address arithmetic, without inventing
 * a semantic cast to long (unsigned word indices must zero-extend).
 */
static size_t codegen_pointer_index(struct codegen *codegen,
	const struct ast_expression *index)
{
	size_t value = codegen_expression(codegen, index);
	size_t result;

	if (type_integer_width(index->type) == 64)
		return value;
	assert(type_integer_width(index->type) == 32);
	result = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =l %s %%t%zu\n", result,
		type_is_unsigned(index->type) ? "extuw" : "extsw", value);
	return result;
}

/* Object lvalues produce addresses; value-context loads are separate nodes. */
static size_t codegen_address(struct codegen *codegen, const struct ast_expression *expression)
{
	assert(expression->is_lvalue || expression->type->kind == type_kind_function ||
		expression->kind == expression_indirection);
	switch (expression->kind) {
	case expression_function_designator: {
		const struct ast_function_designator_expression *function =
			(const struct ast_function_designator_expression *)expression;
		struct token name = function->function->name;
		size_t result = codegen->next_temporary++;

		emit(codegen, "\t%%t%zu =l copy $%.*s\n", result, (int)name.length,
			(const char *)name.spelling_location.source->data + name.spelling_location.offset);
		return result;
	}
	case expression_string: {
		const struct ast_string_expression *string = (const struct ast_string_expression *)expression;
		size_t result = codegen->next_temporary++;

		emit(codegen, "\t%%t%zu =l copy $.Lkcc.string.%zu\n", result, string->object_id);
		return result;
	}
	case expression_name: {
		const struct ast_name_expression *name = (const struct ast_name_expression *)expression;
		size_t result = codegen->next_temporary++;

		assert(name->declaration && type_is_complete_object(name->declaration->type));
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

/* Use the same conversions for AST operands and once-loaded compound lvalues. */
static size_t codegen_convert_value(struct codegen *codegen, size_t value,
	const struct type *source, const struct type *target)
{
	size_t result;
	const char *instruction = "copy";

	if (target->kind == type_kind_bool)
		return codegen_truth_value(codegen, value, source);
	if (type_value_width(target) < 32)
		return codegen_canonicalize(codegen, value, target);
	result = codegen->next_temporary++;
	if (type_value_width(target) == 64 && type_value_width(source) <= 32)
		instruction = type_is_unsigned(source) ? "extuw" : "extsw";
	emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", result, qbe_type(target), instruction, value);
	return result;
}

static size_t codegen_conversion(struct codegen *codegen, const struct ast_expression *operand,
	const struct type *target)
{
	size_t value = codegen_expression(codegen, operand);

	return codegen_convert_value(codegen, value, operand->type, target);
}

/* QBE consumes a word count; valid C shift counts 0..63 are preserved. */
static size_t codegen_shift_count(struct codegen *codegen, size_t value,
	const struct type *type)
{
	size_t count;

	if (type_value_width(type) != 64)
		return value;
	count = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =w copy %%t%zu\n", count, value);
	return count;
}

/* RHS-first is a permitted operand order; the lvalue address is never repeated. */
static size_t codegen_compound_assignment(struct codegen *codegen,
	const struct ast_compound_assignment_expression *node)
{
	size_t right;
	size_t address;
	size_t left;
	size_t value;
	const char *instruction;

	if (node->element_size) {
		right = codegen_pointer_index(codegen, node->right);
		if (node->element_size != 1) {
			size_t scaled = codegen->next_temporary++;

			emit(codegen, "\t%%t%zu =l mul %%t%zu, %ju\n", scaled, right, (uintmax_t)node->element_size);
			right = scaled;
		}
	} else {
		right = codegen_expression(codegen, node->right);
		if (node->operation == binary_shift_left || node->operation == binary_shift_right)
			right = codegen_shift_count(codegen, right, node->right->type);
	}
	address = codegen_address(codegen, node->left);
	left = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", left, qbe_type(node->left->type),
		qbe_load_instruction(node->left->type), address);
	left = codegen_convert_value(codegen, left, node->left->type, node->calculation_type);
	value = codegen->next_temporary++;
	if (node->element_size)
		instruction = node->operation == binary_add ? "add" : "sub";
	else
		instruction = binary_instruction(node->operation, node->calculation_type);
	emit(codegen, "\t%%t%zu =%c %s %%t%zu, %%t%zu\n", value, qbe_type(node->calculation_type),
		instruction, left, right);
	value = codegen_convert_value(codegen, value, node->calculation_type, node->expression.type);
	emit(codegen, "\tstore%c %%t%zu, %%t%zu\n", qbe_store_size(node->left->type), value, address);
	return value;
}

struct update_values {
	size_t previous;
	size_t current;
};

/* Address, load and store each occur once; the caller selects old or new. */
static struct update_values codegen_update(struct codegen *codegen,
	const struct ast_expression *operand, enum update_operator operation,
	const struct type *calculation_type, uint64_t element_size)
{
	size_t address = codegen_address(codegen, operand);
	size_t previous = codegen->next_temporary++;
	size_t value = codegen->next_temporary++;
	uint64_t step = element_size ? element_size : 1;

	emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", previous, qbe_type(calculation_type),
		qbe_load_instruction(operand->type), address);
	emit(codegen, "\t%%t%zu =%c %s %%t%zu, %llu\n", value, qbe_type(calculation_type),
		operation == update_increment ? "add" : "sub", previous, (unsigned long long)step);
	/* _Bool conversion tests the promoted value, never its low bit. */
	if (operand->type->kind == type_kind_bool)
		value = codegen_truth_value(codegen, value, calculation_type);
	else
		value = codegen_canonicalize(codegen, value, operand->type);
	emit(codegen, "\tstore%c %%t%zu, %%t%zu\n", qbe_store_size(operand->type), value, address);
	return (struct update_values) { .previous = previous, .current = value };
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

static size_t codegen_conditional(struct codegen *codegen,
	const struct ast_conditional_expression *node)
{
	size_t condition = codegen_truth(codegen, node->condition);
	size_t then_label = new_label(codegen);
	size_t else_label = new_label(codegen);
	size_t merge_label = new_label(codegen);
	size_t then_value;
	size_t else_value;
	size_t then_predecessor;
	size_t else_predecessor;
	size_t result;

	emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", condition, then_label, else_label);
	emit_label(codegen, then_label);
	then_value = codegen_expression(codegen, node->then_value);
	then_predecessor = codegen->current_label;
	emit(codegen, "\tjmp @b%zu\n", merge_label);
	emit_label(codegen, else_label);
	else_value = codegen_expression(codegen, node->else_value);
	else_predecessor = codegen->current_label;
	emit(codegen, "\tjmp @b%zu\n", merge_label);
	emit_label(codegen, merge_label);
	result = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =%c phi @b%zu %%t%zu, @b%zu %%t%zu\n", result,
		qbe_type(node->expression.type), then_predecessor, then_value, else_predecessor, else_value);
	return result;
}

/* A NULL output emits a void call; no result temporary is manufactured. */
static void emit_call(struct codegen *codegen, const struct ast_call_expression *node,
	size_t *value)
{
	size_t arguments[ast_max_arguments];
	size_t target = 0;
	size_t count = 0;

	/* A direct target is a pure named designator. Computed targets evaluate
	 * once before the arguments, one of C's permitted evaluation orders.
	 */
	if (!node->function)
		target = codegen_expression(codegen, node->callee);
	/* Finish each argument's IL, including branches, before the call line. */
	for (const struct ast_argument *argument = node->arguments; argument;
		argument = argument->next)
		arguments[count++] = codegen_expression(codegen, argument->value);
	assert(count == node->argument_count && count <= ast_max_arguments);
	assert((node->expression.type->kind == type_kind_void) == (value == NULL));
	if (value) {
		*value = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%s call ", *value, qbe_abi_type(node->expression.type));
	} else {
		emit(codegen, "\tcall ");
	}
	if (node->function) {
		struct token name = node->function->name;

		emit(codegen, "$%.*s(", (int)name.length,
			(const char *)name.spelling_location.source->data + name.spelling_location.offset);
	} else {
		emit(codegen, "%%t%zu(", target);
	}
	count = 0;
	for (const struct ast_argument *argument = node->arguments; argument; argument = argument->next) {
		emit(codegen, "%s%s %%t%zu", count ? ", " : "", qbe_abi_type(argument->value->type), arguments[count]);
		count++;
	}
	emit(codegen, ")\n");
	if (value)
		*value = codegen_canonicalize(codegen, *value, node->expression.type);
}

static void codegen_discard_expression(struct codegen *codegen,
	const struct ast_expression *expression);

/* Target size_t values are unsigned long, independent of the compiler host. */
static size_t codegen_layout_constant(struct codegen *codegen, uint64_t value)
{
	size_t result = codegen->next_temporary++;

	emit(codegen, "\t%%t%zu =l copy %ju\n", result, (uintmax_t)value);
	return result;
}

/* Return the temporary containing the value; operands are emitted first. */
static size_t codegen_expression(struct codegen *codegen,
	const struct ast_expression *expression)
{
	size_t temporary;

	assert(type_is_scalar(expression->type));
	switch (expression->kind) {
	case expression_sizeof:
		return codegen_layout_constant(codegen, ((const struct ast_sizeof_expression *)expression)->size);
	case expression_sizeof_type:
		return codegen_layout_constant(codegen, ((const struct ast_sizeof_type_expression *)expression)->size);
	case expression_alignof:
		return codegen_layout_constant(codegen, ((const struct ast_alignof_expression *)expression)->alignment);
	case expression_comma: {
		const struct ast_comma_expression *node = (const struct ast_comma_expression *)expression;

		codegen_discard_expression(codegen, node->left);
		return codegen_expression(codegen, node->right);
	}
	case expression_call: {
		size_t value;

		emit_call(codegen, (const struct ast_call_expression *)expression, &value);
		return value;
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
	case expression_nullptr:
		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =l copy 0\n", temporary);
		return temporary;
	case expression_boolean: {
		const struct ast_boolean_expression *node = (const struct ast_boolean_expression *)expression;

		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =w copy %u\n", temporary, node->value ? 1u : 0u);
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

		if (node->operation == binary_shift_left || node->operation == binary_shift_right)
			right = codegen_shift_count(codegen, right, node->right->type);
		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c %s %%t%zu, %%t%zu\n", temporary, qbe_type(expression->type),
			binary_instruction(node->operation, node->left->type), left, right);
		return temporary;
	}
	case expression_pointer_offset: {
		const struct ast_pointer_offset_expression *node =
			(const struct ast_pointer_offset_expression *)expression;
		size_t base = codegen_expression(codegen, node->base);
		size_t index = codegen_pointer_index(codegen, node->index);
		size_t scaled = codegen->next_temporary++;

		emit(codegen, "\t%%t%zu =l mul %%t%zu, %ju\n", scaled, index,
			(uintmax_t)node->element_size);
		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =l %s %%t%zu, %%t%zu\n", temporary,
			node->subtract ? "sub" : "add", base, scaled);
		return temporary;
	}
	case expression_pointer_difference: {
		const struct ast_pointer_difference_expression *node =
			(const struct ast_pointer_difference_expression *)expression;
		size_t left = codegen_expression(codegen, node->left);
		size_t right = codegen_expression(codegen, node->right);
		size_t bytes = codegen->next_temporary++;

		emit(codegen, "\t%%t%zu =l sub %%t%zu, %%t%zu\n", bytes, left, right);
		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =l div %%t%zu, %ju\n", temporary, bytes,
			(uintmax_t)node->element_size);
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
	case expression_conditional:
		return codegen_conditional(codegen, (const struct ast_conditional_expression *)expression);
	case expression_logical:
		return codegen_logical(codegen,
			(const struct ast_logical_expression *)expression);
	case expression_function_decay: {
		const struct ast_function_decay_expression *node =
			(const struct ast_function_decay_expression *)expression;

		return codegen_address(codegen, node->operand);
	}
	case expression_array_decay: {
		const struct ast_array_decay_expression *node =
			(const struct ast_array_decay_expression *)expression;

		return codegen_address(codegen, node->operand);
	}
	case expression_load: {
		const struct ast_load_expression *node =
			(const struct ast_load_expression *)expression;
		size_t address = codegen_address(codegen, node->operand);

		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", temporary,
			qbe_type(expression->type), qbe_load_instruction(expression->type), address);
		return temporary;
	}
	case expression_postfix_update: {
		const struct ast_postfix_update_expression *node = (const struct ast_postfix_update_expression *)expression;
		struct update_values values = codegen_update(codegen, node->operand, node->operation,
			node->calculation_type, node->element_size);

		return values.previous;
	}
	case expression_prefix_update: {
		const struct ast_prefix_update_expression *node = (const struct ast_prefix_update_expression *)expression;
		struct update_values values = codegen_update(codegen, node->operand, node->operation,
			node->calculation_type, node->element_size);

		return values.current;
	}
	case expression_compound_assignment:
		return codegen_compound_assignment(codegen,
			(const struct ast_compound_assignment_expression *)expression);
	case expression_assignment: {
		const struct ast_assignment_expression *node =
			(const struct ast_assignment_expression *)expression;
		size_t value = codegen_expression(codegen, node->right);
		size_t address = codegen_address(codegen, node->left);

		emit(codegen, "\tstore%c %%t%zu, %%t%zu\n", qbe_store_size(node->left->type), value, address);
		return value;
	}
	case expression_function_designator:
	case expression_string:
	case expression_subscript:
	case expression_name:
	case expression_indirection:
		assert(0 && "missing lvalue-to-rvalue conversion");
		return 0;
	}
	assert(0 && "unknown expression kind");
	return 0;
}

/* Discarded void expressions have effects, not a scalar result or void load. */
static void codegen_discard_expression(struct codegen *codegen,
	const struct ast_expression *expression)
{
	if (expression->type->kind != type_kind_void) {
		codegen_expression(codegen, expression);
		return;
	}
	switch (expression->kind) {
	case expression_conditional: {
		const struct ast_conditional_expression *node = (const struct ast_conditional_expression *)expression;
		size_t condition = codegen_truth(codegen, node->condition);
		size_t then_label = new_label(codegen);
		size_t else_label = new_label(codegen);
		size_t merge_label = new_label(codegen);

		emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", condition, then_label, else_label);
		emit_label(codegen, then_label);
		codegen_discard_expression(codegen, node->then_value);
		emit(codegen, "\tjmp @b%zu\n", merge_label);
		emit_label(codegen, else_label);
		codegen_discard_expression(codegen, node->else_value);
		emit(codegen, "\tjmp @b%zu\n", merge_label);
		emit_label(codegen, merge_label);
		return;
	}
	case expression_comma: {
		const struct ast_comma_expression *node = (const struct ast_comma_expression *)expression;

		codegen_discard_expression(codegen, node->left);
		codegen_discard_expression(codegen, node->right);
		return;
	}
	case expression_call:
		emit_call(codegen, (const struct ast_call_expression *)expression, NULL);
		return;
	case expression_cast: {
		const struct ast_cast_expression *node = (const struct ast_cast_expression *)expression;

		codegen_discard_expression(codegen, node->operand);
		return;
	}
	case expression_indirection: {
		const struct ast_indirection_expression *node = (const struct ast_indirection_expression *)expression;

		codegen_expression(codegen, node->operand);
		return;
	}
	default:
		assert(0 && "unsupported discarded void expression");
	}
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

static bool codegen_control_body(struct codegen *codegen,
	const struct ast_statement *statement, const struct ast_statement *body,
	size_t break_label, size_t continue_label)
{
	struct control_codegen context = {
		.parent = codegen->control,
		.statement = statement,
		.break_label = break_label,
		.continue_label = continue_label,
	};
	bool terminated;

	codegen->control = &context;
	terminated = codegen_statement(codegen, body);
	codegen->control = context.parent;
	return terminated;
}

static bool codegen_switch(struct codegen *codegen,
	const struct ast_switch_statement *node)
{
	size_t body_label = new_label(codegen);
	size_t exit_label = new_label(codegen);
	bool body_terminated;
	size_t control = codegen_expression(codegen, node->control);

	for (const struct ast_case_label *label = node->cases; label; label = label->next) {
		size_t comparison = codegen->next_temporary++;
		size_t next_test = new_label(codegen);
		size_t target = codegen->named_label_count + label->index + 1;

		emit(codegen, "\t%%t%zu =w ceq%c %%t%zu, %llu\n", comparison,
			qbe_type(node->control->type), control, (unsigned long long)label->bits);
		emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", comparison, target, next_test);
		emit_label(codegen, next_test);
	}
	if (node->default_label)
		emit(codegen, "\tjmp @b%zu\n", codegen->named_label_count + node->default_label->index + 1);
	else
		emit(codegen, "\tjmp @b%zu\n", exit_label);
	/* Keep named targets reachable by goto, with switch break/loop continue. */
	emit_label(codegen, body_label);
	body_terminated = codegen_control_body(codegen, &node->statement,
		node->body, exit_label, 0);
	if (!body_terminated)
		emit(codegen, "\tjmp @b%zu\n", exit_label);
	emit_label(codegen, exit_label);
	return false;
}

/* Sema has already resolved the enclosing statement, even across switches. */
static const struct control_codegen *codegen_jump_target(struct codegen *codegen,
	const struct ast_statement *statement)
{
	const struct control_codegen *context = codegen->control;

	while (context && context->statement != statement)
		context = context->parent;
	assert(context);
	return context;
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
	body_terminated = codegen_control_body(codegen, &node->statement,
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
	body_terminated = codegen_control_body(codegen, &node->statement,
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

	if (node->initializer_declarations)
		codegen_block_items(codegen, node->initializer_declarations);
	if (node->initializer_expression)
		codegen_discard_expression(codegen, node->initializer_expression);
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
	body_terminated = codegen_control_body(codegen, &node->statement,
		node->body, exit_label, step_label);
	if (!body_terminated)
		emit(codegen, "\tjmp @b%zu\n", step_label);
	emit_label(codegen, step_label);
	if (node->step)
		codegen_discard_expression(codegen, node->step);
	emit(codegen, "\tjmp @b%zu\n", condition_label);
	emit_label(codegen, exit_label);
	return false;
}

/* Switch targets follow all named goto targets in the reserved range. */
static void codegen_switch_label(struct codegen *codegen, size_t index, bool terminated)
{
	size_t target = codegen->named_label_count + index + 1;

	if (!terminated)
		emit(codegen, "\tjmp @b%zu\n", target);
	emit_label(codegen, target);
}

/* Named targets occupy 1..function->label_count, before generated CFG labels. */
static void codegen_named_label(struct codegen *codegen, const struct ast_label *label,
	bool terminated)
{
	size_t target = label->index + 1;

	if (!terminated)
		emit(codegen, "\tjmp @b%zu\n", target);
	emit_label(codegen, target);
}

/* True means the current block has terminated, not an I/O success flag. */
static bool codegen_statement(struct codegen *codegen,
	const struct ast_statement *statement)
{
	switch (statement->kind) {
	case statement_case: {
		const struct ast_case_statement *node = (const struct ast_case_statement *)statement;

		codegen_switch_label(codegen, node->label->index, false);
		return codegen_statement(codegen, node->body);
	}
	case statement_default: {
		const struct ast_default_statement *node = (const struct ast_default_statement *)statement;

		codegen_switch_label(codegen, node->label->index, false);
		return codegen_statement(codegen, node->body);
	}
	case statement_goto: {
		const struct ast_goto_statement *node = (const struct ast_goto_statement *)statement;

		assert(node->target);
		emit(codegen, "\tjmp @b%zu\n", node->target->index + 1);
		return true;
	}
	case statement_labeled: {
		const struct ast_labeled_statement *node = (const struct ast_labeled_statement *)statement;

		codegen_named_label(codegen, node->label, false);
		return codegen_statement(codegen, node->body);
	}
	case statement_return: {
		const struct ast_return_statement *node =
			(const struct ast_return_statement *)statement;
		if (node->value) {
			size_t value = codegen_expression(codegen, node->value);

			emit(codegen, "\tret %%t%zu\n", value);
		} else {
			emit(codegen, "\tret\n");
		}
		return true;
	}
	case statement_expression: {
		const struct ast_expression_statement *node =
			(const struct ast_expression_statement *)statement;

		codegen_discard_expression(codegen, node->value);
		return false;
	}
	case statement_empty:
		return false;
	case statement_for:
		return codegen_for(codegen, (const struct ast_for_statement *)statement);
	case statement_do:
		return codegen_do(codegen, (const struct ast_do_statement *)statement);
	case statement_switch:
		return codegen_switch(codegen, (const struct ast_switch_statement *)statement);
	case statement_while:
		return codegen_while(codegen, (const struct ast_while_statement *)statement);
	case statement_break: {
		const struct ast_break_statement *node =
			(const struct ast_break_statement *)statement;
		const struct control_codegen *target = codegen_jump_target(codegen, node->target);

		emit(codegen, "\tjmp @b%zu\n", target->break_label);
		return true;
	}
	case statement_continue: {
		const struct ast_continue_statement *node =
			(const struct ast_continue_statement *)statement;
		const struct control_codegen *target = codegen_jump_target(codegen, node->target);

		assert(target->statement->kind != statement_switch);
		emit(codegen, "\tjmp @b%zu\n", target->continue_label);
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
	bool terminated = false;

	while (item) {
		switch (item->kind) {
		case block_item_case:
			codegen_switch_label(codegen, ((const struct ast_block_case *)item)->label->index, terminated);
			terminated = false;
			break;
		case block_item_default:
			codegen_switch_label(codegen, ((const struct ast_block_default *)item)->label->index, terminated);
			terminated = false;
			break;
		case block_item_label:
			codegen_named_label(codegen, ((const struct ast_block_label *)item)->label, terminated);
			terminated = false;
			break;
		case block_item_typedef_declaration:
		case block_item_static_assertion:
			/* Fully checked at translation time; no runtime effect or datum. */
			break;
		case block_item_declaration: {
			const struct ast_local_declaration *local =
				(const struct ast_local_declaration *)item;

			if (terminated) {
				/* Keep later nested targets without inventing a fallthrough edge. */
				emit_label(codegen, new_label(codegen));
				terminated = false;
			}
			codegen_local_initializer(codegen, local);
			break;
		}
		case block_item_statement: {
			const struct ast_statement_item *node =
				(const struct ast_statement_item *)item;

			if (terminated)
				emit_label(codegen, new_label(codegen));
			terminated = codegen_statement(codegen, node->statement);
			break;
		}
		}
		item = item->next;
	}
	return terminated;
}

static bool codegen_function(FILE *stream, const struct ast_function *function)
{
	struct codegen codegen = {
		.stream = stream,
		.next_label = function->label_count + function->switch_label_count + 1,
		.named_label_count = function->label_count,
		.output_ok = true,
	};
	const struct ast_local_declaration *local = function->locals;
	struct token name = function->declaration->name;
	size_t parameter_index = 0;

	assert(type_is_scalar(function->return_type) || function->return_type->kind == type_kind_void);

	if (!function->declaration->symbol->is_internal)
		emit(&codegen, "export ");
	emit(&codegen, "function ");
	if (function->return_type->kind != type_kind_void)
		emit(&codegen, "%s ", qbe_abi_type(function->return_type));
	emit(&codegen, "$%.*s(", (int)name.length,
		(const char *)name.spelling_location.source->data + name.spelling_location.offset);
	for (const struct ast_parameter *parameter = function->declaration->parameters; parameter;
		parameter = parameter->next) {
		if (parameter->is_void_marker)
			continue;
		emit(&codegen, "%s%s %%p%zu", parameter_index ? ", " : "",
			qbe_abi_type(parameter->type), parameter_index);
		parameter_index++;
	}
	emit(&codegen, ") {\n");
	emit_label(&codegen, 0);
	while (local) {
		/* Slots are allocated at entry; initialization is in source order. */
		uint64_t bytes = type_object_size(local->type);
		unsigned alignment = type_object_alignment(local->type);

		if (alignment < 4)
			alignment = 4;
		emit(&codegen, "\t%%v%zu =l alloc%u %ju\n", local->slot, alignment, (uintmax_t)bytes);
		local = local->next_local;
	}
	parameter_index = 0;
	for (const struct ast_parameter *parameter = function->declaration->parameters; parameter;
		parameter = parameter->next) {
		if (parameter->is_void_marker)
			continue;
		if (parameter->local)
			emit(&codegen, "\tstore%c %%p%zu, %%v%zu\n",
				qbe_store_size(parameter->type), parameter_index, parameter->local->slot);
		parameter_index++;
	}
	if (!codegen_block_items(&codegen, function->body->items)) {
		if (function->return_type->kind == type_kind_void)
			emit(&codegen, "\tret\n");
		else
			emit(&codegen, "\tret 0\n");
	}
	emit(&codegen, "}\n");
	if (fflush(stream) != 0)
		codegen.output_ok = false;
	return codegen.output_ok;
}

bool codegen_translation_unit(FILE *stream, const struct ast_translation_unit *unit)
{
	const struct ast_external_declaration *external = unit->declarations;
	struct codegen data_codegen = { .stream = stream, .output_ok = true };

	for (const struct ast_string_expression *string = unit->strings; string;
		string = string->next_string) {
		emit(&data_codegen, "data $.Lkcc.string.%zu = align 1 {\n", string->object_id);
		for (size_t i = 0; i <= string->length; i++)
			emit(&data_codegen, "\tb %u%s\n", (unsigned)string->bytes[i], i == string->length ? "" : ",");
		emit(&data_codegen, "}\n");
	}
	if (!data_codegen.output_ok)
		return false;
	while (external) {
		if (external->kind == external_function_definition &&
			!codegen_function(stream, (const struct ast_function *)external))
			return false;
		external = external->next;
	}
	return fflush(stream) == 0;
}
