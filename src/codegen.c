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

struct abi_registry {
	bool legacy_clang_abi;
	bool gcc12_zero_width_abi;
	bool used[type_max_abi_record_size + 1][17][aggregate_abi_sse + 1][aggregate_abi_sse + 1];
};

struct codegen {
	struct abi_registry *abi;

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

/* QBE supports quoted global names. Emit decoded UTF-8, preserving native ELF
 * symbol spelling across raw source characters and equivalent UCNs. */
static void emit_symbol(struct codegen *codegen, struct token name)
{
	const unsigned char *text = name.spelling_location.source->data + name.spelling_location.offset;
	bool quoted = false;
	for (size_t i = 0; i < name.length; i++)
		if (text[i] >= 128 || text[i] == '\\') { quoted = true; break; }
	if (!quoted) {
		emit(codegen, "$%.*s", (int)name.length, (const char *)text);
		return;
	}
	emit(codegen, "$\"");
	for (size_t i = 0; i < name.length;) {
		size_t start = i;
		uint32_t cp;
		unsigned char bytes[4];
		bool valid = identifier_next(text, name.length, &i, &cp);
		assert(valid); (void)valid; (void)cp;
		size_t n = identifier_utf8(text + start, i - start, bytes);
		emit(codegen, "%.*s", (int)n, (const char *)bytes);
	}
	emit(codegen, "\"");
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
	if (type->kind == type_kind_float) return 's';
	if (type->kind == type_kind_double) return 'd';
	return type_is_record(type) || type_value_width(type) > 32 ? 'l' : 'w';
}

static const char *qbe_abi_type(const struct type *type)
{
	if (type->kind == type_kind_float) return "s";
	if (type->kind == type_kind_double) return "d";
	if (type_object_size(type) == 1)
		return type_is_unsigned(type) ? "ub" : "sb";
	if (type_object_size(type) == 2)
		return type_is_unsigned(type) ? "uh" : "sh";
	return type_value_width(type) > 32 ? "l" : "w";
}

static void emit_abi_type(struct codegen *codegen, const struct type *type)
{
	if (!type_is_record(type)) {
		emit(codegen, "%s", qbe_abi_type(type));
		return;
	}
	struct aggregate_abi abi;
	bool valid = type_aggregate_abi_for_mode(type, &abi, codegen->abi->legacy_clang_abi, codegen->abi->gcc12_zero_width_abi);
	assert(valid && codegen->abi);
	(void)valid;
	codegen->abi->used[abi.size][abi.alignment][abi.classes[0]][abi.classes[1]] = true;
	emit(codegen, ":kcc_abi_%u_%u_%u_%u", abi.size, abi.alignment,
		(unsigned)abi.classes[0], (unsigned)abi.classes[1]);
}

static const char *qbe_load_instruction(const struct type *type)
{
	if (type->kind == type_kind_float) return "loads";
	if (type->kind == type_kind_double) return "loadd";
	if (type_object_size(type) == 1)
		return type_is_unsigned(type) ? "loadub" : "loadsb";
	if (type_object_size(type) == 2)
		return type_is_unsigned(type) ? "loaduh" : "loadsh";
	return type_value_width(type) > 32 ? "loadl" : "loadw";
}

static char qbe_store_size(const struct type *type)
{
	if (type_object_size(type) == 1)
		return 'b';
	if (type_object_size(type) == 2)
		return 'h';
	return qbe_type(type);
}

/* Establish a canonical word/long value after loads, calls, operations and
 * conversions. Padding bits in stored and ABI representations are ignored. */
static size_t codegen_canonicalize(struct codegen *codegen, size_t value,
	const struct type *type)
{
	size_t result;
	const char *instruction;

	if ((type_is_bitint(type) || type_uses_field_integer_representation(type)) &&
		!type_bitint_width_native(type_integer_width(type))) {
		unsigned width = type_integer_width(type);
		unsigned carrier = width <= 32 ? 32 : 64;
		size_t shifted = codegen->next_temporary++;
		result = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c shl %%t%zu, %u\n", shifted,
			carrier == 32 ? 'w' : 'l', value, carrier - width);
		emit(codegen, "\t%%t%zu =%c %s %%t%zu, %u\n", result,
			carrier == 32 ? 'w' : 'l', type_is_unsigned(type) ? "shr" : "sar", shifted, carrier - width);
		return result;
	}
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

/* In memory, clear _BitInt padding bits. Clang assumes these bits are zero
 * when aggregates cross the SysV ABI, while expression values remain signed. */
static size_t codegen_storage_bits(struct codegen *codegen, size_t value, const struct type *type)
{
	if (!type_is_bitint(type) || type_bitint_width_native(type_integer_width(type)))
		return value;
	unsigned width = type_integer_width(type), carrier = width <= 32 ? 32 : 64;
	size_t shifted = codegen->next_temporary++, masked = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =%c shl %%t%zu, %u\n", shifted, carrier == 32 ? 'w' : 'l', value, carrier-width);
	emit(codegen, "\t%%t%zu =%c shr %%t%zu, %u\n", masked, carrier == 32 ? 'w' : 'l', shifted, carrier-width);
	return masked;
}

/* libatomic transports floating values as representation bits, not FP ABI
 * arguments. QBE cast between matching-width FP and integer classes is a bitcast. */
static size_t atomic_to_bits(struct codegen *codegen, size_t value, const struct type *type)
{
	if (type_is_floating(type)) {
		size_t bits = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c cast %%t%zu\n", bits,
			type->kind == type_kind_float ? 'w' : 'l', value);
		return bits;
	}
	return codegen_storage_bits(codegen, value, type);
}

static size_t atomic_from_bits(struct codegen *codegen, size_t bits, const struct type *type)
{
	if (type_is_floating(type)) {
		size_t value = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c cast %%t%zu\n", value, qbe_type(type), bits);
		return value;
	}
	return codegen_canonicalize(codegen, bits, type);
}

/* Do not follow pointer referents. By-value record nesting is bounded by sema. */
static bool contains_volatile(const struct type *type)
{
	if (type->qualifiers & type_qualifier_volatile) return true;
	if (type->kind == type_kind_array)
		return contains_volatile(((const struct array_type *)type)->element);
	return type_is_record(type) && type_record_definition(type)->has_volatile_member;
}

static bool has_record_leaf(const struct type *type)
{
	while (type->kind == type_kind_array) type = ((const struct array_type *)type)->element;
	return type_is_record(type);
}

static void codegen_volatile_copy(struct codegen *codegen, size_t source,
	size_t destination, uint64_t bytes, unsigned flags)
{
	emit(codegen, "\tcall $__kcc_volatile_copy(l %%t%zu, l %%t%zu, l %ju, w %u)\n",
		destination, source, (uintmax_t)bytes, flags);
}

static void codegen_volatile_zero(struct codegen *codegen, size_t destination, uint64_t bytes)
{
	emit(codegen, "\tcall $__kcc_volatile_zero(l %%t%zu, l %ju)\n", destination, (uintmax_t)bytes);
}

/* QBE has no volatile access marker. Calls into the separately compiled
 * runtime preserve an observable scalar access across backend optimization. */
static size_t codegen_volatile_load(struct codegen *codegen, size_t address, const struct type *type)
{
	unsigned width = (unsigned)type_object_size(type);
	size_t bits = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =%c call $__kcc_volatile_load_%u(l %%t%zu)\n",
		bits, width == 8 ? 'l' : 'w', width, address);
	return atomic_from_bits(codegen, bits, type);
}

static void codegen_volatile_store(struct codegen *codegen, size_t address, size_t value,
	const struct type *type)
{
	unsigned width = (unsigned)type_object_size(type);
	size_t bits = codegen_storage_bits(codegen, atomic_to_bits(codegen, value, type), type);
	emit(codegen, "\tcall $__kcc_volatile_store_%u(l %%t%zu, %c %%t%zu)\n",
		width, address, width == 8 ? 'l' : 'w', bits);
}

