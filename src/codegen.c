#include "codegen.h"
#include "sema.h"
#include "type.h"

#include <assert.h>
#include <stdarg.h>
#include <stdlib.h>

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
	/* Aggregate expression values are addresses of captured object bytes. */
	return type_is_record(type) || type_value_width(type) == 64 ? 'l' : 'w';
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

static size_t codegen_compound_literal(struct codegen *codegen,
	const struct ast_compound_literal_expression *literal);

/* Object lvalues produce addresses; value-context loads are separate nodes. */
static size_t codegen_address(struct codegen *codegen, const struct ast_expression *expression)
{
	assert(expression->is_lvalue || expression->type->kind == type_kind_function ||
		expression->kind == expression_indirection || expression->kind == expression_member);
	switch (expression->kind) {
	case expression_compound_literal:
		return codegen_compound_literal(codegen,
			(const struct ast_compound_literal_expression *)expression);
	case expression_function_designator: {
		const struct ast_function_designator_expression *function =
			(const struct ast_function_designator_expression *)expression;
		struct token name = function->function->name;
		size_t result = codegen->next_temporary++;

		emit(codegen, "\t%%t%zu =l copy $%.*s\n", result, (int)name.length,
			(const char *)name.spelling_location.source->data + name.spelling_location.offset);
		return result;
	}
	case expression_external_object: {
		const struct ast_external_object_expression *object =
			(const struct ast_external_object_expression *)expression;
		struct token name = object->object->name;
		size_t result = codegen->next_temporary++;

		emit(codegen, "\t%%t%zu =l copy %s$%.*s\n", result,
			object->object->is_thread_local ? "thread " : "", (int)name.length,
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
	case expression_member: {
		const struct ast_member_expression *node = (const struct ast_member_expression *)expression;
		size_t base = node->indirect ? codegen_expression(codegen, node->operand) :
			node->operand->is_lvalue ? codegen_address(codegen, node->operand) :
			codegen_expression(codegen, node->operand);
		size_t result;

		if (!node->offset)
			return base;
		result = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =l add %%t%zu, %ju\n", result, base, (uintmax_t)node->offset);
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

/* Large QBE blits expand into proportional machine instructions. Keep IL and
 * backend resource use bounded: large record copies use a fixed-size loop,
 * without a libc helper, dynamic stack allocation, or reading past the object. */
static void codegen_record_copy(struct codegen *codegen, size_t source,
	size_t destination, uint64_t bytes)
{
	uint64_t bulk = bytes & ~UINT64_C(7);
	size_t predecessor;
	size_t loop;
	size_t done;
	size_t index;
	size_t next;
	size_t source_address;
	size_t destination_address;
	size_t value;
	size_t condition;

	if (bytes <= 64) {
		emit(codegen, "\tblit %%t%zu, %%t%zu, %ju\n", source, destination, (uintmax_t)bytes);
		return;
	}
	predecessor = codegen->current_label;
	loop = new_label(codegen);
	done = new_label(codegen);
	index = codegen->next_temporary++;
	next = codegen->next_temporary++;
	source_address = codegen->next_temporary++;
	destination_address = codegen->next_temporary++;
	value = codegen->next_temporary++;
	condition = codegen->next_temporary++;
	emit(codegen, "\tjmp @b%zu\n", loop);
	emit_label(codegen, loop);
	emit(codegen, "\t%%t%zu =l phi @b%zu 0, @b%zu %%t%zu\n", index,
		predecessor, loop, next);
	emit(codegen, "\t%%t%zu =l add %%t%zu, %%t%zu\n", source_address, source, index);
	emit(codegen, "\t%%t%zu =l add %%t%zu, %%t%zu\n", destination_address, destination, index);
	emit(codegen, "\t%%t%zu =l loadl %%t%zu\n", value, source_address);
	emit(codegen, "\tstorel %%t%zu, %%t%zu\n", value, destination_address);
	emit(codegen, "\t%%t%zu =l add %%t%zu, 8\n", next, index);
	emit(codegen, "\t%%t%zu =w cultl %%t%zu, %ju\n", condition, next, (uintmax_t)bulk);
	emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", condition, loop, done);
	emit_label(codegen, done);
	for (uint64_t offset = bulk; offset < bytes; offset++) {
		source_address = codegen->next_temporary++;
		destination_address = codegen->next_temporary++;
		value = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =l add %%t%zu, %ju\n", source_address, source, (uintmax_t)offset);
		emit(codegen, "\t%%t%zu =l add %%t%zu, %ju\n", destination_address, destination, (uintmax_t)offset);
		emit(codegen, "\t%%t%zu =w loadub %%t%zu\n", value, source_address);
		emit(codegen, "\tstoreb %%t%zu, %%t%zu\n", value, destination_address);
	}
}

/* These helpers keep initialization proportional to syntax, not object size.
 * Zero-fill and long string/copy writes use bounded loops without libc calls. */
static size_t codegen_byte_offset(struct codegen *codegen, size_t base, uint64_t offset)
{
	if (!offset)
		return base;
	size_t result = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =l add %%t%zu, %ju\n", result, base, (uintmax_t)offset);
	return result;
}

static void codegen_zero_bytes(struct codegen *codegen, size_t destination, uint64_t bytes)
{
	uint64_t bulk = bytes & ~UINT64_C(7);

	if (bytes > 64) {
		size_t predecessor = codegen->current_label;
		size_t loop = new_label(codegen), done = new_label(codegen);
		size_t index = codegen->next_temporary++, next = codegen->next_temporary++;
		size_t address = codegen->next_temporary++, condition = codegen->next_temporary++;

		emit(codegen, "\tjmp @b%zu\n", loop);
		emit_label(codegen, loop);
		emit(codegen, "\t%%t%zu =l phi @b%zu 0, @b%zu %%t%zu\n", index, predecessor, loop, next);
		emit(codegen, "\t%%t%zu =l add %%t%zu, %%t%zu\n", address, destination, index);
		emit(codegen, "\tstorel 0, %%t%zu\n", address);
		emit(codegen, "\t%%t%zu =l add %%t%zu, 8\n", next, index);
		emit(codegen, "\t%%t%zu =w cultl %%t%zu, %ju\n", condition, next, (uintmax_t)bulk);
		emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", condition, loop, done);
		emit_label(codegen, done);
	} else {
		for (uint64_t offset = 0; offset < bulk; offset += 8)
			emit(codegen, "\tstorel 0, %%t%zu\n", codegen_byte_offset(codegen, destination, offset));
	}
	for (uint64_t offset = bulk; offset < bytes; offset++)
		emit(codegen, "\tstoreb 0, %%t%zu\n", codegen_byte_offset(codegen, destination, offset));
}

struct initializer_capture {
	const struct ast_expression *expression;
	size_t value;
};

static void codegen_initializer_plan(struct codegen *codegen,
	const struct ast_initializer_plan *plan, size_t destination)
{
	struct initializer_capture *captures = NULL;
	size_t capacity = 1;

	assert(plan->entry_count <= ast_max_initializer_entries);
	while (capacity < plan->entry_count * 2)
		capacity *= 2;
	if (plan->entry_count) {
		captures = calloc(capacity, sizeof(*captures));
		if (!captures) {
			codegen->output_ok = false;
			return;
		}
	}
	/* A compound literal is a live object when reevaluated. Capture checked
	 * initializer values before clearing any of its previous contents; reads
	 * through an earlier pointer must observe that previous object value. */
	for (const struct ast_initializer_plan_entry *entry = plan->entries; entry; entry = entry->next) {
		if (!entry->length || entry->kind == ast_initializer_write_zero)
			continue;
		assert(entry->expression);
		size_t i = ((uintptr_t)entry->expression >> 3) & (capacity - 1);
		while (captures[i].expression && captures[i].expression != entry->expression)
			i = (i + 1) & (capacity - 1);
		if (!captures[i].expression) {
			size_t value = entry->kind == ast_initializer_write_string ?
				codegen_address(codegen, entry->expression) : codegen_expression(codegen, entry->expression);
			captures[i] = (struct initializer_capture) { entry->expression, value };
		}
	}
	if (plan->zero_fill)
		codegen_zero_bytes(codegen, destination, plan->size);
	for (const struct ast_initializer_plan_entry *entry = plan->entries; entry; entry = entry->next) {
		size_t address, value;

		assert(entry->offset <= plan->size && entry->length <= plan->size - entry->offset);
		if (!entry->length)
			continue;
		address = codegen_byte_offset(codegen, destination, entry->offset);
		if (entry->kind == ast_initializer_write_zero) {
			codegen_zero_bytes(codegen, address, entry->length);
			continue;
		}
		size_t i = ((uintptr_t)entry->expression >> 3) & (capacity - 1);
		while (captures[i].expression != entry->expression) {
			assert(captures[i].expression);
			i = (i + 1) & (capacity - 1);
		}
		value = captures[i].value;
		if (entry->kind == ast_initializer_write_copy || entry->kind == ast_initializer_write_string) {
			value = codegen_byte_offset(codegen, value, entry->source_offset);
			codegen_record_copy(codegen, value, address, entry->length);
		} else {
			assert(entry->kind == ast_initializer_write_expression);
			assert(entry->length == type_object_size(entry->type));
			emit(codegen, "\tstore%c %%t%zu, %%t%zu\n", qbe_store_size(entry->type), value, address);
		}
	}
	free(captures);
}

static size_t codegen_compound_literal(struct codegen *codegen,
	const struct ast_compound_literal_expression *literal)
{
	size_t address = codegen->next_temporary++;

	if (literal->local) {
		emit(codegen, "\t%%t%zu =l copy %%v%zu\n", address, literal->local->slot);
		assert(literal->initializer_plan);
		codegen_initializer_plan(codegen, literal->initializer_plan, address);
	} else {
		assert(literal->object);
		struct token name = literal->object->name;
		emit(codegen, "\t%%t%zu =l copy %s$%.*s\n", address,
			literal->object->is_thread_local ? "thread " : "", (int)name.length,
			(const char *)name.spelling_location.source->data + name.spelling_location.offset);
	}
	return address;
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

	if (type_is_record(target)) {
		assert(type_is_record(source) && type_unqualified_compatible(source, target));
		return value;
	}
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

	assert(type_is_scalar(expression->type) || type_is_record(expression->type));
	switch (expression->kind) {
	case expression_compound_literal:
		return codegen_compound_literal(codegen, (const struct ast_compound_literal_expression *)expression);
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
	case expression_enumerator:
		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =w copy %ju\n", temporary,
			(uintmax_t)((const struct ast_enumerator_expression *)expression)->bits);
		return temporary;
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
		if (type_is_record(expression->type)) {
			/* Captures live in entry-allocated slots, never loop allocations.
			 * Later writes to the original cannot rewrite this value. */
			emit(codegen, "\t%%t%zu =l copy %%r%zu\n", temporary, node->record_temporary_slot);
			codegen_record_copy(codegen, address, temporary, type_object_size(expression->type));
			return temporary;
		}
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

		if (type_is_record(node->left->type))
			codegen_record_copy(codegen, value, address, type_object_size(node->left->type));
		else
			emit(codegen, "\tstore%c %%t%zu, %%t%zu\n", qbe_store_size(node->left->type), value, address);
		return value;
	}
	case expression_member: {
		size_t address = codegen_address(codegen, expression);

		if (type_is_record(expression->type))
			return address;
		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", temporary,
			qbe_type(expression->type), qbe_load_instruction(expression->type), address);
		return temporary;
	}
	case expression_function_designator:
	case expression_external_object:
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
	if (local->initializer_plan) {
		size_t address = codegen->next_temporary++;

		emit(codegen, "\t%%t%zu =l copy %%v%zu\n", address, local->slot);
		codegen_initializer_plan(codegen, local->initializer_plan, address);
	} else if (local->initializer) {
		size_t value = codegen_expression(codegen, local->initializer);

		if (type_is_record(local->type)) {
			size_t address = codegen->next_temporary++;

			emit(codegen, "\t%%t%zu =l copy %%v%zu\n", address, local->slot);
			codegen_record_copy(codegen, value, address, type_object_size(local->type));
		} else
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
		case block_item_tag_declaration:
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
			if (!local->object_symbol && !local->function_symbol)
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
		unsigned alignment = local->alignment ? local->alignment : type_object_alignment(local->type);

		if (alignment < 4)
			alignment = 4;
		emit(&codegen, "\t%%v%zu =l alloc%u %ju\n", local->slot, alignment, (uintmax_t)bytes);
		local = local->next_local;
	}
	for (const struct ast_load_expression *capture = function->record_temporaries; capture;
		capture = capture->next_record_temporary) {
		unsigned alignment = type_object_alignment(capture->expression.type);

		if (alignment < 4)
			alignment = 4;
		emit(&codegen, "\t%%r%zu =l alloc%u %ju\n", capture->record_temporary_slot,
			alignment, (uintmax_t)type_object_size(capture->expression.type));
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

static int initializer_offset_order(const void *left, const void *right)
{
	const struct ast_initializer_plan_entry *a = *(const struct ast_initializer_plan_entry *const *)left;
	const struct ast_initializer_plan_entry *b = *(const struct ast_initializer_plan_entry *const *)right;

	return (a->offset > b->offset) - (a->offset < b->offset);
}

static void codegen_static_initializer(struct codegen *codegen, const struct ast_initializer_plan *plan)
{
	const struct ast_initializer_plan_entry **entries = NULL;
	size_t count = 0;
	uint64_t position = 0;

	if (plan->entry_count) {
		entries = calloc(plan->entry_count, sizeof(*entries));
		if (!entries) {
			codegen->output_ok = false;
			return;
		}
	}
	for (const struct ast_initializer_plan_entry *entry = plan->entries; entry; entry = entry->next) {
		assert(count < plan->entry_count);
		entries[count++] = entry;
	}
	if (count)
		qsort(entries, count, sizeof(*entries), initializer_offset_order);
	for (size_t i = 0; i < count; i++) {
		const struct ast_initializer_plan_entry *entry = entries[i];
		const struct ast_initializer_constant *constant = &entry->constant;

		assert(entry->offset >= position && entry->offset <= plan->size &&
			entry->length <= plan->size - entry->offset);
		if (entry->offset > position)
			emit(codegen, "z %ju, ", (uintmax_t)(entry->offset - position));
		position = entry->offset + entry->length;
		if (!entry->length)
			continue;
		if (entry->kind == ast_initializer_write_zero)
			emit(codegen, "z %zu, ", entry->length);
		else if (entry->kind == ast_initializer_write_string) {
			assert(entry->bytes);
			for (size_t j = 0; j < entry->length; j++)
				emit(codegen, "b %u, ", (unsigned)entry->bytes[entry->source_offset + j]);
		} else if (constant->kind == ast_initializer_constant_address) {
			struct token name;

			assert(entry->length == 8 && !entry->source_offset);
			switch (constant->address_kind) {
			case ast_initializer_address_string:
				emit(codegen, "l $.Lkcc.string.%zu", constant->base.string->object_id);
				break;
			case ast_initializer_address_object:
			case ast_initializer_address_function:
				name = constant->address_kind == ast_initializer_address_object ?
					constant->base.object->name : constant->base.function->name;
				emit(codegen, "l $%.*s", (int)name.length,
					(const char *)name.spelling_location.source->data + name.spelling_location.offset);
				break;
			case ast_initializer_address_compound_literal:
				/* Sema resolves static literals to their canonical symbol. */
				assert(0 && "unresolved compound literal relocation");
				break;
			}
			if (constant->byte_addend)
				emit(codegen, " + %jd", (intmax_t)constant->byte_addend);
			emit(codegen, ", ");
		} else {
			assert(constant->kind == ast_initializer_constant_integer ||
				constant->kind == ast_initializer_constant_null);
			assert(entry->source_offset <= 8 && entry->length <= 8 - entry->source_offset);
			/* Byte slices preserve explicitly overridden scalar storage too;
			 * target representation is Linux amd64 little endian. */
			for (size_t j = 0; j < entry->length; j++)
				emit(codegen, "b %u, ", (unsigned)((constant->bits >>
					(8 * (entry->source_offset + j))) & UINT64_C(255)));
		}
	}
	if (position < plan->size)
		emit(codegen, "z %ju, ", (uintmax_t)(plan->size - position));
	emit(codegen, "}\n");
	free(entries);
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
	bool emitting_statics = false;
	while (external || !emitting_statics) {
		if (!external) {
			emitting_statics = true;
			external = unit->static_declarations;
			if (!external)
				break;
		}
		const struct external_object_symbol *object = NULL;

		if (external->kind == external_object_declaration)
			object = ((const struct ast_external_object_declaration *)external)->symbol;
		else if (external->kind == external_type_declaration)
			object = ((const struct ast_external_type_declaration *)external)->object_symbol;
		if (object && (object->definition ? object->definition : object->tentative_definition) == external) {
			struct token name = object->name;

			/* Explicit definitions supersede the first tentative anchor. */
			assert(type_is_complete_object(object->type));
			emit(&data_codegen, "%s%sdata $%.*s = align %u { ",
				object->is_internal ? "" : "export ", object->is_thread_local ? "thread " : "", (int)name.length,
				(const char *)name.spelling_location.source->data + name.spelling_location.offset,
				object->alignment ? object->alignment : type_object_alignment(object->type));
			if (object->definition && object->initializer_plan)
				codegen_static_initializer(&data_codegen, object->initializer_plan);
			else if (object->definition) {
				uint64_t size = type_object_size(object->type);
				const char *encoding = size == 1 ? "b" : size == 2 ? "h" : size == 4 ? "w" : "l";

				switch (object->initializer_value.kind) {
				case static_data_zero:
					emit(&data_codegen, "z %ju }\n", (uintmax_t)size);
					break;
				case static_data_integer:
					assert(type_is_integer(object->type));
					emit(&data_codegen, "%s %ju }\n", encoding,
						(uintmax_t)object->initializer_value.integer_bits);
					break;
				case static_data_address: {
					const struct static_address *address = &object->initializer_value.address;
					struct token base_name;

					assert(object->type->kind == type_kind_pointer && size == 8);
					switch (address->kind) {
					case static_address_compound_literal:
						assert(0 && "query-only literal address reached emission");
						break;
					case static_address_string:
						emit(&data_codegen, "l $.Lkcc.string.%zu", address->base.string->object_id);
						break;
					case static_address_object:
					case static_address_function:
						base_name = address->kind == static_address_object ?
							address->base.object->name : address->base.function->name;
						emit(&data_codegen, "l $%.*s", (int)base_name.length,
							(const char *)base_name.spelling_location.source->data + base_name.spelling_location.offset);
						break;
					}
					if (address->byte_addend)
						emit(&data_codegen, " + %jd", (intmax_t)address->byte_addend);
					emit(&data_codegen, " }\n");
					break;
				}
				case static_data_null_pointer:
					/* Linux amd64 pointer storage has an eight-byte zero null encoding. */
					assert((object->type->kind == type_kind_pointer || object->type->kind == type_kind_nullptr) && size == 8);
					emit(&data_codegen, "l 0 }\n");
					break;
				}
			} else
				emit(&data_codegen, "z %ju }\n", (uintmax_t)type_object_size(object->type));
			if (!data_codegen.output_ok)
				return false;
		}
		if (external->kind == external_function_definition &&
			!((const struct ast_function *)external)->declaration->symbol->is_inline_only &&
			!codegen_function(stream, (const struct ast_function *)external))
			return false;
		external = external->next;
	}
	return fflush(stream) == 0;
}
