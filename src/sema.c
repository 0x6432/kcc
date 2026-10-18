#include "sema.h"
#include "consteval.h"
#include "type.h"

#include <assert.h>
#include <string.h>
#include <stdio.h>

/* Aliases share type DAGs. Cache shape metrics without expanding repeated edges.
 * The expanded size/depth bounds keep existing recursive type operations safe.
 */
enum typedef_type_limit {
	typedef_max_type_nodes = 4096,
	typedef_max_type_depth = 128,
};

struct typedef_type_shape {
	const struct type *type;
	size_t nodes;
	unsigned depth;
	struct typedef_type_shape *next;
};

struct typedef_binding {
	struct scope *scope;
	struct ast_typedef_declaration *declaration;
	struct typedef_binding *next;
};

struct binding {
	struct ast_local_declaration *declaration;
	struct binding *next;
};

struct scope {
	struct scope *parent;
	struct binding *bindings;
};

struct control_context {
	struct control_context *parent;
	struct ast_statement *statement;
};

struct goto_reference {
	struct ast_goto_statement *statement;
	struct goto_reference *next;
};

struct label_binding {
	struct ast_label *label;
	struct label_binding *next;
};

struct sema {
	struct arena *arena;
	struct diagnostics *diagnostics;
	struct ast_function *function;
	struct scope *scope;
	struct control_context *control;
	struct label_binding *labels;
	size_t label_count;
	size_t switch_label_count;
	struct goto_reference *gotos;
	size_t goto_count;
	size_t local_count;
	uint64_t local_storage;
	struct function_symbol *functions;
	struct external_object_symbol *external_objects;
	size_t external_object_count;
	bool unevaluated;
	struct typedef_binding *typedefs;
	struct typedef_type_shape *typedef_shapes;
	size_t function_count;
	size_t string_count;
	struct ast_string_expression **string_tail;
	struct ast_external_declaration **static_tail;
	size_t static_count;
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

static struct typedef_binding *find_typedef_binding(struct sema *sema, struct token name)
{
	struct typedef_binding *binding = sema->typedefs;

	while (binding) {
		if (same_name(binding->declaration->name, name)) {
			struct scope *scope = sema->scope;

			/* A nearer object hides this alias in the ordinary namespace. */
			while (scope && scope != binding->scope) {
				if (find_in_scope(scope, name))
					return NULL;
				scope = scope->parent;
			}
			return binding;
		}
		binding = binding->next;
	}
	return NULL;
}

static struct ast_typedef_declaration *find_typedef(struct sema *sema, struct token name)
{
	struct typedef_binding *binding = find_typedef_binding(sema, name);

	return binding ? binding->declaration : NULL;
}

static struct external_object_symbol *find_external_object(struct sema *sema, struct token name)
{
	struct external_object_symbol *symbol = sema->external_objects;

