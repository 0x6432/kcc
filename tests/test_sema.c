#include "parse.h"
#include "sema.h"
#include "type.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static struct ast_function *first_function(struct ast_translation_unit *unit)
{
	assert(unit->declarations->kind == external_function_definition);
	return (struct ast_function *)unit->declarations;
}

static void test_resolved_tree(void)
{
	const char *text = "int main(void) { int x=1; int y=x; x=y=7; return x; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_local_declaration *x;
	struct ast_local_declaration *y;
	struct ast_statement_item *item;
	struct ast_expression_statement *statement;
	struct ast_assignment_expression *assignment;
	struct ast_load_expression *load;
	struct ast_name_expression *name;
	struct ast_return_statement *return_statement;

	assert(stream);
	assert(source_from_bytes(&source, "test.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);

	x = (struct ast_local_declaration *)first_function(unit)->body->items;
	y = (struct ast_local_declaration *)x->item.next;
	assert(x->item.kind == block_item_declaration);
	assert(y->item.kind == block_item_declaration);
	assert(x->type == &type_int && y->type == &type_int);
	assert(x->slot == 0 && y->slot == 1);
	assert(first_function(unit)->locals == y && y->next_local == x);
	assert(x->next_local == NULL);
	assert(y->initializer->kind == expression_load);
	load = (struct ast_load_expression *)y->initializer;
	name = (struct ast_name_expression *)load->operand;
	assert(name->expression.kind == expression_name);
	assert(name->declaration == x && name->expression.is_lvalue);
	assert(!load->expression.is_lvalue && load->expression.type == &type_int);

	item = (struct ast_statement_item *)y->item.next;
	assert(item->item.kind == block_item_statement);
	assert(item->statement->kind == statement_expression);
	statement = (struct ast_expression_statement *)item->statement;
	assignment = (struct ast_assignment_expression *)statement->value;
	assert(assignment->expression.kind == expression_assignment);
	assert(!assignment->expression.is_lvalue);
	assert(assignment->left->kind == expression_name);
	assert(((struct ast_name_expression *)assignment->left)->declaration == x);
	assert(assignment->right->kind == expression_assignment);
	assignment = (struct ast_assignment_expression *)assignment->right;
	assert(((struct ast_name_expression *)assignment->left)->declaration == y);
	assert(assignment->right->kind == expression_integer);

	item = (struct ast_statement_item *)item->item.next;
	assert(item->statement->kind == statement_return);
	return_statement = (struct ast_return_statement *)item->statement;
	assert(return_statement->value->kind == expression_load);
	load = (struct ast_load_expression *)return_statement->value;
	assert(((struct ast_name_expression *)load->operand)->declaration == x);
	assert(item->item.next == NULL);

	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

/* Self-initialization has undefined runtime behavior, but is not an undeclared
 * name constraint error. Test its point of declaration without executing it.
 */
static void test_point_of_declaration(void)
{
	const char *text = "int main(void) { int x=x; return 0; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_local_declaration *local;
	struct ast_load_expression *load;

	assert(stream);
	assert(source_from_bytes(&source, "test.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	local = (struct ast_local_declaration *)first_function(unit)->body->items;
	assert(local->initializer->kind == expression_load);
	load = (struct ast_load_expression *)local->initializer;
	assert(((struct ast_name_expression *)load->operand)->declaration == local);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_conditional_scopes_and_logic(void)
{
	const char *text = "int main(void) { int x=1; if(x && (x || 0)) "
		"{ int x=2; return !x; } else return x; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_local_declaration *outer;
	struct ast_local_declaration *inner;
	struct ast_statement_item *item;
	struct ast_if_statement *conditional;
	struct ast_logical_expression *condition;
	struct ast_compound_statement *body;
	struct ast_return_statement *return_node;
	struct ast_unary_expression *not_node;
	struct ast_load_expression *load;

	assert(stream);
	assert(source_from_bytes(&source, "test.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	outer = (struct ast_local_declaration *)first_function(unit)->body->items;
	item = (struct ast_statement_item *)outer->item.next;
	assert(item->statement->kind == statement_if);
	conditional = (struct ast_if_statement *)item->statement;
	assert(conditional->condition->kind == expression_logical);
	condition = (struct ast_logical_expression *)conditional->condition;
	assert(condition->operation == logical_and);
	assert(condition->right->kind == expression_logical);
	assert(condition->expression.type == &type_int);
	load = (struct ast_load_expression *)condition->left;
	assert(load->expression.kind == expression_load);
	assert(((struct ast_name_expression *)load->operand)->declaration == outer);

	assert(conditional->then_branch->kind == statement_compound);
	body = (struct ast_compound_statement *)conditional->then_branch;
	inner = (struct ast_local_declaration *)body->items;
	assert(inner != outer && inner->slot != outer->slot);
	item = (struct ast_statement_item *)inner->item.next;
	return_node = (struct ast_return_statement *)item->statement;
	assert(return_node->value->kind == expression_unary);
	not_node = (struct ast_unary_expression *)return_node->value;
	assert(not_node->operation == unary_not);
	load = (struct ast_load_expression *)not_node->operand;
	assert(((struct ast_name_expression *)load->operand)->declaration == inner);
	return_node = (struct ast_return_statement *)conditional->else_branch;
	assert(return_node->statement.kind == statement_return);
	load = (struct ast_load_expression *)return_node->value;
	assert(((struct ast_name_expression *)load->operand)->declaration == outer);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

/* This source is compiled only: executing it would be an infinite loop. */
static void test_loop_targets(void)
{
	const char *text = "int main(void) { while(1) { while(1) { break; } "
		"continue; } return 0; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_statement_item *item;
	struct ast_while_statement *outer;
	struct ast_while_statement *inner;
	struct ast_compound_statement *outer_body;
	struct ast_compound_statement *inner_body;
	struct ast_break_statement *break_node;
	struct ast_continue_statement *continue_node;

	assert(stream);
	assert(source_from_bytes(&source, "test.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	item = (struct ast_statement_item *)first_function(unit)->body->items;
	assert(item->statement->kind == statement_while);
	outer = (struct ast_while_statement *)item->statement;
	outer_body = (struct ast_compound_statement *)outer->body;
	item = (struct ast_statement_item *)outer_body->items;
	assert(item->statement->kind == statement_while);
	inner = (struct ast_while_statement *)item->statement;
	inner_body = (struct ast_compound_statement *)inner->body;
	{
		struct ast_statement_item *jump =
			(struct ast_statement_item *)inner_body->items;

		assert(jump->statement->kind == statement_break);
		break_node = (struct ast_break_statement *)jump->statement;
		assert(break_node->target == &inner->statement);
	}
	item = (struct ast_statement_item *)item->item.next;
	assert(item->statement->kind == statement_continue);
	continue_node = (struct ast_continue_statement *)item->statement;
	assert(continue_node->target == &outer->statement);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_for_scope_and_target(void)
{
	const char *text = "int main(void) { int i=9; "
		"for(int i=0;i<2;i=i+1) { int i=7; continue; } return i; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_local_declaration *outer;
	struct ast_local_declaration *header;
	struct ast_local_declaration *inner;
	struct ast_statement_item *item;
	struct ast_for_statement *loop;
	struct ast_binary_expression *condition;
	struct ast_assignment_expression *step;
	struct ast_load_expression *load;
	struct ast_compound_statement *body;
	struct ast_continue_statement *jump;
	struct ast_return_statement *return_node;

	assert(stream);
	assert(source_from_bytes(&source, "test.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	outer = (struct ast_local_declaration *)first_function(unit)->body->items;
	item = (struct ast_statement_item *)outer->item.next;
	assert(item->statement->kind == statement_for);
	loop = (struct ast_for_statement *)item->statement;
	header = loop->initializer_declaration;
	assert(header && !loop->initializer_expression);
	assert(loop->condition->kind == expression_binary);
	condition = (struct ast_binary_expression *)loop->condition;
	load = (struct ast_load_expression *)condition->left;
	assert(load->expression.kind == expression_load);
	assert(((struct ast_name_expression *)load->operand)->declaration == header);
	assert(loop->step->kind == expression_assignment);
	step = (struct ast_assignment_expression *)loop->step;
	assert(((struct ast_name_expression *)step->left)->declaration == header);
	body = (struct ast_compound_statement *)loop->body;
	inner = (struct ast_local_declaration *)body->items;
	assert(inner != header && header != outer);
	assert(outer->slot == 0 && header->slot == 1 && inner->slot == 2);
	{
		struct ast_statement_item *jump_item =
			(struct ast_statement_item *)inner->item.next;

		assert(jump_item->statement->kind == statement_continue);
		jump = (struct ast_continue_statement *)jump_item->statement;
		assert(jump->target == &loop->statement);
	}
	item = (struct ast_statement_item *)item->item.next;
	return_node = (struct ast_return_statement *)item->statement;
	load = (struct ast_load_expression *)return_node->value;
	assert(((struct ast_name_expression *)load->operand)->declaration == outer);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_function_symbols(void)
{
	static const char text[] =
		"int f(void); int main(void) { return f(); } "
		"int f(void) { return f(); } int f(void);";
	struct source source = { 0 };
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function_declaration *prototype;
	struct ast_function *main_function;
	struct ast_function *definition;
	struct ast_statement_item *item;
	struct ast_call_expression *call;

	assert(stream);
	assert(source_from_bytes(&source, "functions.c",
		(const unsigned char *)text, sizeof(text) - 1));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics));
	prototype = (struct ast_function_declaration *)unit->declarations;
	assert(prototype->external.kind == external_function_declaration);
	main_function = (struct ast_function *)prototype->external.next;
	definition = (struct ast_function *)main_function->external.next;
	assert(definition->declaration->symbol == prototype->symbol);
	assert(prototype->symbol->definition == definition);
	item = (struct ast_statement_item *)main_function->body->items;
	call = (struct ast_call_expression *)
		((struct ast_return_statement *)item->statement)->value;
	assert(call->expression.kind == expression_call);
	assert(call->function == prototype->symbol);
	assert(call->expression.type == &type_int);
	assert(call->callee->type->kind == type_kind_function);
	item = (struct ast_statement_item *)definition->body->items;
	call = (struct ast_call_expression *)
		((struct ast_return_statement *)item->statement)->value;
	assert(call->function == prototype->symbol);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_parameters_and_arguments(void)
{
	const char *text = "int f(int); int f(int x) { int y=x; return y; } "
		"int main(void) { int a=7; return f(a); }";
	struct source source = { 0 };
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function_declaration *prototype;
	struct ast_function *function;
	struct ast_function *main_function;
	struct ast_parameter *parameter;
	struct ast_local_declaration *y;
	struct ast_local_declaration *a;
	struct ast_statement_item *item;
	struct ast_call_expression *call;
	struct ast_load_expression *load;
	struct function_type *one;
	struct function_type *another_one;
	struct function_type *zero;

	assert(stream);
	assert(source_from_bytes(&source, "parameters.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics));
	prototype = (struct ast_function_declaration *)unit->declarations;
	function = (struct ast_function *)prototype->external.next;
	main_function = (struct ast_function *)function->external.next;
	parameter = function->declaration->parameters;
	assert(parameter->has_name && !parameter->next && parameter->local->slot == 0);
	assert(function->declaration->symbol == prototype->symbol);
	assert(prototype->symbol->type->parameter_count == 1);
	assert(prototype->symbol->type->parameters->type == &type_int);
	assert(!prototype->parameters->has_name);
	y = (struct ast_local_declaration *)function->body->items;
	assert(y->slot == 1 && y->next_local == parameter->local);
	load = (struct ast_load_expression *)y->initializer;
	assert(load->expression.kind == expression_load);
	assert(((struct ast_name_expression *)load->operand)->declaration == parameter->local);
	a = (struct ast_local_declaration *)main_function->body->items;
	assert(a->slot == 0);
	item = (struct ast_statement_item *)a->item.next;
	call = (struct ast_call_expression *)
		((struct ast_return_statement *)item->statement)->value;
	assert(call->expression.kind == expression_call && call->argument_count == 1);
	assert(call->function == prototype->symbol && !call->arguments->next);
	load = (struct ast_load_expression *)call->arguments->value;
	assert(load->expression.kind == expression_load);
	assert(((struct ast_name_expression *)load->operand)->declaration == a);
	one = type_new_function(&arena, &type_int, (const struct type *[]) { &type_int }, 1);
	another_one = type_new_function(&arena, &type_int, (const struct type *[]) { &type_int }, 1);
	zero = type_new_function(&arena, &type_int, NULL, 0);
	assert(one && another_one && zero);
	assert(type_compatible(&one->type, &another_one->type));
	assert(!type_compatible(&one->type, &zero->type));
	assert(!type_compatible(&one->type, &type_int));
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_deferred_preprocessor_error(void)
{
	const char *text = "int main(void) { return 42; }\n#ifndef X\n";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;

	assert(source_from_bytes(&source, "eof.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	assert(!parse_translation_unit(&preprocessor, &arena, &diagnostics));
	assert(diagnostics.errors == 1);
	assert(preprocess_next(&preprocessor).kind == token_eof);
	assert(diagnostics.errors == 1);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}


static void test_bitwise_expression_tree(void)
{
	const char *text = "int main(void) { int x=42; return ~x & 7 ^ 2 | 1 << 2+1; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_local_declaration *local;
	struct ast_statement_item *item;
	struct ast_return_statement *statement;
	struct ast_binary_expression *outer;
	struct ast_binary_expression *shift;
	struct ast_binary_expression *exclusive;
	struct ast_binary_expression *mask;
	struct ast_unary_expression *complement;
	struct ast_load_expression *load;

	assert(source_from_bytes(&source, "bitwise.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics));
	assert(!diagnostics.errors);
	local = (struct ast_local_declaration *)first_function(unit)->body->items;
	item = (struct ast_statement_item *)local->item.next;
	statement = (struct ast_return_statement *)item->statement;
	assert(statement->value->kind == expression_binary);
	outer = (struct ast_binary_expression *)statement->value;
	assert(outer->operation == binary_bit_or && outer->expression.type == &type_int);
	assert(outer->left->kind == expression_binary && outer->right->kind == expression_binary);
	shift = (struct ast_binary_expression *)outer->right;
	assert(shift->operation == binary_shift_left && shift->right->kind == expression_binary);
	assert(((struct ast_binary_expression *)shift->right)->operation == binary_add);
	exclusive = (struct ast_binary_expression *)outer->left;
	assert(exclusive->operation == binary_bit_xor && exclusive->left->kind == expression_binary);
	mask = (struct ast_binary_expression *)exclusive->left;
	assert(mask->operation == binary_bit_and && mask->left->kind == expression_unary);
	complement = (struct ast_unary_expression *)mask->left;
	assert(complement->operation == unary_complement && complement->operand->kind == expression_load);
	load = (struct ast_load_expression *)complement->operand;
	assert(load->expression.type == &type_int && !load->expression.is_lvalue);
	assert(((struct ast_name_expression *)load->operand)->declaration == local);
	assert(outer->expression.depth == 6);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static struct ast_conversion_expression *require_conversion(struct ast_expression *expression,
	const struct type *target, const struct type *operand_type)
{
	struct ast_conversion_expression *conversion;

	assert(expression->kind == expression_conversion && expression->type == target);
	assert(!expression->is_lvalue);
	conversion = (struct ast_conversion_expression *)expression;
	assert(conversion->operand->type == operand_type);
	assert(expression->depth == conversion->operand->depth + 1);
	return conversion;
}

static void test_unsigned_conversion_tree(void)
{
	const char *text = "unsigned f(int a,unsigned b) { unsigned x=a; int y=b; x=y; return x+y; }"
		"int main(void) { return f(-1,1); }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_function *main_function;
	struct ast_local_declaration *x;
	struct ast_local_declaration *y;
	struct ast_statement_item *item;
	struct ast_assignment_expression *assignment;
	struct ast_binary_expression *sum;
	struct ast_conversion_expression *conversion;
	struct ast_call_expression *call;

	assert(source_from_bytes(&source, "unsigned.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	function = first_function(unit);
	main_function = (struct ast_function *)function->external.next;
	assert(function->return_type == &type_uint);
	assert(function->declaration->symbol->type->parameters->type == &type_int);
	assert(function->declaration->symbol->type->parameters->next->type == &type_uint);
	x = (struct ast_local_declaration *)function->body->items;
	y = (struct ast_local_declaration *)x->item.next;
	assert(x->type == &type_uint && y->type == &type_int);
	conversion = require_conversion(x->initializer, &type_uint, &type_int);
	assert(conversion->operand->kind == expression_load);
	assert(((struct ast_load_expression *)conversion->operand)->operand->type == &type_int);
	require_conversion(y->initializer, &type_int, &type_uint);
	item = (struct ast_statement_item *)y->item.next;
	assignment = (struct ast_assignment_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(assignment->expression.kind == expression_assignment && assignment->expression.type == &type_uint);
	require_conversion(assignment->right, &type_uint, &type_int);
	item = (struct ast_statement_item *)item->item.next;
	sum = (struct ast_binary_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(sum->expression.kind == expression_binary && sum->expression.type == &type_uint);
	assert(sum->left->kind == expression_load && sum->left->type == &type_uint);
	require_conversion(sum->right, &type_uint, &type_int);
	item = (struct ast_statement_item *)main_function->body->items;
	conversion = require_conversion(((struct ast_return_statement *)item->statement)->value,
		&type_int, &type_uint);
	assert(conversion->operand->kind == expression_call);
	call = (struct ast_call_expression *)conversion->operand;
	assert(call->arguments->value->type == &type_int);
	require_conversion(call->arguments->next->value, &type_uint, &type_int);
	assert(!type_compatible(&type_int, &type_uint) && type_is_integer(&type_uint));
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_explicit_cast_tree(void)
{
	const char *text = "int main(void) { unsigned x=0xffffffff; return (int)(unsigned int)(int)x; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_local_declaration *local;
	struct ast_statement_item *item;
	struct ast_cast_expression *outer;
	struct ast_cast_expression *middle;
	struct ast_cast_expression *inner;

	assert(source_from_bytes(&source, "casts.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	local = (struct ast_local_declaration *)first_function(unit)->body->items;
	item = (struct ast_statement_item *)local->item.next;
	outer = (struct ast_cast_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(outer->expression.kind == expression_cast && outer->expression.type == &type_int);
	assert(outer->operand->kind == expression_cast && !outer->expression.is_lvalue);
	middle = (struct ast_cast_expression *)outer->operand;
	assert(middle->type_syntax->kind == type_syntax_integer &&
		((struct ast_integer_type_syntax *)middle->type_syntax)->specifier == integer_specifier_unsigned && middle->expression.type == &type_uint);
	assert(middle->operand->kind == expression_cast);
	inner = (struct ast_cast_expression *)middle->operand;
	assert(inner->type_syntax->kind == type_syntax_integer &&
		((struct ast_integer_type_syntax *)inner->type_syntax)->specifier == integer_specifier_int && inner->expression.type == &type_int);
	assert(inner->operand->kind == expression_load && inner->operand->type == &type_uint);
	assert(outer->expression.depth == 5);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_long_types_and_conversions(void)
{
	const struct type *types[] = { &type_int, &type_uint, &type_long, &type_ulong };
	const struct type *usual[][4] = {
		{ &type_int, &type_uint, &type_long, &type_ulong },
		{ &type_uint, &type_uint, &type_long, &type_ulong },
		{ &type_long, &type_long, &type_long, &type_ulong },
		{ &type_ulong, &type_ulong, &type_ulong, &type_ulong },
	};
	const char *text = "long f(unsigned x) { long a=x; unsigned long b=-1; return a+(int)b; }"
		"int main(void) { long x=f(0xffffffff); return x; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_function *main_function;
	struct ast_local_declaration *a;
	struct ast_local_declaration *b;
	struct ast_statement_item *item;
	struct ast_binary_expression *sum;

	for (size_t i = 0; i < 4; i++) {
		assert(type_integer_width(types[i]) == (i < 2 ? 32u : 64u));
		assert(type_is_unsigned(types[i]) == (i == 1 || i == 3));
		for (size_t j = 0; j < 4; j++)
			assert(type_usual_arithmetic(types[i], types[j]) == usual[i][j]);
	}
	assert(type_integer_literal(INT32_MAX, 10, false, 0) == &type_int);
	assert(type_integer_literal((uint64_t)INT32_MAX + 1, 10, false, 0) == &type_long);
	assert(type_integer_literal((uint64_t)INT32_MAX + 1, 16, false, 0) == &type_uint);
	assert(type_integer_literal(UINT32_MAX, 10, true, 0) == &type_uint);
	assert(type_integer_literal((uint64_t)UINT32_MAX + 1, 10, true, 0) == &type_ulong);
	assert(type_integer_literal(INT64_MAX, 16, false, 0) == &type_long);
	assert(type_integer_literal(UINT64_MAX, 16, false, 0) == &type_ulong);
	assert(type_integer_literal(UINT64_MAX, 16, false, 1) == &type_ulong);
	assert(!type_integer_literal(UINT64_MAX, 10, false, 0));
	assert(type_integer_literal(UINT64_MAX, 10, true, 1) == &type_ulong);
	assert(type_integer_literal(0, 10, false, 1) == &type_long);
	assert(type_integer_literal(0, 10, false, 2) == &type_long_long);
	assert(source_from_bytes(&source, "long.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	function = first_function(unit);
	main_function = (struct ast_function *)function->external.next;
	assert(function->return_type == &type_long);
	a = (struct ast_local_declaration *)function->body->items;
	b = (struct ast_local_declaration *)a->item.next;
	require_conversion(a->initializer, &type_long, &type_uint);
	require_conversion(b->initializer, &type_ulong, &type_int);
	item = (struct ast_statement_item *)b->item.next;
	sum = (struct ast_binary_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(sum->expression.kind == expression_binary && sum->expression.type == &type_long);
	require_conversion(sum->right, &type_long, &type_int);
	a = (struct ast_local_declaration *)main_function->body->items;
	item = (struct ast_statement_item *)a->item.next;
	require_conversion(((struct ast_return_statement *)item->statement)->value, &type_int, &type_long);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_long_long_rank(void)
{
	const struct type *types[] = { &type_int, &type_uint, &type_long, &type_ulong,
		&type_long_long, &type_ulong_long };
	const struct type *usual[][6] = {
		{ &type_int, &type_uint, &type_long, &type_ulong, &type_long_long, &type_ulong_long },
		{ &type_uint, &type_uint, &type_long, &type_ulong, &type_long_long, &type_ulong_long },
		{ &type_long, &type_long, &type_long, &type_ulong, &type_long_long, &type_ulong_long },
		{ &type_ulong, &type_ulong, &type_ulong, &type_ulong, &type_ulong_long, &type_ulong_long },
		{ &type_long_long, &type_long_long, &type_long_long, &type_ulong_long, &type_long_long, &type_ulong_long },
		{ &type_ulong_long, &type_ulong_long, &type_ulong_long, &type_ulong_long, &type_ulong_long, &type_ulong_long },
	};
	const char *text = "long long f(unsigned long x) { return x+1LL; }"
		"int main(void) { return f(41UL); }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_statement_item *item;
	struct ast_conversion_expression *conversion;
	struct ast_binary_expression *sum;

	for (size_t i = 0; i < 6; i++)
		for (size_t j = 0; j < 6; j++)
			assert(type_usual_arithmetic(types[i], types[j]) == usual[i][j]);
	assert(type_integer_width(&type_long_long) == 64 && !type_is_unsigned(&type_long_long));
	assert(type_integer_width(&type_ulong_long) == 64 && type_is_unsigned(&type_ulong_long));
	assert(!type_compatible(&type_long, &type_long_long));
	assert(!type_compatible(&type_ulong, &type_ulong_long));
	assert(type_integer_literal(42, 10, false, 2) == &type_long_long);
	assert(type_integer_literal(42, 10, true, 2) == &type_ulong_long);
	assert(type_integer_literal(UINT64_MAX, 16, false, 2) == &type_ulong_long);
	assert(!type_integer_literal(UINT64_MAX, 10, false, 2));
	assert(!type_integer_literal(0, 10, false, 3));
	assert(source_from_bytes(&source, "long-long.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	function = first_function(unit);
	assert(function->return_type == &type_long_long);
	item = (struct ast_statement_item *)function->body->items;
	conversion = require_conversion(((struct ast_return_statement *)item->statement)->value,
		&type_long_long, &type_ulong_long);
	sum = (struct ast_binary_expression *)conversion->operand;
	assert(sum->expression.kind == expression_binary && sum->expression.type == &type_ulong_long);
	require_conversion(sum->left, &type_ulong_long, &type_ulong);
	require_conversion(sum->right, &type_ulong_long, &type_long_long);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_character_expression_tree(void)
{
	const char *text = "int main(void) { return '\\xff'; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_statement_item *item;
	struct ast_return_statement *statement;
	struct ast_character_expression *character;

	assert(source_from_bytes(&source, "character.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	item = (struct ast_statement_item *)first_function(unit)->body->items;
	statement = (struct ast_return_statement *)item->statement;
	assert(statement->value->kind == expression_character);
	character = (struct ast_character_expression *)statement->value;
	assert(character->value == -1 && character->expression.depth == 1);
	assert(!character->expression.type && !character->expression.is_lvalue);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(statement->value == &character->expression);
	assert(character->expression.type == &type_int && !character->expression.is_lvalue);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_char_types_and_promotions(void)
{
	const struct type *bytes[] = { &type_char, &type_schar, &type_uchar };
	const struct type *other[] = { &type_int, &type_uint, &type_long, &type_ulong,
		&type_long_long, &type_ulong_long };
	const char *text = "int main(void) { unsigned char u=255; char c=1; return +u+(u<<c); }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_local_declaration *u;
	struct ast_local_declaration *c;
	struct ast_statement_item *item;
	struct ast_return_statement *statement;
	struct ast_binary_expression *sum;
	struct ast_unary_expression *plus;
	struct ast_binary_expression *shift;

	assert(!type_compatible(&type_char, &type_schar));
	assert(!type_compatible(&type_schar, &type_uchar));
	for (size_t i = 0; i < 3; i++) {
		assert(type_integer_width(bytes[i]) == 8);
		assert(type_is_unsigned(bytes[i]) == (i == 2));
		assert(type_integer_promotion(bytes[i]) == &type_int);
		for (size_t j = 0; j < 3; j++)
			assert(type_usual_arithmetic(bytes[i], bytes[j]) == &type_int);
		for (size_t j = 0; j < 6; j++) {
			assert(type_usual_arithmetic(bytes[i], other[j]) == other[j]);
			assert(type_usual_arithmetic(other[j], bytes[i]) == other[j]);
			assert(type_integer_promotion(other[j]) == other[j]);
		}
	}
	assert(source_from_bytes(&source, "char-types.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	u = (struct ast_local_declaration *)first_function(unit)->body->items;
	c = (struct ast_local_declaration *)u->item.next;
	assert(u->type == &type_uchar && c->type == &type_char);
	require_conversion(u->initializer, &type_uchar, &type_int);
	require_conversion(c->initializer, &type_char, &type_int);
	item = (struct ast_statement_item *)c->item.next;
	statement = (struct ast_return_statement *)item->statement;
	sum = (struct ast_binary_expression *)statement->value;
	assert(sum->expression.kind == expression_binary && sum->expression.type == &type_int);
	plus = (struct ast_unary_expression *)sum->left;
	assert(plus->expression.kind == expression_unary && plus->expression.type == &type_int);
	require_conversion(plus->operand, &type_int, &type_uchar);
	shift = (struct ast_binary_expression *)sum->right;
	assert(shift->expression.kind == expression_binary && shift->expression.type == &type_int);
	require_conversion(shift->left, &type_int, &type_uchar);
	require_conversion(shift->right, &type_int, &type_char);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_short_types_and_promotions(void)
{
	const struct type *small[] = { &type_char, &type_schar, &type_uchar, &type_short, &type_ushort };
	const struct type *wide[] = { &type_int, &type_uint, &type_long, &type_ulong,
		&type_long_long, &type_ulong_long };
	const char *text = "int main(void) { unsigned short u=65535; short c=1; return +u+(u<<c); }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_local_declaration *u;
	struct ast_local_declaration *c;
	struct ast_statement_item *item;
	struct ast_binary_expression *sum;
	struct ast_unary_expression *plus;
	struct ast_binary_expression *shift;

	assert(type_integer_width(&type_short) == 16 && !type_is_unsigned(&type_short));
	assert(type_integer_width(&type_ushort) == 16 && type_is_unsigned(&type_ushort));
	assert(!type_compatible(&type_short, &type_int));
	assert(!type_compatible(&type_short, &type_ushort));
	for (size_t i = 0; i < 5; i++) {
		assert(type_integer_promotion(small[i]) == &type_int);
		for (size_t j = 0; j < 5; j++)
			assert(type_usual_arithmetic(small[i], small[j]) == &type_int);
		for (size_t j = 0; j < 6; j++) {
			assert(type_usual_arithmetic(small[i], wide[j]) == wide[j]);
			assert(type_usual_arithmetic(wide[j], small[i]) == wide[j]);
		}
	}
	assert(source_from_bytes(&source, "short-types.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	u = (struct ast_local_declaration *)first_function(unit)->body->items;
	c = (struct ast_local_declaration *)u->item.next;
	assert(u->type == &type_ushort && c->type == &type_short);
	require_conversion(u->initializer, &type_ushort, &type_int);
	require_conversion(c->initializer, &type_short, &type_int);
	item = (struct ast_statement_item *)c->item.next;
	sum = (struct ast_binary_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(sum->expression.kind == expression_binary && sum->expression.type == &type_int);
	plus = (struct ast_unary_expression *)sum->left;
	assert(plus->expression.kind == expression_unary && plus->expression.type == &type_int);
	require_conversion(plus->operand, &type_int, &type_ushort);
	shift = (struct ast_binary_expression *)sum->right;
	assert(shift->expression.kind == expression_binary && shift->expression.type == &type_int);
	require_conversion(shift->left, &type_int, &type_ushort);
	require_conversion(shift->right, &type_int, &type_short);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_bool_type_and_conversions(void)
{
	const struct type *types[] = { &type_bool, &type_char, &type_schar, &type_uchar,
		&type_short, &type_ushort, &type_int, &type_uint, &type_long, &type_ulong,
		&type_long_long, &type_ulong_long };
	const char *text = "int main(void) { _Bool b=1L<<40; return +b; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_local_declaration *b;
	struct ast_statement_item *item;
	struct ast_unary_expression *plus;

	assert(type_integer_width(&type_bool) == 8 && type_is_unsigned(&type_bool));
	assert(type_integer_promotion(&type_bool) == &type_int);
	assert(!type_compatible(&type_bool, &type_uchar));
	for (size_t i = 0; i < sizeof(types) / sizeof(types[0]); i++) {
		const struct type *promoted = type_integer_promotion(types[i]);

		assert(type_usual_arithmetic(&type_bool, types[i]) == promoted);
		assert(type_usual_arithmetic(types[i], &type_bool) == promoted);
	}
	assert(source_from_bytes(&source, "bool-type.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	b = (struct ast_local_declaration *)first_function(unit)->body->items;
	assert(b->type == &type_bool);
	require_conversion(b->initializer, &type_bool, &type_long);
	item = (struct ast_statement_item *)b->item.next;
	plus = (struct ast_unary_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(plus->expression.kind == expression_unary && plus->expression.type == &type_int);
	require_conversion(plus->operand, &type_int, &type_bool);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_pointer_type_syntax_and_values(void)
{
	const char *text = "int **f(int **p) { int **q=p; return (int **)q; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_type_syntax *syntax;
	struct ast_local_declaration *q;
	struct ast_statement_item *item;
	struct ast_cast_expression *cast;
	const struct pointer_type *pointer;
	struct pointer_type *other;

	assert(source_from_bytes(&source, "pointer.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	syntax = function->declaration->return_syntax;
	assert(syntax->kind == type_syntax_pointer && !syntax->type);
	syntax = ((struct ast_pointer_type_syntax *)syntax)->referent;
	assert(syntax->kind == type_syntax_pointer && !syntax->type);
	syntax = ((struct ast_pointer_type_syntax *)syntax)->referent;
	assert(syntax->kind == type_syntax_integer && !syntax->type);
	assert(((struct ast_integer_type_syntax *)syntax)->specifier == integer_specifier_int);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(function->return_type == function->declaration->return_syntax->type);
	assert(syntax->type == &type_int);
	pointer = (const struct pointer_type *)function->return_type;
	assert(pointer->type.kind == type_kind_pointer && type_value_width(&pointer->type) == 64);
	assert(type_is_scalar(&pointer->type) && !type_is_integer(&pointer->type));
	pointer = (const struct pointer_type *)pointer->referent;
	assert(pointer->type.kind == type_kind_pointer && pointer->referent == &type_int);
	other = type_new_pointer(&arena, &type_uint);
	assert(other && !type_compatible(&pointer->type, &other->type));
	other = type_new_pointer(&arena, &type_int);
	assert(other && type_compatible(&pointer->type, &other->type));
	assert(function->declaration->parameters->local->type_syntax ==
		function->declaration->parameters->type_syntax);
	assert(function->declaration->parameters->local->type ==
		function->declaration->parameters->type_syntax->type);
	q = (struct ast_local_declaration *)function->body->items;
	assert(q->initializer->kind == expression_load && q->initializer->type->kind == type_kind_pointer);
	item = (struct ast_statement_item *)q->item.next;
	cast = (struct ast_cast_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(cast->expression.kind == expression_cast && !cast->expression.is_lvalue);
	assert(cast->expression.type == cast->type_syntax->type);
	assert(type_compatible(cast->expression.type, function->return_type));
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

int main(void)
{
	test_pointer_type_syntax_and_values();
	test_bool_type_and_conversions();
	test_short_types_and_promotions();
	test_char_types_and_promotions();
	test_character_expression_tree();
	test_long_long_rank();
	test_long_types_and_conversions();
	test_explicit_cast_tree();
	test_unsigned_conversion_tree();
	test_bitwise_expression_tree();
	test_deferred_preprocessor_error();
	test_parameters_and_arguments();
	test_function_symbols();
	test_resolved_tree();
	test_point_of_declaration();
	test_conditional_scopes_and_logic();
	test_loop_targets();
	test_for_scope_and_target();
	puts("Semantic AST tests passed");
	return 0;
}