static const char *binary_instruction(enum binary_operator operation, const struct type *operand_type)
{
	bool unsigned_operands;
	bool wide = type_value_width(operand_type) > 32;

	if (type_is_floating(operand_type)) {
		bool single = operand_type->kind == type_kind_float;
		switch (operation) {
		case binary_add: return "add";
		case binary_subtract: return "sub";
		case binary_multiply: return "mul";
		case binary_divide: return "div";
		case binary_equal: return single ? "ceqs" : "ceqd";
		case binary_not_equal: return single ? "cnes" : "cned";
		case binary_less: return single ? "clts" : "cltd";
		case binary_less_equal: return single ? "cles" : "cled";
		case binary_greater: return single ? "cgts" : "cgtd";
		case binary_greater_equal: return single ? "cges" : "cged";
		default: assert(0 && "invalid float operation"); return NULL;
		}
	}
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

	if (type_integer_width(index->type) > 32)
		return value;
	assert(type_integer_width(index->type) <= 32);
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

		emit(codegen, "\t%%t%zu =l copy ", result);
		emit_symbol(codegen, name);
		emit(codegen, "\n");
		return result;
	}
	case expression_external_object: {
		const struct ast_external_object_expression *object =
			(const struct ast_external_object_expression *)expression;
		struct token name = object->object->name;
		size_t result = codegen->next_temporary++;

		emit(codegen, "\t%%t%zu =l copy %s", result, object->object->is_thread_local ? "thread " : "");
		emit_symbol(codegen, name);
		emit(codegen, "\n");
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

		assert(name->declaration && (type_is_complete_object(name->declaration->type) ||
			(name->declaration->type->kind == type_kind_array &&
			((const struct array_type *)name->declaration->type)->runtime_bound)));
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

/* Address the first touched byte and preserve all neighboring bits. */
static const struct record_member *codegen_bit_field(const struct ast_expression *expression)
{
	if (expression->kind != expression_member)
		return NULL;
	const struct record_member *member = ((const struct ast_member_expression *)expression)->member;
	return member && member->is_bit_field && member->bit_width &&
		(member->bit_width < 32 || type_is_bitint(member->type) || type_value_width(member->type) == 64) ? member : NULL;
}

static size_t codegen_field_value(struct codegen *codegen, size_t value,
	const struct record_member *member)
{
	unsigned shift = 32 - member->bit_width;
	size_t shifted = codegen->next_temporary++, result = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =w shl %%t%zu, %u\n", shifted, value, shift);
	emit(codegen, "\t%%t%zu =w %s %%t%zu, %u\n", result,
		type_is_unsigned(member->type) ? "shr" : "sar", shifted, shift);
	return result;
}

static size_t codegen_field_storage_load(struct codegen *codegen, size_t address, unsigned bytes, bool is_volatile)
{
	if (is_volatile) {
		size_t value = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =w copy 0\n", value);
		for (unsigned i = 0; i < bytes; i++) {
			size_t at = codegen->next_temporary++, byte = codegen->next_temporary++;
			size_t shifted = codegen->next_temporary++, combined = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =l add %%t%zu, %u\n", at, address, i);
			emit(codegen, "\t%%t%zu =w call $__kcc_volatile_load_1(l %%t%zu)\n", byte, at);
			emit(codegen, "\t%%t%zu =w shl %%t%zu, %u\n", shifted, byte, 8 * i);
			emit(codegen, "\t%%t%zu =w or %%t%zu, %%t%zu\n", combined, value, shifted);
			value = combined;
		}
		return value;
	}
	size_t value = codegen->next_temporary++;
	if (bytes != 3) {
		emit(codegen, "\t%%t%zu =w %s %%t%zu\n", value,
			bytes == 1 ? "loadub" : bytes == 2 ? "loaduh" : "loadw", address);
		return value;
	}
	size_t tail_address = codegen->next_temporary++, tail = codegen->next_temporary++;
	size_t shifted = codegen->next_temporary++, result = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =w loaduh %%t%zu\n", value, address);
	emit(codegen, "\t%%t%zu =l add %%t%zu, 2\n", tail_address, address);
	emit(codegen, "\t%%t%zu =w loadub %%t%zu\n", tail, tail_address);
	emit(codegen, "\t%%t%zu =w shl %%t%zu, 16\n", shifted, tail);
	emit(codegen, "\t%%t%zu =w or %%t%zu, %%t%zu\n", result, value, shifted);
	return result;
}

static size_t codegen_byte_offset(struct codegen *codegen, size_t base, uint64_t offset);

/* Long-base fields use a 64-bit value and can touch up to eight bytes.
 * Allocation-unit layout ensures bit_offset + bit_width <= 64. Access exactly the occupied bytes so a
 * field at the end of an object does not read or write beyond it. */
static size_t codegen_wide_field_load(struct codegen *codegen, size_t address,
	const struct record_member *member, bool is_volatile)
{
	assert(member->bit_offset + member->bit_width <= 64);
	unsigned bytes = (member->bit_offset + member->bit_width + 7) / 8;
	size_t value = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =l copy 0\n", value);
	for (unsigned i = 0; i < bytes; i++) {
		size_t at = codegen_byte_offset(codegen, address, i);
		size_t byte = codegen->next_temporary++, wide = codegen->next_temporary++;
		size_t shifted = codegen->next_temporary++, combined = codegen->next_temporary++;
		if (is_volatile)
			emit(codegen, "\t%%t%zu =w call $__kcc_volatile_load_1(l %%t%zu)\n", byte, at);
		else
			emit(codegen, "\t%%t%zu =w loadub %%t%zu\n", byte, at);
		emit(codegen, "\t%%t%zu =l extuw %%t%zu\n", wide, byte);
		emit(codegen, "\t%%t%zu =l shl %%t%zu, %u\n", shifted, wide, 8 * i);
		emit(codegen, "\t%%t%zu =l or %%t%zu, %%t%zu\n", combined, value, shifted);
		value = combined;
	}
	unsigned left = 64 - member->bit_offset - member->bit_width;
	unsigned right = 64 - member->bit_width;
	size_t shifted = codegen->next_temporary++, result = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =l shl %%t%zu, %u\n", shifted, value, left);
	emit(codegen, "\t%%t%zu =l %s %%t%zu, %u\n", result,
		type_is_unsigned(member->type) ? "shr" : "sar", shifted, right);
	return result;
}

static size_t codegen_wide_field_store(struct codegen *codegen, size_t address,
	size_t value, const struct record_member *member, bool is_volatile)
{
	assert(member->bit_offset + member->bit_width <= 64);
	unsigned bytes = (member->bit_offset + member->bit_width + 7) / 8;
	uint64_t mask = member->bit_width == 64 ? UINT64_MAX : (UINT64_C(1) << member->bit_width) - 1;
	size_t bits = codegen->next_temporary++, placed = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =l and %%t%zu, %ju\n", bits, value, (uintmax_t)mask);
	emit(codegen, "\t%%t%zu =l shl %%t%zu, %u\n", placed, bits, member->bit_offset);
	uint64_t storage_mask = mask << member->bit_offset;
	for (unsigned i = 0; i < bytes; i++) {
		size_t at = codegen_byte_offset(codegen, address, i);
		size_t old = codegen->next_temporary++, kept = codegen->next_temporary++;
		size_t shifted = codegen->next_temporary++, part = codegen->next_temporary++;
		size_t combined = codegen->next_temporary++;
		unsigned byte_mask = (unsigned)((storage_mask >> (8 * i)) & 255);
		if (is_volatile)
			emit(codegen, "\t%%t%zu =w call $__kcc_volatile_load_1(l %%t%zu)\n", old, at);
		else
			emit(codegen, "\t%%t%zu =w loadub %%t%zu\n", old, at);
		emit(codegen, "\t%%t%zu =w and %%t%zu, %u\n", kept, old, 255 ^ byte_mask);
		emit(codegen, "\t%%t%zu =l shr %%t%zu, %u\n", shifted, placed, 8 * i);
		emit(codegen, "\t%%t%zu =w and %%t%zu, %u\n", part, shifted, byte_mask);
		emit(codegen, "\t%%t%zu =w or %%t%zu, %%t%zu\n", combined, kept, part);
		if (is_volatile)
			emit(codegen, "\tcall $__kcc_volatile_store_1(l %%t%zu, w %%t%zu)\n", at, combined);
		else
			emit(codegen, "\tstoreb %%t%zu, %%t%zu\n", combined, at);
	}
	unsigned shift = 64 - member->bit_width;
	size_t shifted = codegen->next_temporary++, result = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =l shl %%t%zu, %u\n", shifted, bits, shift);
	emit(codegen, "\t%%t%zu =l %s %%t%zu, %u\n", result,
		type_is_unsigned(member->type) ? "shr" : "sar", shifted, shift);
	return result;
}

static size_t codegen_field_load(struct codegen *codegen, size_t address,
	const struct record_member *member, bool is_volatile)
{
	if (type_value_width(member->type) > 32)
		return codegen_wide_field_load(codegen, address, member, is_volatile);
	size_t value = codegen_field_storage_load(codegen, address, (member->bit_offset + member->bit_width + 7) / 8, is_volatile);
	if (member->bit_offset) {
		size_t shifted = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =w shr %%t%zu, %u\n", shifted, value, member->bit_offset);
		value = shifted;
	}
	return codegen_field_value(codegen, value, member);
}

static size_t codegen_field_store(struct codegen *codegen, size_t address, size_t value,
	const struct record_member *member, bool is_volatile)
{
	if (type_value_width(member->type) > 32)
		return codegen_wide_field_store(codegen, address, value, member, is_volatile);
	unsigned bytes = (member->bit_offset + member->bit_width + 7) / 8;
	uint32_t mask = UINT32_MAX >> (32 - member->bit_width);
	uint32_t storage_mask = mask << member->bit_offset;
	size_t old = codegen_field_storage_load(codegen, address, bytes, is_volatile);
	size_t kept = codegen->next_temporary++, bits = codegen->next_temporary++;
	size_t combined = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =w and %%t%zu, %u\n", kept, old, ~storage_mask);
	emit(codegen, "\t%%t%zu =w and %%t%zu, %u\n", bits, value, mask);
	size_t placed = bits;
	if (member->bit_offset) {
		placed = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =w shl %%t%zu, %u\n", placed, bits, member->bit_offset);
	}
	emit(codegen, "\t%%t%zu =w or %%t%zu, %%t%zu\n", combined, kept, placed);
	if (is_volatile) {
		for (unsigned i = 0; i < bytes; i++) {
			size_t at = codegen->next_temporary++, byte = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =l add %%t%zu, %u\n", at, address, i);
			emit(codegen, "\t%%t%zu =w shr %%t%zu, %u\n", byte, combined, 8 * i);
			emit(codegen, "\tcall $__kcc_volatile_store_1(l %%t%zu, w %%t%zu)\n", at, byte);
		}
	} else if (bytes == 3) {
		size_t tail_address = codegen->next_temporary++, tail = codegen->next_temporary++;
		emit(codegen, "\tstoreh %%t%zu, %%t%zu\n", combined, address);
		emit(codegen, "\t%%t%zu =l add %%t%zu, 2\n", tail_address, address);
		emit(codegen, "\t%%t%zu =w shr %%t%zu, 16\n", tail, combined);
		emit(codegen, "\tstoreb %%t%zu, %%t%zu\n", tail, tail_address);
	} else
		emit(codegen, "\tstore%c %%t%zu, %%t%zu\n", bytes == 1 ? 'b' : bytes == 2 ? 'h' : 'w', combined, address);
	return codegen_field_value(codegen, bits, member);
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

static int initializer_offset_order(const void *left, const void *right);

/* Initialize each scalar representation exactly once, including implicit
 * zeros, without expanding large arrays into unbounded generated code. */
static void codegen_volatile_array_range(struct codegen *codegen, size_t destination,
	uint64_t length, unsigned width, bool copy, size_t source)
{
	assert(length && length % width == 0);
	size_t predecessor = codegen->current_label;
	size_t loop = new_label(codegen), done = new_label(codegen);
	size_t index = codegen->next_temporary++, next = codegen->next_temporary++;
	size_t address = codegen->next_temporary++, more = codegen->next_temporary++;
	emit(codegen, "\tjmp @b%zu\n", loop);
	emit_label(codegen, loop);
	emit(codegen, "\t%%t%zu =l phi @b%zu 0, @b%zu %%t%zu\n", index, predecessor, loop, next);
	emit(codegen, "\t%%t%zu =l add %%t%zu, %%t%zu\n", address, destination, index);
	if (copy) {
		size_t source_address = codegen->next_temporary++, bits = codegen->next_temporary++;
		const char *load = width == 1 ? "loadub" : width == 2 ? "loaduh" : "loadw";
		assert(width <= 4);
		emit(codegen, "\t%%t%zu =l add %%t%zu, %%t%zu\n", source_address, source, index);
		emit(codegen, "\t%%t%zu =w %s %%t%zu\n", bits, load, source_address);
		emit(codegen, "\tcall $__kcc_volatile_store_%u(l %%t%zu, w %%t%zu)\n", width, address, bits);
	} else {
		emit(codegen, "\tcall $__kcc_volatile_store_%u(l %%t%zu, %c 0)\n",
			width, address, width == 8 ? 'l' : 'w');
	}
	emit(codegen, "\t%%t%zu =l add %%t%zu, %u\n", next, index, width);
	emit(codegen, "\t%%t%zu =w cultl %%t%zu, %ju\n", more, next, (uintmax_t)length);
	emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", more, loop, done);
	emit_label(codegen, done);
}

static void codegen_initializer_plan(struct codegen *codegen,
	const struct ast_initializer_plan *plan, size_t destination)
{
	struct initializer_capture *captures = NULL;
	size_t capacity = 1;
	bool volatile_aggregate = has_record_leaf(plan->type) && contains_volatile(plan->type);

	/* Volatile scalar plans have one whole-object surviving write. Evaluate
	 * its expression before writing, including for re-evaluated literals. */
	if (type_is_scalar(plan->type) && (plan->type->qualifiers & type_qualifier_volatile)) {
		const struct ast_initializer_plan_entry *entry = plan->entries;
		unsigned width = (unsigned)plan->size;
		assert(type_is_scalar(plan->type));
		assert(entry && !entry->next && entry->offset == 0 && entry->length == plan->size);
		if (entry->kind == ast_initializer_write_zero) {
			emit(codegen, "\tcall $__kcc_volatile_store_%u(l %%t%zu, %c 0)\n",
				width, destination, width == 8 ? 'l' : 'w');
		} else {
			assert(entry->kind == ast_initializer_write_expression && entry->expression);
			size_t value = codegen_expression(codegen, entry->expression);
			codegen_volatile_store(codegen, destination, value, plan->type);
		}
		return;
	}

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
	if (plan->type->kind == type_kind_array && (plan->type->qualifiers & type_qualifier_volatile) &&
		!volatile_aggregate) {
		const struct type *element = plan->type;
		while (element->kind == type_kind_array)
			element = ((const struct array_type *)element)->element;
		unsigned width = (unsigned)type_object_size(element);
		const struct ast_initializer_plan_entry **ordered = calloc(plan->entry_count ? plan->entry_count : 1, sizeof(*ordered));
		if (!ordered) {
			free(captures);
			codegen->output_ok = false;
			return;
		}
		size_t count = 0;
		for (const struct ast_initializer_plan_entry *entry = plan->entries; entry; entry = entry->next)
			if (entry->length && entry->kind != ast_initializer_write_zero)
				ordered[count++] = entry;
		qsort(ordered, count, sizeof(*ordered), initializer_offset_order);
		uint64_t position = 0;
		for (size_t n = 0; n <= count; n++) {
			uint64_t next = n == count ? plan->size : ordered[n]->offset;
			assert(next >= position && next <= plan->size && position % width == 0 && next % width == 0);
			if (next > position)
				codegen_volatile_array_range(codegen, codegen_byte_offset(codegen, destination, position),
					next - position, width, false, 0);
			if (n < count) {
				assert(ordered[n]->length % width == 0 && ordered[n]->length <= plan->size - next);
				position = next + ordered[n]->length;
			}
		}
		free(ordered);
		for (const struct ast_initializer_plan_entry *entry = plan->entries; entry; entry = entry->next) {
			if (!entry->length || entry->kind == ast_initializer_write_zero)
				continue;
			size_t i = ((uintptr_t)entry->expression >> 3) & (capacity - 1);
			while (captures[i].expression != entry->expression) {
				assert(captures[i].expression);
				i = (i + 1) & (capacity - 1);
			}
			size_t address = codegen_byte_offset(codegen, destination, entry->offset);
			if (entry->kind == ast_initializer_write_string) {
				size_t source = codegen_byte_offset(codegen, captures[i].value, entry->source_offset);
				codegen_volatile_array_range(codegen, address, entry->length, width, true, source);
			} else {
				assert(entry->kind == ast_initializer_write_expression && entry->length == width);
				codegen_volatile_store(codegen, address, captures[i].value, entry->type);
			}
		}
		free(captures);
		return;
	}
	if (plan->zero_fill) {
		if (volatile_aggregate) codegen_volatile_zero(codegen, destination, plan->size);
		else codegen_zero_bytes(codegen, destination, plan->size);
	}
	for (const struct ast_initializer_plan_entry *entry = plan->entries; entry; entry = entry->next) {
		size_t address, value;

		assert(entry->offset <= plan->size && entry->length <= plan->size - entry->offset);
		if (!entry->length)
			continue;
		address = codegen_byte_offset(codegen, destination, entry->offset);
		if (entry->kind == ast_initializer_write_zero) {
			if (entry->bit_field && (entry->bit_field->bit_width < 32 || type_is_bitint(entry->bit_field->type) ||
				type_value_width(entry->bit_field->type) == 64)) {
				size_t zero = codegen->next_temporary++;
				emit(codegen, "\t%%t%zu =%c copy 0\n", zero,
					qbe_type(entry->bit_field->type));
				(void)codegen_field_store(codegen, address, zero, entry->bit_field, volatile_aggregate);
			} else if (volatile_aggregate)
				codegen_volatile_zero(codegen, address, entry->length);
			else
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
			if (volatile_aggregate) codegen_volatile_copy(codegen, value, address, entry->length, 2);
			else codegen_record_copy(codegen, value, address, entry->length);
		} else {
			assert(entry->kind == ast_initializer_write_expression);
			assert(entry->bit_field || entry->length == type_object_size(entry->type));
			if (entry->bit_field && entry->bit_field->bit_width &&
				(entry->bit_field->bit_width < 32 || type_is_bitint(entry->bit_field->type) || type_value_width(entry->bit_field->type) == 64))
				(void)codegen_field_store(codegen, address, value, entry->bit_field, volatile_aggregate);
			else if (volatile_aggregate)
				codegen_volatile_store(codegen, address, value, entry->type);
			else
				emit(codegen, "\tstore%c %%t%zu, %%t%zu\n", qbe_store_size(entry->type), codegen_storage_bits(codegen, value, entry->type), address);
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
		emit(codegen, "\t%%t%zu =l copy %s", address, literal->object->is_thread_local ? "thread " : "");
		emit_symbol(codegen, name);
		emit(codegen, "\n");
	}
	return address;
}

/* Value conversion tests the whole source, unlike narrow ABI normalization. */
static size_t codegen_truth_value(struct codegen *codegen, size_t value,
	const struct type *type)
{
	size_t result = codegen->next_temporary++;

	emit(codegen, "\t%%t%zu =w cne%c %%t%zu, %s\n", result, qbe_type(type), value,
		type->kind == type_kind_float ? "s_0.0" : type->kind == type_kind_double ? "d_0.0" : "0");
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
	if (type_is_boolean(target))
		return codegen_truth_value(codegen, value, source);
	if (type_is_floating(source) && type_is_floating(target)) {
		result = codegen->next_temporary++;
		instruction = source->kind == target->kind ? "copy" :
			(source->kind == type_kind_float ? "exts" : "truncd");
		emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", result, qbe_type(target), instruction, value);
		return result;
	}
	if (type_is_integer(source) && type_is_floating(target)) {
		bool wide = type_value_width(source) > 32;
		result = codegen->next_temporary++;
		instruction = wide ? (type_is_unsigned(source) ? "ultof" : "sltof") :
			(type_is_unsigned(source) ? "uwtof" : "swtof");
		emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", result, qbe_type(target), instruction, value);
		return result;
	}
	if (type_is_floating(source) && type_is_integer(target)) {
		bool wide = type_value_width(target) > 32;
		result = codegen->next_temporary++;
		instruction = source->kind == type_kind_float ?
			(type_is_unsigned(target) ? "stoui" : "stosi") :
			(type_is_unsigned(target) ? "dtoui" : "dtosi");
		emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", result, wide ? 'l' : 'w', instruction, value);
		return codegen_canonicalize(codegen, result, target);
	}
	result = codegen->next_temporary++;
	if (type_value_width(target) > 32 && type_value_width(source) <= 32)
		instruction = type_is_unsigned(source) ? "extuw" : "extsw";
	emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", result, qbe_type(target), instruction, value);
	return codegen_canonicalize(codegen, result, target);
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

	if (type_value_width(type) <= 32)
		return value;
	count = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =w copy %%t%zu\n", count, value);
	return count;
}

struct update_values {
	size_t previous;
	size_t current;
};

/* Non-native _BitInt arithmetic must wrap at the declared width, not the
 * storage width. Retry a representation-correct libatomic compare-exchange.
 * The initial relaxed load only seeds expected; the RMW gives the ordering. */
static struct update_values codegen_atomic_bitint_rmw(struct codegen *codegen,
	size_t address, size_t right, const struct type *type, const char *instruction,
	bool explicit_order, size_t order)
{
	unsigned width = (unsigned)type_object_size(type);
	char carrier = width == 8 ? 'l' : 'w';
	char store = width == 1 ? 'b' : width == 2 ? 'h' : carrier;
	size_t initial = codegen->next_temporary++, loop = new_label(codegen), done = new_label(codegen);
	size_t failure = 0;
	if (explicit_order) {
		size_t release = codegen->next_temporary++, acqrel = codegen->next_temporary++;
		size_t r = codegen->next_temporary++, a = codegen->next_temporary++, t = codegen->next_temporary++;
		failure = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =w ceqw %%t%zu, 3\n", release, order);
		emit(codegen, "\t%%t%zu =w ceqw %%t%zu, 4\n", acqrel, order);
		emit(codegen, "\t%%t%zu =w mul %%t%zu, 3\n", r, release);
		emit(codegen, "\t%%t%zu =w mul %%t%zu, 2\n", a, acqrel);
		emit(codegen, "\t%%t%zu =w sub %%t%zu, %%t%zu\n", t, order, r);
		emit(codegen, "\t%%t%zu =w sub %%t%zu, %%t%zu\n", failure, t, a);
	}
	emit(codegen, "\t%%t%zu =%c call $__atomic_load_%u(l %%t%zu, w 0)\n", initial, carrier, width, address);
	emit(codegen, "\tstore%c %%t%zu, %%atomic_compound_expected\n", store, initial);
	emit(codegen, "\tjmp @b%zu\n", loop);
	emit_label(codegen, loop);
	size_t loaded = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =%c %s %%atomic_compound_expected\n", loaded, carrier, qbe_load_instruction(type));
	size_t previous = codegen_canonicalize(codegen, loaded, type);
	size_t arithmetic = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =%c %s %%t%zu, %%t%zu\n", arithmetic, carrier, instruction, previous, right);
	size_t current = codegen_canonicalize(codegen, arithmetic, type);
	size_t desired = codegen_storage_bits(codegen, current, type);
	size_t success = codegen->next_temporary++, flag = codegen->next_temporary++;
	if (explicit_order)
		emit(codegen, "\t%%t%zu =w call $__atomic_compare_exchange_%u(l %%t%zu, l %%atomic_compound_expected, %c %%t%zu, w %%t%zu, w %%t%zu)\n", success, width, address, carrier, desired, order, failure);
	else
		emit(codegen, "\t%%t%zu =w call $__atomic_compare_exchange_%u(l %%t%zu, l %%atomic_compound_expected, %c %%t%zu, w 5, w 5)\n", success, width, address, carrier, desired);
	emit(codegen, "\t%%t%zu =w and %%t%zu, 1\n", flag, success);
	emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", flag, done, loop);
	emit_label(codegen, done);
	return (struct update_values) { .previous = previous, .current = current };
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
	bool pointer = node->left->type->kind == type_kind_pointer;

	if (pointer) {
		right = codegen_pointer_index(codegen, node->right);
		if (node->vm_size_local || node->element_size != 1) {
			size_t scaled = codegen->next_temporary++;

			if (node->vm_size_local)
				emit(codegen, "\t%%t%zu =l mul %%t%zu, %%z%zu\n", scaled, right, node->vm_size_local->slot);
			else
				emit(codegen, "\t%%t%zu =l mul %%t%zu, %ju\n", scaled, right, (uintmax_t)node->element_size);
			right = scaled;
		}
	} else {
		right = codegen_expression(codegen, node->right);
		if (node->operation == binary_shift_left || node->operation == binary_shift_right)
			right = codegen_shift_count(codegen, right, node->right->type);
	}
	address = codegen_address(codegen, node->left);
	if ((node->left->type->qualifiers & type_qualifier_atomic) &&
		!pointer &&
		(type_is_boolean(node->left->type) || node->left->type->kind == type_kind_enum ||
		 (type_is_bitint(node->left->type) && !type_bitint_width_native(type_integer_width(node->left->type))) ||
		 type_is_floating(node->calculation_type) ||
		 (node->operation != binary_add && node->operation != binary_subtract &&
		  node->operation != binary_bit_and && node->operation != binary_bit_or &&
		  node->operation != binary_bit_xor))) {
		unsigned width = (unsigned)type_object_size(node->left->type);
		char bits_type = width == 8 ? 'l' : 'w';
		char store_size = width == 1 ? 'b' : width == 2 ? 'h' : bits_type;
		size_t loop = new_label(codegen), done = new_label(codegen);
		size_t initial = codegen->next_temporary++;
		size_t success, flag, desired;

		/* The expected buffer is private to this invocation. On failure the
		 * library replaces it with the observed representation for retry. */
		emit(codegen, "\t%%t%zu =%c call $__atomic_load_%u(l %%t%zu, w 5)\n",
			initial, bits_type, width, address);
		emit(codegen, "\tstore%c %%t%zu, %%atomic_compound_expected\n", store_size, initial);
		emit(codegen, "\tjmp @b%zu\n", loop);
		emit_label(codegen, loop);
		left = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c %s %%atomic_compound_expected\n", left,
			qbe_type(node->left->type), qbe_load_instruction(node->left->type));
		left = codegen_canonicalize(codegen, left, node->left->type);
		left = codegen_convert_value(codegen, left, node->left->type, node->calculation_type);
		value = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c %s %%t%zu, %%t%zu\n", value,
			qbe_type(node->calculation_type), binary_instruction(node->operation, node->calculation_type), left, right);
		value = codegen_convert_value(codegen, value, node->calculation_type, node->expression.type);
		desired = atomic_to_bits(codegen, value, node->left->type);
		success = codegen->next_temporary++;
		flag = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =w call $__atomic_compare_exchange_%u(l %%t%zu, l %%atomic_compound_expected, %c %%t%zu, w 5, w 5)\n",
			success, width, address, bits_type, desired);
		emit(codegen, "\t%%t%zu =w and %%t%zu, 1\n", flag, success);
		emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", flag, done, loop);
		emit_label(codegen, done);
		return value;
	}
	if (node->left->type->qualifiers & type_qualifier_atomic) {
		const char *atomic_op;
		unsigned width = (unsigned)type_object_size(node->left->type);
		bool wide = width == 8;

		switch (node->operation) {
		case binary_add: atomic_op = "add"; break;
		case binary_subtract: atomic_op = "sub"; break;
		case binary_bit_and: atomic_op = "and"; break;
		case binary_bit_or: atomic_op = "or"; break;
		case binary_bit_xor: atomic_op = "xor"; break;
		default: abort(); /* semantic analysis excludes unsupported operations */
		}
		if (!wide && type_value_width(node->right->type) == 64) {
			size_t narrowed = codegen->next_temporary++;

			emit(codegen, "\t%%t%zu =w copy %%t%zu\n", narrowed, right);
			right = narrowed;
		}
		value = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c call $__atomic_%s_fetch_%u(l %%t%zu, %c %%t%zu, w 5)\n",
			value, wide ? 'l' : 'w', atomic_op, width,
			address, wide ? 'l' : 'w', right);
		return codegen_canonicalize(codegen, value, node->left->type);
	}
	if (codegen_bit_field(node->left))
		left = codegen_field_load(codegen, address, codegen_bit_field(node->left), (node->left->type->qualifiers & type_qualifier_volatile) != 0);
	else if (node->left->type->qualifiers & type_qualifier_volatile)
		left = codegen_volatile_load(codegen, address, node->left->type);
	else {
		left = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", left, qbe_type(node->left->type),
			qbe_load_instruction(node->left->type), address);
	}
	left = codegen_canonicalize(codegen, left, node->left->type);
	left = codegen_convert_value(codegen, left, node->left->type, node->calculation_type);
	value = codegen->next_temporary++;
	if (pointer)
		instruction = node->operation == binary_add ? "add" : "sub";
	else
		instruction = binary_instruction(node->operation, node->calculation_type);
	emit(codegen, "\t%%t%zu =%c %s %%t%zu, %%t%zu\n", value, qbe_type(node->calculation_type),
		instruction, left, right);
	value = codegen_convert_value(codegen, value, node->calculation_type, node->expression.type);
	if (codegen_bit_field(node->left))
		value = codegen_field_store(codegen, address, value, codegen_bit_field(node->left), (node->left->type->qualifiers & type_qualifier_volatile) != 0);
	else if (node->left->type->qualifiers & type_qualifier_volatile)
		codegen_volatile_store(codegen, address, value, node->left->type);
	else
		emit(codegen, "\tstore%c %%t%zu, %%t%zu\n", qbe_store_size(node->left->type), codegen_storage_bits(codegen, value, node->left->type), address);
	return value;
}

