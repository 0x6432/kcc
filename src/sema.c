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
	uint64_t local_storage;
	struct function_symbol *functions;
	size_t function_count;
	size_t string_count;
	struct ast_string_expression **string_tail;
};

static bool same_name(struct token left, struct token right)
{
	return left.length == right.length &&
		memcmp(left.spelling_location.source->data + left.spelling_location.offset,
			right.spelling_location.source->data + right.spelling_location.offset,
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

static const struct type *specifier_type(enum integer_specifier specifier)
{
	switch (specifier) {
	case integer_specifier_bool: return &type_bool;
	case integer_specifier_char: return &type_char;
	case integer_specifier_signed_char: return &type_schar;
	case integer_specifier_unsigned_char: return &type_uchar;
	case integer_specifier_short: return &type_short;
	case integer_specifier_unsigned_short: return &type_ushort;
	case integer_specifier_int: return &type_int;
	case integer_specifier_unsigned: return &type_uint;
	case integer_specifier_long: return &type_long;
	case integer_specifier_unsigned_long: return &type_ulong;
	case integer_specifier_long_long: return &type_long_long;
	case integer_specifier_unsigned_long_long: return &type_ulong_long;
	}
	assert(0 && "unknown integer type specifier");
	return NULL;
}

static bool sema_parameter_names(struct sema *sema,
	struct ast_parameter *parameters)
{
	for (struct ast_parameter *parameter = parameters; parameter;
		parameter = parameter->next) {
		if (!parameter->has_name)
			continue;
		for (struct ast_parameter *prior = parameters; prior != parameter;
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

static const struct type *adjust_parameter_type(struct sema *sema,
	const struct type *declared, struct source_location location);

/* Preserve the written type graph while obtaining an ordinary value type. */
static const struct type *unqualified_type(struct sema *sema, const struct type *type,
	struct source_location location)
{
	const struct type *result = type_unqualified(sema->arena, type);

	if (!result)
		diagnostic_error(sema->diagnostics, location, "out of memory unqualifying type");
	return result;
}

/* Syntax owns spelling/locations; resolved types share compilation lifetime. */
static const struct type *resolve_type_syntax(struct sema *sema, struct ast_type_syntax *syntax)
{
	if (syntax->type)
		return syntax->type;
	switch (syntax->kind) {
	case type_syntax_qualified: {
		struct ast_qualified_type_syntax *qualified = (struct ast_qualified_type_syntax *)syntax;
		const struct type *base = resolve_type_syntax(sema, qualified->base);

		if (!base)
			return NULL;
		syntax->type = type_qualified(sema->arena, base, qualified->qualifiers);
		if (!syntax->type) {
			diagnostic_error(sema->diagnostics, syntax->location, "out of memory qualifying type");
			return NULL;
		}
		break;
	}
	case type_syntax_void:
		syntax->type = &type_void;
		break;
	case type_syntax_integer: {
		struct ast_integer_type_syntax *integer = (struct ast_integer_type_syntax *)syntax;

		syntax->type = specifier_type(integer->specifier);
		break;
	}
	case type_syntax_pointer: {
		struct ast_pointer_type_syntax *pointer = (struct ast_pointer_type_syntax *)syntax;
		const struct type *referent = resolve_type_syntax(sema, pointer->referent);
		struct pointer_type *type;

		if (!referent)
			return NULL;
		if (!type_is_object(referent) && referent->kind != type_kind_function) {
			diagnostic_error(sema->diagnostics, syntax->location, "pointer referent must be an object type");
			return NULL;
		}
		type = type_new_pointer(sema->arena, referent);
		if (!type) {
			diagnostic_error(sema->diagnostics, syntax->location, "out of memory creating pointer type");
			return NULL;
		}
		syntax->type = &type->type;
		break;
	}
	case type_syntax_function: {
		struct ast_function_type_syntax *function = (struct ast_function_type_syntax *)syntax;
		const struct type *return_type = resolve_type_syntax(sema, function->return_syntax);
		const struct type *parameters[ast_max_parameters];
		struct function_type *type;
		size_t count = 0;

		if (!return_type || !sema_parameter_names(sema, function->parameters))
			return NULL;
		if (!type_is_scalar(return_type) && return_type->kind != type_kind_void) {
			diagnostic_error(sema->diagnostics, syntax->location, "function return type must be void or an implemented scalar type");
			return NULL;
		}
		for (struct ast_parameter *parameter = function->parameters; parameter; parameter = parameter->next) {
			const struct type *declared = resolve_type_syntax(sema, parameter->type_syntax);

			if (!declared)
				return NULL;
			if (declared->kind == type_kind_void) {
				diagnostic_error(sema->diagnostics, parameter->location, "parameter cannot have void type");
				return NULL;
			}
			parameter->type = adjust_parameter_type(sema, declared, parameter->location);
			if (!parameter->type)
				return NULL;
			parameters[count] = unqualified_type(sema, parameter->type, parameter->location);
			if (!parameters[count])
				return NULL;
			count++;
		}
		assert(count == function->parameter_count && count <= ast_max_parameters);
		return_type = unqualified_type(sema, return_type, function->return_syntax->location);
		if (!return_type)
			return NULL;
		type = type_new_function(sema->arena, return_type, parameters, count);
		if (!type) {
			diagnostic_error(sema->diagnostics, syntax->location, "out of memory creating function type");
			return NULL;
		}
		syntax->type = &type->type;
		break;
	}
	case type_syntax_array: {
		struct ast_array_type_syntax *array = (struct ast_array_type_syntax *)syntax;
		const struct type *element = resolve_type_syntax(sema, array->element);
		struct array_type *type;
		uint64_t count = array->bound.integer;

		if (!element)
			return NULL;
		if (!type_is_complete_object(element)) {
			diagnostic_error(sema->diagnostics, syntax->location, "array element type must be complete");
			return NULL;
		}
		if (!array->has_bound) {
			type = type_new_incomplete_array(sema->arena, element);
		} else {
			if (!count || count > ast_max_local_storage / type_object_size(element)) {
				diagnostic_error(sema->diagnostics, array->bound.location,
					"array bound must be positive and fit array type storage limit (1 MiB)");
				return NULL;
			}
			type = type_new_array(sema->arena, element, count);
		}
		if (!type) {
			diagnostic_error(sema->diagnostics, syntax->location, "out of memory creating array type");
			return NULL;
		}
		syntax->type = &type->type;
		break;
	}
	}
	return syntax->type;
}

/* Parameter adjustment changes the effective object/signature type, not the
 * declared array syntax cache. Inner array bounds remain in the referent.
 */
static const struct type *adjust_parameter_type(struct sema *sema,
	const struct type *declared, struct source_location location)
{
	const struct array_type *array;
	struct pointer_type *pointer;

	if (declared->kind == type_kind_array) {
		array = (const struct array_type *)declared;
		pointer = type_new_pointer(sema->arena, array->element);
	} else if (declared->kind == type_kind_function) {
		pointer = type_new_pointer(sema->arena, declared);
	} else {
		return declared;
	}
	if (!pointer) {
		diagnostic_error(sema->diagnostics, location, "out of memory adjusting parameter");
		return NULL;
	}
	return &pointer->type;
}

/* Value conversion is broader than compatibility, and only one level deep. */
static bool object_void_pointer_conversion(const struct type *source,
	const struct type *target)
{
	const struct type *source_referent;
	const struct type *target_referent;

	if (source->kind != type_kind_pointer || target->kind != type_kind_pointer)
		return false;
	source_referent = ((const struct pointer_type *)source)->referent;
	target_referent = ((const struct pointer_type *)target)->referent;
	return (source_referent->kind == type_kind_void && type_is_object(target_referent)) ||
		(target_referent->kind == type_kind_void && type_is_object(source_referent));
}

/* Assignment-like pointer conversion may add immediate referent qualifiers,
 * never remove them or covariantly qualify deeper pointer referents. */
static bool implicit_pointer_conversion(const struct type *source, const struct type *target)
{
	const struct type *a;
	const struct type *b;

	if (source->kind != type_kind_pointer || target->kind != type_kind_pointer)
		return false;
	a = ((const struct pointer_type *)source)->referent;
	b = ((const struct pointer_type *)target)->referent;
	if (a->qualifiers & ~b->qualifiers)
		return false;
	return type_unqualified_compatible(a, b) || object_void_pointer_conversion(source, target);
}

static bool check_conversion(struct sema *sema, const struct type *source,
	const struct type *target, struct source_location location)
{
	if (!type_is_scalar(source) || !type_is_scalar(target)) {
		diagnostic_error(sema->diagnostics, location, "conversion requires a scalar value and target");
		return false;
	}
	if (type_compatible(source, target) || implicit_pointer_conversion(source, target) ||
		(type_is_integer(source) && type_is_integer(target)) ||
		(source->kind == type_kind_pointer && target->kind == type_kind_bool))
		return true;
	diagnostic_error(sema->diagnostics, location,
		"unsupported pointer conversion (incompatible pointers or integer/pointer conversion)");
	return false;
}

/* Explicit casts do not grant assignment compatibility or adapt function ABIs. */
static bool check_cast(struct sema *sema, const struct type *source,
	const struct type *target, struct source_location location)
{
	if (source->kind == type_kind_pointer && target->kind == type_kind_pointer) {
		const struct type *source_referent = ((const struct pointer_type *)source)->referent;
		const struct type *target_referent = ((const struct pointer_type *)target)->referent;

		if ((type_is_object(source_referent) && type_is_object(target_referent)) ||
			(source_referent->kind == type_kind_function && target_referent->kind == type_kind_function))
			return true;
	}
	return check_conversion(sema, source, target, location);
}

static bool convert_expression(struct sema *sema, struct ast_expression **slot,
	const struct type *target)
{
	struct ast_conversion_expression *conversion;

	if (!check_conversion(sema, (*slot)->type, target, (*slot)->location))
		return false;
	if (type_compatible((*slot)->type, target))
		return true;
	conversion = ast_new_conversion(sema->arena, *slot, target);
	if (!conversion) {
		diagnostic_error(sema->diagnostics, (*slot)->location,
			"out of memory inserting scalar conversion");
		return false;
	}
	if (!check_expression_depth(sema, &conversion->expression))
		return false;
	*slot = &conversion->expression;
	return true;
}

/* Callers first validate compatible immediate referents or the object/void rule.
 * Composite construction preserves known array bounds even for compatible types.
 */
static const struct type *common_pointer_type(struct sema *sema,
	const struct type *left, const struct type *right, struct source_location location)
{
	const struct type *a = ((const struct pointer_type *)left)->referent;
	const struct type *b = ((const struct pointer_type *)right)->referent;
	const struct type *common;
	struct pointer_type *pointer;

	if (type_unqualified_compatible(a, b)) {
		const struct type *plain_a = unqualified_type(sema, a, location);
		const struct type *plain_b = unqualified_type(sema, b, location);

		if (!plain_a || !plain_b)
			return NULL;
		common = type_composite(sema->arena, plain_a, plain_b);
	} else {
		assert(object_void_pointer_conversion(left, right));
		common = &type_void;
	}
	if (common)
		common = type_qualified(sema->arena, common, a->qualifiers | b->qualifiers);
	pointer = common ? type_new_pointer(sema->arena, common) : NULL;
	if (!pointer)
		diagnostic_error(sema->diagnostics, location, "out of memory creating common pointer type");
	return pointer ? &pointer->type : NULL;
}

/* Equal qualifiers keep existing comparison snapshots unchanged. */
static bool convert_comparison_pointers(struct sema *sema, struct ast_binary_expression *node)
{
	const struct type *left = node->left->type;
	const struct type *right = node->right->type;
	const struct type *a;
	const struct type *b;
	const struct type *common;
	bool equality = node->operation == binary_equal || node->operation == binary_not_equal;

	if (left->kind != type_kind_pointer || right->kind != type_kind_pointer ||
		type_compatible(left, right))
		return true;
	a = ((const struct pointer_type *)left)->referent;
	b = ((const struct pointer_type *)right)->referent;
	if (!type_unqualified_compatible(a, b) && !(equality && object_void_pointer_conversion(left, right)))
		return true; /* The caller diagnoses incompatible pointer comparisons. */
	common = common_pointer_type(sema, left, right, node->expression.location);
	return common && convert_expression(sema, &node->left, common) &&
		convert_expression(sema, &node->right, common);
}

static bool comparison_operator(enum binary_operator operation)
{
	switch (operation) {
	case binary_equal: case binary_not_equal:
	case binary_less: case binary_less_equal:
	case binary_greater: case binary_greater_equal:
		return true;
	default:
		return false;
	}
}

/* Both operands are already analyzed/loaded. Only the integer is promoted;
 * the pointer type and the index's promoted signedness remain explicit.
 */
static struct ast_pointer_offset_expression *lower_pointer_offset(struct sema *sema,
	struct source_location location, struct ast_expression *left,
	struct ast_expression *right, bool subtract)
{
	struct ast_expression *base;
	struct ast_expression *index;
	const struct pointer_type *pointer;
	struct ast_pointer_offset_expression *offset;

	if (left->type->kind == type_kind_pointer && type_is_integer(right->type)) {
		base = left;
		index = right;
	} else if (!subtract && type_is_integer(left->type) && right->type->kind == type_kind_pointer) {
		base = right;
		index = left;
	} else {
		diagnostic_error(sema->diagnostics, location,
			"pointer offset/subscript requires one pointer and one integer operand");
		return NULL;
	}
	if (!convert_expression(sema, &index, type_integer_promotion(index->type)))
		return NULL;
	pointer = (const struct pointer_type *)base->type;
	if (!type_is_complete_object(pointer->referent)) {
		diagnostic_error(sema->diagnostics, location, "pointer arithmetic requires a complete object referent");
		return NULL;
	}
	offset = ast_new_pointer_offset(sema->arena, location,
		base, index, type_object_size(pointer->referent), subtract);
	if (!offset) {
		diagnostic_error(sema->diagnostics, location, "out of memory lowering pointer offset");
		return NULL;
	}
	offset->expression.type = base->type;
	if (!check_expression_depth(sema, &offset->expression))
		return NULL;
	return offset;
}

/* Replace parsed syntax through its slot; never reinterpret its layout or
 * reanalyze shared typed children. Subtraction has target ptrdiff_t = long.
 */
static bool lower_pointer_arithmetic(struct sema *sema,
	struct ast_expression **slot, struct ast_binary_expression *binary)
{
	struct ast_expression *left = binary->left;
	struct ast_expression *right = binary->right;
	struct ast_expression *result;
	bool subtract = binary->operation == binary_subtract;

	if (subtract && left->type->kind == type_kind_pointer && right->type->kind == type_kind_pointer) {
		const struct pointer_type *pointer = (const struct pointer_type *)left->type;
		struct ast_pointer_difference_expression *difference;

		if (!type_unqualified_compatible(pointer->referent,
			((const struct pointer_type *)right->type)->referent)) {
			diagnostic_error(sema->diagnostics, binary->expression.location,
				"pointer subtraction requires compatible pointer operands");
			return false;
		}
		if (!type_is_complete_object(pointer->referent) ||
			!type_is_complete_object(((const struct pointer_type *)right->type)->referent)) {
			diagnostic_error(sema->diagnostics, binary->expression.location,
				"pointer subtraction requires complete object referents");
			return false;
		}
		difference = ast_new_pointer_difference(sema->arena, binary->expression.location,
			left, right, type_object_size(pointer->referent));
		if (!difference) {
			diagnostic_error(sema->diagnostics, binary->expression.location,
				"out of memory lowering pointer difference");
			return false;
		}
		result = &difference->expression;
		result->type = &type_long;
	} else {
		struct ast_pointer_offset_expression *offset = lower_pointer_offset(sema,
			binary->expression.location, left, right, subtract);

		if (!offset)
			return false;
		result = &offset->expression;
	}
	if (!check_expression_depth(sema, result))
		return false;
	*slot = result;
	return true;
}

/* Resolve/types are independent of parsing. Value contexts explicitly load
 * lvalues; assignment's left operand must remain an object, not a loaded value.
 */
static bool sema_expression(struct sema *sema,
	struct ast_expression **expression_slot, bool value_required)
{
	struct ast_expression *expression = *expression_slot;
	const struct type *result_type = &type_int;

	switch (expression->kind) {
	case expression_call: {
		struct ast_call_expression *node = (struct ast_call_expression *)expression;
		const struct pointer_type *pointer;
		const struct function_parameter_type *parameter;

		/* Retain the useful undeclared bare-call diagnostic before name typing. */
		if (node->callee->kind == expression_name) {
			struct ast_name_expression *name = (struct ast_name_expression *)node->callee;

			if (!find_local(sema, name->name) && !find_function(sema, name->name)) {
				diagnostic_error(sema->diagnostics, name->expression.location, "call to undeclared function");
				return false;
			}
		}
		if (!sema_expression(sema, &node->callee, true))
			return false;
		if (node->callee->type->kind != type_kind_pointer ||
			((const struct pointer_type *)node->callee->type)->referent->kind != type_kind_function) {
			diagnostic_error(sema->diagnostics, node->callee->location, "called expression is not a function pointer");
			return false;
		}
		pointer = (const struct pointer_type *)node->callee->type;
		node->signature = (const struct function_type *)pointer->referent;
		if (node->callee->kind == expression_function_decay) {
			struct ast_function_decay_expression *decay = (struct ast_function_decay_expression *)node->callee;

			if (decay->operand->kind == expression_function_designator)
				node->function = ((struct ast_function_designator_expression *)decay->operand)->function;
		}
		if (node->argument_count != node->signature->parameter_count) {
			diagnostic_error(sema->diagnostics, expression->location,
				"argument count does not match function signature");
			return false;
		}
		result_type = node->signature->return_type;
		parameter = node->signature->parameters;
		expression->depth = node->callee->depth + 1;
		for (struct ast_argument *argument = node->arguments; argument;
			argument = argument->next) {
			if (!sema_expression(sema, &argument->value, true) ||
				!convert_expression(sema, &argument->value, parameter->type))
				return false;
			parameter = parameter->next;
			if (argument->value->depth + 1 > expression->depth)
				expression->depth = argument->value->depth + 1;
		}
		break;
	}
	case expression_address: {
		struct ast_address_expression *node = (struct ast_address_expression *)expression;
		struct pointer_type *pointer;

		if (!sema_expression(sema, &node->operand, false))
			return false;
		if (!node->operand->is_lvalue && node->operand->type->kind != type_kind_function &&
			node->operand->kind != expression_indirection) {
			diagnostic_error(sema->diagnostics, expression->location, "address-of requires an object lvalue or function designator");
			return false;
		}
		pointer = type_new_pointer(sema->arena, node->operand->type);
		if (!pointer) {
			diagnostic_error(sema->diagnostics, expression->location, "out of memory creating address type");
			return false;
		}
		result_type = &pointer->type;
		expression->depth = node->operand->depth + 1;
		break;
	}
	case expression_subscript: {
		struct ast_subscript_expression *node = (struct ast_subscript_expression *)expression;
		struct ast_pointer_offset_expression *offset;
		struct ast_indirection_expression *indirection;
		const struct pointer_type *pointer;

		if (!sema_expression(sema, &node->left, true) || !sema_expression(sema, &node->right, true))
			return false;
		offset = lower_pointer_offset(sema, expression->location, node->left, node->right, false);
		if (!offset)
			return false;
		indirection = ast_new_indirection(sema->arena, expression->location, &offset->expression);
		if (!indirection) {
			diagnostic_error(sema->diagnostics, expression->location, "out of memory lowering subscript");
			return false;
		}
		pointer = (const struct pointer_type *)offset->expression.type;
		result_type = pointer->referent;
		expression = &indirection->expression;
		expression->is_lvalue = true;
		*expression_slot = expression;
		/* Common completion below annotates/checks the lvalue and inserts a
		 * load only for value contexts. No typed operand is analyzed twice.
		 */
		break;
	}
	case expression_indirection: {
		struct ast_indirection_expression *node = (struct ast_indirection_expression *)expression;
		const struct pointer_type *pointer;

		if (!sema_expression(sema, &node->operand, true))
			return false;
		if (node->operand->type->kind != type_kind_pointer) {
			diagnostic_error(sema->diagnostics, expression->location, "indirection requires an object pointer");
			return false;
		}
		pointer = (const struct pointer_type *)node->operand->type;
		result_type = pointer->referent;
		expression->is_lvalue = result_type->kind != type_kind_function && result_type->kind != type_kind_void;
		expression->depth = node->operand->depth + 1;
		break;
	}
	case expression_string: {
		struct ast_string_expression *node = (struct ast_string_expression *)expression;
		struct array_type *array = type_new_array(sema->arena, &type_char, node->length + 1);

		if (!array) {
			diagnostic_error(sema->diagnostics, expression->location, "out of memory creating string type");
			return false;
		}
		result_type = &array->type;
		expression->is_lvalue = true;
		node->object_id = sema->string_count++;
		*sema->string_tail = node;
		sema->string_tail = &node->next_string;
		break;
	}
	case expression_boolean:
		result_type = &type_bool;
		break;
	case expression_character:
		break;
	case expression_integer: {
		struct ast_integer_expression *node =
			(struct ast_integer_expression *)expression;

		result_type = type_integer_literal(node->value, node->base ? node->base : 10,
			node->unsigned_suffix, node->long_suffix);
		if (!result_type) {
			diagnostic_error(sema->diagnostics, expression->location,
				"literal does not fit an implemented integer type");
			return false;
		}
		break;
	}
	case expression_name: {
		struct ast_name_expression *node =
			(struct ast_name_expression *)expression;

		node->declaration = find_local(sema, node->name);
		if (node->declaration) {
			result_type = node->declaration->type;
			expression->is_lvalue = true;
		} else {
			struct function_symbol *function = find_function(sema, node->name);
			struct ast_function_designator_expression *designator;

			if (!function) {
				diagnostic_error(sema->diagnostics, expression->location, "use of undeclared identifier");
				return false;
			}
			designator = ast_new_function_designator(sema->arena, expression->location, function);
			if (!designator) {
				diagnostic_error(sema->diagnostics, expression->location, "out of memory creating function designator");
				return false;
			}
			expression = &designator->expression;
			*expression_slot = expression;
			result_type = &function->type->type;
		}
		break;
	}
	case expression_cast: {
		struct ast_cast_expression *node = (struct ast_cast_expression *)expression;

		if (!sema_expression(sema, &node->operand, true))
			return false;
		result_type = resolve_type_syntax(sema, node->type_syntax);
		if (!result_type)
			return false;
		result_type = unqualified_type(sema, result_type, node->type_syntax->location);
		if (!result_type)
			return false;
		if (result_type->kind == type_kind_void) {
			expression->depth = node->operand->depth + 1;
			break;
		}
		if (!type_is_scalar(result_type)) {
			diagnostic_error(sema->diagnostics, expression->location, "cast target must be a scalar type");
			return false;
		}
		if (!check_cast(sema, node->operand->type, result_type, expression->location))
			return false;
		expression->depth = node->operand->depth + 1;
		break;
	}
	case expression_unary: {
		struct ast_unary_expression *node =
			(struct ast_unary_expression *)expression;

		if (!sema_expression(sema, &node->operand, true))
			return false;
		if (!type_is_scalar(node->operand->type)) {
			diagnostic_error(sema->diagnostics, expression->location, "unary operator requires a scalar operand");
			return false;
		}
		if (node->operation != unary_not) {
			if (!type_is_integer(node->operand->type)) {
				diagnostic_error(sema->diagnostics, expression->location, "unary arithmetic requires an integer operand");
				return false;
			}
			result_type = type_integer_promotion(node->operand->type);
			if (!convert_expression(sema, &node->operand, result_type))
				return false;
		}
		expression->depth = node->operand->depth + 1;
		break;
	}
	/* Promote both operands explicitly before usual arithmetic conversions.
	 * Shifts keep the independently promoted left type, not a common type.
	 */
	case expression_binary: {
		struct ast_binary_expression *node =
			(struct ast_binary_expression *)expression;
		unsigned depth;

		if (!sema_expression(sema, &node->left, true))
			return false;
		if (!sema_expression(sema, &node->right, true))
			return false;
		if (!type_is_scalar(node->left->type) || !type_is_scalar(node->right->type)) {
			diagnostic_error(sema->diagnostics, expression->location, "binary operator requires scalar operands");
			return false;
		}
		if (!type_is_integer(node->left->type) || !type_is_integer(node->right->type)) {
			if (node->operation == binary_add || node->operation == binary_subtract)
				return lower_pointer_arithmetic(sema, expression_slot, node);
			if (!comparison_operator(node->operation)) {
				diagnostic_error(sema->diagnostics, expression->location, "invalid pointer binary operator");
				return false;
			}
			if (!convert_comparison_pointers(sema, node))
				return false;
			if (node->left->type->kind != type_kind_pointer || node->right->type->kind != type_kind_pointer ||
				!type_compatible(node->left->type, node->right->type)) {
				diagnostic_error(sema->diagnostics, expression->location,
					"pointer comparison requires compatible pointer operands; null constants are not supported yet");
				return false;
			}
			if (node->operation != binary_equal && node->operation != binary_not_equal &&
				!type_is_object(((const struct pointer_type *)node->left->type)->referent)) {
				diagnostic_error(sema->diagnostics, expression->location,
					"relational comparison requires object pointers");
				return false;
			}
			result_type = &type_int;
		} else {
			if (!convert_expression(sema, &node->left, type_integer_promotion(node->left->type)) ||
				!convert_expression(sema, &node->right, type_integer_promotion(node->right->type)))
				return false;
			if (node->operation == binary_shift_left || node->operation == binary_shift_right) {
				result_type = node->left->type;
			} else {
				const struct type *common = type_usual_arithmetic(node->left->type, node->right->type);

				if (!convert_expression(sema, &node->left, common) ||
					!convert_expression(sema, &node->right, common))
					return false;
				result_type = comparison_operator(node->operation) ? &type_int : common;
			}
		}
		depth = node->left->depth > node->right->depth ?
			node->left->depth : node->right->depth;
		expression->depth = depth + 1;
		break;
	}
	case expression_conditional: {
		struct ast_conditional_expression *node = (struct ast_conditional_expression *)expression;
		const struct type *a;
		const struct type *b;
		unsigned depth;

		/* Skipped arms must satisfy constraints, but only one executes. */
		if (!sema_expression(sema, &node->condition, true) ||
			!sema_expression(sema, &node->then_value, true) || !sema_expression(sema, &node->else_value, true))
			return false;
		if (!type_is_scalar(node->condition->type)) {
			diagnostic_error(sema->diagnostics, node->condition->location,
				"conditional expression requires a scalar condition");
			return false;
		}
		a = node->then_value->type;
		b = node->else_value->type;
		if (type_is_integer(a) && type_is_integer(b)) {
			result_type = type_usual_arithmetic(a, b);
		} else if (a->kind == type_kind_void && b->kind == type_kind_void) {
			result_type = &type_void;
		} else if (a->kind == type_kind_pointer && b->kind == type_kind_pointer &&
			(type_unqualified_compatible(((const struct pointer_type *)a)->referent,
				((const struct pointer_type *)b)->referent) || object_void_pointer_conversion(a, b))) {
			result_type = common_pointer_type(sema, a, b, expression->location);
			if (!result_type)
				return false;
		} else {
			diagnostic_error(sema->diagnostics, expression->location,
				"incompatible conditional operands (null pointer constants are not implemented yet)");
			return false;
		}
		if (result_type->kind != type_kind_void &&
			(!convert_expression(sema, &node->then_value, result_type) ||
			 !convert_expression(sema, &node->else_value, result_type)))
			return false;
		depth = node->then_value->depth > node->else_value->depth ?
			node->then_value->depth : node->else_value->depth;
		if (node->condition->depth > depth)
			depth = node->condition->depth;
		expression->depth = depth + 1;
		break;
	}
	case expression_comma: {
		struct ast_comma_expression *node = (struct ast_comma_expression *)expression;
		unsigned depth;

		if (!sema_expression(sema, &node->left, true) || !sema_expression(sema, &node->right, true))
			return false;
		result_type = node->right->type;
		depth = node->left->depth > node->right->depth ? node->left->depth : node->right->depth;
		expression->depth = depth + 1;
		/* C's comma result is not an lvalue, even when its right operand was one. */
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
		if (!type_is_scalar(node->left->type) || !type_is_scalar(node->right->type)) {
			diagnostic_error(sema->diagnostics, expression->location, "logical operator requires scalar operands");
			return false;
		}
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
		if (!node->left->is_lvalue || node->left->type->kind == type_kind_array ||
			(node->left->type->qualifiers & type_qualifier_const)) {
			diagnostic_error(sema->diagnostics, node->left->location,
				"assignment requires a modifiable lvalue");
			return false;
		}
		if (!sema_expression(sema, &node->right, true) ||
			!convert_expression(sema, &node->right, node->left->type))
			return false;
		result_type = node->left->type;
		depth = node->left->depth > node->right->depth ?
			node->left->depth : node->right->depth;
		expression->depth = depth + 1;
		break;
	}
	case expression_function_designator:
	case expression_function_decay:
	case expression_pointer_offset:
	case expression_pointer_difference:
	case expression_conversion:
	case expression_load:
	case expression_array_decay:
		/* Lowered nodes are introduced during this single semantic pass. */
		assert(0 && "conversion node before semantic analysis");
		return false;
	}
	expression->type = result_type;
	if (!check_expression_depth(sema, expression))
		return false;

	if (value_required && expression->type->kind == type_kind_function) {
		struct pointer_type *pointer = type_new_pointer(sema->arena, expression->type);
		struct ast_function_decay_expression *decay;

		if (!pointer) {
			diagnostic_error(sema->diagnostics, expression->location, "out of memory creating function decay type");
			return false;
		}
		decay = ast_new_function_decay(sema->arena, expression, &pointer->type);
		if (!decay) {
			diagnostic_error(sema->diagnostics, expression->location, "out of memory inserting function decay");
			return false;
		}
		if (!check_expression_depth(sema, &decay->expression))
			return false;
		*expression_slot = &decay->expression;
	} else if (value_required && expression->type->kind == type_kind_array) {
		const struct array_type *array = (const struct array_type *)expression->type;
		struct pointer_type *pointer = type_new_pointer(sema->arena, array->element);
		struct ast_array_decay_expression *decay;

		if (!pointer) {
			diagnostic_error(sema->diagnostics, expression->location, "out of memory creating decay type");
			return false;
		}
		decay = ast_new_array_decay(sema->arena, expression, &pointer->type);
		if (!decay) {
			diagnostic_error(sema->diagnostics, expression->location, "out of memory inserting array decay");
			return false;
		}
		if (!check_expression_depth(sema, &decay->expression))
			return false;
		*expression_slot = &decay->expression;
	} else if (value_required && expression->is_lvalue) {
		struct ast_load_expression *load = ast_new_load(sema->arena, expression);

		if (!load) {
			diagnostic_error(sema->diagnostics, expression->location,
				"out of memory inserting lvalue conversion");
			return false;
		}
		load->expression.type = unqualified_type(sema, expression->type, expression->location);
		if (!load->expression.type)
			return false;
		if (!check_expression_depth(sema, &load->expression))
			return false;
		*expression_slot = &load->expression;
	}
	return true;
}

static bool sema_condition(struct sema *sema, struct ast_expression **slot)
{
	if (!sema_expression(sema, slot, true))
		return false;
	if (!type_is_scalar((*slot)->type)) {
		diagnostic_error(sema->diagnostics, (*slot)->location, "condition requires a scalar value");
		return false;
	}
	return true;
}

static bool bind_local(struct sema *sema, struct ast_local_declaration *local,
	const struct type *effective_type)
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

	/* Binding precedes initializer analysis; parameter spills use the adjusted
	 * type while retaining their declared syntax as source provenance.
	 */
	assert(type_is_complete_object(effective_type));
	local->type = effective_type;
	if (type_object_size(local->type) > ast_max_local_storage - sema->local_storage) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"function exceeds local object storage limit (1 MiB)");
		return false;
	}
	sema->local_storage += type_object_size(local->type);
	if (local->type->kind == type_kind_array && local->initializer) {
		diagnostic_error(sema->diagnostics, local->name.location, "array initializers are not supported yet");
		return false;
	}
	local->slot = sema->local_count++;
	local->next_local = sema->function->locals;
	sema->function->locals = local;
	if (local->initializer) {
		const struct type *target = unqualified_type(sema, local->type, local->name.location);

		return target && sema_expression(sema, &local->initializer, true) &&
			convert_expression(sema, &local->initializer, target);
	}
	return true;
}

static bool sema_local(struct sema *sema, struct ast_local_declaration *local)
{
	const struct type *type = resolve_type_syntax(sema, local->type_syntax);

	if (!type)
		return false;
	if (type->kind == type_kind_function) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"block-scope function declarations are not supported yet");
		return false;
	}
	if (!type_is_complete_object(type)) {
		diagnostic_error(sema->diagnostics, local->name.location, "local object type must be complete");
		return false;
	}
	return bind_local(sema, local, type);
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
	success = sema_condition(sema, &node->condition);
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
	success = sema_condition(sema, &node->condition);
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
		success = sema_condition(sema, &node->condition);
	sema->scope = scope.parent;
	return success;
}