	while (symbol) {
		if (same_name(symbol->name, name))
			return symbol;
		symbol = symbol->next;
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

static bool sema_expression(struct sema *sema,
	struct ast_expression **expression_slot, bool value_required);
static const struct type *resolve_function_syntax(struct sema *sema,
	struct ast_function_type_syntax *function);

static const struct type *resolve_type_syntax(struct sema *sema, struct ast_type_syntax *syntax);

/* Non-VM queries retain constraints without creating evaluated function uses. */
static bool sema_unevaluated_expression(struct sema *sema,
	struct ast_expression **expression_slot)
{
	bool saved = sema->unevaluated;
	bool success;

	sema->unevaluated = true;
	success = sema_expression(sema, expression_slot, false);
	sema->unevaluated = saved;
	return success;
}

static const struct type *resolve_unevaluated_type_syntax(struct sema *sema,
	struct ast_type_syntax *syntax)
{
	bool saved = sema->unevaluated;
	const struct type *type;

	sema->unevaluated = true;
	type = resolve_type_syntax(sema, syntax);
	sema->unevaluated = saved;
	return type;
}

/* Syntax owns spelling/locations; resolved types share compilation lifetime. */
static const struct type *resolve_type_syntax(struct sema *sema, struct ast_type_syntax *syntax)
{
	if (syntax->type)
		return syntax->type;
	switch (syntax->kind) {
	case type_syntax_inferred:
		diagnostic_error(sema->diagnostics, syntax->location,
			"inferred type requires an initialized local definition");
		return NULL;
	case type_syntax_typedef_name: {
		struct ast_typedef_name_type_syntax *alias = (struct ast_typedef_name_type_syntax *)syntax;
		struct ast_typedef_declaration *declaration = find_typedef(sema, alias->name);

		if (!declaration) {
			diagnostic_error(sema->diagnostics, alias->name.location, "unknown typedef name");
			return NULL;
		}
		syntax->type = declaration->type;
		break;
	}
	case type_syntax_qualified: {
		struct ast_qualified_type_syntax *qualified = (struct ast_qualified_type_syntax *)syntax;
		const struct type *base = resolve_type_syntax(sema, qualified->base);

		if (!base)
			return NULL;
		if (base->kind == type_kind_function && qualified->qualifiers) {
			diagnostic_error(sema->diagnostics, syntax->location, "function type cannot be qualified");
			return NULL;
		}
		syntax->type = type_qualified(sema->arena, base, qualified->qualifiers);
		if (!syntax->type) {
			diagnostic_error(sema->diagnostics, syntax->location, "out of memory qualifying type");
			return NULL;
		}
		break;
	}
	case type_syntax_typeof_type: {
		struct ast_typeof_type_syntax *query = (struct ast_typeof_type_syntax *)syntax;
		const struct type *operand = resolve_unevaluated_type_syntax(sema, query->operand);

		if (!operand)
			return NULL;
		syntax->type = query->unqualify ? unqualified_type(sema, operand, syntax->location) : operand;
		if (!syntax->type)
			return NULL;
		break;
	}
	case type_syntax_typeof_expression: {
		struct ast_typeof_expression_syntax *query = (struct ast_typeof_expression_syntax *)syntax;

		/* Preserve only the root load/decay boundary; children keep their constraints.
		 * Variably modified types are unsupported, so no operand evaluation occurs.
		 */
		if (!sema_unevaluated_expression(sema, &query->operand))
			return NULL;
		syntax->type = query->unqualify ?
			unqualified_type(sema, query->operand->type, syntax->location) : query->operand->type;
		if (!syntax->type)
			return NULL;
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
	case type_syntax_function:
		syntax->type = resolve_function_syntax(sema, (struct ast_function_type_syntax *)syntax);
		break;
	case type_syntax_array: {
		struct ast_array_type_syntax *array = (struct ast_array_type_syntax *)syntax;
		const struct type *element = resolve_type_syntax(sema, array->element);
		struct array_type *type;
		uint64_t count = 0;

		if (!element)
			return NULL;
		if (!type_is_complete_object(element)) {
			diagnostic_error(sema->diagnostics, syntax->location, "array element type must be complete");
			return NULL;
		}
		if (!array->bound) {
			type = type_new_incomplete_array(sema->arena, element);
		} else {
			struct constant_result result;
			bool negative;

			if (!sema_expression(sema, &array->bound, true))
				return NULL;
			result = evaluate_integer_constant(array->bound);
			if (result.status != constant_value) {
				diagnostic_error(sema->diagnostics, result.location,
					result.status == constant_not_constant ?
					"array bound must be an integer constant expression; variable-length arrays are not supported yet" :
					result.message);
				return NULL;
			}
			count = result.bits;
			negative = !type_is_unsigned(result.type) &&
				(count & (UINT64_C(1) << (type_integer_width(result.type) - 1)));
			if (negative || !count || count > ast_max_local_storage / type_object_size(element)) {
				diagnostic_error(sema->diagnostics, array->bound->location,
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

/* Prototype names denote type-only objects, not runtime parameter spill slots.
 * A parameter's name enters scope only after its whole declarator is resolved.
 * Written register provenance restricts addresses, but never enters its type.
 */
static bool bind_prototype_parameter(struct sema *sema, const struct ast_parameter *parameter)
{
	struct ast_local_declaration *local;
	struct binding *binding;

	if (!parameter->has_name)
		return true;
	local = ast_new_local(sema->arena, parameter->location, parameter->name, NULL);
	binding = arena_alloc(sema->arena, sizeof(*binding));
	if (!local || !binding) {
		diagnostic_error(sema->diagnostics, parameter->location,
			"out of memory binding prototype parameter");
		return false;
	}
	local->type_syntax = parameter->type_syntax;
	local->type = parameter->type;
	local->is_register = parameter->is_register;
	*binding = (struct binding) { .declaration = local, .next = sema->scope->bindings };
	sema->scope->bindings = binding;
	return true;
}

static const struct type *resolve_function_syntax(struct sema *sema,
	struct ast_function_type_syntax *function)
{
	const struct type *return_type = resolve_type_syntax(sema, function->return_syntax);
	const struct type *parameters[ast_max_parameters];
	struct scope scope = { .parent = sema->scope };
	struct function_type *type = NULL;
	size_t count = 0;
	bool void_marker = false;

	if (!return_type || !sema_parameter_names(sema, function->parameters))
		return NULL;
	if (!type_is_scalar(return_type) && return_type->kind != type_kind_void) {
		diagnostic_error(sema->diagnostics, function->syntax.location,
			"function return type must be void or an implemented scalar type");
		return NULL;
	}
	sema->scope = &scope;
	for (struct ast_parameter *parameter = function->parameters; parameter; parameter = parameter->next) {
		const struct type *declared = resolve_type_syntax(sema, parameter->type_syntax);

		if (!declared)
			goto done;
		if (declared->kind == type_kind_void) {
			/* Resolve query-derived void without removing its written syntax. */
			if (function->parameter_count == 1 && !parameter->has_name && !declared->qualifiers) {
				parameter->type = declared;
				parameter->is_void_marker = true;
				void_marker = true;
				continue;
			}
			diagnostic_error(sema->diagnostics, parameter->location, "parameter cannot have void type");
			goto done;
		}
		parameter->type = adjust_parameter_type(sema, declared, parameter->location);
		if (!parameter->type)
			goto done;
		parameters[count] = unqualified_type(sema, parameter->type, parameter->location);
		if (!parameters[count] || !bind_prototype_parameter(sema, parameter))
			goto done;
		count++;
	}
	/* Written query-derived void has one node, but the ABI has no parameters. */
	assert(count + (void_marker ? 1 : 0) == function->parameter_count);
	assert(count <= ast_max_parameters);
	return_type = unqualified_type(sema, return_type, function->return_syntax->location);
	if (!return_type)
		goto done;
	type = type_new_function(sema->arena, return_type, parameters, count);
	if (!type)
		diagnostic_error(sema->diagnostics, function->syntax.location, "out of memory creating function type");
done:
	sema->scope = scope.parent;
	return type ? &type->type : NULL;
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
		((source->kind == type_kind_pointer || source->kind == type_kind_nullptr) && target->kind == type_kind_bool))
		return true;
	diagnostic_error(sema->diagnostics, location,
		"unsupported pointer conversion (incompatible pointers or integer/pointer conversion)");
	return false;
}

/* C23 6.3.2.3: nullptr, a zero integer constant expression, or that
 * integer expression explicitly cast to unqualified void *. A zero-valued object is not enough.
 * Query only checked trees; failure is not evidence of a null constant.
 */
static bool is_null_pointer_constant(const struct ast_expression *expression)
{
	struct constant_result result;

	if (expression->kind == expression_nullptr)
		return true;
	if (expression->kind == expression_cast && expression->type->kind == type_kind_pointer) {
		const struct type *referent = ((const struct pointer_type *)expression->type)->referent;

		if (referent->kind != type_kind_void || referent->qualifiers)
			return false;
		expression = ((const struct ast_cast_expression *)expression)->operand;
	}
	if (!type_is_integer(expression->type))
		return false;
	result = evaluate_integer_constant(expression);
	return result.status == constant_value && result.bits == 0;
}

/* A nullptr_t value need not itself be a constant (for example, a comma
 * result). The conversion/equality rules admit either kind of source.
 */
static bool is_null_pointer_source(const struct ast_expression *expression)
{
	return expression->type->kind == type_kind_nullptr || is_null_pointer_constant(expression);
}

/* Explicit casts do not grant assignment compatibility or adapt function ABIs. */
static bool check_cast(struct sema *sema, const struct ast_expression *operand,
	const struct type *target, struct source_location location)
{
	const struct type *source = operand->type;

	/* Both explicit and assignment-like conversions admit checked null constants.
	 * Nonconstant integer/pointer zero values remain ineligible.
	 */
	if (target->kind == type_kind_nullptr) {
		if (is_null_pointer_source(operand))
			return true;
		diagnostic_error(sema->diagnostics, location,
			"cast to nullptr type requires a null pointer constant or nullptr value");
		return false;
	}
	if (target->kind == type_kind_pointer && is_null_pointer_source(operand))
		return true;
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

	/* C23's normative assignment constraint admits a null pointer constant
	 * for nullptr_t as well as pointer targets. Keep the source-form check.
	 */
	if (!((target->kind == type_kind_pointer || target->kind == type_kind_nullptr) &&
		is_null_pointer_source(*slot)) &&
		!check_conversion(sema, (*slot)->type, target, (*slot)->location))
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

	/* nullptr_t/null-constant equality lowers to explicit void * conversions.
	 * Original nullptr_t and integer operands remain inside their own nodes.
	 */
	if (equality && ((left->kind == type_kind_nullptr && is_null_pointer_source(node->right)) ||
		(right->kind == type_kind_nullptr && is_null_pointer_source(node->left)))) {
		struct pointer_type *pointer = type_new_pointer(sema->arena, &type_void);

		if (!pointer) {
			diagnostic_error(sema->diagnostics, node->expression.location,
				"out of memory creating nullptr comparison type");
			return false;
		}
		return convert_expression(sema, &node->left, &pointer->type) &&
			convert_expression(sema, &node->right, &pointer->type);
	}
	/* Equality accepts a null constant in either position, including void *
	 * null constants opposite function pointers. Relational operators do not.
	 */
	if (equality && left->kind == type_kind_pointer && is_null_pointer_source(node->right))
		return convert_expression(sema, &node->right, left);
	if (equality && right->kind == type_kind_pointer && is_null_pointer_source(node->left))
		return convert_expression(sema, &node->left, right);
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
/* Both update forms keep one lvalue subtree, never a duplicated assignment. */
static const struct type *sema_update_operand(struct sema *sema,
	struct ast_expression *expression, struct ast_expression **operand,
	const struct type **calculation_type, uint64_t *element_size)
{
	const struct type *operand_type;
	const struct type *result_type;

	if (!sema_expression(sema, operand, false))
		return NULL;
	operand_type = (*operand)->type;
	if (!(*operand)->is_lvalue || (operand_type->qualifiers & type_qualifier_const) ||
		(!type_is_integer(operand_type) && operand_type->kind != type_kind_pointer)) {
		diagnostic_error(sema->diagnostics, expression->location,
			"update requires a modifiable integer or pointer lvalue");
		return NULL;
	}
	result_type = unqualified_type(sema, operand_type, expression->location);
	if (!result_type)
		return NULL;
	if (operand_type->kind == type_kind_pointer) {
		const struct type *referent = ((const struct pointer_type *)operand_type)->referent;

		if (!type_is_complete_object(referent)) {
			diagnostic_error(sema->diagnostics, expression->location,
				"pointer update requires a complete object referent");
			return NULL;
		}
		*calculation_type = result_type;
		*element_size = type_object_size(referent);
	} else {
		*calculation_type = type_integer_promotion(result_type);
		*element_size = 0;
	}
	expression->depth = (*operand)->depth + 1;
	return result_type;
}

static struct external_object_symbol *visible_file_object(struct sema *sema, struct token name)
{
	struct external_object_symbol *symbol = find_external_object(sema, name);
	return symbol && symbol->file_type ? symbol : NULL;
}

static struct function_symbol *visible_file_function(struct sema *sema, struct token name)
{
	struct function_symbol *symbol = find_function(sema, name);
	return symbol && symbol->file_type ? symbol : NULL;
}

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

			if (!find_typedef(sema, name->name) && !find_local(sema, name->name) &&
				!visible_file_function(sema, name->name) && !visible_file_object(sema, name->name)) {
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
		if (node->operand->kind == expression_name &&
			((struct ast_name_expression *)node->operand)->declaration->is_register) {
			diagnostic_error(sema->diagnostics, expression->location,
				"cannot take the address of a register object");
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
	case expression_nullptr:
		result_type = &type_nullptr;
		break;
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
		struct external_object_symbol *object;

		/* A visible typedef hides outer ordinary names; it is never a value. */
		if (find_typedef(sema, node->name)) {
			diagnostic_error(sema->diagnostics, expression->location, "typedef name is not an expression");
			return false;
		}
		node->declaration = find_local(sema, node->name);
		object = node->declaration ? node->declaration->object_symbol :
			visible_file_object(sema, node->name);
		if (sema->function && object && object->is_internal && !object->is_block_static) {
				sema->function->inline_has_internal_reference = true;
				sema->function->inline_reference_location = expression->location;
			}
		if (object) {
			struct ast_external_object_expression *reference =
				ast_new_external_object(sema->arena, expression->location, object);

			if (!reference) {
				diagnostic_error(sema->diagnostics, expression->location,
					"out of memory creating external object reference");
				return false;
			}
			*expression_slot = expression = &reference->expression;
			expression->is_lvalue = true;
			result_type = node->declaration ? node->declaration->type : object->file_type;
		} else if (node->declaration && !node->declaration->function_symbol) {
			if (!node->declaration->type) {
				diagnostic_error(sema->diagnostics, expression->location,
					"inferred name is unavailable in its initializer");
				return false;
			}
			result_type = node->declaration->type;
			expression->is_lvalue = true;
		} else {
			struct function_symbol *function = node->declaration ?
				node->declaration->function_symbol : visible_file_function(sema, node->name);
			struct ast_function_designator_expression *designator;

			if (!function) {
				diagnostic_error(sema->diagnostics, expression->location, "use of undeclared identifier");
				return false;
			}
			if (sema->function && function->is_internal) {
				sema->function->inline_has_internal_reference = true;
				sema->function->inline_reference_location = expression->location;
			}
			designator = ast_new_function_designator(sema->arena, expression->location, function);
			if (!designator) {
				diagnostic_error(sema->diagnostics, expression->location, "out of memory creating function designator");
				return false;
			}
			if (!sema->unevaluated)
				function->is_referenced = true;
			*expression_slot = expression = &designator->expression;
			result_type = node->declaration ? node->declaration->type : &function->file_type->type;
		}
		break;
	}
	case expression_sizeof: {
		struct ast_sizeof_expression *node = (struct ast_sizeof_expression *)expression;

		/* No immediate load/array/function decay; constraints still apply inside. */
		if (!sema_unevaluated_expression(sema, &node->operand))
			return false;
		if (!type_is_complete_object(node->operand->type)) {
			diagnostic_error(sema->diagnostics, expression->location, "sizeof requires a complete object type");
			return false;
		}
		node->size = type_object_size(node->operand->type);
		result_type = &type_ulong;
		expression->depth = node->operand->depth + 1;
		break;
	}
	case expression_sizeof_type: {
		struct ast_sizeof_type_expression *node = (struct ast_sizeof_type_expression *)expression;
		const struct type *type = resolve_unevaluated_type_syntax(sema, node->type_syntax);

		if (!type)
			return false;
		if (!type_is_complete_object(type)) {
			diagnostic_error(sema->diagnostics, expression->location, "sizeof requires a complete object type");
			return false;
		}
		node->size = type_object_size(type);
		result_type = &type_ulong;
		break;
	}
	case expression_alignof: {
		struct ast_alignof_expression *node = (struct ast_alignof_expression *)expression;
		const struct type *type = resolve_unevaluated_type_syntax(sema, node->type_syntax);

		if (!type)
			return false;
		if (!type_is_complete_object(type)) {
			diagnostic_error(sema->diagnostics, expression->location, "alignof requires a complete object type");
			return false;
		}
		node->alignment = type_object_alignment(type);
		result_type = &type_ulong;
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
		if (!check_cast(sema, node->operand, result_type, expression->location))
			return false;
		expression->depth = node->operand->depth + 1;
		break;
	}
	case expression_postfix_update: {
		struct ast_postfix_update_expression *node = (struct ast_postfix_update_expression *)expression;

		result_type = sema_update_operand(sema, expression, &node->operand,
			&node->calculation_type, &node->element_size);
		if (!result_type)
			return false;
		break;
	}
	case expression_prefix_update: {
		struct ast_prefix_update_expression *node = (struct ast_prefix_update_expression *)expression;

		result_type = sema_update_operand(sema, expression, &node->operand,
			&node->calculation_type, &node->element_size);
		if (!result_type)
			return false;
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
					"pointer comparison requires compatible pointers or an equality null constant");
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
		} else if (a->kind == type_kind_nullptr && b->kind == type_kind_nullptr) {
			result_type = &type_nullptr;
		} else if (a->kind == type_kind_void && b->kind == type_kind_void) {
			result_type = &type_void;
		} else if (a->kind == type_kind_pointer && is_null_pointer_source(node->else_value)) {
			result_type = a;
		} else if (b->kind == type_kind_pointer && is_null_pointer_source(node->then_value)) {
			result_type = b;
		} else if (a->kind == type_kind_pointer && b->kind == type_kind_pointer &&
			(type_unqualified_compatible(((const struct pointer_type *)a)->referent,
				((const struct pointer_type *)b)->referent) || object_void_pointer_conversion(a, b))) {
			result_type = common_pointer_type(sema, a, b, expression->location);
			if (!result_type)
				return false;
		} else {
			diagnostic_error(sema->diagnostics, expression->location,
				"incompatible conditional operands");
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
	case expression_compound_assignment: {
		struct ast_compound_assignment_expression *node =
			(struct ast_compound_assignment_expression *)expression;
		const struct type *left_type;
		unsigned depth;

		if (!sema_expression(sema, &node->left, false))
			return false;
		left_type = node->left->type;
		if (!node->left->is_lvalue || (left_type->qualifiers & type_qualifier_const) ||
			(!type_is_integer(left_type) && left_type->kind != type_kind_pointer)) {
			diagnostic_error(sema->diagnostics, node->left->location,
				"compound assignment requires a modifiable integer or pointer lvalue");
			return false;
		}
		if (!sema_expression(sema, &node->right, true))
			return false;
		if (!type_is_integer(node->right->type)) {
			diagnostic_error(sema->diagnostics, node->right->location,
				"compound assignment requires an integer right operand");
			return false;
		}
		result_type = unqualified_type(sema, left_type, expression->location);
		if (!result_type)
			return false;
		if (left_type->kind == type_kind_pointer) {
			const struct type *referent = ((const struct pointer_type *)left_type)->referent;

			if (node->operation != binary_add && node->operation != binary_subtract) {
				diagnostic_error(sema->diagnostics, expression->location,
					"only additive compound assignment accepts a pointer left operand");
				return false;
			}
			if (!type_is_complete_object(referent)) {
				diagnostic_error(sema->diagnostics, expression->location,
					"pointer compound assignment requires a complete object referent");
				return false;
			}
			node->calculation_type = result_type;
			node->element_size = type_object_size(referent);
			if (!convert_expression(sema, &node->right, type_integer_promotion(node->right->type)))
				return false;
		} else if (node->operation == binary_shift_left || node->operation == binary_shift_right) {
			/* Shift operands promote independently; unsigned RHS does not change left. */
			node->calculation_type = type_integer_promotion(result_type);
			node->element_size = 0;
			if (!convert_expression(sema, &node->right, type_integer_promotion(node->right->type)))
				return false;
		} else {
			node->calculation_type = type_usual_arithmetic(result_type, node->right->type);
			node->element_size = 0;
			if (!convert_expression(sema, &node->right, node->calculation_type))
				return false;
		}
		depth = node->left->depth > node->right->depth ? node->left->depth : node->right->depth;
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
	case expression_external_object:
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
		struct pointer_type *pointer;
		struct ast_array_decay_expression *decay;

		/* Direct sizeof/typeof operands never enter value conversion. */
		if (!sema->unevaluated && expression->kind == expression_name &&
			((struct ast_name_expression *)expression)->declaration->is_register) {
			diagnostic_error(sema->diagnostics, expression->location,
				"register array-to-pointer conversion is not supported");
			return false;
		}
		pointer = type_new_pointer(sema->arena, array->element);
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

/* Reserve an ordinary name before any initializer is analyzed. */
static bool reserve_local_name(struct sema *sema, struct ast_local_declaration *local)
{
	struct binding *binding;
	struct typedef_binding *alias = find_typedef_binding(sema, local->name);

	if (alias && alias->scope == sema->scope) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"ordinary declaration conflicts with typedef name");
		return false;
	}
	if (find_in_scope(sema->scope, local->name)) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"redeclaration of local in this scope");
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
	return true;
}

/* Parameter spills use the adjusted type, retaining written source syntax. */
static bool complete_local_storage(struct sema *sema, struct ast_local_declaration *local,
	const struct type *effective_type)
{
	assert(type_is_complete_object(effective_type));
	if (sema->local_count == ast_max_locals) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"function exceeds local limit (256)");
		return false;
	}
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
	return true;
}

/* Analyze once: lowered loads/decays/conversions must never be revisited. */
static bool sema_local_initializer(struct sema *sema, struct ast_local_declaration *local)
{
	if (local->initializer) {
		const struct type *target = unqualified_type(sema, local->type, local->name.location);

		return target && sema_expression(sema, &local->initializer, true) &&
			convert_expression(sema, &local->initializer, target);
	}
	return true;
}

/* Explicit declarations complete their binding before the initializer. */
static bool bind_local(struct sema *sema, struct ast_local_declaration *local,
	const struct type *effective_type)
{
	return reserve_local_name(sema, local) && complete_local_storage(sema, local, effective_type) &&
		sema_local_initializer(sema, local);
}

/* Hide outer names immediately, but expose no type until inference completes. */
static bool sema_inferred_local(struct sema *sema, struct ast_local_declaration *local)
{
	struct ast_inferred_type_syntax *syntax = (struct ast_inferred_type_syntax *)local->type_syntax;
	const struct type *type;
	const struct type *target;

	if (!local->initializer) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"inferred auto requires an assignment initializer");
		return false;
	}
	if (!reserve_local_name(sema, local) || !sema_expression(sema, &local->initializer, true))
		return false;
	type = local->initializer->type;
	if (!type_is_scalar(type) || !type_is_complete_object(type)) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"inferred auto requires a complete scalar initializer type");
		return false;
	}
	type = type_qualified(sema->arena, type, syntax->qualifiers);
	if (!type) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"out of memory qualifying inferred type");
		return false;
	}
	syntax->syntax.type = type;
	if (!complete_local_storage(sema, local, type))
		return false;
	target = unqualified_type(sema, type, local->name.location);
	return target && convert_expression(sema, &local->initializer, target);
}

static bool sema_block_storage(struct sema *sema, struct ast_local_declaration *local,
	const struct type *type);

static bool sema_local(struct sema *sema, struct ast_local_declaration *local)
{
	const struct type *type;

	if (local->is_inline && local->type_syntax->kind == type_syntax_inferred) {
		diagnostic_error(sema->diagnostics, local->name.location, "inline requires a function declaration");
		return false;
	}
	if (local->type_syntax->kind == type_syntax_inferred) {
		if (local->is_static || local->is_extern) {
			diagnostic_error(sema->diagnostics, local->name.location,
				"static or extern auto inference is not supported yet");
			return false;
		}
		return sema_inferred_local(sema, local);
	}
	type = resolve_type_syntax(sema, local->type_syntax);
	if (!type)
		return false;
	if (local->is_inline && type->kind != type_kind_function) {
		diagnostic_error(sema->diagnostics, local->name.location, "inline requires a function declaration");
		return false;
	}
	if (local->is_auto && type->kind == type_kind_function) {
		diagnostic_error(sema->diagnostics, local->name.location, "auto storage requires an object type");
		return false;
	}
	if (local->is_extern || local->is_static || type->kind == type_kind_function)
		return sema_block_storage(sema, local, type);
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

static bool sema_control_body(struct sema *sema, struct ast_statement *statement,
	struct ast_statement *body)
{
	struct control_context context = { sema->control, statement };
	bool success;

	sema->control = &context;
	success = sema_substatement(sema, body);
	sema->control = context.parent;
	return success;
}

static bool sema_switch(struct sema *sema, struct ast_switch_statement *node)
{
	struct scope scope = { .parent = sema->scope };
	bool success;

	sema->scope = &scope;
	success = sema_expression(sema, &node->control, true);
	if (success && !type_is_integer(node->control->type)) {
		diagnostic_error(sema->diagnostics, node->control->location,
			"switch control requires an integer expression");
		success = false;
	}
	if (success)
		success = convert_expression(sema, &node->control,
			type_integer_promotion(node->control->type));
	if (success)
		success = sema_control_body(sema, &node->statement, node->body);
	sema->scope = scope.parent;
	return success;
}

static bool sema_while(struct sema *sema, struct ast_while_statement *node)
{
	struct scope scope = { .parent = sema->scope };
	bool success;

	sema->scope = &scope;
	success = sema_condition(sema, &node->condition);
	if (success)
		success = sema_control_body(sema, &node->statement, node->body);
	sema->scope = scope.parent;
	return success;
}

static bool sema_do(struct sema *sema, struct ast_do_statement *node)
{
	struct scope scope = { .parent = sema->scope };
	bool success;

	sema->scope = &scope;
	success = sema_control_body(sema, &node->statement, node->body);
	if (success)
		success = sema_condition(sema, &node->condition);
	sema->scope = scope.parent;
	return success;
}

static bool sema_typedef_declaration(struct sema *sema, struct ast_typedef_declaration *declaration);

static bool sema_block_items(struct sema *sema, struct ast_block_item *item);

static bool sema_for(struct sema *sema, struct ast_for_statement *node)
{
	struct scope scope = { .parent = sema->scope };
	struct typedef_binding *saved_typedefs = sema->typedefs;
	bool success = true;

	sema->scope = &scope;
	if (node->initializer_declarations)
		success = sema_block_items(sema, node->initializer_declarations);
	for (struct ast_block_item *item = node->initializer_declarations; success && item; item = item->next) {
		if (item->kind == block_item_declaration) {
			struct ast_local_declaration *local = (struct ast_local_declaration *)item;
			if (local->object_symbol || local->function_symbol) {
				diagnostic_error(sema->diagnostics, local->name.location,
					"for declaration requires an automatic or register object");
				success = false;
			}
		}
	}
	if (success && node->initializer_expression)
		success = sema_expression(sema, &node->initializer_expression, true);
	if (success && node->condition)
		success = sema_condition(sema, &node->condition);
	if (success && node->step)
		success = sema_expression(sema, &node->step, true);
	if (success)
		success = sema_control_body(sema, &node->statement, node->body);
	sema->typedefs = saved_typedefs;
	sema->scope = scope.parent;
	return success;
}

/* Labels have function scope, separate from ordinary object/function names. */
static bool sema_label(struct sema *sema, struct ast_label *label)
{
	struct label_binding *binding;

	for (binding = sema->labels; binding; binding = binding->next)
		if (same_name(binding->label->name, label->name)) {
			diagnostic_error(sema->diagnostics, label->name.location, "duplicate label in function");
			return false;
		}
	if (sema->label_count == ast_max_labels) {
		diagnostic_error(sema->diagnostics, label->name.location, "function exceeds label limit (512)");
		return false;
	}
	binding = arena_alloc(sema->arena, sizeof(*binding));
	if (!binding) {
		diagnostic_error(sema->diagnostics, label->name.location, "out of memory binding label");
		return false;
	}
	*binding = (struct label_binding) { .label = label, .next = sema->labels };
	sema->labels = binding;
	label->index = sema->label_count++;
	return true;
}

static bool sema_goto(struct sema *sema, struct ast_goto_statement *node)
{
	struct goto_reference *reference;

	if (sema->goto_count == ast_max_gotos) {
		diagnostic_error(sema->diagnostics, node->statement.location, "function exceeds goto limit (4096)");
		return false;
	}
	reference = arena_alloc(sema->arena, sizeof(*reference));
	if (!reference) {
		diagnostic_error(sema->diagnostics, node->statement.location, "out of memory recording goto");
		return false;
	}
	*reference = (struct goto_reference) { .statement = node, .next = sema->gotos };
	sema->gotos = reference;
	sema->goto_count++;
	return true;
}

/* Only the complete function label namespace can resolve forward references. */
static bool resolve_gotos(struct sema *sema)
{
	for (struct goto_reference *reference = sema->gotos; reference; reference = reference->next) {
		struct ast_goto_statement *node = reference->statement;
		struct label_binding *binding;

		for (binding = sema->labels; binding; binding = binding->next)
			if (same_name(binding->label->name, node->name))
				break;
		if (!binding) {
			diagnostic_error(sema->diagnostics, node->name.location,
				"goto target is not defined in this function");
			return false;
		}
		node->target = binding->label;
	}
	return true;
}

/* A loop does not hide its enclosing switch from case/default labels. */
static struct ast_switch_statement *enclosing_switch(struct sema *sema)
{
	struct control_context *context = sema->control;

	while (context && context->statement->kind != statement_switch)
		context = context->parent;
	return context ? (struct ast_switch_statement *)context->statement : NULL;
}

static bool reserve_switch_label(struct sema *sema, struct ast_switch_statement *owner,
	struct source_location location, size_t *index)
{
	if (owner->label_count == ast_max_switch_labels) {
		diagnostic_error(sema->diagnostics, location, "switch exceeds label limit (1024)");
		return false;
	}
	if (sema->switch_label_count == ast_max_function_switch_labels) {
		diagnostic_error(sema->diagnostics, location, "function exceeds switch-label limit (4096)");
		return false;
	}
	*index = sema->switch_label_count++;
	owner->label_count++;
	return true;
}

static bool sema_case_label(struct sema *sema, struct ast_case_label *label)
{
	struct ast_switch_statement *owner = enclosing_switch(sema);
	struct constant_result result;

	if (!owner) {
		diagnostic_error(sema->diagnostics, label->location, "case requires an enclosing switch");
		return false;
	}
	if (!sema_expression(sema, &label->value, true))
		return false;
	if (!type_is_integer(label->value->type)) {
		diagnostic_error(sema->diagnostics, label->value->location, "case requires an integer constant expression");
		return false;
	}
	if (!convert_expression(sema, &label->value, owner->control->type))
		return false;
	result = evaluate_integer_constant(label->value);
	if (result.status != constant_value) {
		diagnostic_error(sema->diagnostics, result.location, result.message);
		return false;
	}
	for (struct ast_case_label *previous = owner->cases; previous; previous = previous->next)
		if (previous->bits == result.bits) {
			diagnostic_error(sema->diagnostics, label->location, "duplicate case value after conversion");
			return false;
		}
	if (!reserve_switch_label(sema, owner, label->location, &label->index))
		return false;
	label->owner = owner;
	label->bits = result.bits;
	/* Dispatch order is immaterial; source-order target indices stay stable. */
	label->next = owner->cases;
	owner->cases = label;
	return true;
}

static bool sema_default_label(struct sema *sema, struct ast_default_label *label)
{
	struct ast_switch_statement *owner = enclosing_switch(sema);

	if (!owner) {
		diagnostic_error(sema->diagnostics, label->location, "default requires an enclosing switch");
		return false;
	}
	if (owner->default_label) {
		diagnostic_error(sema->diagnostics, label->location, "duplicate default label in switch");
		return false;
	}
	if (!reserve_switch_label(sema, owner, label->location, &label->index))
		return false;
	label->owner = owner;
	owner->default_label = label;
	return true;
}

static bool sema_statement(struct sema *sema, struct ast_statement *statement)
{
	switch (statement->kind) {
	case statement_case: {
		struct ast_case_statement *node = (struct ast_case_statement *)statement;

		return sema_case_label(sema, node->label) && sema_statement(sema, node->body);
	}
	case statement_default: {
		struct ast_default_statement *node = (struct ast_default_statement *)statement;

		return sema_default_label(sema, node->label) && sema_statement(sema, node->body);
	}
	case statement_goto:
		return sema_goto(sema, (struct ast_goto_statement *)statement);
	case statement_labeled: {
		struct ast_labeled_statement *node = (struct ast_labeled_statement *)statement;

		return sema_label(sema, node->label) && sema_statement(sema, node->body);
	}
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
	case statement_switch:
		return sema_switch(sema, (struct ast_switch_statement *)statement);
	case statement_while:
		return sema_while(sema, (struct ast_while_statement *)statement);
	case statement_break: {
		struct ast_break_statement *node = (struct ast_break_statement *)statement;

		if (!sema->control) {
			diagnostic_error(sema->diagnostics, statement->location,
				"break requires an enclosing loop or switch");
			return false;
		}
		node->target = sema->control->statement;
		return true;
	}
	case statement_continue: {
		struct ast_continue_statement *node =
			(struct ast_continue_statement *)statement;
		struct control_context *context = sema->control;

		while (context && context->statement->kind == statement_switch)
			context = context->parent;
		if (!context) {
			diagnostic_error(sema->diagnostics, statement->location,
				"continue requires an enclosing loop");
			return false;
		}
		node->target = context->statement;
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

/* Assertion messages are diagnostic bytes, never static objects or format strings. */
static void failed_static_assertion(struct sema *sema, const struct ast_static_assertion *node)
{
	static const char prefix[] = "static assertion failed: ";
	static const char hex[] = "0123456789abcdef";
	const struct ast_string_expression *string = node->message;
	char *message;
	size_t offset;

	if (!string) {
		diagnostic_error(sema->diagnostics, node->location, "static assertion failed");
		return;
	}
	/* Parser bounds message length by ast_max_string_length. */
	message = arena_alloc(sema->arena, sizeof(prefix) + 2 + string->length * 4);
	if (!message) {
		diagnostic_error(sema->diagnostics, node->location,
			"out of memory formatting static assertion message");
		return;
	}
	memcpy(message, prefix, sizeof(prefix) - 1);
	offset = sizeof(prefix) - 1;
	message[offset++] = '"';
	for (size_t i = 0; i < string->length; i++) {
		unsigned char byte = string->bytes[i];

		if (byte == '"' || byte == '\\') {
			message[offset++] = '\\';
			message[offset++] = (char)byte;
		} else if (byte >= 32 && byte <= 126) {
			message[offset++] = (char)byte;
		} else {
			message[offset++] = '\\';
			message[offset++] = 'x';
			message[offset++] = hex[byte >> 4];
			message[offset++] = hex[byte & 15];
		}
	}
	message[offset++] = '"';
	message[offset] = 0;
	diagnostic_error(sema->diagnostics, node->location, message);
}

static bool sema_static_assertion(struct sema *sema, struct ast_static_assertion *node)
{
	struct constant_result result;

	if (!sema_expression(sema, &node->condition, true))
		return false;
	result = evaluate_integer_constant(node->condition);
	if (result.status != constant_value) {
		diagnostic_error(sema->diagnostics, result.location, result.message);
		return false;
	}
	if (!result.bits) {
		failed_static_assertion(sema, node);
		return false;
	}
	return true;
}

static bool sema_block_items(struct sema *sema, struct ast_block_item *item)
{
	while (item) {
		switch (item->kind) {
		case block_item_case:
			if (!sema_case_label(sema, ((struct ast_block_case *)item)->label))
				return false;
			break;
		case block_item_default:
			if (!sema_default_label(sema, ((struct ast_block_default *)item)->label))
				return false;
			break;
		case block_item_label:
			if (!sema_label(sema, ((struct ast_block_label *)item)->label))
				return false;
			break;
		case block_item_static_assertion:
			if (!sema_static_assertion(sema, ((struct ast_block_static_assertion *)item)->declaration))
				return false;
			break;
		case block_item_typedef_declaration:
			if (!sema_typedef_declaration(sema, ((struct ast_block_typedef_declaration *)item)->declaration))
				return false;
			break;
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
	struct typedef_binding *saved_typedefs = sema->typedefs;
	bool success;

	sema->scope = &scope;
	success = sema_block_items(sema, node->items);
	sema->typedefs = saved_typedefs;
	sema->scope = scope.parent;
	return success;
}

static bool sema_function_body(struct sema *sema, struct ast_function *definition)
{
	struct scope scope = { 0 };
	struct typedef_binding *saved_typedefs = sema->typedefs;
	bool success = false;

	assert(!sema->scope && !sema->control);
	sema->function = definition;
	sema->labels = NULL;
	sema->label_count = 0;
	sema->switch_label_count = 0;
	sema->gotos = NULL;
	sema->goto_count = 0;
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
		parameter->local->is_register = parameter->is_register;
		if (!bind_local(sema, parameter->local, parameter->type))
			goto done;
	}
	/* Parameters and outermost body declarations inhabit the same scope. */
	success = sema_block_items(sema, definition->body->items) && resolve_gotos(sema);
	if (success) {
		definition->label_count = sema->label_count;
		definition->switch_label_count = sema->switch_label_count;
	}
done:
	sema->typedefs = saved_typedefs;
	sema->scope = NULL;
	sema->function = NULL;
	sema->labels = NULL;
	sema->label_count = 0;
	sema->switch_label_count = 0;
	sema->gotos = NULL;
	sema->goto_count = 0;
	return success;
}

/* Shared registration preserves one compatibility/composite policy for both
 * written function declarators and query-derived function declarations.
 */
static struct function_symbol *register_function(struct sema *sema, struct token name,
	const struct function_type *type, struct ast_function *definition, bool is_static)
{
	struct function_symbol *symbol = find_function(sema, name);
	bool canonical_is_visible = symbol && symbol->file_type == symbol->type;
	const struct type *return_type;

	if (find_external_object(sema, name)) {
		diagnostic_error(sema->diagnostics, name.location,
			"function name conflicts with external object");
		return NULL;
	}
	if (!sema->scope && find_typedef(sema, name)) {
		diagnostic_error(sema->diagnostics, name.location, "function name conflicts with typedef name");
		return NULL;
	}
	if (name.length == 4 && memcmp(name.spelling_location.source->data +
		name.spelling_location.offset, "main", 4) == 0 && type->parameter_count) {
		diagnostic_error(sema->diagnostics, name.location,
			"only zero-parameter main is supported yet");
		return NULL;
	}
	if (is_static && name.length == 4 && memcmp(name.spelling_location.source->data +
		name.spelling_location.offset, "main", 4) == 0) {
		diagnostic_error(sema->diagnostics, name.location,
			"static main is not supported on the Linux target");
		return NULL;
	}
	if (is_static && symbol && !symbol->is_internal) {
		diagnostic_error(sema->diagnostics, name.location,
			"static declaration after external linkage is not supported");
		return NULL;
	}
	return_type = type->return_type;
	if (name.length == 4 && memcmp(name.spelling_location.source->data +
		name.spelling_location.offset, "main", 4) == 0 &&
		!type_compatible(return_type, &type_int)) {
		diagnostic_error(sema->diagnostics, name.location, "main must return int");
		return NULL;
	}
	if (symbol && !type_compatible(&symbol->type->type, &type->type)) {
		diagnostic_error(sema->diagnostics, name.location,
			"incompatible function declaration");
		return NULL;
	}

	if (!symbol) {
		if (sema->function_count == ast_max_functions) {
			diagnostic_error(sema->diagnostics, name.location,
				"translation unit exceeds function limit (256)");
			return NULL;
		}
		symbol = arena_alloc(sema->arena, sizeof(*symbol));
		if (!symbol) {
			diagnostic_error(sema->diagnostics, name.location,
				"out of memory creating function symbol");
			return NULL;
		}
		*symbol = (struct function_symbol) {
			.name = name,
			.type = type,
			.is_internal = is_static,
			.next = sema->functions,
		};
		sema->functions = symbol;
		sema->function_count++;
	}
	if (definition && symbol->definition) {
		diagnostic_error(sema->diagnostics, name.location,
			"redefinition of function");
		return NULL;
	}
	/* Compatibility alone is not transitive for unknown array bounds. Retain
	 * known bounds in the visible composite without rewriting syntax caches.
	 */
	if (symbol->type != type) {
		const struct type *composite = type_composite(sema->arena, &symbol->type->type, &type->type);

		if (!composite) {
			diagnostic_error(sema->diagnostics, name.location,
				"out of memory creating composite function type");
			return NULL;
		}
		symbol->type = (const struct function_type *)composite;
	}
	if (!sema->scope) {
		const struct type *visible = canonical_is_visible ? &symbol->type->type : symbol->file_type ?
			type_composite(sema->arena, &symbol->file_type->type, &type->type) : &type->type;
		if (!visible) {
			diagnostic_error(sema->diagnostics, name.location, "out of memory creating visible function type");
			return NULL;
		}
		symbol->file_type = (const struct function_type *)visible;
	}
	return symbol;
}

/* A tentative anchor owns storage once; extern-only symbols own none. */
static struct external_object_symbol *register_external_object(struct sema *sema,
	struct token name, const struct type *type,
	struct ast_external_declaration *tentative_definition, bool is_static, bool is_extern, bool is_thread_local)
{
	struct external_object_symbol *symbol = find_external_object(sema, name);
	const struct type *composite = type;

	if (tentative_definition && name.length == 4 && memcmp(name.spelling_location.source->data +
		name.spelling_location.offset, "main", 4) == 0) {
		diagnostic_error(sema->diagnostics, name.location,
			"tentative main object is not supported on the Linux target");
		return NULL;
	}
	if (!type_is_scalar(type) && type->kind != type_kind_array) {
		diagnostic_error(sema->diagnostics, name.location,
			"only scalar or array file-scope objects are supported yet");
		return NULL;
	}
	/* C23 6.2.2p4-5: only extern inherits prior object linkage. Unlike
	 * functions, unadorned file objects always declare external linkage.
	 * Refuse mixed-linkage UB (p7) in either direction before mutation.
	 */
	if (symbol && ((is_static && !symbol->is_internal) ||
		(!is_static && !is_extern && symbol->is_internal))) {
		diagnostic_error(sema->diagnostics, name.location,
			"object declaration conflicts with prior linkage");
		return NULL;
	}
	if ((!sema->scope && find_typedef(sema, name)) || find_function(sema, name)) {
		diagnostic_error(sema->diagnostics, name.location,
			"external object conflicts with prior ordinary declaration");
		return NULL;
	}
	if (symbol && symbol->is_thread_local != is_thread_local) {
		diagnostic_error(sema->diagnostics, name.location,
			"thread_local declaration conflicts with prior storage duration");
		return NULL;
	}
	if (symbol) {
		if (!type_compatible(symbol->type, type)) {
			diagnostic_error(sema->diagnostics, name.location,
				"incompatible external object declaration");
			return NULL;
		}
		composite = type_composite(sema->arena, symbol->type, type);
		if (!composite) {
			diagnostic_error(sema->diagnostics, name.location,
				"out of memory creating composite external object type");
			return NULL;
		}
	}
	/* C23 6.9.2p3 requires internal tentative objects to be complete NOW,
	 * using the composite with visible PRIOR declarations (6.2.7p4).
	 * A later declaration or TU-end fallback cannot repair this UB.
	 * Keep both canonical state and captured written types untouched on error.
	 */
	if (tentative_definition && (symbol ? symbol->is_internal : is_static) &&
		!type_is_complete_object(composite)) {
		diagnostic_error(sema->diagnostics, name.location,
			"internal tentative object requires a complete type at its declaration");
		return NULL;
	}
	if (symbol) {
		if (!sema->scope) {
			const struct type *visible = symbol->file_type == symbol->type ? composite : symbol->file_type ?
				type_composite(sema->arena, symbol->file_type, type) : type;
			if (!visible) {
				diagnostic_error(sema->diagnostics, name.location, "out of memory creating visible object type");
				return NULL;
			}
			symbol->file_type = visible;
		}
		symbol->type = composite;
		if (tentative_definition && !symbol->tentative_definition)
			symbol->tentative_definition = tentative_definition;
		return symbol;
	}
	if (sema->external_object_count == ast_max_external_objects) {
		diagnostic_error(sema->diagnostics, name.location,
			"translation unit exceeds external object limit (256)");
		return NULL;
	}
	symbol = arena_alloc(sema->arena, sizeof(*symbol));
	if (!symbol) {
		diagnostic_error(sema->diagnostics, name.location,
			"out of memory creating external object symbol");
		return NULL;
	}
	*symbol = (struct external_object_symbol) {
		.name = name,
		.type = type,
		.tentative_definition = tentative_definition,
		.file_type = sema->scope ? NULL : type,
		.is_thread_local = is_thread_local,
		.is_internal = is_static,
		.next = sema->external_objects,
	};
	sema->external_objects = symbol;
	sema->external_object_count++;
	return symbol;
}

/* Make the declaration's own name visible during initialization, but publish
 * neither ownership nor a changed canonical composite on failure. Existing
 * expressions always retain the same canonical symbol identity.
 */
static struct external_object_symbol *sema_file_object(struct sema *sema,
	struct ast_external_declaration *external, struct token name,
	const struct type *type, struct ast_expression **initializer,
	bool is_static, bool is_extern, bool is_query, bool is_thread_local)
{
	struct external_object_symbol *previous = find_external_object(sema, name);
	struct external_object_symbol saved = { 0 };
	struct external_object_symbol *symbol;
	struct constant_result value;
	struct address_initializer_result address_value;
	bool is_address = false;
	bool zero_definition = !is_extern && !*initializer && (is_thread_local || sema->scope);
	const struct type *target;

	if (zero_definition && name.length == 4 && memcmp(name.spelling_location.source->data +
		name.spelling_location.offset, "main", 4) == 0) {
		diagnostic_error(sema->diagnostics, name.location, "main object definition is not supported on the Linux target");
		return NULL;
	}
	if (zero_definition && previous && previous->definition) {
		diagnostic_error(sema->diagnostics, name.location, "multiple definitions of thread_local object");
		return NULL;
	}
	if (*initializer) {
		if (!type_is_integer(type) && type->kind != type_kind_pointer && type->kind != type_kind_nullptr) {
			diagnostic_error(sema->diagnostics, (*initializer)->location,
				is_query ? "query-derived external declarations require ';' for non-integer initializers" :
				is_extern ? "non-integer extern object definitions are not supported yet" :
				"non-integer file-scope object initializers are not supported yet");
			return NULL;
		}
		if (previous && previous->definition) {
			diagnostic_error(sema->diagnostics, name.location,
				"multiple initialized definitions of object");
			return NULL;
		}
		if (name.length == 4 && memcmp(name.spelling_location.source->data +
			name.spelling_location.offset, "main", 4) == 0) {
			diagnostic_error(sema->diagnostics, name.location,
				"initialized main object is not supported on the Linux target");
			return NULL;
		}
	}
	if (previous)
		saved = *previous;
	symbol = register_external_object(sema, name, type,
		!is_extern && !*initializer && !zero_definition ? external : NULL, is_static, is_extern, is_thread_local);
	if (!symbol)
		return NULL;
	if (zero_definition) {
		const struct type *visible = sema->scope ? type : symbol->file_type;
		if (!type_is_complete_object(visible)) {
			diagnostic_error(sema->diagnostics, name.location, "thread_local definition requires a complete object type");
			goto rollback;
		}
		symbol->definition = external;
		symbol->initializer_value = (struct static_data_value) { .kind = static_data_zero };
		return symbol;
	}
	if (!*initializer)
		return symbol;
	if (!sema_expression(sema, initializer, true))
		goto rollback;
	/* Check the original expression before narrowing (notably to _Bool).
	 * An implicit conversion cannot hide evaluated invalid ICE arithmetic.
	 */
	if (type->kind == type_kind_pointer || type->kind == type_kind_nullptr) {
		struct null_initializer_result null_value = evaluate_null_initializer(*initializer);

		if (null_value.status == constant_invalid) {
			diagnostic_error(sema->diagnostics, null_value.location, null_value.message);
			goto rollback;
		}
		if (null_value.status != constant_value) {
			address_value = evaluate_address_initializer(*initializer);
			if (address_value.status != constant_value) {
				diagnostic_error(sema->diagnostics, address_value.location, address_value.message);
				goto rollback;
			}
			is_address = true;
		}
	} else {
		value = evaluate_integer_constant(*initializer);
		if (value.status != constant_value) {
			diagnostic_error(sema->diagnostics, value.location,
				value.status == constant_not_constant ?
				"file-scope initializer must be an integer constant expression" : value.message);
			goto rollback;
		}
	}
	target = unqualified_type(sema, type, name.location);
	if (!target || !convert_expression(sema, initializer, target))
		goto rollback;
	if (type->kind == type_kind_pointer || type->kind == type_kind_nullptr) {
		if (is_address) {
			/* Assignment conversion remains authoritative, but its ordinary
			 * void-pointer rule cannot widen this bounded static-data proof.
			 * Check the final type against the captured direct origin too.
			 */
			address_value = evaluate_address_initializer(*initializer);
			if (address_value.status != constant_value) {
				diagnostic_error(sema->diagnostics, address_value.location, address_value.message);
				goto rollback;
			}
			symbol->initializer_value = (struct static_data_value) {
				.kind = static_data_address, .address = address_value.address,
			};
		} else {
			/* Codegen selects the target's null encoding, not an ICE. */
			symbol->initializer_value = (struct static_data_value) { .kind = static_data_null_pointer };
		}
	} else {
		value = evaluate_integer_constant(*initializer);
		if (value.status != constant_value) {
			diagnostic_error(sema->diagnostics, value.location, value.message);
			goto rollback;
		}
		symbol->initializer_value = (struct static_data_value) {
			.kind = static_data_integer, .integer_bits = value.bits,
		};
	}
	symbol->definition = external;
	return symbol;
rollback:
	if (previous)
		*previous = saved;
	else {
		assert(sema->external_objects == symbol);
		sema->external_objects = symbol->next;
		sema->external_object_count--;
	}
	return NULL;
}

/* File declarations alone decide whether a body supplies an external
 * definition. Block declarations can request inline, but never change that
 * all-file-declarations predicate. No inline substitution is performed.
 */
static bool record_inline(struct sema *sema, struct function_symbol *symbol,
	bool is_inline, bool is_extern, bool at_file_scope, struct source_location location)
{
	if (is_inline && symbol->name.length == 4 && memcmp(symbol->name.spelling_location.source->data +
		symbol->name.spelling_location.offset, "main", 4) == 0) {
		diagnostic_error(sema->diagnostics, location, "inline is not permitted on hosted main");
		return false;
	}
	symbol->has_inline_declaration |= is_inline;
	if (at_file_scope && (!is_inline || is_extern))
		symbol->has_noninline_file_declaration = true;
	return true;
}

/* A block binding carries a source-point composite independently of the
 * canonical entity. Leaving its scope never publishes that composite elsewhere.
 */
static bool sema_block_storage(struct sema *sema, struct ast_local_declaration *local,
	const struct type *type)
{
	struct ast_local_declaration *prior = find_local(sema, local->name);
	struct ast_local_declaration *same = find_in_scope(sema->scope, local->name);
	struct typedef_binding *alias = find_typedef_binding(sema, local->name);
	const struct type *visible_type = NULL;
	bool inherited_internal = false;
	struct external_object_symbol *object = find_external_object(sema, local->name);
	struct function_symbol *function = find_function(sema, local->name);

	if (type->kind == type_kind_function) {
		if (local->is_thread_local || local->is_static || local->is_register) {
			diagnostic_error(sema->diagnostics, local->name.location,
				local->is_thread_local ? "thread_local requires an object type" :
				local->is_static ? "block-scope static function declaration is not permitted" :
				"register storage requires an object type");
			return false;
		}
	} else if (local->is_static && !type_is_complete_object(type)) {
		diagnostic_error(sema->diagnostics, local->name.location, "static local object type must be complete");
		return false;
	}
	if ((alias && alias->scope == sema->scope) ||
		(same && (local->is_static || (!same->object_symbol && !same->function_symbol) || same->is_static))) {
		diagnostic_error(sema->diagnostics, local->name.location,
			alias && alias->scope == sema->scope ? "ordinary declaration conflicts with typedef name" :
			"redeclaration of local in this scope");
		return false;
	}
	if (!local->is_static && local->initializer) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"block-scope extern declaration cannot have an initializer");
		return false;
	}
	if (local->is_static) {
		const struct type *qualified = type;

		while (qualified->kind == type_kind_array)
			qualified = ((const struct array_type *)qualified)->element;
		if (!(qualified->qualifiers & type_qualifier_const)) {
			sema->function->inline_has_modifiable_static = true;
			sema->function->inline_static_location = local->name.location;
		}
		struct source *source = arena_alloc(sema->arena, sizeof(*source));
		unsigned char *spelling = arena_alloc(sema->arena, 64);
		struct ast_external_object_declaration *definition;
		struct token name = local->name;

		if (!source || !spelling)
			goto allocation_failure;
		int length = snprintf((char *)spelling, 64, ".Lkcc.static.%zu", sema->static_count++);
		assert(length > 0 && length < 64);
		*source = (struct source) { .data = spelling, .length = (size_t)length };
		name.spelling_location = (struct source_location) { .source = source };
		name.length = (size_t)length;
		definition = ast_new_external_object_declaration(sema->arena,
			local->name.location, local->type_syntax, name, false);
		if (!definition)
			goto allocation_failure;
		definition->is_static = true;
		definition->is_thread_local = local->is_thread_local;
		definition->type = type;
		local->type = type;
		local->object_symbol = register_external_object(sema, name, type, NULL,
			true, false, local->is_thread_local);
		if (!local->object_symbol || !reserve_local_name(sema, local))
			return false;
		local->object_symbol->is_block_static = true;
		definition->symbol = sema_file_object(sema, &definition->external, name,
			type, &local->initializer, true, false, false, local->is_thread_local);
		if (!definition->symbol)
			return false;
		definition->initializer = local->initializer;
		*sema->static_tail = &definition->external;
		sema->static_tail = &definition->external.next;
		return true;
	}
	/* Only a lexically visible declaration with linkage contributes to the
	 * local composite and inherited linkage. An automatic/static-local/typedef
	 * hiding an internal entity must not silently inherit its linkage.
	 */
	if (!alias) {
		if (prior) {
			if (!prior->is_static && (prior->object_symbol || prior->function_symbol)) {
				visible_type = prior->type;
				inherited_internal = prior->object_symbol ? prior->object_symbol->is_internal :
					prior->function_symbol->is_internal;
			}
		} else if (object && object->file_type) {
			visible_type = object->file_type;
			inherited_internal = object->is_internal;
		} else if (function && function->file_type) {
			visible_type = &function->file_type->type;
			inherited_internal = function->is_internal;
		}
	}
	if ((object && object->is_internal && !inherited_internal) ||
		(function && function->is_internal && !inherited_internal)) {
		diagnostic_error(sema->diagnostics, local->name.location,
			"block extern declaration conflicts with hidden internal linkage");
		return false;
	}
	if (visible_type) {
		if (!type_compatible(visible_type, type)) {
			diagnostic_error(sema->diagnostics, local->name.location,
				type->kind == type_kind_function ? "incompatible function declaration" :
				"incompatible external object declaration");
			return false;
		}
		type = type_composite(sema->arena, visible_type, type);
		if (!type)
			goto allocation_failure;
	}
	if (type->kind == type_kind_function) {
		local->function_symbol = register_function(sema, local->name,
			(const struct function_type *)type, NULL, inherited_internal);
		if (!local->function_symbol)
			return false;
		if (!record_inline(sema, local->function_symbol, local->is_inline, local->is_extern,
			false, local->name.location))
			return false;
	} else {
		local->object_symbol = register_external_object(sema, local->name, type,
			NULL, inherited_internal, true, local->is_thread_local);
		if (!local->object_symbol)
			return false;
	}
	local->type = type;
	if (same) {
		struct binding *binding = arena_alloc(sema->arena, sizeof(*binding));
		if (!binding)
			goto allocation_failure;
		*binding = (struct binding) { local, sema->scope->bindings };
		sema->scope->bindings = binding;
		return true;
	}
	return reserve_local_name(sema, local);
allocation_failure:
	diagnostic_error(sema->diagnostics, local->name.location, "out of memory binding block storage");
	return false;
}

static bool sema_external_object_declaration(struct sema *sema,
	struct ast_external_object_declaration *declaration)
{
	const struct type *type = resolve_type_syntax(sema, declaration->type_syntax);

	if (!type)
		return false;
	if (declaration->is_inline) {
		diagnostic_error(sema->diagnostics, declaration->name.location, "inline requires a function declaration");
		return false;
	}
	declaration->symbol = sema_file_object(sema, &declaration->external,
		declaration->name, type, &declaration->initializer,
		declaration->is_static, declaration->is_extern, false, declaration->is_thread_local);
	if (!declaration->symbol)
		return false;
	declaration->type = type;
	return true;
}

static bool sema_external_type_declaration(struct sema *sema,
	struct ast_external_type_declaration *declaration)
{
	const struct type *type = resolve_type_syntax(sema, declaration->type_syntax);

	if (!type)
		return false;
	if (type->kind != type_kind_function) {
		if (declaration->is_inline) {
			diagnostic_error(sema->diagnostics, declaration->name.location, "inline requires a function declaration");
			return false;
		}
		declaration->object_symbol = sema_file_object(sema, &declaration->external,
			declaration->name, type, &declaration->initializer,
			declaration->is_static, declaration->is_extern, true, declaration->is_thread_local);
		if (!declaration->object_symbol)
			return false;
		declaration->type = type;
		return true;
	}
	if (declaration->initializer) {
		diagnostic_error(sema->diagnostics, declaration->name.location,
			"query-derived external declarations require ';'; functions cannot have initializers");
		return false;
	}
	if (declaration->is_thread_local) {
		diagnostic_error(sema->diagnostics, declaration->name.location, "thread_local requires an object type");
		return false;
	}
	declaration->symbol = register_function(sema, declaration->name,
		(const struct function_type *)type, NULL, declaration->is_static);
	if (!declaration->symbol)
		return false;
	if (!record_inline(sema, declaration->symbol, declaration->is_inline, declaration->is_extern,
		true, declaration->name.location))
		return false;
	declaration->type = type;
	return true;
}

static bool sema_function_declaration(struct sema *sema,
	struct ast_function_declaration *declaration, struct ast_function *definition)
{
	const struct type *resolved;
	struct function_symbol *symbol;

	/* Queries in a definition's declarator are part of that definition too,
	 * including unevaluated references in return/parameter type syntax.
	 */
	sema->function = definition;
	resolved = resolve_type_syntax(sema, &declaration->type_syntax->syntax);
	sema->function = NULL;
	if (!resolved)
		return false;
	assert(resolved->kind == type_kind_function);
	if (declaration->is_thread_local) {
		diagnostic_error(sema->diagnostics, declaration->name.location, "thread_local requires an object type");
		return false;
	}
	symbol = register_function(sema, declaration->name,
		(const struct function_type *)resolved, definition, declaration->is_static);
	if (!symbol)
		return false;
	declaration->symbol = symbol;
	if (!record_inline(sema, symbol, declaration->is_inline, declaration->is_extern,
		true, declaration->name.location))
		return false;
	if (!definition)
		return true;
	/* Install the definition before its body: direct recursion is visible. */
	symbol->definition = definition;
	definition->return_type = symbol->type->return_type;
	return sema_function_body(sema, definition);
}

static struct typedef_type_shape *measure_typedef_type(struct sema *sema,
	const struct type *type, unsigned nesting, struct source_location location)
{
	struct typedef_type_shape *shape = sema->typedef_shapes;
	const struct type *child = NULL;
	const struct function_parameter_type *parameter = NULL;
	size_t nodes = 1;
	unsigned depth = 1;

	while (shape) {
		if (shape->type == type)
			return shape;
		shape = shape->next;
	}
	if (nesting == typedef_max_type_depth) {
		diagnostic_error(sema->diagnostics, location, "typedef type exceeds expanded depth limit (128)");
		return NULL;
	}
	if (type->kind == type_kind_pointer)
		child = ((const struct pointer_type *)type)->referent;
	else if (type->kind == type_kind_array)
		child = ((const struct array_type *)type)->element;
	else if (type->kind == type_kind_function) {
		child = ((const struct function_type *)type)->return_type;
		parameter = ((const struct function_type *)type)->parameters;
	}
	while (child) {
		struct typedef_type_shape *part = measure_typedef_type(sema, child, nesting + 1, location);

		if (!part)
			return NULL;
		if (part->depth >= typedef_max_type_depth) {
			diagnostic_error(sema->diagnostics, location, "typedef type exceeds expanded depth limit (128)");
			return NULL;
		}
		if (part->nodes > typedef_max_type_nodes - nodes) {
			diagnostic_error(sema->diagnostics, location, "typedef type exceeds expanded node limit (4096)");
			return NULL;
		}
		nodes += part->nodes;
		if (depth < part->depth + 1)
			depth = part->depth + 1;
		child = parameter ? parameter->type : NULL;
		if (parameter)
			parameter = parameter->next;
	}
	shape = arena_alloc(sema->arena, sizeof(*shape));
	if (!shape) {
		diagnostic_error(sema->diagnostics, location, "out of memory measuring typedef type");
		return NULL;
	}
	*shape = (struct typedef_type_shape) {
		.type = type,
		.nodes = nodes,
		.depth = depth,
		.next = sema->typedef_shapes,
	};
	sema->typedef_shapes = shape;
	return shape;
}

static bool sema_typedef_declaration(struct sema *sema, struct ast_typedef_declaration *declaration)
{
	struct typedef_binding *binding;
	struct typedef_binding *previous;
	const struct type *type = resolve_type_syntax(sema, declaration->type_syntax);

	if (!type)
		return false;
	if (!sema->scope && (visible_file_function(sema, declaration->name) ||
		visible_file_object(sema, declaration->name))) {
		diagnostic_error(sema->diagnostics, declaration->name.location,
			"typedef name conflicts with prior ordinary declaration");
		return false;
	}
	if (sema->scope && find_in_scope(sema->scope, declaration->name)) {
		diagnostic_error(sema->diagnostics, declaration->name.location,
			"typedef name conflicts with prior ordinary declaration");
		return false;
	}
	if (!measure_typedef_type(sema, type, 0, declaration->location))
		return false;

	previous = find_typedef_binding(sema, declaration->name);
	/* Only the current scope redeclares; an outer alias remains independent. */
	if (previous && previous->scope == sema->scope) {
		if (!type_same(previous->declaration->type, type)) {
			diagnostic_error(sema->diagnostics, declaration->name.location,
				"typedef redeclaration has different type");
			return false;
		}
		declaration->type = previous->declaration->type;
		return true;
	}

	binding = arena_alloc(sema->arena, sizeof(*binding));
	if (!binding) {
		diagnostic_error(sema->diagnostics, declaration->location, "out of memory binding typedef name");
		return false;
	}
	declaration->type = type;
	*binding = (struct typedef_binding) {
		.scope = sema->scope, .declaration = declaration, .next = sema->typedefs,
	};
	sema->typedefs = binding;
	return true;
}

/* Finish tentative storage only after every source-point type query is checked.
 * Replace canonical unknown outer arrays; never rewrite captured source types.
 */
static bool finalize_tentative_objects(struct sema *sema)
{
	for (struct external_object_symbol *symbol = sema->external_objects; symbol; symbol = symbol->next) {
		const struct array_type *array;
		struct array_type *completed;

		if (symbol->definition || !symbol->tentative_definition || symbol->type->kind != type_kind_array)
			continue;
		array = (const struct array_type *)symbol->type;
		if (array->count)
			continue;
		assert(!symbol->is_internal);
		if (!type_is_complete_object(array->element) ||
			type_object_size(array->element) > ast_max_local_storage) {
			diagnostic_error(sema->diagnostics, symbol->tentative_definition->location,
				"tentative array element must be complete and fit array type storage limit (1 MiB)");
			return false;
		}
		completed = type_new_array(sema->arena, array->element, 1);
		if (!completed) {
			diagnostic_error(sema->diagnostics, symbol->tentative_definition->location,
				"out of memory completing tentative array type");
			return false;
		}
		symbol->type = &completed->type;
	}
	return true;
}

bool sema_translation_unit(struct ast_translation_unit *unit, struct arena *arena,
	struct diagnostics *diagnostics)
{
	struct sema sema = {
		.arena = arena,
		.diagnostics = diagnostics,
		.string_tail = &unit->strings,
		.static_tail = &unit->static_declarations,
	};
	struct ast_external_declaration *external = unit->declarations;

	while (external) {
		struct ast_function *definition = NULL;
		struct ast_function_declaration *declaration;

		if (external->kind == external_typedef_declaration) {
			if (!sema_typedef_declaration(&sema,
				((struct ast_external_typedef_declaration *)external)->declaration))
				return false;
			external = external->next;
			continue;
		}

		if (external->kind == external_static_assertion) {
			if (!sema_static_assertion(&sema,
				((struct ast_external_static_assertion *)external)->declaration))
				return false;
			external = external->next;
			continue;
		}
		if (external->kind == external_object_declaration) {
			if (!sema_external_object_declaration(&sema,
				(struct ast_external_object_declaration *)external))
				return false;
			external = external->next;
			continue;
		}
		if (external->kind == external_type_declaration) {
			if (!sema_external_type_declaration(&sema,
				(struct ast_external_type_declaration *)external))
				return false;
			external = external->next;
			continue;
		}
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
	for (struct function_symbol *symbol = sema.functions; symbol; symbol = symbol->next) {
		symbol->is_inline_only = !symbol->is_internal && symbol->has_inline_declaration &&
			!symbol->has_noninline_file_declaration;
		if (!symbol->is_internal && symbol->has_inline_declaration && !symbol->definition) {
			diagnostic_error(diagnostics, symbol->name.location,
				"external inline function requires a definition in this translation unit");
			return false;
		}
		if (symbol->is_inline_only && symbol->definition->inline_has_modifiable_static) {
			diagnostic_error(diagnostics, symbol->definition->inline_static_location,
				"external inline definition cannot define a modifiable static or thread object");
			return false;
		}
		if (symbol->is_inline_only && symbol->definition->inline_has_internal_reference) {
			diagnostic_error(diagnostics, symbol->definition->inline_reference_location,
				"external inline definition cannot reference an internal-linkage identifier");
			return false;
		}
		if (symbol->is_internal && symbol->is_referenced && !symbol->definition) {
			diagnostic_error(diagnostics, symbol->name.location,
				"referenced internal function requires a definition");
			return false;
		}
	}
	return finalize_tentative_objects(&sema);
}