/* Floating, boolean and enum updates need the same representation-aware
 * compare-exchange loop as compound assignments, with the old value retained
 * for postfix results. The operand address has already been evaluated once. */
static struct update_values codegen_atomic_scalar_update(struct codegen *codegen,
	size_t address, const struct type *type, const struct type *calculation_type,
	enum update_operator operation)
{
	unsigned width = (unsigned)type_object_size(type);
	char bits_type = width == 8 ? 'l' : 'w';
	char store_size = width == 1 ? 'b' : width == 2 ? 'h' : bits_type;
	size_t initial = codegen->next_temporary++, loop = new_label(codegen), done = new_label(codegen);
	emit(codegen, "\t%%t%zu =%c call $__atomic_load_%u(l %%t%zu, w 5)\n", initial, bits_type, width, address);
	emit(codegen, "\tstore%c %%t%zu, %%atomic_compound_expected\n", store_size, initial);
	emit(codegen, "\tjmp @b%zu\n", loop);
	emit_label(codegen, loop);
	size_t previous = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =%c %s %%atomic_compound_expected\n", previous,
		qbe_type(type), qbe_load_instruction(type));
	previous = codegen_canonicalize(codegen, previous, type);
	size_t arithmetic = codegen_convert_value(codegen, previous, type, calculation_type);
	size_t value = codegen->next_temporary++;
	const char *one = type_is_floating(calculation_type) ?
		(calculation_type->kind == type_kind_float ? "s_1.0" : "d_1.0") : "1";
	emit(codegen, "\t%%t%zu =%c %s %%t%zu, %s\n", value, qbe_type(calculation_type),
		operation == update_increment ? "add" : "sub", arithmetic, one);
	value = codegen_convert_value(codegen, value, calculation_type, type);
	size_t desired = atomic_to_bits(codegen, value, type);
	size_t success = codegen->next_temporary++, flag = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =w call $__atomic_compare_exchange_%u(l %%t%zu, l %%atomic_compound_expected, %c %%t%zu, w 5, w 5)\n",
		success, width, address, bits_type, desired);
	emit(codegen, "\t%%t%zu =w and %%t%zu, 1\n", flag, success);
	emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", flag, done, loop);
	emit_label(codegen, done);
	return (struct update_values) { .previous = previous, .current = value };
}