static bool sema_block_items(struct sema *sema, struct ast_block_item *item);

static bool sema_for(struct sema *sema, struct ast_for_statement *node)
{
	struct scope scope = { .parent = sema->scope };
	bool success = true;

	sema->scope = &scope;
	if (node->initializer_declarations)
		success = sema_block_items(sema, node->initializer_declarations);
	if (success && node->initializer_expression)
		success = sema_expression(sema, &node->initializer_expression, true);
	if (success && node->condition)
		success = sema_condition(sema, &node->condition);
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

		if (sema->function->return_type->kind == type_kind_void) {
			if (node->value) {
				diagnostic_error(sema->diagnostics, statement->location, "void function return cannot have an expression");
				return false;
			}
			return true;
		}
		if (!node->value) {
			diagnostic_error(sema->diagnostics, statement->location, "nonvoid function return requires an expression");
			return false;
		}
		return sema_expression(sema, &node->value, true) &&
			convert_expression(sema, &node->value, sema->function->return_type);
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

static bool sema_function_body(struct sema *sema, struct ast_function *definition)
{
	struct scope scope = { 0 };
	bool success = false;

	assert(!sema->scope && !sema->loop);
	sema->function = definition;
	sema->local_count = 0;
	sema->local_storage = 0;
	sema->scope = &scope;
	for (struct ast_parameter *parameter = definition->declaration->parameters; parameter;
		parameter = parameter->next) {
		/* Unnamed C23 parameters remain in the ABI, without a source binding. */
		if (!parameter->has_name)
			continue;
		parameter->local = ast_new_local(sema->arena, parameter->location,
			parameter->name, NULL);
		if (!parameter->local) {
			diagnostic_error(sema->diagnostics, parameter->location,
				"out of memory creating parameter local");
			goto done;
		}
		parameter->local->type_syntax = parameter->type_syntax;
		if (!bind_local(sema, parameter->local, parameter->type))
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
	const struct function_type *type;
	struct token main_name = declaration->name;
	const struct type *return_type;
	const struct type *resolved;
	if (main_name.length == 4 && memcmp(main_name.spelling_location.source->data +
		main_name.spelling_location.offset, "main", 4) == 0 && declaration->parameter_count) {
		diagnostic_error(sema->diagnostics, main_name.location,
			"only zero-parameter main is supported yet");
		return false;
	}
	resolved = resolve_type_syntax(sema, &declaration->type_syntax->syntax);
	if (!resolved)
		return false;
	assert(resolved->kind == type_kind_function);
	type = (const struct function_type *)resolved;
	return_type = type->return_type;
	if (main_name.length == 4 && memcmp(main_name.spelling_location.source->data +
		main_name.spelling_location.offset, "main", 4) == 0 &&
		!type_compatible(return_type, &type_int)) {
		diagnostic_error(sema->diagnostics, main_name.location, "main must return int");
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
	/* Compatibility alone is not transitive for unknown array bounds. Retain
	 * known bounds in the visible composite without rewriting syntax caches.
	 */
	if (symbol->type != type) {
		const struct type *composite = type_composite(sema->arena, &symbol->type->type, &type->type);

		if (!composite) {
			diagnostic_error(sema->diagnostics, declaration->name.location,
				"out of memory creating composite function type");
			return false;
		}
		symbol->type = (const struct function_type *)composite;
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
	struct sema sema = {
		.arena = arena,
		.diagnostics = diagnostics,
		.string_tail = &unit->strings,
	};
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