/* Address, load and store each occur once; the caller selects old or new. */
static struct update_values codegen_update(struct codegen *codegen,
	const struct ast_expression *operand, enum update_operator operation,
	const struct type *calculation_type, uint64_t element_size,
	const struct ast_local_declaration *vm_size_local)
{
	size_t address = codegen_address(codegen, operand);
	size_t previous = codegen->next_temporary++;
	size_t value = codegen->next_temporary++;
	uint64_t step = element_size ? element_size : 1;

	if ((operand->type->qualifiers & type_qualifier_atomic) &&
		(type_is_boolean(operand->type) || type_is_floating(operand->type) ||
		 operand->type->kind == type_kind_enum))
		return codegen_atomic_scalar_update(codegen, address, operand->type, calculation_type, operation);
	if ((operand->type->qualifiers & type_qualifier_atomic) && type_is_bitint(operand->type) &&
		!type_bitint_width_native(type_integer_width(operand->type))) {
		size_t one = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c copy 1\n", one, qbe_type(operand->type));
		return codegen_atomic_bitint_rmw(codegen, address, one, operand->type,
			operation == update_increment ? "add" : "sub", false, 0);
	}
	if (operand->type->qualifiers & type_qualifier_atomic) {
		unsigned width = (unsigned)type_object_size(operand->type);
		bool wide = width == 8;

		if (vm_size_local) {
			emit(codegen, "\t%%t%zu =l call $__atomic_fetch_%s_%u(l %%t%zu, l %%z%zu, w 5)\n",
				previous, operation == update_increment ? "add" : "sub", width, address, vm_size_local->slot);
			emit(codegen, "\t%%t%zu =l %s %%t%zu, %%z%zu\n", value,
				operation == update_increment ? "add" : "sub", previous, vm_size_local->slot);
		} else {
			emit(codegen, "\t%%t%zu =%c call $__atomic_fetch_%s_%u(l %%t%zu, %c %ju, w 5)\n",
				previous, wide ? 'l' : 'w', operation == update_increment ? "add" : "sub",
				width, address, wide ? 'l' : 'w', (uintmax_t)step);
			emit(codegen, "\t%%t%zu =%c %s %%t%zu, %ju\n", value, wide ? 'l' : 'w',
				operation == update_increment ? "add" : "sub", previous, (uintmax_t)step);
		}
		previous = codegen_canonicalize(codegen, previous, operand->type);
		value = codegen_canonicalize(codegen, value, operand->type);
		return (struct update_values) { .previous = previous, .current = value };
	}
	if (codegen_bit_field(operand))
		previous = codegen_field_load(codegen, address, codegen_bit_field(operand), (operand->type->qualifiers & type_qualifier_volatile) != 0);
	else if (operand->type->qualifiers & type_qualifier_volatile)
		previous = codegen_volatile_load(codegen, address, operand->type);
	else
		emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", previous, qbe_type(calculation_type),
			qbe_load_instruction(operand->type), address);
	previous = codegen_canonicalize(codegen, previous, operand->type);
	size_t arithmetic = previous;
	bool wide_field = codegen_bit_field(operand) && type_value_width(operand->type) > 32;
	if (wide_field)
		arithmetic = codegen_convert_value(codegen, previous, operand->type, calculation_type);
	if (type_is_floating(calculation_type))
		emit(codegen, "\t%%t%zu =%c %s %%t%zu, %s\n", value, qbe_type(calculation_type),
			operation == update_increment ? "add" : "sub", arithmetic,
			calculation_type->kind == type_kind_float ? "s_1.0" : "d_1.0");
	else if (vm_size_local)
		emit(codegen, "\t%%t%zu =l %s %%t%zu, %%z%zu\n", value,
			operation == update_increment ? "add" : "sub", arithmetic, vm_size_local->slot);
	else
		emit(codegen, "\t%%t%zu =%c %s %%t%zu, %llu\n", value, qbe_type(calculation_type),
			operation == update_increment ? "add" : "sub", arithmetic, (unsigned long long)step);
	if (wide_field)
		value = codegen_convert_value(codegen, value, calculation_type, operand->type);
	/* _Bool conversion tests the promoted value, never its low bit. */
	if (type_is_boolean(operand->type))
		value = codegen_truth_value(codegen, value, calculation_type);
	else
		value = codegen_canonicalize(codegen, value, operand->type);
	if (codegen_bit_field(operand))
		value = codegen_field_store(codegen, address, value, codegen_bit_field(operand), (operand->type->qualifiers & type_qualifier_volatile) != 0);
	else if (operand->type->qualifiers & type_qualifier_volatile)
		codegen_volatile_store(codegen, address, value, operand->type);
	else
		emit(codegen, "\tstore%c %%t%zu, %%t%zu\n", qbe_store_size(operand->type), codegen_storage_bits(codegen, value, operand->type), address);
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
		argument = argument->next) {
		size_t value_arg = codegen_expression(codegen, argument->value);
		/* Clang reads the storage-width value for non-native bit-precise
		 * ellipsis arguments; padding bits must not carry sign extension. */
		if (node->signature->variadic && count >= node->signature->parameter_count &&
			type_is_bitint(argument->value->type) &&
			!type_bitint_width_native(type_integer_width(argument->value->type))) {
			unsigned width = type_integer_width(argument->value->type);
			unsigned carrier = width <= 32 ? 32 : 64;
			size_t shifted = codegen->next_temporary++;
			size_t masked = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =%c shl %%t%zu, %u\n", shifted,
				carrier == 32 ? 'w' : 'l', value_arg, carrier - width);
			emit(codegen, "\t%%t%zu =%c shr %%t%zu, %u\n", masked,
				carrier == 32 ? 'w' : 'l', shifted, carrier - width);
			value_arg = masked;
		}
		if (type_is_record(argument->value->type)) {
			size_t destination = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =l copy %%a%zu\n", destination, argument->abi_slot);
			codegen_record_copy(codegen, value_arg, destination, type_object_size(argument->value->type));
			value_arg = destination;
		}
		arguments[count++] = value_arg;
	}
	assert(count == node->argument_count && count <= ast_max_arguments);
	assert((node->expression.type->kind == type_kind_void) == (value == NULL));
	if (value) {
		*value = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =", *value);
		emit_abi_type(codegen, node->expression.type);
		emit(codegen, " call ");
	} else {
		emit(codegen, "\tcall ");
	}
	if (node->function) {
		struct token name = node->function->name;

		emit_symbol(codegen, name);
		emit(codegen, "(");
	} else {
		emit(codegen, "%%t%zu(", target);
	}
	count = 0;
	for (const struct ast_argument *argument = node->arguments; argument; argument = argument->next) {
		if (node->signature->variadic && count == node->signature->parameter_count)
			emit(codegen, "%s...", count ? ", " : "");
		emit(codegen, "%s", (count || (node->signature->variadic && !node->signature->parameter_count)) ? ", " : "");
		if (node->signature->variadic && count >= node->signature->parameter_count &&
			type_is_bitint(argument->value->type) &&
			!type_bitint_width_native(type_integer_width(argument->value->type)) &&
			type_object_size(argument->value->type) <= 2)
			emit(codegen, "%s", type_object_size(argument->value->type) == 1 ? "ub" : "uh");
		else
			emit_abi_type(codegen, argument->value->type);
		emit(codegen, " %%t%zu", arguments[count]);
		count++;
	}
	if (node->signature->variadic && count == node->signature->parameter_count)
		emit(codegen, "%s...", count ? ", " : "");
	emit(codegen, ")\n");
	if (value && !type_is_record(node->expression.type))
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

/* SysV va_list exposes separate GP and FP register cursors. Aggregate fetches
 * consume all required registers atomically or fall back to the overflow area.
 * QBE's vaarg handles only scalar base types, so materialize record bytes in
 * a rounded entry slot from the ABI register-save area or stack. */
static size_t codegen_va_record(struct codegen *codegen,
	const struct ast_va_expression *node, size_t list)
{
	struct aggregate_abi abi;
	bool valid = type_aggregate_abi_for_mode(node->expression.type, &abi,
		codegen->abi->legacy_clang_abi, codegen->abi->gcc12_zero_width_abi);
	assert(valid);
	(void)valid;
	size_t result = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =l copy %%q%zu\n", result, node->record_abi_slot);
	size_t overflow = new_label(codegen), done = new_label(codegen);
	if (abi.size <= 16) {
		unsigned gp_count = 0, fp_count = 0;
		for (unsigned i = 0; i < (abi.size + 7) / 8; i++) {
			gp_count += abi.classes[i] == aggregate_abi_integer;
			fp_count += abi.classes[i] == aggregate_abi_sse;
		}
		size_t gp = codegen->next_temporary++, fp = codegen->next_temporary++;
		size_t fp_addr = codegen_byte_offset(codegen, list, 4);
		size_t gp_ok = codegen->next_temporary++, fp_ok = codegen->next_temporary++;
		size_t both = codegen->next_temporary++, registers = new_label(codegen);
		emit(codegen, "\t%%t%zu =w loadw %%t%zu\n", gp, list);
		emit(codegen, "\t%%t%zu =w loadw %%t%zu\n", fp, fp_addr);
		emit(codegen, "\t%%t%zu =w culew %%t%zu, %u\n", gp_ok, gp, 48 - 8 * gp_count);
		emit(codegen, "\t%%t%zu =w culew %%t%zu, %u\n", fp_ok, fp, 176 - 16 * fp_count);
		emit(codegen, "\t%%t%zu =w and %%t%zu, %%t%zu\n", both, gp_ok, fp_ok);
		emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", both, registers, overflow);
		emit_label(codegen, registers);
		size_t save_ptr = codegen_byte_offset(codegen, list, 16);
		size_t save = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =l loadl %%t%zu\n", save, save_ptr);
		unsigned gp_index = 0, fp_index = 0;
		for (unsigned i = 0; i < (abi.size + 7) / 8; i++) {
			bool integer = abi.classes[i] == aggregate_abi_integer;
			size_t base = integer ? gp : fp;
			unsigned increment = integer ? 8 * gp_index++ : 16 * fp_index++;
			size_t off = codegen->next_temporary++, address = codegen->next_temporary++;
			size_t bits = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =l extuw %%t%zu\n", off, base);
			emit(codegen, "\t%%t%zu =l add %%t%zu, %%t%zu\n", address, save, off);
			if (increment) address = codegen_byte_offset(codegen, address, increment);
			emit(codegen, "\t%%t%zu =l loadl %%t%zu\n", bits, address);
			size_t target = codegen_byte_offset(codegen, result, i * 8);
			emit(codegen, "\tstorel %%t%zu, %%t%zu\n", bits, target);
		}
		if (gp_count) {
			size_t next = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =w add %%t%zu, %u\n", next, gp, gp_count * 8);
			emit(codegen, "\tstorew %%t%zu, %%t%zu\n", next, list);
		}
		if (fp_count) {
			size_t next = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =w add %%t%zu, %u\n", next, fp, fp_count * 16);
			emit(codegen, "\tstorew %%t%zu, %%t%zu\n", next, fp_addr);
		}
		emit(codegen, "\tjmp @b%zu\n", done);
	} else {
		emit(codegen, "\tjmp @b%zu\n", overflow);
	}
	emit_label(codegen, overflow);
	size_t pointer = codegen_byte_offset(codegen, list, 8);
	size_t address = codegen->next_temporary++, next = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =l loadl %%t%zu\n", address, pointer);
	if (abi.alignment > 8) {
		size_t shifted = codegen->next_temporary++, aligned = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =l add %%t%zu, 15\n", shifted, address);
		emit(codegen, "\t%%t%zu =l and %%t%zu, -16\n", aligned, shifted);
		address = aligned;
	}
	emit(codegen, "\t%%t%zu =l add %%t%zu, %u\n", next, address, (abi.size + 7) & ~7u);
	emit(codegen, "\tstorel %%t%zu, %%t%zu\n", next, pointer);
	codegen_record_copy(codegen, address, result, abi.size);
	emit(codegen, "\tjmp @b%zu\n", done);
	emit_label(codegen, done);
	return result;
}

/* Return the temporary containing the value; operands are emitted first. */
static size_t codegen_expression(struct codegen *codegen,
	const struct ast_expression *expression)
{
	size_t temporary;

	assert(type_is_scalar(expression->type) || type_is_record(expression->type));
	switch (expression->kind) {
	case expression_atomic_fetch: {
		const struct ast_atomic_expression *node = (const struct ast_atomic_expression *)expression;
		const struct type *referent = ((const struct pointer_type *)node->object->type)->referent;
		unsigned width = (unsigned)type_object_size(referent);
		bool wide = width == 8;
		char value_type = wide ? 'l' : 'w';
		size_t object = codegen_expression(codegen, node->object);
		size_t expected = node->expected ? codegen_expression(codegen, node->expected) : 0;
		size_t argument = node->argument ? codegen_expression(codegen, node->argument) : 0;
		size_t order = node->order ? codegen_expression(codegen, node->order) : 0;
		size_t failure_order = node->failure_order ? codegen_expression(codegen, node->failure_order) : 0;
		const char *operation;
		size_t argument_bits = node->argument ? atomic_to_bits(codegen, argument, referent) : 0;

		if (node->pointer_element_size > 1) {
			size_t scaled = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =l mul %%t%zu, %ju\n", scaled, argument_bits,
				(uintmax_t)node->pointer_element_size);
			argument_bits = scaled;
		}
		if (node->operation == ast_atomic_is_lock_free) {
			size_t result = codegen->next_temporary++;
			temporary = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =w call $__atomic_is_lock_free(l %u, l %%t%zu)\n",
				result, width, object);
			emit(codegen, "\t%%t%zu =w and %%t%zu, 1\n", temporary, result);
			return temporary;
		}
		if (node->operation == ast_atomic_compare_exchange) {
			size_t result = codegen->next_temporary++;
			temporary = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =w call $__atomic_compare_exchange_%u(l %%t%zu, l %%t%zu, %c %%t%zu, ",
				result, width, object, expected, value_type, argument_bits);
			if (node->order)
				emit(codegen, "w %%t%zu, w %%t%zu)\n", order, failure_order);
			else
				emit(codegen, "w 5, w 5)\n");
			emit(codegen, "\t%%t%zu =w and %%t%zu, 1\n", temporary, result);
			return temporary;
		}
		if (node->operation == ast_atomic_load) {
			temporary = codegen->next_temporary++;
			if (node->order)
				emit(codegen, "\t%%t%zu =%c call $__atomic_load_%u(l %%t%zu, w %%t%zu)\n", temporary, value_type, width, object, order);
			else
				emit(codegen, "\t%%t%zu =%c call $__atomic_load_%u(l %%t%zu, w 5)\n", temporary, value_type, width, object);
			return atomic_from_bits(codegen, temporary, referent);
		}
		if (node->operation == ast_atomic_store) {
			if (node->order)
				emit(codegen, "\tcall $__atomic_store_%u(l %%t%zu, %c %%t%zu, w %%t%zu)\n", width, object, value_type, argument_bits, order);
			else
				emit(codegen, "\tcall $__atomic_store_%u(l %%t%zu, %c %%t%zu, w 5)\n", width, object, value_type, argument_bits);
			return argument;
		}
		if (type_is_bitint(referent) && !type_bitint_width_native(type_integer_width(referent)) &&
			(node->operation == ast_atomic_fetch_add || node->operation == ast_atomic_fetch_sub ||
			 node->operation == ast_atomic_fetch_and || node->operation == ast_atomic_fetch_or ||
			 node->operation == ast_atomic_fetch_xor)) {
			const char *op = node->operation == ast_atomic_fetch_add ? "add" :
				node->operation == ast_atomic_fetch_sub ? "sub" :
				node->operation == ast_atomic_fetch_and ? "and" :
				node->operation == ast_atomic_fetch_or ? "or" : "xor";
			return codegen_atomic_bitint_rmw(codegen, object, argument, referent, op,
				node->order != NULL, order).previous;
		}
		switch (node->operation) {
		case ast_atomic_fetch_add: operation = "fetch_add"; break;
		case ast_atomic_fetch_sub: operation = "fetch_sub"; break;
		case ast_atomic_fetch_and: operation = "fetch_and"; break;
		case ast_atomic_fetch_or: operation = "fetch_or"; break;
		case ast_atomic_fetch_xor: operation = "fetch_xor"; break;
		case ast_atomic_exchange: operation = "exchange"; break;
		default: abort();
		}
		temporary = codegen->next_temporary++;
		if (node->order)
			emit(codegen, "\t%%t%zu =%c call $__atomic_%s_%u(l %%t%zu, %c %%t%zu, w %%t%zu)\n",
				temporary, value_type, operation, width, object, value_type, argument_bits, order);
		else
			emit(codegen, "\t%%t%zu =%c call $__atomic_%s_%u(l %%t%zu, %c %%t%zu, w 5)\n",
				temporary, value_type, operation, width, object, value_type, argument_bits);
		return atomic_from_bits(codegen, temporary, referent);
	}
	case expression_va: {
		const struct ast_va_expression *node = (const struct ast_va_expression *)expression;
		size_t list = codegen_expression(codegen, node->list);

		assert(node->operation == ast_va_arg);
		if (type_is_record(expression->type))
			return codegen_va_record(codegen, node, list);
		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c vaarg %%t%zu\n", temporary,
			qbe_type(expression->type), list);
		return codegen_canonicalize(codegen, temporary, expression->type);
	}
	case expression_compound_literal:
		return codegen_compound_literal(codegen, (const struct ast_compound_literal_expression *)expression);
	case expression_sizeof: {
		const struct ast_sizeof_expression *node = (const struct ast_sizeof_expression *)expression;
		if (node->vla_local) {
			/* Tracked row expressions evaluate their pointer and index effects. */
			if (node->evaluate_vla_operand)
				(void)codegen_address(codegen, node->operand);
			size_t value = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =l copy %%z%zu\n", value, node->vla_local->slot);
			return value;
		}
		return codegen_layout_constant(codegen, node->size);
	}
	case expression_sizeof_type: {
		const struct ast_sizeof_type_expression *node = (const struct ast_sizeof_type_expression *)expression;
		if (node->vla_bound) {
			size_t bound = codegen_expression(codegen, node->vla_bound);
			size_t wide = codegen_convert_value(codegen, bound, node->vla_bound->type, &type_ulong);
			size_t positive = codegen->next_temporary++, within = codegen->next_temporary++;
			size_t valid = codegen->next_temporary++, size = codegen->next_temporary++;
			size_t good = new_label(codegen), bad = new_label(codegen);

			emit(codegen, "\t%%t%zu =w cnel %%t%zu, 0\n", positive, wide);
			emit(codegen, "\t%%t%zu =w culel %%t%zu, %ju\n", within, wide,
				(uintmax_t)(ast_max_local_storage / node->vla_element_size));
			emit(codegen, "\t%%t%zu =w and %%t%zu, %%t%zu\n", valid, positive, within);
			emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", valid, good, bad);
			emit_label(codegen, bad);
			emit(codegen, "\tcall $abort()\n\thlt\n");
			emit_label(codegen, good);
			emit(codegen, "\t%%t%zu =l mul %%t%zu, %ju\n", size, wide, (uintmax_t)node->vla_element_size);
			return size;
		}
		return codegen_layout_constant(codegen, node->size);
	}
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
	case expression_enum_constant: {
		const struct ast_enum_constant_expression *node =
			(const struct ast_enum_constant_expression *)expression;
		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c copy %ju\n", temporary, qbe_type(expression->type),
			(uintmax_t)node->bits);
		return codegen_canonicalize(codegen, temporary, expression->type);
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
	case expression_floating: {
		const struct ast_integer_expression *node = (const struct ast_integer_expression *)expression;
		size_t bits = codegen->next_temporary++;
		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c copy %ju\n", bits,
			expression->type->kind == type_kind_float ? 'w' : 'l', (uintmax_t)node->value);
		emit(codegen, "\t%%t%zu =%c cast %%t%zu\n", temporary, qbe_type(expression->type), bits);
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
			if (type_is_floating(expression->type)) {
				size_t bits = codegen->next_temporary++;
				size_t flipped = codegen->next_temporary++;
				bool single = expression->type->kind == type_kind_float;
				emit(codegen, "\t%%t%zu =%c cast %%t%zu\n", bits, single ? 'w' : 'l', operand);
				emit(codegen, "\t%%t%zu =%c xor %%t%zu, %s\n", flipped, single ? 'w' : 'l', bits,
					single ? "2147483648" : "9223372036854775808");
				emit(codegen, "\t%%t%zu =%c cast %%t%zu\n", temporary, qbe_type(expression->type), flipped);
			} else
				emit(codegen, "\t%%t%zu =%c sub 0, %%t%zu\n", temporary, qbe_type(expression->type), operand);
			break;
		case unary_complement:
			emit(codegen, "\t%%t%zu =%c xor %%t%zu, -1\n", temporary, qbe_type(expression->type), operand);
			break;
		case unary_not:
			emit(codegen, "\t%%t%zu =w ceq%c %%t%zu, %s\n", temporary, qbe_type(node->operand->type), operand,
				node->operand->type->kind == type_kind_float ? "s_0.0" : node->operand->type->kind == type_kind_double ? "d_0.0" : "0");
			break;
		}
		return (type_is_bitint(expression->type) || type_uses_field_integer_representation(expression->type)) ?
			codegen_canonicalize(codegen, temporary, expression->type) : temporary;
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
		return (type_is_bitint(expression->type) || type_uses_field_integer_representation(expression->type)) ?
			codegen_canonicalize(codegen, temporary, expression->type) : temporary;
	}
	case expression_pointer_offset: {
		const struct ast_pointer_offset_expression *node =
			(const struct ast_pointer_offset_expression *)expression;
		size_t base = codegen_expression(codegen, node->base);
		size_t index = codegen_pointer_index(codegen, node->index);
		size_t scaled = codegen->next_temporary++;

		if (node->vm_size_local)
			emit(codegen, "\t%%t%zu =l mul %%t%zu, %%z%zu\n", scaled, index,
				node->vm_size_local->slot);
		else
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
		if (node->vm_size_local)
			emit(codegen, "\t%%t%zu =l div %%t%zu, %%z%zu\n", temporary, bytes,
				node->vm_size_local->slot);
		else
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
		if (codegen_bit_field(node->operand))
			return codegen_field_load(codegen, address, codegen_bit_field(node->operand), (node->operand->type->qualifiers & type_qualifier_volatile) != 0);
		if (node->operand->type->qualifiers & type_qualifier_atomic) {
			/* libatomic's ABI memory order 5 is __ATOMIC_SEQ_CST. */
			unsigned width = (unsigned)type_object_size(node->operand->type);
			bool wide = width == 8;
			emit(codegen, "\t%%t%zu =%c call $__atomic_load_%u(l %%t%zu, w 5)\n",
				temporary, wide ? 'l' : 'w', width, address);
			return atomic_from_bits(codegen, temporary, node->operand->type);
		}
		if (type_is_record(expression->type)) {
			/* Captures live in entry-allocated slots, never loop allocations.
			 * Later writes to the original cannot rewrite this value. */
			emit(codegen, "\t%%t%zu =l copy %%r%zu\n", temporary, node->record_temporary_slot);
			if (contains_volatile(node->operand->type))
				codegen_volatile_copy(codegen, address, temporary, type_object_size(expression->type), 1);
			else codegen_record_copy(codegen, address, temporary, type_object_size(expression->type));
			return temporary;
		}
		if (node->operand->type->qualifiers & type_qualifier_volatile)
			return codegen_volatile_load(codegen, address, node->operand->type);
		emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", temporary,
			qbe_type(expression->type), qbe_load_instruction(expression->type), address);
		return codegen_canonicalize(codegen, temporary, expression->type);
	}
	case expression_postfix_update: {
		const struct ast_postfix_update_expression *node = (const struct ast_postfix_update_expression *)expression;
		struct update_values values = codegen_update(codegen, node->operand, node->operation,
			node->calculation_type, node->element_size, node->vm_size_local);

		return values.previous;
	}
	case expression_prefix_update: {
		const struct ast_prefix_update_expression *node = (const struct ast_prefix_update_expression *)expression;
		struct update_values values = codegen_update(codegen, node->operand, node->operation,
			node->calculation_type, node->element_size, node->vm_size_local);

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

		if (codegen_bit_field(node->left))
			value = codegen_field_store(codegen, address, value, codegen_bit_field(node->left), (node->left->type->qualifiers & type_qualifier_volatile) != 0);
		else if (node->left->type->qualifiers & type_qualifier_atomic) {
			unsigned width = (unsigned)type_object_size(node->left->type);
			bool wide = width == 8;
			size_t bits = atomic_to_bits(codegen, value, node->left->type);
			emit(codegen, "\tcall $__atomic_store_%u(l %%t%zu, %c %%t%zu, w 5)\n",
				width, address, wide ? 'l' : 'w', bits);
		}
		else if (type_is_record(node->left->type)) {
			if (contains_volatile(node->left->type))
				codegen_volatile_copy(codegen, value, address, type_object_size(node->left->type), 2);
			else codegen_record_copy(codegen, value, address, type_object_size(node->left->type));
		} else if (node->left->type->qualifiers & type_qualifier_volatile)
			codegen_volatile_store(codegen, address, value, node->left->type);
		else
			emit(codegen, "\tstore%c %%t%zu, %%t%zu\n", qbe_store_size(node->left->type), codegen_storage_bits(codegen, value, node->left->type), address);
		return value;
	}
	case expression_member: {
		size_t address = codegen_address(codegen, expression);

		if (type_is_record(expression->type))
			return address;
		if (codegen_bit_field(expression))
			return codegen_field_load(codegen, address, codegen_bit_field(expression), (expression->type->qualifiers & type_qualifier_volatile) != 0);
		if (expression->type->qualifiers & type_qualifier_volatile)
			return codegen_volatile_load(codegen, address, expression->type);
		temporary = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =%c %s %%t%zu\n", temporary,
			qbe_type(expression->type), qbe_load_instruction(expression->type), address);
		return codegen_canonicalize(codegen, temporary, expression->type);
	}
	case expression_function_designator:
	case expression_generic:
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
	case expression_va: {
		const struct ast_va_expression *node = (const struct ast_va_expression *)expression;
		size_t destination = codegen_expression(codegen, node->list);
		if (node->operation == ast_va_start)
			emit(codegen, "\tvastart %%t%zu\n", destination);
		else if (node->operation == ast_va_copy) {
			size_t source = codegen_expression(codegen, node->source);
			codegen_record_copy(codegen, source, destination, 24);
		} else
			assert(node->operation == ast_va_end);
		return;
	}
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
		uint64_t bits = label->bits;
		unsigned width = type_integer_width(node->control->type);

		/* Constant evaluation stores low-width bits; signed QBE word/long
		 * control values are sign-extended to their carrier width. */
		if (width < 64 && !type_is_unsigned(node->control->type) &&
			(bits & (UINT64_C(1) << (width - 1))))
			bits |= UINT64_MAX << width;
		emit(codegen, "\t%%t%zu =w ceq%c %%t%zu, %llu\n", comparison,
			qbe_type(node->control->type), control, (unsigned long long)(width <= 32 ? (uint32_t)bits : bits));
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
			if (contains_volatile(local->type))
				codegen_volatile_copy(codegen, value, address, type_object_size(local->type), 2);
			else codegen_record_copy(codegen, value, address, type_object_size(local->type));
		} else if (local->type->qualifiers & type_qualifier_volatile) {
			size_t address = codegen->next_temporary++;
			emit(codegen, "\t%%t%zu =l copy %%v%zu\n", address, local->slot);
			codegen_volatile_store(codegen, address, value, local->type);
		} else
			emit(codegen, "\tstore%c %%t%zu, %%v%zu\n", qbe_store_size(local->type), codegen_storage_bits(codegen, value, local->type), local->slot);
	}
}

/* Align a QBE alloc16 result inside the reserved padding. `name` is a
 * fixed compiler-generated temporary namespace (v for locals, r for record
 * captures); it never contains user-controlled text. */
static void codegen_fixed_slot(struct codegen *codegen, char name, size_t slot,
	uint64_t bytes, unsigned alignment)
{
	if (alignment < 4)
		alignment = 4;
	if (alignment <= 16) {
		emit(codegen, "\t%%%c%zu =l alloc%u %ju\n", name, slot, alignment, (uintmax_t)bytes);
		return;
	}
	size_t raw = codegen->next_temporary++, biased = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =l alloc16 %ju\n", raw,
		(uintmax_t)(bytes + type_stack_alignment_padding(alignment)));
	emit(codegen, "\t%%t%zu =l add %%t%zu, %u\n", biased, raw, alignment - 1);
	emit(codegen, "\t%%%c%zu =l and %%t%zu, -%u\n", name, slot, biased, alignment);
}

/* A VM pointer owns only a saved type size, not dynamic array storage. Its
 * bound is checked against the same 1 MiB type limit as sizeof(type VLA). */
static void codegen_vm_pointer_bound(struct codegen *codegen, const struct ast_local_declaration *local)
{
	size_t bound = codegen_expression(codegen, local->vm_pointer_bound);
	size_t wide = codegen_convert_value(codegen, bound, local->vm_pointer_bound->type, &type_ulong);
	size_t positive = codegen->next_temporary++, within = codegen->next_temporary++;
	size_t valid = codegen->next_temporary++;
	size_t good = new_label(codegen), bad = new_label(codegen);
	emit(codegen, "\t%%t%zu =w cnel %%t%zu, 0\n", positive, wide);
	emit(codegen, "\t%%t%zu =w culel %%t%zu, %ju\n", within, wide,
		(uintmax_t)(ast_max_local_storage / local->vm_pointer_element_size));
	emit(codegen, "\t%%t%zu =w and %%t%zu, %%t%zu\n", valid, positive, within);
	emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", valid, good, bad);
	emit_label(codegen, bad);
	emit(codegen, "\tcall $abort()\n\thlt\n");
	emit_label(codegen, good);
	emit(codegen, "\t%%z%zu =l mul %%t%zu, %ju\n", local->slot, wide,
		(uintmax_t)local->vm_pointer_element_size);
}

/* Each execution allocates from a cumulative runtime budget; storage is not
 * reclaimed until return. Invalid bounds terminate before allocation. */
static void codegen_vla(struct codegen *codegen, const struct ast_local_declaration *local)
{
	const struct array_type *array = (const struct array_type *)local->type;
	size_t bound = codegen_expression(codegen, local->vla_bound);
	size_t wide = codegen_convert_value(codegen, bound, local->vla_bound->type, &type_ulong);
	size_t positive = codegen->next_temporary++;
	size_t within = codegen->next_temporary++;
	size_t remaining = codegen->next_temporary++;
	size_t fits = codegen->next_temporary++;
	size_t positive_and_within = codegen->next_temporary++;
	size_t valid = codegen->next_temporary++;
	size_t new_remaining = codegen->next_temporary++;
	size_t good = new_label(codegen), bad = new_label(codegen);
	unsigned alignment = type_object_alignment(array->element);
	if (local->alignment > alignment)
		alignment = local->alignment;
	if (alignment < 4)
		alignment = 4;
	size_t charged = 0;
	if (alignment > 16)
		charged = codegen->next_temporary++;
	emit(codegen, "\t%%t%zu =w cnel %%t%zu, 0\n", positive, wide);
	emit(codegen, "\t%%t%zu =w culel %%t%zu, %ju\n", within, wide, (uintmax_t)local->vla_max_count);
	emit(codegen, "\t%%z%zu =l mul %%t%zu, %ju\n", local->slot, wide,
		(uintmax_t)type_object_size(array->element));
	if (alignment > 16)
		emit(codegen, "\t%%t%zu =l add %%z%zu, %u\n", charged, local->slot,
			type_stack_alignment_padding(alignment));
	emit(codegen, "\t%%t%zu =l loadl %%vla_budget\n", remaining);
	if (alignment > 16)
		emit(codegen, "\t%%t%zu =w culel %%t%zu, %%t%zu\n", fits, charged, remaining);
	else
		emit(codegen, "\t%%t%zu =w culel %%z%zu, %%t%zu\n", fits, local->slot, remaining);
	emit(codegen, "\t%%t%zu =w and %%t%zu, %%t%zu\n", positive_and_within, positive, within);
	emit(codegen, "\t%%t%zu =w and %%t%zu, %%t%zu\n", valid, positive_and_within, fits);
	emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", valid, good, bad);
	emit_label(codegen, bad);
	emit(codegen, "\tcall $abort()\n\thlt\n");
	emit_label(codegen, good);
	if (alignment > 16)
		emit(codegen, "\t%%t%zu =l sub %%t%zu, %%t%zu\n", new_remaining, remaining, charged);
	else
		emit(codegen, "\t%%t%zu =l sub %%t%zu, %%z%zu\n", new_remaining, remaining, local->slot);
	emit(codegen, "\tstorel %%t%zu, %%vla_budget\n", new_remaining);
	if (alignment > 16) {
		size_t raw = codegen->next_temporary++, biased = codegen->next_temporary++;
		emit(codegen, "\t%%t%zu =l alloc16 %%t%zu\n", raw, charged);
		emit(codegen, "\t%%t%zu =l add %%t%zu, %u\n", biased, raw, alignment - 1);
		emit(codegen, "\t%%v%zu =l and %%t%zu, -%u\n", local->slot, biased, alignment);
	} else
		emit(codegen, "\t%%v%zu =l alloc%u %%z%zu\n", local->slot, alignment, local->slot);
	if (local->initializer_syntax) {
		/* C23 empty initialization; supported x86-64 types use all-zero
		 * representations for zero, null pointers, and aggregate padding. */
		size_t predecessor = codegen->current_label;
		size_t loop = new_label(codegen), done = new_label(codegen);
		size_t index = codegen->next_temporary++, next = codegen->next_temporary++;
		size_t address = codegen->next_temporary++, more = codegen->next_temporary++;

		emit(codegen, "\tjmp @b%zu\n", loop);
		emit_label(codegen, loop);
		emit(codegen, "\t%%t%zu =l phi @b%zu 0, @b%zu %%t%zu\n", index, predecessor, loop, next);
		emit(codegen, "\t%%t%zu =l add %%v%zu, %%t%zu\n", address, local->slot, index);
		if (contains_volatile(local->type)) {
			const struct type *element = array->element;
			while (element->kind == type_kind_array)
				element = ((const struct array_type *)element)->element;
			unsigned width = type_is_record(element) ? 1 : (unsigned)type_object_size(element);
			emit(codegen, "\tcall $__kcc_volatile_store_%u(l %%t%zu, %c 0)\n",
				width, address, width == 8 ? 'l' : 'w');
			emit(codegen, "\t%%t%zu =l add %%t%zu, %u\n", next, index, width);
		} else {
			emit(codegen, "\tstoreb 0, %%t%zu\n", address);
			emit(codegen, "\t%%t%zu =l add %%t%zu, 1\n", next, index);
		}
		emit(codegen, "\t%%t%zu =w cultl %%t%zu, %%z%zu\n", more, next, local->slot);
		emit(codegen, "\tjnz %%t%zu, @b%zu, @b%zu\n", more, loop, done);
		emit_label(codegen, done);
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

			if (type_is_record(node->value->type)) {
				size_t destination = codegen->next_temporary++;
				emit(codegen, "\t%%t%zu =l copy %%retbuf\n", destination);
				codegen_record_copy(codegen, value, destination, type_object_size(node->value->type));
				value = destination;
			}
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
			if (local->vla_bound)
				codegen_vla(codegen, local);
			else if (!local->object_symbol && !local->function_symbol) {
				if (local->vm_pointer_bound)
					codegen_vm_pointer_bound(codegen, local);
				codegen_local_initializer(codegen, local);
			}
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

static bool codegen_function(FILE *stream, const struct ast_function *function, struct abi_registry *abi)
{
	struct codegen codegen = {
		.stream = stream,
		.abi = abi,
		.next_label = function->label_count + function->switch_label_count + 1,
		.named_label_count = function->label_count,
		.output_ok = true,
	};
	const struct ast_local_declaration *local = function->locals;
	struct token name = function->declaration->name;
	size_t parameter_index = 0;

	assert(type_is_scalar(function->return_type) || type_is_record(function->return_type) || function->return_type->kind == type_kind_void);

	if (!function->declaration->symbol->is_internal)
		emit(&codegen, "export ");
	emit(&codegen, "function ");
	if (function->return_type->kind != type_kind_void) {
		emit_abi_type(&codegen, function->return_type);
		emit(&codegen, " ");
	}
	emit_symbol(&codegen, name);
	emit(&codegen, "(");
	for (const struct ast_parameter *parameter = function->declaration->parameters; parameter;
		parameter = parameter->next) {
		if (parameter->is_void_marker)
			continue;
		emit(&codegen, "%s", parameter_index ? ", " : "");
		emit_abi_type(&codegen, parameter->type);
		emit(&codegen, " %%p%zu", parameter_index);
		parameter_index++;
	}
	if (function->declaration->type_syntax->variadic)
		emit(&codegen, "%s...", parameter_index ? ", " : "");
	emit(&codegen, ") {\n");
	emit_label(&codegen, 0);
	if (function->atomic_compound_scratch)
		emit(&codegen, "\t%%atomic_compound_expected =l alloc8 8\n");
	for (const struct ast_local_declaration *vla = function->locals; vla; vla = vla->next_local) {
		if (vla->vla_bound) {
			emit(&codegen, "\t%%vla_budget =l alloc8 8\n");
			emit(&codegen, "\tstorel %ju, %%vla_budget\n", (uintmax_t)function->vla_storage_budget);
			break;
		}
	}
	while (local) {
		/* Dynamic storage is allocated at its declaration, not at entry. */
		if (local->vla_bound) {
			local = local->next_local;
			continue;
		}
		/* Slots are allocated at entry; initialization is in source order. */
		uint64_t bytes = type_object_size(local->type);
		unsigned alignment = type_object_alignment(local->type);

		if (local->alignment > alignment)
			alignment = local->alignment;
		codegen_fixed_slot(&codegen, 'v', local->slot, bytes, alignment);
		local = local->next_local;
	}
	for (const struct ast_load_expression *capture = function->record_temporaries; capture;
		capture = capture->next_record_temporary) {
		unsigned alignment = type_object_alignment(capture->expression.type);

		codegen_fixed_slot(&codegen, 'r', capture->record_temporary_slot,
			type_object_size(capture->expression.type), alignment);
	}
	/* QBE loads complete eightbytes, including for small objects. Staging
	 * buffers are rounded up so it never reads past a source subobject. */
	if (type_is_record(function->return_type))
		emit(&codegen, "\t%%retbuf =l alloc%u %ju\n", type_object_alignment(function->return_type) > 8 ? 16 : 8,
			(uintmax_t)((type_object_size(function->return_type) + 7) & ~UINT64_C(7)));
	for (const struct ast_argument *argument = function->abi_arguments; argument; argument = argument->next_abi_argument)
		emit(&codegen, "\t%%a%zu =l alloc%u %ju\n", argument->abi_slot,
			type_object_alignment(argument->value->type) > 8 ? 16 : 8,
			(uintmax_t)((type_object_size(argument->value->type) + 7) & ~UINT64_C(7)));
	for (const struct ast_va_expression *node = function->record_va_args; node; node = node->next_record_va)
		emit(&codegen, "\t%%q%zu =l alloc%u %ju\n", node->record_abi_slot,
			type_object_alignment(node->expression.type) > 8 ? 16 : 8,
			(uintmax_t)((type_object_size(node->expression.type) + 7) & ~UINT64_C(7)));
	parameter_index = 0;
	for (const struct ast_parameter *parameter = function->declaration->parameters; parameter;
		parameter = parameter->next) {
		if (parameter->is_void_marker)
			continue;
		if (parameter->local && type_is_record(parameter->type)) {
			size_t source = codegen.next_temporary++, destination = codegen.next_temporary++;
			emit(&codegen, "\t%%t%zu =l copy %%p%zu\n", source, parameter_index);
			emit(&codegen, "\t%%t%zu =l copy %%v%zu\n", destination, parameter->local->slot);
			if (contains_volatile(parameter->type))
				codegen_volatile_copy(&codegen, source, destination, type_object_size(parameter->type), 2);
			else codegen_record_copy(&codegen, source, destination, type_object_size(parameter->type));
		} else if (parameter->local && (parameter->type->qualifiers & type_qualifier_volatile)) {
			size_t address = codegen.next_temporary++, value = codegen.next_temporary++;
			emit(&codegen, "\t%%t%zu =l copy %%v%zu\n", address, parameter->local->slot);
			emit(&codegen, "\t%%t%zu =%c copy %%p%zu\n", value, qbe_type(parameter->type), parameter_index);
			codegen_volatile_store(&codegen, address, value, parameter->type);
		} else if (parameter->local) {
			if (type_is_bitint(parameter->type) && !type_bitint_width_native(type_integer_width(parameter->type))) {
				size_t value = codegen.next_temporary++;
				emit(&codegen, "\t%%t%zu =%c copy %%p%zu\n", value, qbe_type(parameter->type), parameter_index);
				value = codegen_storage_bits(&codegen, value, parameter->type);
				emit(&codegen, "\tstore%c %%t%zu, %%v%zu\n", qbe_store_size(parameter->type), value, parameter->local->slot);
			} else
				emit(&codegen, "\tstore%c %%p%zu, %%v%zu\n", qbe_store_size(parameter->type), parameter_index, parameter->local->slot);
		}
		parameter_index++;
	}
	/* Parameters have been spilled before any bound can read or update them. */
	for (const struct ast_parameter *parameter = function->declaration->parameters; parameter;
		parameter = parameter->next) {
		if (parameter->type_syntax->kind == type_syntax_array) {
			const struct ast_array_type_syntax *array = (const struct ast_array_type_syntax *)parameter->type_syntax;
			if (array->evaluate_parameter_bound)
				(void)codegen_expression(&codegen, array->bound);
		}
	}
	if (!codegen_block_items(&codegen, function->body->items)) {
		if (function->return_type->kind == type_kind_void)
			emit(&codegen, "\tret\n");
		else if (type_is_record(function->return_type))
			emit(&codegen, "\tret %%retbuf\n");
		else
			emit(&codegen, "\tret %s\n", function->return_type->kind == type_kind_float ? "s_0.0" : function->return_type->kind == type_kind_double ? "d_0.0" : "0");
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

static uint64_t field_integer_storage_bits(uint64_t bits, const struct type *type)
{
	if (type_uses_field_integer_representation(type) && !type_is_unsigned(type)) {
		unsigned width = type_integer_width(type);
		if (bits & (UINT64_C(1) << (width - 1)))
			bits |= UINT64_MAX << width;
	}
	return bits;
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

		/* Static field writes may share bytes. Group only overlapping extents,
		 * merging at most plan->size bytes (bounded by the initializer limit). */
		if (entry->bit_field) {
			uint64_t start = entry->offset, end = start + entry->length;
			size_t last = i + 1;
			while (last < count && entries[last]->bit_field && entries[last]->offset < end) {
				uint64_t next_end = entries[last]->offset + entries[last]->length;
				if (next_end > end) end = next_end;
				last++;
			}
			assert(start >= position && end <= plan->size);
			if (start > position) emit(codegen, "z %ju, ", (uintmax_t)(start - position));
			unsigned char *bytes = calloc((size_t)(end - start), 1);
			if (!bytes) { codegen->output_ok = false; free(entries); return; }
			for (size_t k = i; k < last; k++) {
				const struct ast_initializer_plan_entry *f = entries[k];
				if (f->kind == ast_initializer_write_zero) continue;
				assert(f->constant.kind == ast_initializer_constant_integer);
				assert(f->bit_field->bit_offset + f->bit_field->bit_width <= 64);
				uint64_t mask = f->bit_field->bit_width == 64 ? UINT64_MAX :
					(UINT64_C(1) << f->bit_field->bit_width) - 1;
				uint64_t bits = (f->constant.bits & mask) << f->bit_field->bit_offset;
				for (size_t j = 0; j < f->length; j++)
					bytes[f->offset - start + j] |= (unsigned char)(bits >> (8 * j));
			}
			for (uint64_t j = 0; j < end - start; j++) emit(codegen, "b %u, ", (unsigned)bytes[j]);
			free(bytes);
			position = end;
			i = last - 1;
			continue;
		}
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
				emit(codegen, "l ");
				emit_symbol(codegen, name);
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
			uint64_t bits = field_integer_storage_bits(constant->bits, entry->type);
			if (type_is_bitint(entry->type) && type_integer_width(entry->type) < 64)
				bits &= (UINT64_C(1) << type_integer_width(entry->type)) - 1;
			for (size_t j = 0; j < entry->length; j++)
				emit(codegen, "b %u, ", (unsigned)((bits >>
					(8 * (entry->source_offset + j))) & UINT64_C(255)));
		}
	}
	if (position < plan->size)
		emit(codegen, "z %ju, ", (uintmax_t)(plan->size - position));
	emit(codegen, "}\n");
	free(entries);
}

static bool codegen_translation_unit_body(FILE *stream, const struct ast_translation_unit *unit, struct abi_registry *abi)
{
	const struct ast_external_declaration *external = unit->declarations;
	struct codegen data_codegen = { .stream = stream, .output_ok = true };

	for (const struct ast_string_expression *string = unit->strings; string;
		string = string->next_string) {
		unsigned width = string->encoding == character_utf16 ? 2 : string->encoding >= character_utf32 ? 4 : 1;
		emit(&data_codegen, "data $.Lkcc.string.%zu = align %u {\n", string->object_id, width);
		for (size_t i = 0; i < string->length + width; i++)
			emit(&data_codegen, "\tb %u%s\n", (unsigned)string->bytes[i], i + 1 == string->length + width ? "" : ",");
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
			emit(&data_codegen, "%s%sdata ",
				object->is_internal ? "" : "export ", object->is_thread_local ? "thread " : "");
			emit_symbol(&data_codegen, name);
			emit(&data_codegen, " = align %u { ",
				object->alignment > type_object_alignment(object->type) ?
					object->alignment : type_object_alignment(object->type));
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
					assert(type_is_integer(object->type) || object->type->kind == type_kind_pointer);
					emit(&data_codegen, "%s %ju }\n", encoding,
						(uintmax_t)field_integer_storage_bits(object->initializer_value.integer_bits, object->type));
					break;
				case static_data_floating:
					assert(type_is_floating(object->type));
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
						emit(&data_codegen, "l ");
						emit_symbol(&data_codegen, base_name);
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
			!codegen_function(stream, (const struct ast_function *)external, abi))
			return false;
		external = external->next;
	}
	return fflush(stream) == 0;
}

/* QBE requires aggregate types before any use. Generate the translation unit
 * once into a temporary stream while collecting ABI shapes, then emit the
 * small, deduplicated type prelude followed by the unchanged body. */
bool codegen_translation_unit_with_options(FILE *stream, const struct ast_translation_unit *unit,
	const struct codegen_options *options)
{
	struct abi_registry abi = { .legacy_clang_abi = options && options->legacy_clang_abi,
		.gcc12_zero_width_abi = options && options->gcc12_zero_width_abi };
	FILE *body = tmpfile();
	if (!body) return false;
	bool ok = codegen_translation_unit_body(body, unit, &abi);
	for (unsigned size = 1; ok && size <= type_max_abi_record_size; size++)
		for (unsigned align = 1; align <= 16; align *= 2)
			for (unsigned c0 = 0; c0 < 3; c0++)
				for (unsigned c1 = 0; c1 < 3; c1++) {
					if (!abi.used[size][align][c0][c1]) continue;
					if (fprintf(stream, "type :kcc_abi_%u_%u_%u_%u = align %u { ", size, align, c0, c1, align) < 0) ok = false;
					if (size > 16) {
						if (fprintf(stream, "%u", size) < 0) ok = false;
					} else {
						unsigned classes[2] = { c0, c1 };
						for (unsigned i = 0; i < (size + 7) / 8; i++) {
							unsigned n = size - i * 8 < 8 ? size - i * 8 : 8;
							if (fprintf(stream, "%s%c %u", i ? ", " : "", classes[i] == aggregate_abi_sse ? 's' : 'b',
								classes[i] == aggregate_abi_sse ? n / 4 : n) < 0) ok = false;
						}
					}
					if (fprintf(stream, " }\n") < 0) ok = false;
				}
	if (ok && fseek(body, 0, SEEK_SET) != 0) ok = false;
	char buffer[4096];
	while (ok) {
		size_t n = fread(buffer, 1, sizeof buffer, body);
		if (n && fwrite(buffer, 1, n, stream) != n) ok = false;
		if (n < sizeof buffer) { if (ferror(body)) ok = false; break; }
	}
	if (fclose(body) != 0 || fflush(stream) != 0) ok = false;
	return ok;
}

bool codegen_translation_unit(FILE *stream, const struct ast_translation_unit *unit)
{
	return codegen_translation_unit_with_options(stream, unit, NULL);
}
