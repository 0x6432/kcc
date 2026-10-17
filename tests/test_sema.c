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
	header = (struct ast_local_declaration *)loop->initializer_declarations;
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
	assert(call->callee->kind == expression_function_decay && call->callee->type->kind == type_kind_pointer);
	assert(&call->signature->type == prototype->type_syntax->syntax.type ||
		type_compatible(&call->signature->type, prototype->type_syntax->syntax.type));
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

static void test_pointer_lvalue_tree(void)
{
	const char *text = "int main(void) { int x=1; int *p=&x; *p=42; return *p; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_local_declaration *x;
	struct ast_local_declaration *p;
	struct ast_address_expression *address;
	struct ast_statement_item *item;
	struct ast_assignment_expression *assignment;
	struct ast_indirection_expression *indirection;
	struct ast_load_expression *load;

	assert(source_from_bytes(&source, "pointer-lvalue.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	x = (struct ast_local_declaration *)first_function(unit)->body->items;
	p = (struct ast_local_declaration *)x->item.next;
	address = (struct ast_address_expression *)p->initializer;
	assert(address->expression.kind == expression_address && !address->expression.is_lvalue);
	assert(address->operand->kind == expression_name && address->operand->is_lvalue);
	assert(((struct pointer_type *)address->expression.type)->referent == &type_int);
	assert(type_compatible(address->expression.type, p->type));
	item = (struct ast_statement_item *)p->item.next;
	assignment = (struct ast_assignment_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(assignment->expression.kind == expression_assignment && !assignment->expression.is_lvalue);
	indirection = (struct ast_indirection_expression *)assignment->left;
	assert(indirection->expression.kind == expression_indirection && indirection->expression.is_lvalue);
	assert(indirection->expression.type == &type_int);
	assert(indirection->operand->kind == expression_load && indirection->operand->type->kind == type_kind_pointer);
	item = (struct ast_statement_item *)item->item.next;
	load = (struct ast_load_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(load->expression.kind == expression_load && load->expression.type == &type_int);
	assert(load->expression.depth == 4 && !load->expression.is_lvalue);
	assert(load->operand->kind == expression_indirection && load->operand->is_lvalue);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_pointer_equality_tree(void)
{
	const char *text = "int f(int *p,int *q) { return p==q; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_statement_item *item;
	struct ast_binary_expression *equality;

	assert(source_from_bytes(&source, "pointer-equality.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	item = (struct ast_statement_item *)first_function(unit)->body->items;
	equality = (struct ast_binary_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(equality->expression.kind == expression_binary && equality->operation == binary_equal);
	assert(equality->expression.type == &type_int && equality->expression.depth == 3);
	assert(equality->left->kind == expression_load && equality->right->kind == expression_load);
	assert(equality->left->type->kind == type_kind_pointer && equality->right->type->kind == type_kind_pointer);
	assert(type_compatible(equality->left->type, equality->right->type));
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_pointer_arithmetic_tree(void)
{
	const char *text = "int *f(int *p,unsigned short n) { return n+p; } "
		"long g(short *p,short *q) { return p-q; }";
	const struct type *types[] = { &type_bool, &type_char, &type_schar, &type_uchar,
		&type_short, &type_ushort, &type_int, &type_uint, &type_long, &type_ulong,
		&type_long_long, &type_ulong_long };
	const uint64_t sizes[] = { 1, 1, 1, 1, 2, 2, 4, 4, 8, 8, 8, 8 };
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_statement_item *item;
	struct ast_return_statement *statement;
	struct ast_binary_expression *parsed;
	struct ast_pointer_offset_expression *offset;
	struct ast_pointer_difference_expression *difference;
	struct ast_conversion_expression *promotion;
	struct pointer_type *pointer;

	for (size_t i = 0; i < sizeof(types) / sizeof(types[0]); i++) {
		assert(type_object_size(types[i]) == sizes[i]);
		assert(type_object_alignment(types[i]) == sizes[i]);
	}
	pointer = type_new_pointer(&arena, &type_int);
	assert(pointer && type_object_size(&pointer->type) == 8);
	assert(source_from_bytes(&source, "pointer-arithmetic.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	item = (struct ast_statement_item *)function->body->items;
	statement = (struct ast_return_statement *)item->statement;
	parsed = (struct ast_binary_expression *)statement->value;
	assert(parsed->expression.kind == expression_binary && parsed->operation == binary_add);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(statement->value != &parsed->expression);
	assert(statement->value->kind == expression_pointer_offset);
	offset = (struct ast_pointer_offset_expression *)statement->value;
	assert(offset->expression.type->kind == type_kind_pointer && offset->expression.depth == 4);
	assert(!offset->expression.is_lvalue && !offset->subtract && offset->element_size == 4);
	assert(offset->base == parsed->right && offset->base->kind == expression_load);
	assert(type_compatible(offset->expression.type, offset->base->type));
	promotion = require_conversion(offset->index, &type_int, &type_ushort);
	assert(promotion->operand == parsed->left && promotion->operand->kind == expression_load);
	function = (struct ast_function *)unit->declarations->next;
	item = (struct ast_statement_item *)function->body->items;
	statement = (struct ast_return_statement *)item->statement;
	assert(statement->value->kind == expression_pointer_difference);
	difference = (struct ast_pointer_difference_expression *)statement->value;
	assert(difference->expression.type == &type_long && difference->expression.depth == 3);
	assert(!difference->expression.is_lvalue && difference->element_size == 2);
	assert(difference->left->kind == expression_load && difference->right->kind == expression_load);
	assert(type_compatible(difference->left->type, difference->right->type));
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_pointer_subscript_tree(void)
{
	const char *text = "int f(int *p,unsigned short n) { return n[p]; } "
		"int *g(int *p) { return &p[1]; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_statement_item *item;
	struct ast_return_statement *statement;
	struct ast_subscript_expression *parsed;
	struct ast_load_expression *load;
	struct ast_indirection_expression *indirection;
	struct ast_pointer_offset_expression *offset;
	struct ast_conversion_expression *promotion;
	struct ast_address_expression *address;

	assert(source_from_bytes(&source, "subscript.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	item = (struct ast_statement_item *)function->body->items;
	statement = (struct ast_return_statement *)item->statement;
	assert(statement->value->kind == expression_subscript);
	parsed = (struct ast_subscript_expression *)statement->value;
	assert(parsed->left->kind == expression_name && parsed->right->kind == expression_name);
	assert(parsed->expression.depth == 2);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(statement->value != &parsed->expression && statement->value->kind == expression_load);
	load = (struct ast_load_expression *)statement->value;
	assert(load->expression.type == &type_int && load->expression.depth == 6);
	assert(load->operand->kind == expression_indirection && load->operand->is_lvalue);
	indirection = (struct ast_indirection_expression *)load->operand;
	assert(indirection->expression.type == &type_int && indirection->expression.depth == 5);
	assert(indirection->operand->kind == expression_pointer_offset);
	offset = (struct ast_pointer_offset_expression *)indirection->operand;
	assert(offset->base == parsed->right && offset->element_size == 4 && !offset->subtract);
	assert(offset->expression.depth == 4 && offset->base->kind == expression_load);
	promotion = require_conversion(offset->index, &type_int, &type_ushort);
	assert(promotion->operand == parsed->left && promotion->operand->kind == expression_load);
	function = (struct ast_function *)function->external.next;
	item = (struct ast_statement_item *)function->body->items;
	statement = (struct ast_return_statement *)item->statement;
	assert(statement->value->kind == expression_address);
	address = (struct ast_address_expression *)statement->value;
	assert(address->expression.type->kind == type_kind_pointer && address->expression.depth == 5);
	assert(address->operand->kind == expression_indirection && address->operand->is_lvalue);
	indirection = (struct ast_indirection_expression *)address->operand;
	assert(indirection->operand->kind == expression_pointer_offset && indirection->expression.depth == 4);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_local_array_tree(void)
{
	const char *text = "int f(void) { int a[3]; int *p=a; return a[1]; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_local_declaration *a;
	struct ast_local_declaration *p;
	struct ast_array_type_syntax *syntax;
	const struct array_type *type;
	struct array_type *other;
	struct ast_array_decay_expression *decay;
	struct ast_statement_item *item;
	struct ast_expression *value;
	struct ast_indirection_expression *indirection;
	struct ast_pointer_offset_expression *offset;

	assert(source_from_bytes(&source, "local-array.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	a = (struct ast_local_declaration *)first_function(unit)->body->items;
	assert(a->type_syntax->kind == type_syntax_array && !a->type_syntax->type);
	syntax = (struct ast_array_type_syntax *)a->type_syntax;
	assert(((struct ast_integer_expression *)syntax->bound)->value == 3 && syntax->element->kind == type_syntax_integer);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(a->type == syntax->syntax.type && a->type->kind == type_kind_array);
	type = (const struct array_type *)a->type;
	assert(type->element == &type_int && type->count == 3 && syntax->element->type == &type_int);
	assert(type_is_complete_object(a->type) && !type_is_scalar(a->type) && !type_is_integer(a->type));
	assert(type_object_size(a->type) == 12 && type_object_alignment(a->type) == 4);
	other = type_new_array(&arena, &type_int, 3);
	assert(other && type_compatible(a->type, &other->type));
	other = type_new_array(&arena, &type_int, 4);
	assert(other && !type_compatible(a->type, &other->type));
	other = type_new_array(&arena, &type_uint, 3);
	assert(other && !type_compatible(a->type, &other->type));
	p = (struct ast_local_declaration *)a->item.next;
	assert(p->initializer->kind == expression_array_decay);
	decay = (struct ast_array_decay_expression *)p->initializer;
	assert(decay->expression.type->kind == type_kind_pointer && decay->expression.depth == 2);
	assert(!decay->expression.is_lvalue && decay->operand->is_lvalue && decay->operand->type == a->type);
	assert(((const struct pointer_type *)decay->expression.type)->referent == &type_int);
	assert(((struct ast_name_expression *)decay->operand)->declaration == a);
	item = (struct ast_statement_item *)p->item.next;
	value = ((struct ast_return_statement *)item->statement)->value;
	assert(value->kind == expression_load && value->type == &type_int && value->depth == 5);
	indirection = (struct ast_indirection_expression *)((struct ast_load_expression *)value)->operand;
	assert(indirection->expression.kind == expression_indirection && indirection->expression.is_lvalue);
	offset = (struct ast_pointer_offset_expression *)indirection->operand;
	assert(offset->expression.kind == expression_pointer_offset && offset->element_size == 4);
	assert(offset->base->kind == expression_array_decay);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_multidimensional_array_tree(void)
{
	const char *text = "int f(void) { int a[2][3]; int *p=a[1]; return p[2]; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_local_declaration *a;
	struct ast_local_declaration *p;
	struct ast_array_type_syntax *outer_syntax;
	struct ast_array_type_syntax *inner_syntax;
	const struct array_type *outer;
	const struct array_type *inner;
	struct array_type *other_inner;
	struct array_type *other_outer;
	struct ast_array_decay_expression *row_decay;
	struct ast_array_decay_expression *matrix_decay;
	struct ast_indirection_expression *indirection;
	struct ast_pointer_offset_expression *offset;

	assert(source_from_bytes(&source, "matrix.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	a = (struct ast_local_declaration *)first_function(unit)->body->items;
	assert(a->type_syntax->kind == type_syntax_array);
	outer_syntax = (struct ast_array_type_syntax *)a->type_syntax;
	assert(((struct ast_integer_expression *)outer_syntax->bound)->value == 2 && outer_syntax->element->kind == type_syntax_array);
	inner_syntax = (struct ast_array_type_syntax *)outer_syntax->element;
	assert(((struct ast_integer_expression *)inner_syntax->bound)->value == 3 && inner_syntax->element->kind == type_syntax_integer);
	assert(outer_syntax->syntax.location.offset == (size_t)(strstr(text, "[2]") - text));
	assert(inner_syntax->syntax.location.offset == (size_t)(strstr(text, "[3]") - text));
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	outer = (const struct array_type *)a->type;
	assert(outer->type.kind == type_kind_array && outer->count == 2);
	assert(outer_syntax->syntax.type == &outer->type && outer->element->kind == type_kind_array);
	inner = (const struct array_type *)outer->element;
	assert(inner_syntax->syntax.type == &inner->type && inner->count == 3 && inner->element == &type_int);
	assert(type_object_size(&outer->type) == 24 && type_object_alignment(&outer->type) == 4);
	other_inner = type_new_array(&arena, &type_int, 2);
	assert(other_inner);
	other_outer = type_new_array(&arena, &other_inner->type, 3);
	assert(other_outer && type_object_size(&other_outer->type) == 24);
	assert(!type_compatible(&outer->type, &other_outer->type));
	p = (struct ast_local_declaration *)a->item.next;
	assert(p->initializer->kind == expression_array_decay && p->initializer->depth == 5);
	row_decay = (struct ast_array_decay_expression *)p->initializer;
	assert(((const struct pointer_type *)row_decay->expression.type)->referent == &type_int);
	assert(row_decay->operand->kind == expression_indirection && row_decay->operand->type == &inner->type);
	indirection = (struct ast_indirection_expression *)row_decay->operand;
	offset = (struct ast_pointer_offset_expression *)indirection->operand;
	assert(offset->expression.kind == expression_pointer_offset && offset->element_size == 12);
	assert(offset->base->kind == expression_array_decay);
	matrix_decay = (struct ast_array_decay_expression *)offset->base;
	assert(matrix_decay->operand->kind == expression_name && matrix_decay->operand->type == a->type);
	assert(((const struct pointer_type *)matrix_decay->expression.type)->referent == &inner->type);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_string_expression_tree(void)
{
	const char *text = "char *f(void) { return \"a\\0b\"; } char *g(void) { return \"a\\0b\"; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_statement_item *item;
	struct ast_return_statement *statement;
	struct ast_string_expression *string;
	struct ast_array_decay_expression *decay;
	const struct array_type *array;

	assert(source_from_bytes(&source, "string.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors && !unit->strings);
	item = (struct ast_statement_item *)first_function(unit)->body->items;
	statement = (struct ast_return_statement *)item->statement;
	assert(statement->value->kind == expression_string);
	string = (struct ast_string_expression *)statement->value;
	assert(string->length == 3 && string->bytes[0] == 'a' && string->bytes[1] == 0);
	assert(string->bytes[2] == 'b' && string->bytes[3] == 0 && !string->expression.type);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(statement->value->kind == expression_array_decay && statement->value->depth == 2);
	decay = (struct ast_array_decay_expression *)statement->value;
	assert(decay->operand == &string->expression && string->expression.is_lvalue);
	assert(((const struct pointer_type *)decay->expression.type)->referent == &type_char);
	assert(string->expression.type->kind == type_kind_array && unit->strings == string);
	array = (const struct array_type *)string->expression.type;
	assert(array->element == &type_char && array->count == 4 && type_object_size(&array->type) == 4);
	assert(string->object_id == 0 && string->next_string && string->next_string->object_id == 1);
	assert(string->next_string->length == 3 && !string->next_string->next_string);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_concatenated_string_tree(void)
{
	const char *text = "char *f(void) { return \"a\" /*gap*/ \"\\0\" \"b\"; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_statement_item *item;
	struct ast_string_expression *string;
	const struct array_type *array;

	assert(source_from_bytes(&source, "concatenation.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors && !unit->strings);
	item = (struct ast_statement_item *)first_function(unit)->body->items;
	string = (struct ast_string_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(string->expression.kind == expression_string && string->expression.depth == 1);
	assert(string->expression.location.offset == (size_t)(strchr(text, '"') - text));
	assert(string->length == 3 && string->bytes[0] == 'a' && string->bytes[1] == 0);
	assert(string->bytes[2] == 'b' && string->bytes[3] == 0);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(unit->strings == string && string->object_id == 0 && !string->next_string);
	array = (const struct array_type *)string->expression.type;
	assert(array->type.kind == type_kind_array && array->element == &type_char && array->count == 4);
	assert(((struct ast_return_statement *)item->statement)->value->kind == expression_array_decay);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_array_parameter_adjustment(void)
{
	const char *text = "int f(int [7][3]); int f(int a[2][3]) { return a[1][2]; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function_declaration *prototype;
	struct ast_function *function;
	struct ast_parameter *parameter;
	const struct array_type *declared;
	const struct array_type *row;
	const struct pointer_type *effective;

	assert(source_from_bytes(&source, "array-parameter.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	prototype = (struct ast_function_declaration *)unit->declarations;
	assert(prototype->external.kind == external_function_declaration);
	assert(!prototype->parameters->has_name && !prototype->parameters->type);
	function = (struct ast_function *)prototype->external.next;
	parameter = function->declaration->parameters;
	assert(parameter->has_name && parameter->type_syntax->kind == type_syntax_array && !parameter->type);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	declared = (const struct array_type *)parameter->type_syntax->type;
	assert(declared->type.kind == type_kind_array && declared->count == 2);
	row = (const struct array_type *)declared->element;
	assert(row->type.kind == type_kind_array && row->count == 3 && row->element == &type_int);
	assert(parameter->type->kind == type_kind_pointer);
	effective = (const struct pointer_type *)parameter->type;
	assert(effective->referent == &row->type);
	assert(parameter->local->type_syntax == parameter->type_syntax);
	assert(parameter->local->type == parameter->type && parameter->local->type != &declared->type);
	assert(type_object_size(parameter->local->type) == 8 && type_object_size(&declared->type) == 24);
	assert(type_compatible(parameter->type, prototype->parameters->type));
	assert(((const struct array_type *)prototype->parameters->type_syntax->type)->count == 7);
	assert(function->declaration->symbol == prototype->symbol);
	assert(type_compatible(prototype->symbol->type->parameters->type, parameter->type));
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_incomplete_array_parameter(void)
{
	const char *text = "int f(int [7][3]); int f(int a[][3]) { return a[1][2]; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function_declaration *prototype;
	struct ast_function *function;
	struct ast_parameter *parameter;
	struct ast_array_type_syntax *syntax;
	const struct array_type *declared;
	const struct array_type *row;
	struct array_type *unknown;
	struct array_type *complete;
	struct array_type *different;

	assert(source_from_bytes(&source, "incomplete-parameter.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	prototype = (struct ast_function_declaration *)unit->declarations;
	function = (struct ast_function *)prototype->external.next;
	parameter = function->declaration->parameters;
	syntax = (struct ast_array_type_syntax *)parameter->type_syntax;
	assert(syntax->syntax.kind == type_syntax_array && !syntax->bound && !syntax->syntax.type);
	assert(((struct ast_array_type_syntax *)syntax->element)->bound);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	declared = (const struct array_type *)syntax->syntax.type;
	assert(declared->type.kind == type_kind_array && !declared->count);
	assert(!type_is_complete_object(&declared->type) && !type_is_scalar(&declared->type));
	row = (const struct array_type *)declared->element;
	assert(row->type.kind == type_kind_array && row->count == 3 && row->element == &type_int);
	assert(type_is_complete_object(&row->type) && type_object_size(&row->type) == 12);
	assert(parameter->type->kind == type_kind_pointer && parameter->local->type == parameter->type);
	assert(((const struct pointer_type *)parameter->type)->referent == &row->type);
	assert(type_object_size(parameter->local->type) == 8);
	assert(parameter->local->type_syntax == parameter->type_syntax);
	assert(type_compatible(parameter->type, prototype->parameters->type));
	unknown = type_new_incomplete_array(&arena, &type_int);
	complete = type_new_array(&arena, &type_int, 3);
	different = type_new_array(&arena, &type_uint, 3);
	assert(unknown && complete && different);
	assert(!unknown->count && !type_is_complete_object(&unknown->type));
	assert(type_compatible(&unknown->type, &complete->type));
	assert(type_compatible(&complete->type, &unknown->type));
	assert(!type_compatible(&unknown->type, &different->type));
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_parenthesized_object_declarators(void)
{
	const char *text = "int f(int (*p)[3]) { int *a[2]; int (*b)[3]=(int (*)[3])p; "
		"int *(*c[2])[3]; return b[0][1]; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_parameter *parameter;
	struct ast_local_declaration *a;
	struct ast_local_declaration *b;
	struct ast_local_declaration *c;
	struct ast_array_type_syntax *array_syntax;
	struct ast_pointer_type_syntax *pointer_syntax;
	struct ast_cast_expression *cast;
	const struct array_type *array;
	const struct pointer_type *pointer;

	assert(source_from_bytes(&source, "declarators.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	parameter = function->declaration->parameters;
	a = (struct ast_local_declaration *)function->body->items;
	b = (struct ast_local_declaration *)a->item.next;
	c = (struct ast_local_declaration *)b->item.next;
	assert(parameter->type_syntax->kind == type_syntax_pointer);
	assert(a->type_syntax->kind == type_syntax_array && !a->type_syntax->type);
	array_syntax = (struct ast_array_type_syntax *)a->type_syntax;
	assert(array_syntax->bound && ((struct ast_integer_expression *)array_syntax->bound)->value == 2);
	assert(array_syntax->element->kind == type_syntax_pointer);
	pointer_syntax = (struct ast_pointer_type_syntax *)array_syntax->element;
	assert(pointer_syntax->referent->kind == type_syntax_integer);
	assert(b->type_syntax->kind == type_syntax_pointer && b->initializer->kind == expression_cast);
	pointer_syntax = (struct ast_pointer_type_syntax *)b->type_syntax;
	assert(pointer_syntax->referent->kind == type_syntax_array);
	array_syntax = (struct ast_array_type_syntax *)pointer_syntax->referent;
	assert(array_syntax->bound && ((struct ast_integer_expression *)array_syntax->bound)->value == 3);
	assert(array_syntax->element->kind == type_syntax_integer);
	cast = (struct ast_cast_expression *)b->initializer;
	assert(cast->type_syntax->kind == type_syntax_pointer && !cast->type_syntax->type);
	array_syntax = (struct ast_array_type_syntax *)c->type_syntax;
	assert(array_syntax->syntax.kind == type_syntax_array && ((struct ast_integer_expression *)array_syntax->bound)->value == 2);
	pointer_syntax = (struct ast_pointer_type_syntax *)array_syntax->element;
	assert(pointer_syntax->syntax.kind == type_syntax_pointer);
	array_syntax = (struct ast_array_type_syntax *)pointer_syntax->referent;
	assert(array_syntax->syntax.kind == type_syntax_array && ((struct ast_integer_expression *)array_syntax->bound)->value == 3);
	assert(array_syntax->element->kind == type_syntax_pointer);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(parameter->type == parameter->type_syntax->type && parameter->local->type == parameter->type);
	assert(type_compatible(parameter->type, b->type) && type_compatible(cast->expression.type, b->type));
	assert(type_object_size(a->type) == 16 && type_object_size(b->type) == 8);
	assert(type_object_size(c->type) == 16 && type_object_alignment(c->type) == 8);
	array = (const struct array_type *)c->type;
	assert(array->type.kind == type_kind_array && array->count == 2);
	pointer = (const struct pointer_type *)array->element;
	assert(pointer->type.kind == type_kind_pointer);
	array = (const struct array_type *)pointer->referent;
	assert(array->type.kind == type_kind_array && array->count == 3 && type_object_size(&array->type) == 24);
	pointer = (const struct pointer_type *)array->element;
	assert(pointer->type.kind == type_kind_pointer && pointer->referent == &type_int);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_incomplete_object_pointer_composite(void)
{
	const char *text = "int f(int (*)[]); int f(int (*)[3]); "
		"int f(int (*p)[]) { int (*q)[]=p; return (*q)[2]; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function_declaration *first;
	struct ast_function_declaration *second;
	struct ast_function *function;
	struct ast_parameter *parameter;
	const struct pointer_type *declared;
	const struct pointer_type *visible;
	const struct array_type *unknown;
	const struct array_type *known;
	const struct type *composite;
	struct array_type *left_array;
	struct array_type *right_array;
	const struct array_type *merged;

	assert(source_from_bytes(&source, "incomplete-pointer.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	first = (struct ast_function_declaration *)unit->declarations;
	second = (struct ast_function_declaration *)first->external.next;
	function = (struct ast_function *)second->external.next;
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	parameter = function->declaration->parameters;
	declared = (const struct pointer_type *)parameter->type;
	assert(declared->type.kind == type_kind_pointer && declared->referent->kind == type_kind_array);
	unknown = (const struct array_type *)declared->referent;
	assert(!unknown->count && unknown->element == &type_int);
	assert(type_is_object(&unknown->type) && !type_is_complete_object(&unknown->type));
	assert(type_is_complete_object(&declared->type) && type_object_size(&declared->type) == 8);
	assert(parameter->type == parameter->type_syntax->type && parameter->local->type == parameter->type);
	visible = (const struct pointer_type *)first->symbol->type->parameters->type;
	known = (const struct array_type *)visible->referent;
	assert(known->type.kind == type_kind_array && known->count == 3 && known->element == &type_int);
	assert(known != unknown && !unknown->count && type_object_size(&known->type) == 12);
	assert(first->symbol == second->symbol && first->symbol == function->declaration->symbol);
	assert(!type_is_object(&first->symbol->type->type));
	assert(((const struct array_type *)((const struct pointer_type *)first->parameters->type)->referent)->count == 0);
	assert(((const struct array_type *)((const struct pointer_type *)second->parameters->type)->referent)->count == 3);
	composite = type_composite(&arena, &declared->type, &visible->type);
	assert(composite && composite->kind == type_kind_pointer);
	assert(((const struct array_type *)((const struct pointer_type *)composite)->referent)->count == 3);
	assert(type_composite(&arena, &visible->type, &declared->type) == &visible->type);
	left_array = type_new_array(&arena, &declared->type, 2);
	right_array = type_new_array(&arena, &visible->type, 2);
	assert(left_array && right_array && type_compatible(&left_array->type, &right_array->type));
	composite = type_composite(&arena, &left_array->type, &right_array->type);
	assert(composite && composite->kind == type_kind_array);
	merged = (const struct array_type *)composite;
	assert(merged->count == 2 && type_object_size(composite) == 16);
	visible = (const struct pointer_type *)merged->element;
	assert(((const struct array_type *)visible->referent)->count == 3 && !unknown->count);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_local_declaration_list_tree(void)
{
	const char *text = "int f(void) { int x=13,*p=&x,y=*p+1; "
		"for(int i=0,n=1;i<n;i=i+1) y=y+1; return x+y; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_local_declaration *x;
	struct ast_local_declaration *p;
	struct ast_local_declaration *y;
	struct ast_local_declaration *i;
	struct ast_local_declaration *n;
	struct ast_statement_item *item;
	struct ast_for_statement *loop;
	struct ast_address_expression *address;
	struct ast_name_expression *name;
	struct ast_binary_expression *condition;
	struct ast_load_expression *load;

	assert(source_from_bytes(&source, "declaration-list.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	x = (struct ast_local_declaration *)first_function(unit)->body->items;
	p = (struct ast_local_declaration *)x->item.next;
	y = (struct ast_local_declaration *)p->item.next;
	assert(x->item.kind == block_item_declaration && p->item.kind == block_item_declaration);
	assert(y->item.kind == block_item_declaration && y->type_syntax == x->type_syntax);
	assert(x->type_syntax->kind == type_syntax_integer && !x->type_syntax->type);
	assert(p->type_syntax->kind == type_syntax_pointer);
	assert(((struct ast_pointer_type_syntax *)p->type_syntax)->referent == x->type_syntax);
	assert(x->name.location.offset < p->name.location.offset && p->name.location.offset < y->name.location.offset);
	item = (struct ast_statement_item *)y->item.next;
	assert(item->item.kind == block_item_statement && item->statement->kind == statement_for);
	loop = (struct ast_for_statement *)item->statement;
	i = (struct ast_local_declaration *)loop->initializer_declarations;
	n = (struct ast_local_declaration *)i->item.next;
	assert(i->item.kind == block_item_declaration && n->item.kind == block_item_declaration && !n->item.next);
	assert(i->type_syntax == n->type_syntax && i->type_syntax != x->type_syntax);
	assert(!loop->initializer_expression);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(x->type == &type_int && y->type == &type_int && p->type->kind == type_kind_pointer);
	assert(x->slot == 0 && p->slot == 1 && y->slot == 2 && i->slot == 3 && n->slot == 4);
	assert(x->type_syntax->type == &type_int && ((const struct pointer_type *)p->type)->referent == &type_int);
	address = (struct ast_address_expression *)p->initializer;
	assert(address->expression.kind == expression_address && address->operand->kind == expression_name);
	name = (struct ast_name_expression *)address->operand;
	assert(name->declaration == x);
	condition = (struct ast_binary_expression *)loop->condition;
	assert(condition->expression.kind == expression_binary);
	load = (struct ast_load_expression *)condition->left;
	assert(load->expression.kind == expression_load && ((struct ast_name_expression *)load->operand)->declaration == i);
	load = (struct ast_load_expression *)condition->right;
	assert(load->expression.kind == expression_load && ((struct ast_name_expression *)load->operand)->declaration == n);
	assert(item->item.next && !item->item.next->next);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_unnamed_definition_parameter_tree(void)
{
	const char *text = "long long f(int,char x,int [],int (*)[3],short,int,long long,long long y) "
		"{ int z=42; return x+y+z; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_parameter *parameter;
	struct ast_local_declaration *x = NULL;
	struct ast_local_declaration *y = NULL;
	struct ast_local_declaration *z;
	const struct function_parameter_type *signature_parameter;
	size_t index = 0;

	assert(source_from_bytes(&source, "unnamed-definition.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	assert(function->declaration->parameter_count == 8);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	signature_parameter = function->declaration->symbol->type->parameters;
	for (parameter = function->declaration->parameters; parameter; parameter = parameter->next) {
		assert(signature_parameter && type_compatible(parameter->type, signature_parameter->type));
		if (index == 1 || index == 7) {
			assert(parameter->has_name && parameter->local && parameter->local->type == parameter->type);
			if (index == 1)
				x = parameter->local;
			else
				y = parameter->local;
		} else {
			assert(!parameter->has_name && !parameter->local);
		}
		if (index == 2) {
			assert(parameter->type_syntax->kind == type_syntax_array);
			assert(!type_is_complete_object(parameter->type_syntax->type));
			assert(parameter->type->kind == type_kind_pointer);
			assert(((const struct pointer_type *)parameter->type)->referent == &type_int);
		}
		signature_parameter = signature_parameter->next;
		index++;
	}
	assert(index == 8 && !signature_parameter && x && y && x->slot == 0 && y->slot == 1);
	z = (struct ast_local_declaration *)function->body->items;
	assert(z->slot == 2 && z->type == &type_int && function->locals == z);
	assert(z->next_local == y && y->next_local == x && !x->next_local);
	assert(function->return_type == &type_long_long);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_function_declarator_syntax_tree(void)
{
	const char *text = "int (*row(int (*)[]))[]; "
		"int (*(row)(int (*p)[3]))[3] { return p; }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function_declaration *prototype;
	struct ast_function *definition;
	struct ast_function_declaration *declaration;
	struct ast_function_type_syntax *syntax;
	struct ast_pointer_type_syntax *pointer_syntax;
	struct ast_array_type_syntax *array_syntax;
	const struct function_type *declared;
	const struct function_type *visible;
	const struct pointer_type *pointer;
	const struct array_type *array;

	assert(source_from_bytes(&source, "function-declarator.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	prototype = (struct ast_function_declaration *)unit->declarations;
	definition = (struct ast_function *)prototype->external.next;
	declaration = definition->declaration;
	syntax = declaration->type_syntax;
	assert(syntax->syntax.kind == type_syntax_function && !syntax->syntax.type);
	assert(declaration->return_syntax == syntax->return_syntax && declaration->parameters == syntax->parameters);
	assert(declaration->parameter_count == 1 && syntax->parameter_count == 1);
	pointer_syntax = (struct ast_pointer_type_syntax *)syntax->return_syntax;
	assert(pointer_syntax->syntax.kind == type_syntax_pointer);
	array_syntax = (struct ast_array_type_syntax *)pointer_syntax->referent;
	assert(array_syntax->syntax.kind == type_syntax_array && array_syntax->bound);
	assert(((struct ast_integer_expression *)array_syntax->bound)->value == 3 && array_syntax->element->kind == type_syntax_integer);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	declared = (const struct function_type *)prototype->type_syntax->syntax.type;
	assert(declared->type.kind == type_kind_function && declared->parameter_count == 1);
	pointer = (const struct pointer_type *)declared->return_type;
	array = (const struct array_type *)pointer->referent;
	assert(pointer->type.kind == type_kind_pointer && array->type.kind == type_kind_array && !array->count);
	assert(!type_is_complete_object(&array->type) && type_object_size(&pointer->type) == 8);
	visible = declaration->symbol->type;
	assert(prototype->symbol == declaration->symbol && visible != declared);
	pointer = (const struct pointer_type *)visible->return_type;
	array = (const struct array_type *)pointer->referent;
	assert(array->count == 3 && array->element == &type_int && type_object_size(&array->type) == 12);
	pointer = (const struct pointer_type *)visible->parameters->type;
	assert(((const struct array_type *)pointer->referent)->count == 3);
	assert(definition->return_type == visible->return_type);
	assert(declaration->parameters->local && declaration->parameters->local->type == declaration->parameters->type);
	assert(type_compatible(declaration->parameters->type, visible->parameters->type));
	assert(((const struct function_type *)syntax->syntax.type)->return_type == pointer_syntax->syntax.type);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_function_pointer_expression_tree(void)
{
	const char *text = "int apply(int cb(int),int x) { return cb(x); } "
		"int identity(int x) { return x; } int main(void) { int (*p)(int)=identity; return apply(p,42); }";
	struct source source;
	struct preprocessor preprocessor;
	struct diagnostics diagnostics = { 0 };
	struct arena arena = { 0 };
	struct ast_translation_unit *unit;
	struct ast_function *apply;
	struct ast_function *identity;
	struct ast_function *main_function;
	struct ast_parameter *callback;
	struct ast_local_declaration *p;
	struct ast_call_expression *call;
	struct ast_statement_item *item;
	struct ast_function_decay_expression *decay;
	struct ast_function_designator_expression *designator;
	struct ast_load_expression *load;
	const struct pointer_type *pointer;

	assert(source_from_bytes(&source, "callbacks.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	apply = first_function(unit);
	identity = (struct ast_function *)apply->external.next;
	main_function = (struct ast_function *)identity->external.next;
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	callback = apply->declaration->parameters;
	assert(callback->type_syntax->kind == type_syntax_function && callback->type_syntax->type->kind == type_kind_function);
	assert(callback->type->kind == type_kind_pointer && callback->local->type == callback->type);
	pointer = (const struct pointer_type *)callback->type;
	assert(pointer->referent == callback->type_syntax->type && !type_is_object(pointer->referent));
	assert(type_object_size(&pointer->type) == 8);
	item = (struct ast_statement_item *)apply->body->items;
	call = (struct ast_call_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(call->expression.kind == expression_call && !call->function && call->expression.depth == 3);
	assert(&call->signature->type == pointer->referent && call->signature->parameter_count == 1);
	load = (struct ast_load_expression *)call->callee;
	assert(load->expression.kind == expression_load && ((struct ast_name_expression *)load->operand)->declaration == callback->local);
	p = (struct ast_local_declaration *)main_function->body->items;
	decay = (struct ast_function_decay_expression *)p->initializer;
	assert(decay->expression.kind == expression_function_decay && decay->expression.depth == 2);
	assert(decay->expression.type->kind == type_kind_pointer && type_compatible(decay->expression.type, p->type));
	designator = (struct ast_function_designator_expression *)decay->operand;
	assert(designator->expression.kind == expression_function_designator && designator->expression.depth == 1);
	assert(designator->function == identity->declaration->symbol && !designator->expression.is_lvalue);
	assert(designator->expression.type->kind == type_kind_function);
	item = (struct ast_statement_item *)p->item.next;
	call = (struct ast_call_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(call->function == apply->declaration->symbol && call->callee->kind == expression_function_decay);
	assert(call->expression.depth == 3 && call->signature->parameter_count == 2);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_void_type_and_effect_tree(void)
{
	const char *text = "void f(void) { return; } void g(void (*p)(void),void *q) { p(); (void)f(); &*q; *q; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *f;
	struct ast_function *g;
	struct ast_statement_item *item;
	struct ast_expression *expression;
	struct ast_parameter *parameter;
	struct ast_address_expression *address;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors && sema_translation_unit(unit, &arena, &diagnostics));
	f = first_function(unit);
	g = (struct ast_function *)f->external.next;
	assert(f->return_type == &type_void && !f->declaration->parameters);
	assert(f->declaration->return_syntax->kind == type_syntax_void);
	assert(f->declaration->return_syntax->type == &type_void);
	assert(!f->locals);
	item = (struct ast_statement_item *)f->body->items;
	assert(item->statement->kind == statement_return);
	assert(!((struct ast_return_statement *)item->statement)->value);
	assert(type_is_object(&type_void) && !type_is_complete_object(&type_void));
	assert(!type_is_scalar(&type_void) && !type_is_integer(&type_void));
	assert(type_compatible(&type_void, &type_void) && !type_compatible(&type_void, &type_int));
	assert(type_composite(&arena, &type_void, &type_void) == &type_void);
	parameter = g->declaration->parameters;
	assert(g->return_type == &type_void && g->locals && g->locals->next_local && !g->locals->next_local->next_local);
	assert(parameter->type->kind == type_kind_pointer);
	assert(((const struct function_type *)((const struct pointer_type *)parameter->type)->referent)->return_type == &type_void);
	parameter = parameter->next;
	assert(((const struct pointer_type *)parameter->type)->referent == &type_void);
	assert(type_object_size(parameter->type) == 8);
	item = (struct ast_statement_item *)g->body->items;
	expression = ((struct ast_expression_statement *)item->statement)->value;
	assert(expression->kind == expression_call && expression->type == &type_void && !expression->is_lvalue);
	assert(!((struct ast_call_expression *)expression)->function);
	item = (struct ast_statement_item *)item->item.next;
	expression = ((struct ast_expression_statement *)item->statement)->value;
	assert(expression->kind == expression_cast && expression->type == &type_void);
	assert(((struct ast_cast_expression *)expression)->operand->kind == expression_call);
	item = (struct ast_statement_item *)item->item.next;
	address = (struct ast_address_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(address->expression.kind == expression_address && address->operand->kind == expression_indirection);
	assert(address->operand->type == &type_void && !address->operand->is_lvalue);
	item = (struct ast_statement_item *)item->item.next;
	expression = ((struct ast_expression_statement *)item->statement)->value;
	assert(expression->kind == expression_indirection && expression->type == &type_void && !expression->is_lvalue);
	assert(!item->item.next && !diagnostics.errors);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_object_void_conversion_tree(void)
{
	const char *text = "void *erase(int *p) { return p; } "
		"int equal(void *v,int *p) { v==p; return p==v; } "
		"int *restore(void *p) { return p; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *erase;
	struct ast_function *equal;
	struct ast_function *restore;
	struct ast_statement_item *item;
	struct ast_conversion_expression *conversion;
	struct ast_binary_expression *comparison;
	const struct type *object_pointer;
	const struct type *void_pointer;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors && sema_translation_unit(unit, &arena, &diagnostics));
	erase = first_function(unit);
	equal = (struct ast_function *)erase->external.next;
	restore = (struct ast_function *)equal->external.next;
	object_pointer = erase->declaration->parameters->type;
	void_pointer = erase->return_type;
	assert(object_pointer->kind == type_kind_pointer && void_pointer->kind == type_kind_pointer);
	assert(!type_compatible(object_pointer, void_pointer));
	assert(((const struct pointer_type *)void_pointer)->referent == &type_void);
	item = (struct ast_statement_item *)erase->body->items;
	conversion = (struct ast_conversion_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(conversion->expression.kind == expression_conversion && conversion->expression.type == void_pointer);
	assert(conversion->operand->type == object_pointer && conversion->operand->kind == expression_load);
	assert(conversion->expression.depth == 3 && conversion->operand->depth == 2);
	item = (struct ast_statement_item *)equal->body->items;
	comparison = (struct ast_binary_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(comparison->expression.kind == expression_binary && comparison->expression.type == &type_int);
	assert(comparison->left->kind == expression_load && comparison->right->kind == expression_conversion);
	assert(type_compatible(comparison->left->type, comparison->right->type));
	assert(((const struct pointer_type *)comparison->right->type)->referent == &type_void);
	assert(comparison->expression.depth == 4);
	item = (struct ast_statement_item *)item->item.next;
	comparison = (struct ast_binary_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(comparison->left->kind == expression_conversion && comparison->right->kind == expression_load);
	assert(type_compatible(comparison->left->type, comparison->right->type));
	assert(comparison->expression.depth == 4);
	item = (struct ast_statement_item *)restore->body->items;
	conversion = (struct ast_conversion_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(conversion->expression.kind == expression_conversion);
	assert(type_compatible(conversion->expression.type, object_pointer));
	assert(type_compatible(conversion->operand->type, void_pointer));
	assert(!type_compatible(object_pointer, void_pointer) && !diagnostics.errors);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_explicit_pointer_cast_tree(void)
{
	const char *text = "unsigned char *bytes(int *p) { return (unsigned char *)p; } "
		"int (*restore(int (*p)(int)))(int) { return (int (*)(int))(void (*)(void))p; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *bytes;
	struct ast_function *restore;
	struct ast_statement_item *item;
	struct ast_cast_expression *cast;
	struct ast_cast_expression *inner;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors && sema_translation_unit(unit, &arena, &diagnostics));
	bytes = first_function(unit);
	restore = (struct ast_function *)bytes->external.next;
	item = (struct ast_statement_item *)bytes->body->items;
	cast = (struct ast_cast_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(cast->expression.kind == expression_cast && cast->operand->kind == expression_load);
	assert(cast->expression.type == cast->type_syntax->type && cast->expression.depth == 3);
	assert(type_compatible(cast->expression.type, bytes->return_type));
	assert(!type_compatible(cast->expression.type, cast->operand->type));
	assert(((const struct pointer_type *)cast->expression.type)->referent == &type_uchar);
	assert(((const struct pointer_type *)cast->operand->type)->referent == &type_int);
	item = (struct ast_statement_item *)restore->body->items;
	cast = (struct ast_cast_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(cast->expression.kind == expression_cast && cast->expression.depth == 4);
	inner = (struct ast_cast_expression *)cast->operand;
	assert(inner->expression.kind == expression_cast && inner->expression.depth == 3);
	assert(inner->operand->kind == expression_load && inner->operand->depth == 2);
	assert(type_compatible(cast->expression.type, restore->return_type));
	assert(type_compatible(cast->expression.type, inner->operand->type));
	assert(!type_compatible(cast->expression.type, inner->expression.type));
	assert(inner->expression.type == inner->type_syntax->type && cast->expression.type == cast->type_syntax->type);
	assert(((const struct pointer_type *)inner->expression.type)->referent->kind == type_kind_function);
	assert(((const struct pointer_type *)cast->expression.type)->referent->kind == type_kind_function);
	assert(!diagnostics.errors);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_comma_expression_tree(void)
{
	const char *text = "int f(int x) { int y=(x,2),z=3; x=1,x=2,x+y; return (void)x,z; } "
		"void g(void) { (void)1,(void)2; } int add(int a,int b) { return a+b; } "
		"int call(void) { return add((1,2),3); }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *f;
	struct ast_function *g;
	struct ast_function *add;
	struct ast_function *call_function;
	struct ast_local_declaration *y;
	struct ast_local_declaration *z;
	struct ast_statement_item *item;
	struct ast_comma_expression *comma;
	struct ast_call_expression *call;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors && sema_translation_unit(unit, &arena, &diagnostics));
	f = first_function(unit);
	g = (struct ast_function *)f->external.next;
	add = (struct ast_function *)g->external.next;
	call_function = (struct ast_function *)add->external.next;
	y = (struct ast_local_declaration *)f->body->items;
	z = (struct ast_local_declaration *)y->item.next;
	assert(y->item.kind == block_item_declaration && z->item.kind == block_item_declaration);
	comma = (struct ast_comma_expression *)y->initializer;
	assert(comma->expression.kind == expression_comma && comma->expression.type == &type_int);
	assert(comma->left->kind == expression_load && comma->right->kind == expression_integer);
	assert(comma->expression.depth == 3 && !comma->expression.is_lvalue);
	item = (struct ast_statement_item *)z->item.next;
	comma = (struct ast_comma_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(comma->expression.kind == expression_comma && comma->left->kind == expression_comma);
	assert(comma->right->kind == expression_binary && comma->expression.depth == 4);
	assert(((struct ast_comma_expression *)comma->left)->left->kind == expression_assignment);
	assert(((struct ast_comma_expression *)comma->left)->right->kind == expression_assignment);
	item = (struct ast_statement_item *)item->item.next;
	comma = (struct ast_comma_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(comma->expression.kind == expression_comma && comma->expression.type == &type_int);
	assert(comma->left->type == &type_void && comma->right->kind == expression_load);
	assert(comma->expression.depth == 4 && !comma->expression.is_lvalue);
	item = (struct ast_statement_item *)g->body->items;
	comma = (struct ast_comma_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(comma->expression.kind == expression_comma && comma->expression.type == &type_void);
	assert(comma->left->type == &type_void && comma->right->type == &type_void);
	assert(comma->expression.depth == 3 && !comma->expression.is_lvalue);
	item = (struct ast_statement_item *)call_function->body->items;
	call = (struct ast_call_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(call->expression.kind == expression_call && call->argument_count == 2);
	assert(call->arguments->value->kind == expression_comma);
	assert(call->arguments->next->value->kind == expression_integer && !call->arguments->next->next);
	assert(!diagnostics.errors);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_const_qualification_tree(void)
{
	const char *text = "const int f(const int x) { const int a=x; "
		"const int *const p=&a; int y=(const int)a; (const int *const)p; return *p; } "
		"int f(int); int compare(int *p,const int *q,void *v) { p==q; v==q; q-p; return 0; } "
		"int read(const int a[][3]) { return a[0][0]; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *f;
	struct ast_function *compare;
	struct ast_function *read;
	struct ast_local_declaration *a;
	struct ast_local_declaration *p;
	struct ast_local_declaration *y;
	struct ast_qualified_type_syntax *qualified;
	struct ast_pointer_type_syntax *pointer_syntax;
	struct ast_cast_expression *cast;
	struct ast_load_expression *load;
	struct ast_statement_item *item;
	struct ast_binary_expression *comparison;
	struct ast_pointer_difference_expression *difference;
	const struct function_type *signature;
	const struct pointer_type *pointer;
	const struct array_type *array;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors && sema_translation_unit(unit, &arena, &diagnostics));
	f = first_function(unit);
	compare = (struct ast_function *)f->external.next->next;
	read = (struct ast_function *)compare->external.next;
	signature = (const struct function_type *)f->declaration->type_syntax->syntax.type;
	assert(!signature->return_type->qualifiers && !signature->parameters->type->qualifiers);
	assert(type_compatible(signature->return_type, &type_int));
	assert(f->declaration->return_syntax->kind == type_syntax_qualified);
	assert(f->declaration->return_syntax->type->qualifiers == type_qualifier_const);
	assert(f->declaration->parameters->type->qualifiers == type_qualifier_const);
	assert(f->declaration->parameters->local->type == f->declaration->parameters->type);
	assert(!f->return_type->qualifiers);
	a = (struct ast_local_declaration *)f->body->items;
	p = (struct ast_local_declaration *)a->item.next;
	y = (struct ast_local_declaration *)p->item.next;
	assert(a->type->qualifiers == type_qualifier_const);
	qualified = (struct ast_qualified_type_syntax *)a->type_syntax;
	assert(qualified->syntax.kind == type_syntax_qualified && qualified->syntax.type == a->type);
	assert(qualified->qualifiers == type_qualifier_const && qualified->base->kind == type_syntax_integer);
	assert(!qualified->base->type->qualifiers && qualified->base->type == &type_int);
	load = (struct ast_load_expression *)a->initializer;
	assert(load->expression.kind == expression_load && !load->expression.type->qualifiers);
	assert(load->operand->type->qualifiers == type_qualifier_const && load->operand->is_lvalue);
	assert(load->expression.depth == 2 && !load->expression.is_lvalue);
	assert(p->type->qualifiers == type_qualifier_const && p->type->kind == type_kind_pointer);
	pointer = (const struct pointer_type *)p->type;
	assert(pointer->referent->qualifiers == type_qualifier_const);
	qualified = (struct ast_qualified_type_syntax *)p->type_syntax;
	assert(qualified->syntax.kind == type_syntax_qualified && qualified->base->kind == type_syntax_pointer);
	pointer_syntax = (struct ast_pointer_type_syntax *)qualified->base;
	assert(!pointer_syntax->syntax.type->qualifiers);
	assert(pointer_syntax->referent->kind == type_syntax_qualified);
	assert(!p->initializer->type->qualifiers && type_compatible(p->initializer->type, pointer_syntax->syntax.type));
	cast = (struct ast_cast_expression *)y->initializer;
	assert(cast->expression.kind == expression_cast && !cast->expression.type->qualifiers);
	assert(cast->type_syntax->type->qualifiers == type_qualifier_const);
	assert(cast->operand->kind == expression_load && !cast->operand->type->qualifiers);
	assert(cast->expression.depth == 3);
	item = (struct ast_statement_item *)y->item.next;
	cast = (struct ast_cast_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(cast->expression.kind == expression_cast && !cast->expression.type->qualifiers);
	assert(cast->type_syntax->type->qualifiers == type_qualifier_const);
	assert(((const struct pointer_type *)cast->expression.type)->referent->qualifiers == type_qualifier_const);
	load = (struct ast_load_expression *)cast->operand;
	assert(load->expression.kind == expression_load && !load->expression.type->qualifiers);
	assert(load->operand->type == p->type && load->expression.depth == 2);
	item = (struct ast_statement_item *)item->item.next;
	load = (struct ast_load_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(load->expression.kind == expression_load && !load->expression.type->qualifiers);
	assert(load->operand->kind == expression_indirection && load->operand->is_lvalue);
	assert(load->operand->type->qualifiers == type_qualifier_const && load->expression.depth == 4);

	item = (struct ast_statement_item *)compare->body->items;
	comparison = (struct ast_binary_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(comparison->expression.kind == expression_binary && comparison->left->kind == expression_conversion);
	assert(comparison->right->kind == expression_load && comparison->expression.depth == 4);
	assert(type_compatible(comparison->left->type, comparison->right->type));
	pointer = (const struct pointer_type *)comparison->left->type;
	assert(pointer->referent->qualifiers == type_qualifier_const && pointer->referent->kind == type_kind_int);
	item = (struct ast_statement_item *)item->item.next;
	comparison = (struct ast_binary_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(comparison->left->kind == expression_conversion && comparison->right->kind == expression_conversion);
	assert(type_compatible(comparison->left->type, comparison->right->type));
	pointer = (const struct pointer_type *)comparison->left->type;
	assert(pointer->referent->kind == type_kind_void && pointer->referent->qualifiers == type_qualifier_const);
	assert(comparison->expression.depth == 4);
	item = (struct ast_statement_item *)item->item.next;
	difference = (struct ast_pointer_difference_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(difference->expression.kind == expression_pointer_difference && difference->expression.type == &type_long);
	assert(difference->expression.depth == 3 && difference->element_size == 4);

	assert(read->declaration->parameters->type_syntax->kind == type_syntax_array);
	array = (const struct array_type *)read->declaration->parameters->type_syntax->type;
	assert(!array->count && array->type.qualifiers == type_qualifier_const);
	assert(array->element->kind == type_kind_array && array->element->qualifiers == type_qualifier_const);
	assert(((const struct array_type *)array->element)->element->qualifiers == type_qualifier_const);
	pointer = (const struct pointer_type *)read->declaration->parameters->type;
	assert(pointer->type.kind == type_kind_pointer && !pointer->type.qualifiers);
	assert(pointer->referent == array->element);
	assert(!type_int.qualifiers && !type_void.qualifiers && !diagnostics.errors);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}


static void test_boolean_constant_tree(void)
{
	const char *text = "bool id(_Bool); _Bool id(const bool x) { "
		"const bool a=true; bool b=false; return x; } "
		"int main(void) { return +true; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_local_declaration *a;
	struct ast_local_declaration *b;
	struct ast_boolean_expression *constant;
	struct ast_statement_item *item;
	struct ast_unary_expression *plus;
	struct ast_conversion_expression *promotion;

	assert(stream);
	assert(source_from_bytes(&source, "boolean.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	function = (struct ast_function *)unit->declarations->next;
	assert(function->external.kind == external_function_definition);
	assert(function->return_type == &type_bool);
	assert(function->declaration->parameters->type->qualifiers == type_qualifier_const);
	a = (struct ast_local_declaration *)function->body->items;
	b = (struct ast_local_declaration *)a->item.next;
	assert(a->type->kind == type_kind_bool && a->type->qualifiers == type_qualifier_const);
	assert(b->type == &type_bool);
	constant = (struct ast_boolean_expression *)a->initializer;
	assert(constant->expression.kind == expression_boolean && constant->value);
	assert(constant->expression.type == &type_bool && constant->expression.depth == 1);
	assert(!constant->expression.is_lvalue);
	constant = (struct ast_boolean_expression *)b->initializer;
	assert(constant->expression.kind == expression_boolean && !constant->value);
	assert(constant->expression.type == &type_bool && constant->expression.depth == 1);
	assert(!constant->expression.is_lvalue);
	function = (struct ast_function *)function->external.next;
	item = (struct ast_statement_item *)function->body->items;
	plus = (struct ast_unary_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(plus->expression.kind == expression_unary && plus->expression.type == &type_int);
	assert(plus->expression.depth == 3 && !plus->expression.is_lvalue);
	promotion = (struct ast_conversion_expression *)plus->operand;
	require_conversion(&promotion->expression, &type_int, &type_bool);
	assert(promotion->operand->kind == expression_boolean && promotion->operand->depth == 1);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}


static void test_conditional_expression_tree(void)
{
	const char *text = "int f(void) { 1?true:false; return 0; } "
		"const int *g(int *p,const int *q) { return 1?p:q; } "
		"int (*h(int (*a)[],int (*b)[3]))[3] { return 0?a:b; } "
		"void v(int *p) { 1?(void)(*p=1):(void)(*p=2); return; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_statement_item *item;
	struct ast_conditional_expression *conditional;
	const struct pointer_type *pointer;
	const struct array_type *array;

	assert(stream);
	assert(source_from_bytes(&source, "conditional.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	function = first_function(unit);
	item = (struct ast_statement_item *)function->body->items;
	conditional = (struct ast_conditional_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(conditional->expression.kind == expression_conditional);
	assert(conditional->expression.type == &type_int && conditional->expression.depth == 3);
	assert(!conditional->expression.is_lvalue && conditional->condition->type == &type_int);
	require_conversion(conditional->then_value, &type_int, &type_bool);
	require_conversion(conditional->else_value, &type_int, &type_bool);
	assert(((struct ast_conversion_expression *)conditional->then_value)->operand->kind == expression_boolean);
	function = (struct ast_function *)function->external.next;
	item = (struct ast_statement_item *)function->body->items;
	conditional = (struct ast_conditional_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(conditional->expression.kind == expression_conditional && !conditional->expression.is_lvalue);
	pointer = (const struct pointer_type *)conditional->expression.type;
	assert(pointer->type.kind == type_kind_pointer && !pointer->type.qualifiers);
	assert(pointer->referent->kind == type_kind_int && pointer->referent->qualifiers == type_qualifier_const);
	assert(conditional->then_value->kind == expression_conversion);
	assert(conditional->else_value->kind == expression_load);
	function = (struct ast_function *)function->external.next;
	item = (struct ast_statement_item *)function->body->items;
	conditional = (struct ast_conditional_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(conditional->expression.kind == expression_conditional);
	pointer = (const struct pointer_type *)conditional->expression.type;
	array = (const struct array_type *)pointer->referent;
	assert(array->type.kind == type_kind_array && array->count == 3 && array->element == &type_int);
	/* Composite result must not rewrite the earlier parameter's incomplete type. */
	pointer = (const struct pointer_type *)function->declaration->parameters->type;
	assert(((const struct array_type *)pointer->referent)->count == 0);
	function = (struct ast_function *)function->external.next;
	item = (struct ast_statement_item *)function->body->items;
	conditional = (struct ast_conditional_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(conditional->expression.kind == expression_conditional);
	assert(conditional->expression.type == &type_void && !conditional->expression.is_lvalue);
	assert(conditional->then_value->type == &type_void && conditional->else_value->type == &type_void);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

static void test_conditional_integer_types(void)
{
	const struct type *types[] = { &type_bool, &type_char, &type_schar, &type_uchar,
		&type_short, &type_ushort, &type_int, &type_uint, &type_long, &type_ulong,
		&type_long_long, &type_ulong_long };
	const char *names[] = { "_Bool", "char", "signed char", "unsigned char", "short",
		"unsigned short", "int", "unsigned", "long", "unsigned long", "long long", "unsigned long long" };

	for (size_t a = 0; a < sizeof(types) / sizeof(types[0]); a++)
		for (size_t b = 0; b < sizeof(types) / sizeof(types[0]); b++) {
			char text[256];
			struct source source;
			struct arena arena = { 0 };
			struct diagnostics diagnostics = { 0 };
			struct preprocessor preprocessor;
			struct ast_translation_unit *unit;
			struct ast_statement_item *item;
			struct ast_conditional_expression *conditional;
			const struct type *expected = type_usual_arithmetic(types[a], types[b]);

			assert(snprintf(text, sizeof(text), "int main(void) { 1?(%s)0:(%s)0; return 0; }", names[a], names[b]) > 0);
			assert(source_from_bytes(&source, "conditional-types.c", (const unsigned char *)text, strlen(text)));
			assert(source_prepare(&source));
			preprocess_init(&preprocessor, &source, &diagnostics);
			unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
			assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
			item = (struct ast_statement_item *)first_function(unit)->body->items;
			conditional = (struct ast_conditional_expression *)((struct ast_expression_statement *)item->statement)->value;
			assert(conditional->expression.kind == expression_conditional && !conditional->expression.is_lvalue);
			assert(conditional->expression.type == expected);
			assert(conditional->then_value->type == expected && conditional->else_value->type == expected);
			arena_destroy(&arena);
			preprocess_destroy(&preprocessor);
			source_destroy(&source);
		}
}


static void test_sizeof_alignment_tree(void)
{
	const char *text = "unsigned long f(int a[3],int g(void)) { int b[2][3]; "
		"sizeof b; sizeof b[0]; sizeof a; sizeof g; sizeof true; "
		"sizeof(true?false:true); sizeof(int (*)[3]); alignof(const int[2][3]); "
		"return sizeof(b[0][1]=42); }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_local_declaration *b;
	struct ast_statement_item *item;
	struct ast_sizeof_expression *size;
	struct ast_sizeof_type_expression *type_size;
	struct ast_alignof_expression *alignment;
	const struct array_type *array;
	const struct pointer_type *pointer;

	assert(stream);
	assert(source_from_bytes(&source, "layout.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	function = first_function(unit);
	b = (struct ast_local_declaration *)function->body->items;
	item = (struct ast_statement_item *)b->item.next;
	size = (struct ast_sizeof_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(size->expression.kind == expression_sizeof && size->expression.type == &type_ulong);
	assert(size->expression.depth == 2 && !size->expression.is_lvalue && size->size == 24);
	assert(size->operand->kind == expression_name && size->operand->is_lvalue);
	assert(size->operand->type == b->type && size->operand->type->kind == type_kind_array);
	item = (struct ast_statement_item *)item->item.next;
	size = (struct ast_sizeof_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(size->expression.kind == expression_sizeof && size->size == 12);
	assert(size->operand->kind == expression_indirection && size->operand->is_lvalue);
	array = (const struct array_type *)size->operand->type;
	assert(array->type.kind == type_kind_array && array->count == 3);
	item = (struct ast_statement_item *)item->item.next;
	size = (struct ast_sizeof_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(size->size == 8 && size->operand->kind == expression_name && size->operand->is_lvalue);
	assert(size->operand->type == function->declaration->parameters->type);
	assert(size->operand->type->kind == type_kind_pointer);
	item = (struct ast_statement_item *)item->item.next;
	size = (struct ast_sizeof_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(size->size == 8 && size->operand->kind == expression_name);
	pointer = (const struct pointer_type *)size->operand->type;
	assert(pointer->type.kind == type_kind_pointer && pointer->referent->kind == type_kind_function);
	item = (struct ast_statement_item *)item->item.next;
	size = (struct ast_sizeof_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(size->size == 1 && size->operand->kind == expression_boolean && size->expression.depth == 2);
	item = (struct ast_statement_item *)item->item.next;
	size = (struct ast_sizeof_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(size->size == 4 && size->operand->kind == expression_conditional && size->expression.depth == 4);
	assert(size->operand->type == &type_int);
	item = (struct ast_statement_item *)item->item.next;
	type_size = (struct ast_sizeof_type_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(type_size->expression.kind == expression_sizeof_type && type_size->expression.type == &type_ulong);
	assert(type_size->size == 8 && type_size->expression.depth == 1 && !type_size->expression.is_lvalue);
	pointer = (const struct pointer_type *)type_size->type_syntax->type;
	assert(pointer->type.kind == type_kind_pointer && pointer->referent->kind == type_kind_array);
	item = (struct ast_statement_item *)item->item.next;
	alignment = (struct ast_alignof_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(alignment->expression.kind == expression_alignof && alignment->expression.type == &type_ulong);
	assert(alignment->alignment == 4 && alignment->expression.depth == 1 && !alignment->expression.is_lvalue);
	array = (const struct array_type *)alignment->type_syntax->type;
	assert(array->type.kind == type_kind_array && array->type.qualifiers == type_qualifier_const && array->count == 2);
	assert(array->element->kind == type_kind_array && array->element->qualifiers == type_qualifier_const);
	item = (struct ast_statement_item *)item->item.next;
	size = (struct ast_sizeof_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(size->expression.kind == expression_sizeof && size->expression.type == &type_ulong && size->size == 4);
	assert(size->operand->kind == expression_assignment && !size->operand->is_lvalue);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}


static void test_static_assertion_tree(void)
{
	const char *text = "static_assert(true,\"a\\0\" \"b\");"
		"int f(int x) { _Static_assert(sizeof x==4,\"parameter\");"
		"const short y=1; { static_assert(sizeof y==2); }"
		"for(static_assert(1,\"for\");0;) ; return x; }"
		"static_assert(sizeof f(1)==4);";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_external_static_assertion *external;
	struct ast_function *function;
	struct ast_block_static_assertion *block;
	struct ast_local_declaration *local;
	struct ast_statement_item *item;
	struct ast_compound_statement *compound;
	struct ast_for_statement *loop;
	struct ast_binary_expression *comparison;
	struct ast_sizeof_expression *size;

	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	external = (struct ast_external_static_assertion *)unit->declarations;
	assert(external->external.kind == external_static_assertion);
	assert(external->declaration->condition->kind == expression_boolean);
	assert(external->declaration->message->length == 3);
	assert(memcmp(external->declaration->message->bytes, "a\0b", 4) == 0);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(!unit->strings && !external->declaration->message->expression.type);
	assert(external->declaration->condition->type == &type_bool);
	function = (struct ast_function *)external->external.next;
	assert(function->external.kind == external_function_definition);
	block = (struct ast_block_static_assertion *)function->body->items;
	assert(block->item.kind == block_item_static_assertion);
	comparison = (struct ast_binary_expression *)block->declaration->condition;
	assert(comparison->expression.kind == expression_binary);
	size = (struct ast_sizeof_expression *)comparison->left;
	assert(size->expression.kind == expression_sizeof && size->size == 4);
	assert(size->operand->kind == expression_name && size->operand->is_lvalue);
	assert(((struct ast_name_expression *)size->operand)->declaration == function->declaration->parameters->local);
	local = (struct ast_local_declaration *)block->item.next;
	assert(local->item.kind == block_item_declaration);
	assert(function->locals == local && local->next_local == function->declaration->parameters->local);
	assert(!local->next_local->next_local);
	item = (struct ast_statement_item *)local->item.next;
	compound = (struct ast_compound_statement *)item->statement;
	assert(compound->statement.kind == statement_compound);
	block = (struct ast_block_static_assertion *)compound->items;
	assert(block->item.kind == block_item_static_assertion && !block->declaration->message);
	comparison = (struct ast_binary_expression *)block->declaration->condition;
	size = (struct ast_sizeof_expression *)comparison->left;
	assert(size->size == 2 && ((struct ast_name_expression *)size->operand)->declaration == local);
	item = (struct ast_statement_item *)item->item.next;
	loop = (struct ast_for_statement *)item->statement;
	assert(loop->statement.kind == statement_for && !loop->initializer_expression);
	assert(loop->initializer_declarations->kind == block_item_static_assertion);
	external = (struct ast_external_static_assertion *)function->external.next;
	assert(external->external.kind == external_static_assertion && !external->external.next);
	assert(!unit->strings && !external->declaration->message);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_constant_bound_tree(void)
{
	const char *text = "int f(int n, int a[sizeof n], int (*cb)(char n, int b[sizeof n])) {"
		"int local[sizeof n+1]; return 0; }"
		"int g(void) { char n; int (*p)(int n,int a[sizeof n]); int b[sizeof n]; char a; int (*q)(int a[sizeof a]); return 0; }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_parameter *parameter;
	struct ast_array_type_syntax *array;
	struct ast_sizeof_expression *size;
	struct ast_name_expression *name;
	struct ast_function_type_syntax *callback;
	struct ast_local_declaration *local;
	struct ast_local_declaration *outer;

	assert(source_from_bytes(&source, "bounds.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	parameter = function->declaration->parameters->next;
	array = (struct ast_array_type_syntax *)parameter->type_syntax;
	assert(array->syntax.kind == type_syntax_array && array->bound->kind == expression_sizeof);
	assert(!array->syntax.type && !array->bound->type);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(((const struct array_type *)array->syntax.type)->count == 4);
	size = (struct ast_sizeof_expression *)array->bound;
	assert(size->size == 4 && size->operand->kind == expression_name);
	name = (struct ast_name_expression *)size->operand;
	assert(name->declaration->type == &type_int && !name->declaration->next_local);
	assert(name->declaration != function->declaration->parameters->local);
	assert(!name->declaration->initializer);
	callback = (struct ast_function_type_syntax *)
		((struct ast_pointer_type_syntax *)parameter->next->type_syntax)->referent;
	assert(callback->syntax.kind == type_syntax_function);
	array = (struct ast_array_type_syntax *)callback->parameters->next->type_syntax;
	assert(((const struct array_type *)array->syntax.type)->count == 1);
	size = (struct ast_sizeof_expression *)array->bound;
	assert(size->size == 1 && ((struct ast_name_expression *)size->operand)->declaration->type == &type_char);
	assert(!callback->parameters->local && !callback->parameters->next->local);
	local = (struct ast_local_declaration *)function->body->items;
	assert(((const struct array_type *)local->type)->count == 5);
	array = (struct ast_array_type_syntax *)local->type_syntax;
	assert(array->bound->kind == expression_binary && array->bound->type == &type_ulong);
	size = (struct ast_sizeof_expression *)((struct ast_binary_expression *)array->bound)->left;
	assert(((struct ast_name_expression *)size->operand)->declaration == function->declaration->parameters->local);
	function = (struct ast_function *)function->external.next;
	outer = (struct ast_local_declaration *)function->body->items;
	local = (struct ast_local_declaration *)outer->item.next;
	callback = (struct ast_function_type_syntax *)((struct ast_pointer_type_syntax *)local->type_syntax)->referent;
	array = (struct ast_array_type_syntax *)callback->parameters->next->type_syntax;
	assert(((const struct array_type *)array->syntax.type)->count == 4);
	local = (struct ast_local_declaration *)local->item.next;
	assert(((const struct array_type *)local->type)->count == 1);
	size = (struct ast_sizeof_expression *)((struct ast_array_type_syntax *)local->type_syntax)->bound;
	assert(((struct ast_name_expression *)size->operand)->declaration == outer);
	outer = (struct ast_local_declaration *)local->item.next;
	local = (struct ast_local_declaration *)outer->item.next;
	callback = (struct ast_function_type_syntax *)((struct ast_pointer_type_syntax *)local->type_syntax)->referent;
	array = (struct ast_array_type_syntax *)callback->parameters->type_syntax;
	assert(((const struct array_type *)array->syntax.type)->count == 1);
	size = (struct ast_sizeof_expression *)array->bound;
	assert(((struct ast_name_expression *)size->operand)->declaration == outer);
	assert(!unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_null_constant_tree(void)
{
	const char *text = "int f(const int *p,int (*cb)(int)) { int *q=1-1; "
		"int (*r)(int)=(void *)0; const int *s=1?p:(void *)0; "
		"int (*t)(int)=0?(void *)0:cb; return 0==p; }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_local_declaration *q;
	struct ast_local_declaration *r;
	struct ast_local_declaration *local_s;
	struct ast_local_declaration *t;
	struct ast_conversion_expression *conversion;
	struct ast_cast_expression *cast;
	struct ast_conditional_expression *conditional;
	struct ast_statement_item *item;
	struct ast_return_statement *return_statement;
	struct ast_binary_expression *comparison;
	const struct type *p_type;
	const struct type *cb_type;

	assert(source_from_bytes(&source, "null-constants.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	q = (struct ast_local_declaration *)function->body->items;
	r = (struct ast_local_declaration *)q->item.next;
	local_s = (struct ast_local_declaration *)r->item.next;
	t = (struct ast_local_declaration *)local_s->item.next;
	assert(q->initializer->kind == expression_binary);
	assert(r->initializer->kind == expression_cast);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	p_type = function->declaration->parameters->type;
	cb_type = function->declaration->parameters->next->type;
	assert(q->slot == 2 && r->slot == 3 && local_s->slot == 4 && t->slot == 5);
	assert(function->locals == t && t->next_local == local_s);
	assert(q->initializer->kind == expression_conversion);
	conversion = (struct ast_conversion_expression *)q->initializer;
	assert(conversion->expression.type == q->type && conversion->operand->kind == expression_binary);
	assert(conversion->operand->type == &type_int && conversion->expression.depth == 3);
	assert(r->initializer->kind == expression_conversion);
	conversion = (struct ast_conversion_expression *)r->initializer;
	assert(conversion->expression.type == r->type && conversion->operand->kind == expression_cast);
	cast = (struct ast_cast_expression *)conversion->operand;
	assert(((const struct pointer_type *)cast->expression.type)->referent == &type_void);
	assert(cast->operand->kind == expression_integer && cast->operand->type == &type_int);
	assert(conversion->expression.depth == 3 && cast->expression.depth == 2);
	assert(local_s->initializer->kind == expression_conditional);
	conditional = (struct ast_conditional_expression *)local_s->initializer;
	assert(conditional->expression.type == p_type);
	assert(((const struct pointer_type *)p_type)->referent->qualifiers == type_qualifier_const);
	assert(conditional->else_value->kind == expression_conversion);
	assert(conditional->else_value->type == p_type);
	assert(t->initializer->kind == expression_conditional);
	conditional = (struct ast_conditional_expression *)t->initializer;
	assert(conditional->expression.type == cb_type && conditional->then_value->type == cb_type);
	assert(conditional->then_value->kind == expression_conversion && conditional->else_value->kind == expression_load);
	item = (struct ast_statement_item *)t->item.next;
	return_statement = (struct ast_return_statement *)item->statement;
	comparison = (struct ast_binary_expression *)return_statement->value;
	assert(comparison->expression.kind == expression_binary && comparison->expression.type == &type_int);
	assert(comparison->left->kind == expression_conversion && comparison->right->kind == expression_load);
	assert(comparison->left->type == p_type && comparison->right->type == p_type);
	assert(!unit->strings && !item->item.next);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}



static void test_null_boolean_tree(void)
{
	const char *text = "int *f(void) { return false; }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_statement_item *item;
	struct ast_conversion_expression *conversion;
	struct ast_boolean_expression *boolean;

	assert(source_from_bytes(&source, "false-null.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	item = (struct ast_statement_item *)first_function(unit)->body->items;
	conversion = (struct ast_conversion_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(conversion->expression.kind == expression_conversion && conversion->expression.depth == 2);
	assert(conversion->expression.type->kind == type_kind_pointer);
	boolean = (struct ast_boolean_expression *)conversion->operand;
	assert(boolean->expression.kind == expression_boolean && boolean->expression.type == &type_bool);
	assert(!boolean->value && boolean->expression.depth == 1);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_nullptr_tree(void)
{
	const char *text = "int f(int *p) { int *q=nullptr; _Bool b=nullptr; "
		"int *r=(0,nullptr); int *t=1?nullptr:nullptr; int *s=1?p:nullptr; return nullptr==0; }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_local_declaration *q;
	struct ast_local_declaration *b;
	struct ast_local_declaration *r;
	struct ast_local_declaration *t;
	struct ast_local_declaration *local_s;
	struct ast_conversion_expression *conversion;
	struct ast_conditional_expression *conditional;
	struct ast_binary_expression *comparison;
	struct ast_statement_item *item;

	assert(source_from_bytes(&source, "nullptr.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	q = (struct ast_local_declaration *)function->body->items;
	assert(q->initializer->kind == expression_nullptr && q->initializer->depth == 1);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	b = (struct ast_local_declaration *)q->item.next;
	r = (struct ast_local_declaration *)b->item.next;
	t = (struct ast_local_declaration *)r->item.next;
	local_s = (struct ast_local_declaration *)t->item.next;
	assert(q->slot == 1 && b->slot == 2 && r->slot == 3 && t->slot == 4 && local_s->slot == 5);
	conversion = (struct ast_conversion_expression *)q->initializer;
	assert(conversion->expression.kind == expression_conversion && conversion->expression.type == q->type);
	assert(conversion->expression.depth == 2 && conversion->operand->kind == expression_nullptr);
	assert(conversion->operand->type == &type_nullptr && !conversion->operand->is_lvalue);
	assert(conversion->operand->depth == 1);
	conversion = (struct ast_conversion_expression *)b->initializer;
	assert(conversion->expression.kind == expression_conversion && conversion->expression.type == &type_bool);
	assert(conversion->operand->kind == expression_nullptr && conversion->operand->type == &type_nullptr);
	conversion = (struct ast_conversion_expression *)r->initializer;
	assert(conversion->expression.kind == expression_conversion && conversion->operand->kind == expression_comma);
	assert(conversion->operand->type == &type_nullptr);
	conversion = (struct ast_conversion_expression *)t->initializer;
	assert(conversion->expression.kind == expression_conversion && conversion->operand->kind == expression_conditional);
	conditional = (struct ast_conditional_expression *)conversion->operand;
	assert(conditional->expression.type == &type_nullptr && conditional->then_value->type == &type_nullptr);
	assert(conditional->else_value->type == &type_nullptr && conditional->expression.depth == 2);
	conditional = (struct ast_conditional_expression *)local_s->initializer;
	assert(conditional->expression.kind == expression_conditional);
	assert(conditional->expression.type == function->declaration->parameters->type);
	assert(conditional->else_value->kind == expression_conversion);
	assert(conditional->else_value->type == conditional->expression.type);
	item = (struct ast_statement_item *)local_s->item.next;
	comparison = (struct ast_binary_expression *)((struct ast_return_statement *)item->statement)->value;
	assert(comparison->expression.kind == expression_binary && comparison->expression.type == &type_int);
	assert(comparison->left->kind == expression_conversion && comparison->right->kind == expression_conversion);
	conversion = (struct ast_conversion_expression *)comparison->left;
	assert(conversion->operand->kind == expression_nullptr && conversion->operand->type == &type_nullptr);
	assert(((const struct pointer_type *)conversion->expression.type)->referent == &type_void);
	conversion = (struct ast_conversion_expression *)comparison->right;
	assert(conversion->operand->kind == expression_integer && conversion->operand->type == &type_int);
	assert(!unit->strings && function->locals == local_s && !item->item.next);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}


static void test_prefix_update_tree(void)
{
	const char *text = "int f(_Bool b,unsigned char c,const int *p) { ++b; --c; ++p; return 42; }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_statement_item *item;
	struct ast_prefix_update_expression *update;
	struct ast_expression *parsed_operand;

	assert(source_from_bytes(&source, "prefix-update.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	item = (struct ast_statement_item *)function->body->items;
	update = (struct ast_prefix_update_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->expression.kind == expression_prefix_update && update->expression.depth == 2);
	parsed_operand = update->operand;
	assert(parsed_operand->kind == expression_name && parsed_operand->depth == 1);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(update->operand == parsed_operand && update->operand->is_lvalue);
	assert(update->operand->type == &type_bool && update->expression.type == &type_bool);
	assert(!update->expression.is_lvalue && update->expression.depth == 2);
	assert(update->operation == update_increment && update->calculation_type == &type_int && !update->element_size);
	assert(update->expression.location.offset == (size_t)(strstr(text, "++b") - text));
	item = (struct ast_statement_item *)item->item.next;
	update = (struct ast_prefix_update_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->expression.kind == expression_prefix_update && update->expression.type == &type_uchar);
	assert(update->operand->is_lvalue && update->operand->kind == expression_name);
	assert(update->operation == update_decrement && update->calculation_type == &type_int && !update->element_size);
	item = (struct ast_statement_item *)item->item.next;
	update = (struct ast_prefix_update_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->expression.kind == expression_prefix_update && !update->expression.is_lvalue);
	assert(update->calculation_type == update->expression.type && update->element_size == 4);
	assert(update->operand->kind == expression_name && update->operand->is_lvalue);
	assert(((const struct pointer_type *)update->expression.type)->referent->qualifiers == type_qualifier_const);
	assert(!update->expression.type->qualifiers && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}


static void test_postfix_update_tree(void)
{
	const char *text = "int f(_Bool b,unsigned char c,const int *p) { b++; c--; p++; return 42; }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_statement_item *item;
	struct ast_postfix_update_expression *update;
	struct ast_expression *parsed_operand;

	assert(source_from_bytes(&source, "postfix-update.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	item = (struct ast_statement_item *)function->body->items;
	update = (struct ast_postfix_update_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->expression.kind == expression_postfix_update && update->expression.depth == 2);
	parsed_operand = update->operand;
	assert(parsed_operand->kind == expression_name && parsed_operand->depth == 1);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(update->operand == parsed_operand && update->operand->is_lvalue);
	assert(update->operand->type == &type_bool && update->expression.type == &type_bool);
	assert(!update->expression.is_lvalue && update->expression.depth == 2);
	assert(update->operation == update_increment && update->calculation_type == &type_int && !update->element_size);
	assert(update->expression.location.offset == (size_t)(strstr(text, "b++") + 1 - text));
	item = (struct ast_statement_item *)item->item.next;
	update = (struct ast_postfix_update_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->expression.kind == expression_postfix_update && update->expression.type == &type_uchar);
	assert(update->operand->is_lvalue && update->operand->kind == expression_name);
	assert(update->operation == update_decrement && update->calculation_type == &type_int && !update->element_size);
	item = (struct ast_statement_item *)item->item.next;
	update = (struct ast_postfix_update_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->expression.kind == expression_postfix_update && !update->expression.is_lvalue);
	assert(update->calculation_type == update->expression.type && update->element_size == 4);
	assert(update->operand->kind == expression_name && update->operand->is_lvalue);
	assert(((const struct pointer_type *)update->expression.type)->referent->qualifiers == type_qualifier_const);
	assert(!update->expression.type->qualifiers && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}



static void test_compound_assignment_tree(void)
{
	const char *text = "int f(_Bool b,unsigned char c,const int *p) { b+=2UL; c-=3L; p+=true; return 42; }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_statement_item *item;
	struct ast_compound_assignment_expression *update;
	struct ast_expression *parsed_left;
	struct ast_expression *parsed_right;

	assert(source_from_bytes(&source, "compound.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	item = (struct ast_statement_item *)function->body->items;
	update = (struct ast_compound_assignment_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->expression.kind == expression_compound_assignment && update->expression.depth == 2);
	parsed_left = update->left;
	parsed_right = update->right;
	assert(parsed_left->kind == expression_name && parsed_right->kind == expression_integer);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(update->left == parsed_left && update->left->is_lvalue && update->right == parsed_right);
	assert(update->left->type == &type_bool && update->expression.type == &type_bool);
	assert(!update->expression.is_lvalue && update->expression.depth == 2);
	assert(update->operation == binary_add && update->calculation_type == &type_ulong && !update->element_size);
	assert(update->expression.location.offset == (size_t)(strstr(text, "b+=") + 1 - text));
	item = (struct ast_statement_item *)item->item.next;
	update = (struct ast_compound_assignment_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->expression.type == &type_uchar && !update->expression.is_lvalue);
	assert(update->left->kind == expression_name && update->left->is_lvalue);
	assert(update->operation == binary_subtract && update->calculation_type == &type_long && !update->element_size);
	assert(update->right->type == &type_long);
	item = (struct ast_statement_item *)item->item.next;
	update = (struct ast_compound_assignment_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->expression.kind == expression_compound_assignment && !update->expression.is_lvalue);
	assert(update->calculation_type == update->expression.type && update->element_size == 4);
	assert(update->left->kind == expression_name && update->left->is_lvalue);
	assert(((const struct pointer_type *)update->expression.type)->referent->qualifiers == type_qualifier_const);
	assert(!update->expression.type->qualifiers && update->expression.depth == 3 && !unit->strings);
	require_conversion(update->right, &type_int, &type_bool);
	assert(((struct ast_conversion_expression *)update->right)->operand->kind == expression_boolean);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}


static void test_integer_compound_tree(void)
{
	const char *text = "int f(unsigned char c,int i,long l,_Bool b,unsigned short s) { "
		"c*=3UL; i>>=1UL; l<<=2U; b|=4294967296UL; i<<=s; return 42; }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_statement_item *item;
	struct ast_compound_assignment_expression *update;
	struct ast_expression *parsed_left;
	struct ast_expression *parsed_right;

	assert(source_from_bytes(&source, "integer-compound.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	item = (struct ast_statement_item *)function->body->items;
	update = (struct ast_compound_assignment_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->expression.kind == expression_compound_assignment && update->expression.depth == 2);
	parsed_left = update->left;
	parsed_right = update->right;
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(update->left == parsed_left && update->right == parsed_right);
	assert(update->left->kind == expression_name && update->left->is_lvalue);
	assert(update->expression.type == &type_uchar && !update->expression.is_lvalue);
	assert(update->operation == binary_multiply && update->calculation_type == &type_ulong);
	assert(!update->element_size && update->expression.depth == 2);
	assert(update->expression.location.offset == (size_t)(strstr(text, "c*=") + 1 - text));
	item = (struct ast_statement_item *)item->item.next;
	update = (struct ast_compound_assignment_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->operation == binary_shift_right && update->calculation_type == &type_int);
	assert(update->expression.type == &type_int && update->right->type == &type_ulong);
	assert(update->right->kind == expression_integer && !update->expression.is_lvalue);
	item = (struct ast_statement_item *)item->item.next;
	update = (struct ast_compound_assignment_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->operation == binary_shift_left && update->calculation_type == &type_long);
	assert(update->expression.type == &type_long && update->right->type == &type_uint);
	item = (struct ast_statement_item *)item->item.next;
	update = (struct ast_compound_assignment_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->operation == binary_bit_or && update->calculation_type == &type_ulong);
	assert(update->expression.type == &type_bool && update->left->is_lvalue && !update->expression.is_lvalue);
	item = (struct ast_statement_item *)item->item.next;
	update = (struct ast_compound_assignment_expression *)((struct ast_expression_statement *)item->statement)->value;
	assert(update->operation == binary_shift_left && update->calculation_type == &type_int);
	assert(update->expression.type == &type_int && update->expression.depth == 4);
	require_conversion(update->right, &type_int, &type_ushort);
	assert(((struct ast_conversion_expression *)update->right)->operand->kind == expression_load);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}



static void test_named_label_tree(void)
{
	const char *text = "int f(int x) { x: int y=1; if(x) yes: y+=1; tail: return y; }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_block_label *first;
	struct ast_block_label *tail;
	struct ast_local_declaration *local;
	struct ast_statement_item *item;
	struct ast_if_statement *branch;
	struct ast_labeled_statement *labeled;
	struct ast_compound_assignment_expression *assignment;
	size_t local_count = 0;

	assert(source_from_bytes(&source, "labels.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	first = (struct ast_block_label *)function->body->items;
	assert(first->item.kind == block_item_label && first->label->name.kind == token_identifier);
	assert(first->label->name.location.offset == (size_t)(strstr(text, "x:") - text));
	local = (struct ast_local_declaration *)first->item.next;
	assert(local->item.kind == block_item_declaration);
	item = (struct ast_statement_item *)local->item.next;
	branch = (struct ast_if_statement *)item->statement;
	assert(branch->statement.kind == statement_if);
	labeled = (struct ast_labeled_statement *)branch->then_branch;
	assert(labeled->statement.kind == statement_labeled);
	assert(labeled->label->name.location.offset == (size_t)(strstr(text, "yes:") - text));
	assert(labeled->body->kind == statement_expression);
	assignment = (struct ast_compound_assignment_expression *)((struct ast_expression_statement *)labeled->body)->value;
	assert(assignment->expression.kind == expression_compound_assignment);
	tail = (struct ast_block_label *)item->item.next;
	assert(tail->item.kind == block_item_label && tail->item.next->kind == block_item_statement);
	assert(tail->label->name.location.offset == (size_t)(strstr(text, "tail:") - text));
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(assignment->expression.type == &type_int && assignment->left->is_lvalue);
	assert(((struct ast_name_expression *)assignment->left)->declaration == local);
	for (local = function->locals; local; local = local->next_local)
		local_count++;
	assert(local_count == 2 && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}


static void test_goto_tree(void)
{
	const char *text = "int f(void) { goto tail; head: if(0) inner: goto head; tail: return 42; } "
		"int g(void) { goto head; head: return 1; }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_statement_item *item;
	struct ast_goto_statement *forward;
	struct ast_goto_statement *backward;
	struct ast_block_label *head;
	struct ast_block_label *tail;
	struct ast_if_statement *branch;
	struct ast_labeled_statement *inner;

	assert(source_from_bytes(&source, "goto.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	item = (struct ast_statement_item *)function->body->items;
	forward = (struct ast_goto_statement *)item->statement;
	assert(forward->statement.kind == statement_goto && !forward->target);
	assert(forward->name.location.offset == (size_t)(strstr(text, "goto tail") + 5 - text));
	head = (struct ast_block_label *)item->item.next;
	assert(head->item.kind == block_item_label);
	item = (struct ast_statement_item *)head->item.next;
	branch = (struct ast_if_statement *)item->statement;
	assert(branch->statement.kind == statement_if);
	inner = (struct ast_labeled_statement *)branch->then_branch;
	assert(inner->statement.kind == statement_labeled);
	backward = (struct ast_goto_statement *)inner->body;
	assert(backward->statement.kind == statement_goto && !backward->target);
	tail = (struct ast_block_label *)item->item.next;
	assert(tail->item.kind == block_item_label);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(function->label_count == 3 && !function->locals && !unit->strings);
	assert(forward->target == tail->label && backward->target == head->label);
	assert(head->label->index == 0 && inner->label->index == 1 && tail->label->index == 2);
	function = (struct ast_function *)function->external.next;
	item = (struct ast_statement_item *)function->body->items;
	forward = (struct ast_goto_statement *)item->statement;
	head = (struct ast_block_label *)item->item.next;
	assert(function->label_count == 1 && forward->target == head->label && head->label->index == 0);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}


static void test_switch_foundation_tree(void)
{
	const char *text = "int f(unsigned char x) { for(;;) switch(x) { switch(x) continue; break; } return 0; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_statement_item *item;
	struct ast_for_statement *loop;
	struct ast_switch_statement *outer;
	struct ast_switch_statement *inner;
	struct ast_compound_statement *body;
	struct ast_continue_statement *continuation;
	struct ast_break_statement *exit;
	struct ast_expression *original;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	item = (struct ast_statement_item *)first_function(unit)->body->items;
	loop = (struct ast_for_statement *)item->statement;
	assert(loop->statement.kind == statement_for);
	outer = (struct ast_switch_statement *)loop->body;
	assert(outer->statement.kind == statement_switch);
	assert(outer->statement.location.offset == (size_t)(strstr(text, "switch") - text));
	original = outer->control;
	assert(original->kind == expression_name);
	body = (struct ast_compound_statement *)outer->body;
	assert(body->statement.kind == statement_compound);
	item = (struct ast_statement_item *)body->items;
	inner = (struct ast_switch_statement *)item->statement;
	assert(inner->statement.kind == statement_switch);
	continuation = (struct ast_continue_statement *)inner->body;
	assert(continuation->statement.kind == statement_continue && !continuation->target);
	exit = (struct ast_break_statement *)((struct ast_statement_item *)item->item.next)->statement;
	assert(exit->statement.kind == statement_break && !exit->target);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(!diagnostics.errors);
	assert(outer->control->kind == expression_conversion && outer->control->type == &type_int);
	assert(inner->control->type == &type_int);
	assert(original->type == &type_uchar);
	assert(continuation->target == &loop->statement);
	assert(exit->target == &outer->statement);
	assert(first_function(unit)->locals && !first_function(unit)->locals->next_local);
	assert(!unit->strings);

	fclose(stream);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}


static void test_switch_case_tree(void)
{
	const char *text = "int f(unsigned x) { switch(x) { case -1: { switch(x) { case -1: break; default: break; } } case 0: break; default: break; } end: return 0; } int g(void) { switch(1) { case 1: return 0; } return 0; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_statement_item *item;
	struct ast_switch_statement *outer;
	struct ast_switch_statement *inner;
	struct ast_compound_statement *body;
	struct ast_compound_statement *nested;
	struct ast_case_label *negative;
	struct ast_case_label *zero;
	struct ast_default_label *fallback;
	struct ast_expression *original;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	item = (struct ast_statement_item *)function->body->items;
	outer = (struct ast_switch_statement *)item->statement;
	assert(outer->statement.kind == statement_switch);
	body = (struct ast_compound_statement *)outer->body;
	negative = ((struct ast_block_case *)body->items)->label;
	assert(body->items->kind == block_item_case && !negative->owner);
	original = negative->value;
	assert(original->kind == expression_unary);
	assert(negative->location.offset == (size_t)(strstr(text, "case -1") - text));
	item = (struct ast_statement_item *)body->items->next;
	nested = (struct ast_compound_statement *)item->statement;
	assert(nested->statement.kind == statement_compound);
	inner = (struct ast_switch_statement *)((struct ast_statement_item *)nested->items)->statement;
	assert(inner->statement.kind == statement_switch);
	zero = ((struct ast_block_case *)item->item.next)->label;
	fallback = ((struct ast_block_default *)item->item.next->next->next)->label;
	assert(!fallback->owner);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(outer->control->type == &type_uint);
	assert(outer->label_count == 3 && inner->label_count == 2);
	assert(function->switch_label_count == 5 && function->label_count == 1);
	assert(negative->owner == outer && zero->owner == outer && fallback->owner == outer);
	assert(negative->index == 0 && zero->index == 3 && fallback->index == 4);
	assert(negative->bits == UINT32_MAX && zero->bits == 0);
	assert(negative->value->kind == expression_conversion && negative->value->type == &type_uint);
	assert(((struct ast_conversion_expression *)negative->value)->operand == original);
	assert(original->type == &type_int);
	assert(outer->cases == zero && zero->next == negative && !negative->next);
	assert(outer->default_label == fallback);
	assert(inner->cases->owner == inner && inner->cases->bits == UINT32_MAX);
	assert(inner->cases->index == 1 && inner->default_label->index == 2);
	function = (struct ast_function *)function->external.next;
	outer = (struct ast_switch_statement *)((struct ast_statement_item *)function->body->items)->statement;
	assert(function->switch_label_count == 1 && !function->label_count && outer->cases->index == 0);
	assert(!unit->strings);

	fclose(stream);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}


static void test_typeof_type_tree(void)
{
	const char *text = "int f(void) { typeof(const int) x=1; typeof_unqual(const int) y=2; typeof_unqual(const int * const) p=&x; typeof_unqual(const int[2]) a; return y; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_local_declaration *x;
	struct ast_local_declaration *y;
	struct ast_local_declaration *p;
	struct ast_local_declaration *a;
	struct ast_typeof_type_syntax *query;
	const struct type *operand;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	x = (struct ast_local_declaration *)first_function(unit)->body->items;
	y = (struct ast_local_declaration *)x->item.next;
	p = (struct ast_local_declaration *)y->item.next;
	a = (struct ast_local_declaration *)p->item.next;
	query = (struct ast_typeof_type_syntax *)x->type_syntax;
	assert(query->syntax.kind == type_syntax_typeof_type && !query->unqualify);
	assert(query->syntax.location.offset == (size_t)(strstr(text, "typeof(") - text));
	assert(!query->syntax.type && query->operand->kind == type_syntax_qualified);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(query->syntax.type == query->operand->type && x->type == query->syntax.type);
	assert(x->type->kind == type_kind_int && x->type->qualifiers == type_qualifier_const);
	query = (struct ast_typeof_type_syntax *)y->type_syntax;
	assert(query->unqualify && !y->type->qualifiers && y->type->kind == type_kind_int);
	assert(query->operand->type->qualifiers == type_qualifier_const);
	query = (struct ast_typeof_type_syntax *)p->type_syntax;
	operand = query->operand->type;
	assert(operand->kind == type_kind_pointer && operand->qualifiers == type_qualifier_const);
	assert(p->type->kind == type_kind_pointer && !p->type->qualifiers);
	assert(((const struct pointer_type *)p->type)->referent == ((const struct pointer_type *)operand)->referent);
	assert(((const struct pointer_type *)p->type)->referent->qualifiers == type_qualifier_const);
	query = (struct ast_typeof_type_syntax *)a->type_syntax;
	operand = query->operand->type;
	assert(operand->kind == type_kind_array && operand->qualifiers == type_qualifier_const);
	assert(a->type->kind == type_kind_array && !a->type->qualifiers);
	assert(!((const struct array_type *)a->type)->element->qualifiers);
	assert(((const struct array_type *)operand)->element->qualifiers == type_qualifier_const);
	assert(!unit->strings);

	fclose(stream);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}


static void test_typeof_expression_tree(void)
{
	const char *text = "int f(void) { const int x=1; typeof(x) y=2; int a[2]; typeof(a) b; typeof_unqual(x) z=3; typeof(f) *p=f; typeof((x,x)) v=4; typeof(z++) n=5; return z; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_local_declaration *x;
	struct ast_local_declaration *y;
	struct ast_local_declaration *a;
	struct ast_local_declaration *b;
	struct ast_local_declaration *z;
	struct ast_local_declaration *p;
	struct ast_local_declaration *v;
	struct ast_local_declaration *n;
	struct ast_typeof_expression_syntax *query;
	struct ast_comma_expression *comma;
	struct ast_expression *original;
	size_t local_count = 0;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	x = (struct ast_local_declaration *)first_function(unit)->body->items;
	y = (struct ast_local_declaration *)x->item.next;
	a = (struct ast_local_declaration *)y->item.next;
	b = (struct ast_local_declaration *)a->item.next;
	z = (struct ast_local_declaration *)b->item.next;
	p = (struct ast_local_declaration *)z->item.next;
	v = (struct ast_local_declaration *)p->item.next;
	n = (struct ast_local_declaration *)v->item.next;
	query = (struct ast_typeof_expression_syntax *)y->type_syntax;
	assert(query->syntax.kind == type_syntax_typeof_expression && !query->unqualify);
	assert(query->syntax.location.offset == (size_t)(strstr(text, "typeof(") - text));
	assert(!query->syntax.type && !query->operand->type);
	original = query->operand;
	assert(original->kind == expression_name);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(query->operand == original && original->is_lvalue);
	assert(((struct ast_name_expression *)original)->declaration == x);
	assert(query->syntax.type == x->type && query->syntax.type == y->type);
	assert(y->type->qualifiers == type_qualifier_const);
	query = (struct ast_typeof_expression_syntax *)b->type_syntax;
	assert(query->operand->kind == expression_name && query->operand->is_lvalue);
	assert(b->type == a->type && b->type->kind == type_kind_array);
	query = (struct ast_typeof_expression_syntax *)z->type_syntax;
	assert(query->unqualify && !z->type->qualifiers && z->type->kind == type_kind_int);
	assert(query->operand->type == x->type && query->operand->type->qualifiers);
	query = (struct ast_typeof_expression_syntax *)((struct ast_pointer_type_syntax *)p->type_syntax)->referent;
	assert(query->operand->kind == expression_function_designator && !query->operand->is_lvalue);
	assert(query->syntax.type->kind == type_kind_function);
	assert(((const struct pointer_type *)p->type)->referent == query->syntax.type);
	query = (struct ast_typeof_expression_syntax *)v->type_syntax;
	comma = (struct ast_comma_expression *)query->operand;
	assert(comma->expression.kind == expression_comma && !v->type->qualifiers);
	assert(comma->left->kind == expression_load && comma->right->kind == expression_load);
	query = (struct ast_typeof_expression_syntax *)n->type_syntax;
	assert(query->operand->kind == expression_postfix_update && !query->operand->is_lvalue);
	assert(query->syntax.type == query->operand->type && !n->type->qualifiers);
	for (struct ast_local_declaration *local = first_function(unit)->locals; local; local = local->next_local)
		local_count++;
	assert(local_count == 8 && !unit->strings);

	fclose(stream);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_void_parameter_query_tree(void)
{
	const char *text = "int f(typeof(void)) { return 42; } int main(typeof((void)0)) { int (*p)(typeof_unqual(const void))=f; return p(); }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *f;
	struct ast_function *main_function;
	struct ast_parameter *marker;
	struct ast_parameter *main_marker;
	struct ast_local_declaration *callback;
	struct ast_function_type_syntax *callback_syntax;
	struct ast_parameter *callback_marker;
	struct ast_type_syntax *written;
	const struct function_type *signature;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	f = first_function(unit);
	main_function = (struct ast_function *)f->external.next;
	marker = f->declaration->parameters;
	main_marker = main_function->declaration->parameters;
	assert(marker && !marker->next && !marker->has_name && !marker->is_void_marker);
	assert(!marker->type && marker->type_syntax->kind == type_syntax_typeof_type);
	assert(f->declaration->parameter_count == 1 && f->declaration->type_syntax->parameter_count == 1);
	written = marker->type_syntax;
	callback = (struct ast_local_declaration *)main_function->body->items;
	callback_syntax = (struct ast_function_type_syntax *)((struct ast_pointer_type_syntax *)callback->type_syntax)->referent;
	callback_marker = callback_syntax->parameters;
	assert(callback_marker && !callback_marker->is_void_marker && !callback_marker->type);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(f->declaration->parameters == marker && marker->type_syntax == written);
	assert(marker->is_void_marker && !marker->local && marker->type == &type_void);
	assert(!f->locals && f->declaration->parameter_count == 1);
	assert(!f->declaration->symbol->type->parameter_count && !f->declaration->symbol->type->parameters);
	assert(main_marker->is_void_marker && !main_marker->local && main_marker->type == &type_void);
	assert(!main_function->declaration->symbol->type->parameter_count);
	assert(main_function->locals == callback && !callback->next_local && callback->slot == 0);
	assert(callback_marker->is_void_marker && !callback_marker->local && !callback_marker->type->qualifiers);
	assert(callback_marker->type->kind == type_kind_void && callback_syntax->parameter_count == 1);
	signature = (const struct function_type *)((const struct pointer_type *)callback->type)->referent;
	assert(!signature->parameter_count && !signature->parameters);
	assert(type_compatible(&signature->type, &f->declaration->symbol->type->type));
	assert(!unit->strings);

	fclose(stream);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_nullptr_assignment_conversion_tree(void)
{
	const char *text = "typeof(nullptr) f(typeof(nullptr) n) { return 0; } int main(void) { typeof(nullptr) n=0; n=(void *)0; return f(0)==n?42:1; }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_function *main_function;
	struct ast_return_statement *return_statement;
	struct ast_local_declaration *local;
	struct ast_statement_item *item;
	struct ast_assignment_expression *assignment;
	struct ast_conditional_expression *conditional;
	struct ast_binary_expression *comparison;
	struct ast_call_expression *call;
	struct ast_conversion_expression *conversion;
	struct ast_expression *original;

	assert(source_from_bytes(&source, "nullptr-conversion.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	main_function = (struct ast_function *)function->external.next;
	local = (struct ast_local_declaration *)main_function->body->items;
	original = local->initializer;
	assert(original->kind == expression_integer && original->depth == 1);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(function->return_type == &type_nullptr);
	item = (struct ast_statement_item *)function->body->items;
	return_statement = (struct ast_return_statement *)item->statement;
	conversion = (struct ast_conversion_expression *)return_statement->value;
	assert(conversion->expression.kind == expression_conversion && conversion->expression.type == &type_nullptr);
	assert(conversion->operand->kind == expression_integer && conversion->operand->type == &type_int);
	conversion = (struct ast_conversion_expression *)local->initializer;
	assert(conversion->expression.kind == expression_conversion && conversion->expression.type == &type_nullptr);
	assert(conversion->operand == original && original->type == &type_int && conversion->expression.depth == 2);
	assert(local->type == &type_nullptr && local->slot == 0 && !local->next_local);
	item = (struct ast_statement_item *)local->item.next;
	assignment = (struct ast_assignment_expression *)((struct ast_expression_statement *)item->statement)->value;
	conversion = (struct ast_conversion_expression *)assignment->right;
	assert(assignment->expression.type == &type_nullptr && assignment->left->is_lvalue);
	assert(conversion->expression.kind == expression_conversion && conversion->expression.type == &type_nullptr);
	assert(conversion->operand->kind == expression_cast && conversion->operand->type->kind == type_kind_pointer);
	item = (struct ast_statement_item *)item->item.next;
	conditional = (struct ast_conditional_expression *)((struct ast_return_statement *)item->statement)->value;
	comparison = (struct ast_binary_expression *)conditional->condition;
	conversion = (struct ast_conversion_expression *)comparison->left;
	assert(conversion->expression.kind == expression_conversion && conversion->operand->kind == expression_call);
	call = (struct ast_call_expression *)conversion->operand;
	assert(call->expression.type == &type_nullptr && call->argument_count == 1);
	conversion = (struct ast_conversion_expression *)call->arguments->value;
	assert(conversion->expression.kind == expression_conversion && conversion->expression.type == &type_nullptr);
	assert(conversion->operand->kind == expression_integer && conversion->operand->type == &type_int);
	assert(main_function->locals == local && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_queried_function_declaration_tree(void)
{
	const char *text = "int seed(int (*p)[]); typeof(seed) alias; int alias(int (*p)[2]) { return (*p)[1]; } typeof(alias) again; int again(int (*p)[2]) { return alias(p); } int main(void) { int a[2]; a[1]=42; return again(&a); }";
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { 0 };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function_declaration *seed;
	struct ast_external_type_declaration *alias;
	struct ast_external_type_declaration *again;
	struct ast_function *definition;
	struct ast_function *again_definition;
	struct ast_typeof_expression_syntax *query;
	struct ast_type_syntax *written;
	const struct function_type *cached;
	const struct array_type *array;

	assert(source_from_bytes(&source, "queried-function.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	seed = (struct ast_function_declaration *)unit->declarations;
	alias = (struct ast_external_type_declaration *)seed->external.next;
	assert(alias->external.kind == external_type_declaration && !alias->type && !alias->symbol);
	written = alias->type_syntax;
	query = (struct ast_typeof_expression_syntax *)written;
	assert(written->kind == type_syntax_typeof_expression && !written->type);
	assert(query->operand->kind == expression_name && !query->operand->type);
	definition = (struct ast_function *)alias->external.next;
	again = (struct ast_external_type_declaration *)definition->external.next;
	again_definition = (struct ast_function *)again->external.next;
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(alias->type_syntax == written && alias->type == written->type);
	assert(query->operand->kind == expression_function_designator && !query->operand->is_lvalue);
	assert(((struct ast_function_designator_expression *)query->operand)->function == seed->symbol);
	assert(query->operand->type == alias->type && alias->type == &seed->symbol->type->type);
	assert(alias->symbol != seed->symbol && alias->symbol == definition->declaration->symbol);
	assert(alias->symbol->definition == definition && !seed->symbol->definition);
	cached = (const struct function_type *)alias->type;
	array = (const struct array_type *)((const struct pointer_type *)cached->parameters->type)->referent;
	assert(array->type.kind == type_kind_array && !array->count);
	array = (const struct array_type *)((const struct pointer_type *)alias->symbol->type->parameters->type)->referent;
	assert(array->count == 2 && &alias->symbol->type->type != alias->type);
	assert(again->external.kind == external_type_declaration && again->type == &alias->symbol->type->type);
	assert(again->symbol != alias->symbol && again->symbol == again_definition->declaration->symbol);
	assert(again->symbol->definition == again_definition && again->type_syntax->type == again->type);
	assert(definition->locals == definition->declaration->parameters->local);
	assert(definition->locals && !definition->locals->next_local && definition->locals->slot == 0);
	assert(!unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
}

static void test_typedef_tree(void)
{
	const char *text = "typedef int number; typedef number pair[2]; typedef int signature(number); "
		"signature f; int f(int x) { return x; } int main(void) { "
		"goto number; number: pair a; a[0]=42; return f(a[0]); }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_typedef_declaration *number;
	struct ast_typedef_declaration *pair;
	struct ast_typedef_declaration *signature;
	struct ast_external_type_declaration *prototype;
	struct ast_function *definition;
	struct ast_function *main_function;
	struct ast_local_declaration *local;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	assert(unit->declarations->kind == external_typedef_declaration);
	number = ((struct ast_external_typedef_declaration *)unit->declarations)->declaration;
	pair = ((struct ast_external_typedef_declaration *)unit->declarations->next)->declaration;
	signature = ((struct ast_external_typedef_declaration *)unit->declarations->next->next)->declaration;
	prototype = (struct ast_external_type_declaration *)unit->declarations->next->next->next;
	assert(prototype->external.kind == external_type_declaration);
	assert(prototype->type_syntax->kind == type_syntax_typedef_name);
	assert(!number->type && !pair->type && !signature->type && !prototype->type);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	assert(number->type == &type_int);
	assert(pair->type == pair->type_syntax->type && pair->type->kind == type_kind_array);
	assert(((const struct array_type *)pair->type)->element == number->type);
	assert(signature->type == signature->type_syntax->type && signature->type->kind == type_kind_function);
	assert(prototype->type_syntax->type == signature->type && prototype->type == signature->type);
	definition = (struct ast_function *)prototype->external.next;
	assert(definition->external.kind == external_function_definition);
	assert(prototype->symbol == definition->declaration->symbol);
	main_function = (struct ast_function *)definition->external.next;
	assert(main_function->external.kind == external_function_definition);
	local = main_function->locals;
	assert(local && !local->next_local && local->type == pair->type);
	assert(local->type_syntax->kind == type_syntax_typedef_name);
	assert(!unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_typedef_redeclaration_tree(void)
{
	const char *text = "typedef int A[2]; typedef int A[2]; typedef A A; "
		"typedef int F(const int); typedef int F(int); int main(void) { A a; a[1]=42; return a[1]; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_external_declaration *external;
	struct ast_typedef_declaration *first;
	struct ast_typedef_declaration *second;
	struct ast_typedef_declaration *self;
	struct ast_typedef_declaration *function;
	struct ast_typedef_declaration *repeated_function;
	struct ast_function *main_function;
	struct array_type *unknown;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	external = unit->declarations;
	first = ((struct ast_external_typedef_declaration *)external)->declaration;
	external = external->next;
	second = ((struct ast_external_typedef_declaration *)external)->declaration;
	external = external->next;
	self = ((struct ast_external_typedef_declaration *)external)->declaration;
	external = external->next;
	function = ((struct ast_external_typedef_declaration *)external)->declaration;
	external = external->next;
	repeated_function = ((struct ast_external_typedef_declaration *)external)->declaration;
	main_function = (struct ast_function *)external->next;
	assert(first->type == second->type && first->type == self->type);
	assert(first->type == first->type_syntax->type);
	assert(second->type_syntax->type != first->type_syntax->type);
	assert(type_same(first->type_syntax->type, second->type_syntax->type));
	assert(self->type_syntax->type == first->type);
	assert(function->type == repeated_function->type);
	assert(function->type_syntax->type != repeated_function->type_syntax->type);
	assert(type_same(function->type_syntax->type, repeated_function->type_syntax->type));
	assert(main_function->locals && !main_function->locals->next_local);
	assert(main_function->locals->type == first->type && !unit->strings);
	unknown = type_new_incomplete_array(&arena, &type_int);
	assert(unknown);
	assert(type_compatible(&unknown->type, first->type));
	assert(!type_same(&unknown->type, first->type));
	assert(!type_same(first->type, &unknown->type));
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_typedef_declaration_list_tree(void)
{
	const char *text = "typedef int T,*P,A[2],F(T),T; F f; "
		"int f(int x) { return x; } int main(void) { A a; a[1]=42; return f(a[1]); }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_external_declaration *external;
	struct ast_typedef_declaration *aliases[5];
	struct ast_external_type_declaration *prototype;
	struct ast_function *definition;
	struct ast_function *main_function;
	struct ast_type_syntax *base;
	size_t i;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	external = unit->declarations;
	for (i = 0; i < 5; i++) {
		assert(external && external->kind == external_typedef_declaration);
		aliases[i] = ((struct ast_external_typedef_declaration *)external)->declaration;
		assert(!aliases[i]->type && !aliases[i]->type_syntax->type);
		external = external->next;
	}
	base = aliases[0]->type_syntax;
	assert(aliases[4]->type_syntax == base);
	assert(aliases[1]->type_syntax->kind == type_syntax_pointer);
	assert(((struct ast_pointer_type_syntax *)aliases[1]->type_syntax)->referent == base);
	assert(aliases[2]->type_syntax->kind == type_syntax_array);
	assert(((struct ast_array_type_syntax *)aliases[2]->type_syntax)->element == base);
	assert(aliases[3]->type_syntax->kind == type_syntax_function);
	assert(((struct ast_function_type_syntax *)aliases[3]->type_syntax)->return_syntax == base);
	prototype = (struct ast_external_type_declaration *)external;
	assert(prototype->external.kind == external_type_declaration);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	assert(aliases[0]->type == &type_int && aliases[4]->type == &type_int);
	assert(((const struct pointer_type *)aliases[1]->type)->referent == &type_int);
	assert(((const struct array_type *)aliases[2]->type)->element == &type_int);
	assert(prototype->type == aliases[3]->type);
	definition = (struct ast_function *)prototype->external.next;
	assert(definition->external.kind == external_function_definition);
	assert(definition->declaration->symbol == prototype->symbol);
	main_function = (struct ast_function *)definition->external.next;
	assert(main_function->external.kind == external_function_definition);
	assert(!main_function->external.next);
	assert(main_function->locals && !main_function->locals->next_local);
	assert(main_function->locals->type == aliases[2]->type && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_block_typedef_tree(void)
{
	const char *text = "int f(void) { typedef int T,T,*P; T x=40; "
		"{ typedef T U; U y=2; x+=y; } return x; } "
		"typedef long T; int main(void) { T x=2; return f()+x; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *first;
	struct ast_function *main_function;
	struct ast_block_item *item;
	struct ast_typedef_declaration *alias;
	struct ast_typedef_declaration *repeated;
	struct ast_typedef_declaration *pointer;
	struct ast_typedef_declaration *nested_alias;
	struct ast_typedef_declaration *file_alias;
	struct ast_local_declaration *local;
	struct ast_compound_statement *nested;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	first = (struct ast_function *)unit->declarations;
	assert(first->external.kind == external_function_definition);
	item = first->body->items;
	assert(item->kind == block_item_typedef_declaration);
	alias = ((struct ast_block_typedef_declaration *)item)->declaration;
	item = item->next;
	assert(item->kind == block_item_typedef_declaration);
	repeated = ((struct ast_block_typedef_declaration *)item)->declaration;
	item = item->next;
	assert(item->kind == block_item_typedef_declaration);
	pointer = ((struct ast_block_typedef_declaration *)item)->declaration;
	assert(alias->type_syntax == repeated->type_syntax);
	assert(((struct ast_pointer_type_syntax *)pointer->type_syntax)->referent == alias->type_syntax);
	assert(!alias->type && !repeated->type && !pointer->type);
	item = item->next;
	assert(item->kind == block_item_declaration);
	local = (struct ast_local_declaration *)item;
	item = item->next;
	assert(item->kind == block_item_statement);
	nested = (struct ast_compound_statement *)((struct ast_statement_item *)item)->statement;
	assert(nested->statement.kind == statement_compound);
	assert(nested->items->kind == block_item_typedef_declaration);
	nested_alias = ((struct ast_block_typedef_declaration *)nested->items)->declaration;
	assert(first->external.next->kind == external_typedef_declaration);
	file_alias = ((struct ast_external_typedef_declaration *)first->external.next)->declaration;
	main_function = (struct ast_function *)first->external.next->next;
	assert(main_function->external.kind == external_function_definition);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	assert(alias->type == &type_int && repeated->type == alias->type);
	assert(nested_alias->type == alias->type);
	assert(((const struct pointer_type *)pointer->type)->referent == alias->type);
	assert(file_alias->type == &type_long);
	assert(local->type == alias->type && !local->next_local);
	assert(first->locals && first->locals->next_local == local);
	assert(first->locals->type == nested_alias->type);
	assert(main_function->locals && !main_function->locals->next_local);
	assert(main_function->locals->type == file_alias->type && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_for_typedef_tree(void)
{
	const char *text = "int main(void) { int done=0; "
		"for(typedef int T,T,*P;done<1;done+=(T)1) { T x=42; if(x!=42) return 1; } "
		"typedef long T; T x=42; return x; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_block_item *item;
	struct ast_for_statement *loop;
	struct ast_typedef_declaration *alias;
	struct ast_typedef_declaration *repeated;
	struct ast_typedef_declaration *pointer;
	struct ast_typedef_declaration *after;
	struct ast_local_declaration *local;
	size_t local_count = 0;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	function = (struct ast_function *)unit->declarations;
	assert(function->external.kind == external_function_definition && !function->external.next);
	item = function->body->items->next;
	assert(item->kind == block_item_statement);
	loop = (struct ast_for_statement *)((struct ast_statement_item *)item)->statement;
	assert(loop->statement.kind == statement_for && !loop->initializer_expression);
	assert(item->next->kind == block_item_typedef_declaration);
	after = ((struct ast_block_typedef_declaration *)item->next)->declaration;
	item = loop->initializer_declarations;
	assert(item->kind == block_item_typedef_declaration);
	alias = ((struct ast_block_typedef_declaration *)item)->declaration;
	item = item->next;
	assert(item->kind == block_item_typedef_declaration);
	repeated = ((struct ast_block_typedef_declaration *)item)->declaration;
	item = item->next;
	assert(item->kind == block_item_typedef_declaration && !item->next);
	pointer = ((struct ast_block_typedef_declaration *)item)->declaration;
	assert(alias->type_syntax == repeated->type_syntax);
	assert(((struct ast_pointer_type_syntax *)pointer->type_syntax)->referent == alias->type_syntax);
	assert(!alias->type && !repeated->type && !pointer->type && !after->type);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	assert(alias->type == &type_int && repeated->type == alias->type);
	assert(((const struct pointer_type *)pointer->type)->referent == alias->type);
	assert(after->type == &type_long);
	for (local = function->locals; local; local = local->next_local)
		local_count++;
	assert(local_count == 3 && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_typedef_shadowing_tree(void)
{
	const char *text = "typedef long T; int main(void) { typedef int T,T,*P; T x=40; "
		"{ typedef T *T,*T; T p=&x; { typedef char T; T y=2; x+=y; } "
		"T q=p; if(*q!=42) return 1; } T z=0; return x+z; } T f(T x) { return x; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_function *after;
	struct ast_block_item *item;
	struct ast_compound_statement *nested;
	struct ast_compound_statement *deep;
	struct ast_typedef_declaration *file_alias;
	struct ast_typedef_declaration *outer;
	struct ast_typedef_declaration *repeated;
	struct ast_typedef_declaration *inner;
	struct ast_typedef_declaration *inner_repeated;
	struct ast_typedef_declaration *deep_alias;
	struct ast_local_declaration *local;
	size_t local_count = 0;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	assert(unit->declarations->kind == external_typedef_declaration);
	file_alias = ((struct ast_external_typedef_declaration *)unit->declarations)->declaration;
	function = (struct ast_function *)unit->declarations->next;
	assert(function->external.kind == external_function_definition);
	after = (struct ast_function *)function->external.next;
	assert(after->external.kind == external_function_definition && !after->external.next);
	item = function->body->items;
	assert(item->kind == block_item_typedef_declaration);
	outer = ((struct ast_block_typedef_declaration *)item)->declaration;
	repeated = ((struct ast_block_typedef_declaration *)item->next)->declaration;
	item = item->next->next->next->next;
	assert(item->kind == block_item_statement);
	nested = (struct ast_compound_statement *)((struct ast_statement_item *)item)->statement;
	assert(nested->statement.kind == statement_compound);
	item = nested->items;
	assert(item->kind == block_item_typedef_declaration);
	inner = ((struct ast_block_typedef_declaration *)item)->declaration;
	inner_repeated = ((struct ast_block_typedef_declaration *)item->next)->declaration;
	item = item->next->next->next;
	assert(item->kind == block_item_statement);
	deep = (struct ast_compound_statement *)((struct ast_statement_item *)item)->statement;
	assert(deep->statement.kind == statement_compound);
	assert(deep->items->kind == block_item_typedef_declaration);
	deep_alias = ((struct ast_block_typedef_declaration *)deep->items)->declaration;
	assert(!file_alias->type && !outer->type && !inner->type && !deep_alias->type);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	assert(file_alias->type == &type_long);
	assert(outer->type == &type_int && repeated->type == outer->type);
	assert(inner->type->kind == type_kind_pointer && inner_repeated->type == inner->type);
	assert(((const struct pointer_type *)inner->type)->referent == outer->type);
	assert(deep_alias->type == &type_char);
	assert(((struct ast_local_declaration *)nested->items->next->next)->type == inner->type);
	assert(((struct ast_local_declaration *)deep->items->next)->type == deep_alias->type);
	assert(((struct ast_local_declaration *)item->next)->type == inner->type);
	assert(after->return_type == file_alias->type);
	assert(after->declaration->parameters->type == file_alias->type);
	for (local = function->locals; local; local = local->next_local)
		local_count++;
	assert(local_count == 5 && function->locals->type == outer->type && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_typedef_function_shadowing_tree(void)
{
	const char *text = "int f(int x) { return x; } int main(void) { int (*before)(int)=f; "
		"{ typedef long f; f x=2; if(sizeof(f)!=8 || x!=2) return 1; } "
		"int (*after)(int)=f; return before(after(42)); }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *callee;
	struct ast_function *function;
	struct ast_local_declaration *before;
	struct ast_local_declaration *after;
	struct ast_block_item *item;
	struct ast_compound_statement *block;
	struct ast_typedef_declaration *alias;
	struct ast_function_decay_expression *decay;
	struct ast_function_designator_expression *designator;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	callee = first_function(unit);
	function = (struct ast_function *)callee->external.next;
	assert(function->external.kind == external_function_definition && !function->external.next);
	item = function->body->items;
	assert(item->kind == block_item_declaration);
	before = (struct ast_local_declaration *)item;
	item = item->next;
	assert(item->kind == block_item_statement);
	block = (struct ast_compound_statement *)((struct ast_statement_item *)item)->statement;
	assert(block->statement.kind == statement_compound);
	assert(block->items->kind == block_item_typedef_declaration);
	alias = ((struct ast_block_typedef_declaration *)block->items)->declaration;
	assert(item->next->kind == block_item_declaration);
	after = (struct ast_local_declaration *)item->next;
	assert(!alias->type);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0 && alias->type == &type_long);
	assert(before->initializer->kind == expression_function_decay);
	decay = (struct ast_function_decay_expression *)before->initializer;
	assert(decay->operand->kind == expression_function_designator);
	designator = (struct ast_function_designator_expression *)decay->operand;
	assert(designator->function == callee->declaration->symbol);
	assert(after->initializer->kind == expression_function_decay);
	decay = (struct ast_function_decay_expression *)after->initializer;
	assert(decay->operand->kind == expression_function_designator);
	designator = (struct ast_function_designator_expression *)decay->operand;
	assert(designator->function == callee->declaration->symbol);
	assert(((struct ast_local_declaration *)block->items->next)->type == alias->type);
	assert(function->locals == after && after->next_local->type == alias->type);
	assert(after->next_local->next_local == before && !before->next_local && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_typedef_object_shadowing_tree(void)
{
	const char *text = "int f(int T) { int *p=&T; { typedef long T; T x=2; *p+=x; } "
		"return T; } int main(void) { return f(40); }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_local_declaration *parameter;
	struct ast_local_declaration *pointer;
	struct ast_local_declaration *inner;
	struct ast_block_item *item;
	struct ast_compound_statement *block;
	struct ast_typedef_declaration *alias;
	struct ast_address_expression *address;
	struct ast_return_statement *returned;
	struct ast_load_expression *load;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	function = first_function(unit);
	item = function->body->items;
	assert(item->kind == block_item_declaration);
	pointer = (struct ast_local_declaration *)item;
	item = item->next;
	assert(item->kind == block_item_statement);
	block = (struct ast_compound_statement *)((struct ast_statement_item *)item)->statement;
	assert(block->statement.kind == statement_compound);
	assert(block->items->kind == block_item_typedef_declaration);
	alias = ((struct ast_block_typedef_declaration *)block->items)->declaration;
	assert(block->items->next->kind == block_item_declaration);
	inner = (struct ast_local_declaration *)block->items->next;
	assert(item->next->kind == block_item_statement);
	returned = (struct ast_return_statement *)((struct ast_statement_item *)item->next)->statement;
	assert(returned->statement.kind == statement_return && !alias->type);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0 && alias->type == &type_long);
	parameter = function->declaration->parameters->local;
	assert(parameter && parameter->type == &type_int && parameter->slot == 0);
	assert(pointer->initializer->kind == expression_address);
	address = (struct ast_address_expression *)pointer->initializer;
	assert(address->operand->kind == expression_name);
	assert(((struct ast_name_expression *)address->operand)->declaration == parameter);
	assert(returned->value->kind == expression_load);
	load = (struct ast_load_expression *)returned->value;
	assert(load->operand->kind == expression_name);
	assert(((struct ast_name_expression *)load->operand)->declaration == parameter);
	assert(inner->type == alias->type && inner->slot == 2 && pointer->slot == 1);
	assert(function->locals == inner && inner->next_local == pointer);
	assert(pointer->next_local == parameter && !parameter->next_local && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_object_typedef_shadowing_tree(void)
{
	const char *text = "typedef long T; int main(void) { T T=40,*P=&T; "
		"{ typedef char T; { int T=2; *P+=T; } T c=1; if(c!=1) return 1; } return T; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_typedef_declaration *outer;
	struct ast_typedef_declaration *inner;
	struct ast_local_declaration *value;
	struct ast_local_declaration *pointer;
	struct ast_local_declaration *nested;
	struct ast_local_declaration *character;
	struct ast_compound_statement *block;
	struct ast_compound_statement *deep;
	struct ast_block_item *item;
	struct ast_return_statement *returned;
	struct ast_address_expression *address;
	struct ast_load_expression *load;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	outer = ((struct ast_external_typedef_declaration *)unit->declarations)->declaration;
	assert(unit->declarations->next->kind == external_function_definition);
	function = (struct ast_function *)unit->declarations->next;
	item = function->body->items;
	assert(item->kind == block_item_declaration);
	value = (struct ast_local_declaration *)item;
	item = item->next;
	assert(item->kind == block_item_declaration);
	pointer = (struct ast_local_declaration *)item;
	assert(pointer->type_syntax->kind == type_syntax_pointer);
	assert(((struct ast_pointer_type_syntax *)pointer->type_syntax)->referent == value->type_syntax);
	item = item->next;
	block = (struct ast_compound_statement *)((struct ast_statement_item *)item)->statement;
	assert(block->statement.kind == statement_compound);
	inner = ((struct ast_block_typedef_declaration *)block->items)->declaration;
	deep = (struct ast_compound_statement *)((struct ast_statement_item *)block->items->next)->statement;
	assert(deep->statement.kind == statement_compound);
	nested = (struct ast_local_declaration *)deep->items;
	character = (struct ast_local_declaration *)block->items->next->next;
	returned = (struct ast_return_statement *)((struct ast_statement_item *)item->next)->statement;
	assert(returned->statement.kind == statement_return);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	assert(outer->type == &type_long && inner->type == &type_char);
	assert(value->type == outer->type && value->type_syntax->type == outer->type);
	assert(pointer->type->kind == type_kind_pointer);
	assert(((const struct pointer_type *)pointer->type)->referent == outer->type);
	assert(pointer->initializer->kind == expression_address);
	address = (struct ast_address_expression *)pointer->initializer;
	assert(address->operand->kind == expression_name);
	assert(((struct ast_name_expression *)address->operand)->declaration == value);
	assert(returned->value->kind == expression_conversion);
	assert(((struct ast_conversion_expression *)returned->value)->operand->kind == expression_load);
	load = (struct ast_load_expression *)((struct ast_conversion_expression *)returned->value)->operand;
	assert(load->operand->kind == expression_name);
	assert(((struct ast_name_expression *)load->operand)->declaration == value);
	assert(nested->type == &type_int && character->type == inner->type);
	assert(value->slot == 0 && pointer->slot == 1 && nested->slot == 2 && character->slot == 3);
	assert(function->locals == character && character->next_local == nested);
	assert(nested->next_local == pointer && pointer->next_local == value);
	assert(!value->next_local && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_parameter_typedef_shadowing_tree(void)
{
	const char *text = "typedef long T; int proto(int T,typeof(T) x); "
		"int f(int T,typeof(T) x,int (*cb)(char T,typeof(T) y),typeof(T) z) { "
		"typeof(T) v=T; return v; } int g(T x) { return x; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_typedef_declaration *alias;
	struct ast_function_declaration *prototype;
	struct ast_function *function;
	struct ast_function *following;
	struct ast_parameter *parameter;
	struct ast_parameter *callback;
	struct ast_function_type_syntax *nested;
	struct ast_typeof_expression_syntax *first_query;
	struct ast_typeof_expression_syntax *nested_query;
	struct ast_typeof_expression_syntax *last_query;
	struct ast_typeof_expression_syntax *body_query;
	struct ast_local_declaration *local;
	struct ast_name_expression *captured;
	struct ast_name_expression *inner_captured;
	struct ast_name_expression *body_captured;
	struct ast_load_expression *load;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	alias = ((struct ast_external_typedef_declaration *)unit->declarations)->declaration;
	prototype = (struct ast_function_declaration *)unit->declarations->next;
	assert(prototype->external.kind == external_function_declaration);
	function = (struct ast_function *)prototype->external.next;
	assert(function->external.kind == external_function_definition);
	following = (struct ast_function *)function->external.next;
	parameter = function->declaration->parameters;
	assert(parameter->has_name && !parameter->local);
	first_query = (struct ast_typeof_expression_syntax *)parameter->next->type_syntax;
	assert(first_query->syntax.kind == type_syntax_typeof_expression);
	assert(first_query->operand->kind == expression_name);
	captured = (struct ast_name_expression *)first_query->operand;
	callback = parameter->next->next;
	assert(callback->type_syntax->kind == type_syntax_pointer);
	nested = (struct ast_function_type_syntax *)((struct ast_pointer_type_syntax *)callback->type_syntax)->referent;
	assert(nested->syntax.kind == type_syntax_function && nested->parameter_count == 2);
	nested_query = (struct ast_typeof_expression_syntax *)nested->parameters->next->type_syntax;
	assert(nested_query->syntax.kind == type_syntax_typeof_expression);
	assert(nested_query->operand->kind == expression_name);
	inner_captured = (struct ast_name_expression *)nested_query->operand;
	last_query = (struct ast_typeof_expression_syntax *)callback->next->type_syntax;
	assert(last_query->syntax.kind == type_syntax_typeof_expression);
	assert(last_query->operand->kind == expression_name);
	local = (struct ast_local_declaration *)function->body->items;
	assert(local->item.kind == block_item_declaration);
	body_query = (struct ast_typeof_expression_syntax *)local->type_syntax;
	assert(body_query->syntax.kind == type_syntax_typeof_expression);
	assert(body_query->operand->kind == expression_name);
	body_captured = (struct ast_name_expression *)body_query->operand;
	assert(following->declaration->parameters->type_syntax->kind == type_syntax_typedef_name);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(alias->type == &type_long);
	assert(first_query->syntax.type == &type_int && last_query->syntax.type == &type_int);
	assert(nested_query->syntax.type == &type_char && body_query->syntax.type == &type_int);
	/* Prototype queries capture type-only objects, not definition spill locals. */
	assert(captured->declaration && captured->declaration != parameter->local);
	assert(captured->declaration->type == &type_int && !captured->declaration->next_local);
	assert(((struct ast_name_expression *)last_query->operand)->declaration == captured->declaration);
	assert(inner_captured->declaration != captured->declaration);
	assert(inner_captured->declaration->type == &type_char);
	assert(!nested->parameters->local && !nested->parameters->next->local);
	assert(!prototype->parameters->local && !prototype->parameters->next->local);
	assert(body_captured->declaration == parameter->local);
	assert(local->initializer->kind == expression_load);
	load = (struct ast_load_expression *)local->initializer;
	assert(load->operand->kind == expression_name);
	assert(((struct ast_name_expression *)load->operand)->declaration == parameter->local);
	assert(parameter->local->slot == 0 && parameter->next->local->slot == 1);
	assert(callback->local->slot == 2 && callback->next->local->slot == 3 && local->slot == 4);
	assert(function->locals == local && local->next_local == callback->next->local);
	assert(callback->next->local->next_local == callback->local);
	assert(callback->local->next_local == parameter->next->local);
	assert(parameter->next->local->next_local == parameter->local && !parameter->local->next_local);
	assert(following->declaration->parameters->type == alias->type && !unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_typedef_specifier_placement_tree(void)
{
	const char *text = "long typedef T; int f(void) { T typedef U,*P,F(U); "
		"U x=42; P p=&x; return *p; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_typedef_declaration *outer;
	struct ast_typedef_declaration *aliases[3];
	struct ast_function *function;
	struct ast_block_item *item;
	struct ast_local_declaration *value;
	struct ast_local_declaration *pointer;
	struct ast_type_syntax *base;
	const struct function_type *signature;
	size_t keyword_offset = (size_t)(strstr(text, "T typedef") + 2 - text);

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	assert(unit->declarations->kind == external_typedef_declaration);
	outer = ((struct ast_external_typedef_declaration *)unit->declarations)->declaration;
	assert(outer->location.offset == 5 && !outer->type);
	function = (struct ast_function *)unit->declarations->next;
	assert(function->external.kind == external_function_definition);
	item = function->body->items;
	for (size_t i = 0; i < 3; i++) {
		assert(item && item->kind == block_item_typedef_declaration);
		aliases[i] = ((struct ast_block_typedef_declaration *)item)->declaration;
		assert(aliases[i]->location.offset == keyword_offset && !aliases[i]->type);
		item = item->next;
	}
	base = aliases[0]->type_syntax;
	assert(base->kind == type_syntax_typedef_name);
	assert(aliases[1]->type_syntax->kind == type_syntax_pointer);
	assert(((struct ast_pointer_type_syntax *)aliases[1]->type_syntax)->referent == base);
	assert(aliases[2]->type_syntax->kind == type_syntax_function);
	assert(((struct ast_function_type_syntax *)aliases[2]->type_syntax)->return_syntax == base);
	value = (struct ast_local_declaration *)item;
	assert(value->item.kind == block_item_declaration);
	pointer = (struct ast_local_declaration *)item->next;
	assert(pointer->item.kind == block_item_declaration);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(outer->type == &type_long && aliases[0]->type == outer->type);
	assert(base->type == outer->type);
	assert(((const struct pointer_type *)aliases[1]->type)->referent == outer->type);
	signature = (const struct function_type *)aliases[2]->type;
	assert(signature->type.kind == type_kind_function && signature->parameter_count == 1);
	assert(signature->return_type == outer->type && signature->parameters->type == outer->type);
	assert(value->type == outer->type && pointer->type == aliases[1]->type);
	assert(value->slot == 0 && pointer->slot == 1);
	assert(function->locals == pointer && pointer->next_local == value && !value->next_local);
	assert(pointer->initializer->kind == expression_address);
	assert(((struct ast_name_expression *)((struct ast_address_expression *)pointer->initializer)->operand)->declaration == value);
	assert(!unit->strings);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_register_scalar_tree(void)
{
	const char *text = "typedef long T; int f(void) { T register x=40,y=x+2; "
		"typeof(x) z=y; long *p=&z; return *p; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_local_declaration *x;
	struct ast_local_declaration *y;
	struct ast_local_declaration *z;
	struct ast_local_declaration *p;
	struct ast_binary_expression *sum;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = (struct ast_function *)unit->declarations->next;
	x = (struct ast_local_declaration *)function->body->items;
	y = (struct ast_local_declaration *)x->item.next;
	z = (struct ast_local_declaration *)y->item.next;
	p = (struct ast_local_declaration *)z->item.next;
	assert(x->is_register && y->is_register && !z->is_register && !p->is_register);
	assert(x->type_syntax == y->type_syntax);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(x->type == &type_long && y->type == x->type && z->type == x->type);
	assert(x->slot == 0 && y->slot == 1 && z->slot == 2 && p->slot == 3);
	assert(function->locals == p && p->next_local == z && z->next_local == y);
	assert(y->next_local == x && !x->next_local);
	sum = (struct ast_binary_expression *)y->initializer;
	assert(sum->left->kind == expression_load);
	assert(((struct ast_load_expression *)sum->left)->operand->kind == expression_name);
	assert(((struct ast_name_expression *)((struct ast_load_expression *)sum->left)->operand)->declaration == x);
	assert(z->initializer->kind == expression_load);
	assert(((struct ast_load_expression *)z->initializer)->operand->kind == expression_name);
	assert(((struct ast_name_expression *)((struct ast_load_expression *)z->initializer)->operand)->declaration == y);
	assert(p->initializer->kind == expression_address);
	assert(((struct ast_name_expression *)((struct ast_address_expression *)p->initializer)->operand)->declaration == z);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_register_array_tree(void)
{
	const char *text = "int f(void) { register int a[2]; typeof(a) b; "
		"int *p=b; return sizeof(a); }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_local_declaration *a;
	struct ast_local_declaration *b;
	struct ast_local_declaration *p;
	struct ast_typeof_expression_syntax *query;
	struct ast_array_decay_expression *decay;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = (struct ast_function *)unit->declarations;
	a = (struct ast_local_declaration *)function->body->items;
	b = (struct ast_local_declaration *)a->item.next;
	p = (struct ast_local_declaration *)b->item.next;
	assert(a->is_register && !b->is_register && !p->is_register);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(a->type->kind == type_kind_array && a->type == b->type);
	assert(type_object_size(a->type) == 8);
	assert(a->slot == 0 && b->slot == 1 && p->slot == 2);
	assert(function->locals == p && p->next_local == b && b->next_local == a);
	assert(!a->next_local);
	query = (struct ast_typeof_expression_syntax *)b->type_syntax;
	assert(query->operand->kind == expression_name);
	assert(((struct ast_name_expression *)query->operand)->declaration == a);
	assert(query->operand->type == a->type);
	assert(p->initializer->kind == expression_array_decay);
	decay = (struct ast_array_decay_expression *)p->initializer;
	assert(decay->operand->kind == expression_name);
	assert(((struct ast_name_expression *)decay->operand)->declaration == b);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_explicit_auto_tree(void)
{
	const char *text = "int f(void) { auto int a[2],*p=a; int auto x=40,y=x+2; return y; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_local_declaration *a;
	struct ast_local_declaration *p;
	struct ast_local_declaration *x;
	struct ast_local_declaration *y;
	struct ast_binary_expression *sum;
	struct ast_array_decay_expression *decay;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = (struct ast_function *)unit->declarations;
	a = (struct ast_local_declaration *)function->body->items;
	p = (struct ast_local_declaration *)a->item.next;
	x = (struct ast_local_declaration *)p->item.next;
	y = (struct ast_local_declaration *)x->item.next;
	assert(!a->is_register && !p->is_register && !x->is_register && !y->is_register);
	assert(((struct ast_array_type_syntax *)a->type_syntax)->element ==
		((struct ast_pointer_type_syntax *)p->type_syntax)->referent);
	assert(x->type_syntax == y->type_syntax);
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	assert(a->type->kind == type_kind_array && x->type == &type_int && y->type == &type_int);
	assert(a->slot == 0 && p->slot == 1 && x->slot == 2 && y->slot == 3);
	assert(function->locals == y && y->next_local == x && x->next_local == p);
	assert(p->next_local == a && !a->next_local);
	assert(p->initializer->kind == expression_array_decay);
	decay = (struct ast_array_decay_expression *)p->initializer;
	assert(decay->operand->kind == expression_name);
	assert(((struct ast_name_expression *)decay->operand)->declaration == a);
	sum = (struct ast_binary_expression *)y->initializer;
	assert(sum->left->kind == expression_load);
	assert(((struct ast_load_expression *)sum->left)->operand->kind == expression_name);
	assert(((struct ast_name_expression *)((struct ast_load_expression *)sum->left)->operand)->declaration == x);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_local_binding_phases_tree(void)
{
	const char *text = "int f(void) { int x=sizeof(x),*p=&x; char *s=\"*\"; "
		"int (*q)(void)=f; int a[2],*r=a; return *s; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_local_declaration *locals[6];
	struct ast_block_item *item;
	struct ast_sizeof_expression *size;
	struct ast_array_decay_expression *decay;
	struct ast_function_decay_expression *callback;
	struct ast_conversion_expression *conversion;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = (struct ast_function *)unit->declarations;
	item = function->body->items;
	for (size_t i = 0; i < 6; i++) {
		assert(item && item->kind == block_item_declaration);
		locals[i] = (struct ast_local_declaration *)item;
		assert(!locals[i]->is_register);
		item = item->next;
	}
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	for (size_t i = 0; i < 6; i++) {
		assert(locals[i]->slot == i && locals[i]->type);
		assert(locals[i]->next_local == (i ? locals[i - 1] : NULL));
	}
	assert(function->locals == locals[5]);
	conversion = require_conversion(locals[0]->initializer, &type_int, &type_ulong);
	assert(conversion->operand->kind == expression_sizeof);
	size = (struct ast_sizeof_expression *)conversion->operand;
	assert(size->size == 4 && size->operand->kind == expression_name);
	assert(((struct ast_name_expression *)size->operand)->declaration == locals[0]);
	assert(locals[1]->initializer->kind == expression_address);
	assert(((struct ast_name_expression *)((struct ast_address_expression *)locals[1]->initializer)->operand)->declaration == locals[0]);
	assert(locals[2]->initializer->kind == expression_array_decay);
	decay = (struct ast_array_decay_expression *)locals[2]->initializer;
	assert(decay->operand->kind == expression_string);
	assert(unit->strings == (struct ast_string_expression *)decay->operand);
	assert(unit->strings->object_id == 0 && !unit->strings->next_string);
	assert(locals[3]->initializer->kind == expression_function_decay);
	callback = (struct ast_function_decay_expression *)locals[3]->initializer;
	assert(callback->operand->kind == expression_function_designator);
	assert(((struct ast_function_designator_expression *)callback->operand)->function == function->declaration->symbol);
	assert(locals[4]->type->kind == type_kind_array && type_object_size(locals[4]->type) == 8);
	assert(locals[5]->initializer->kind == expression_array_decay);
	decay = (struct ast_array_decay_expression *)locals[5]->initializer;
	assert(decay->operand->kind == expression_name);
	assert(((struct ast_name_expression *)decay->operand)->declaration == locals[4]);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_auto_inference_tree(void)
{
	const char *text = "int f(void) { register const int x=40; auto y=x; "
		"const auto z=y+2; auto s=\"*\"; auto q=f; int a[2]; auto r=a; return z; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_local_declaration *locals[7];
	struct ast_block_item *item;
	struct ast_inferred_type_syntax *syntax;
	struct ast_array_decay_expression *decay;
	struct ast_function_decay_expression *callback;
	struct ast_load_expression *load;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	item = function->body->items;
	for (size_t i = 0; i < 7; i++) {
		assert(item && item->kind == block_item_declaration);
		locals[i] = (struct ast_local_declaration *)item;
		assert(!locals[i]->type);
		if (i != 0 && i != 5) {
			assert(locals[i]->type_syntax->kind == type_syntax_inferred);
			assert(!locals[i]->type_syntax->type && !locals[i]->is_register);
		}
		item = item->next;
	}
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	for (size_t i = 0; i < 7; i++) {
		assert(locals[i]->slot == i && locals[i]->type);
		assert(locals[i]->type_syntax->type == locals[i]->type);
		assert(locals[i]->next_local == (i ? locals[i - 1] : NULL));
	}
	assert(function->locals == locals[6]);
	assert(locals[0]->is_register && locals[0]->type->qualifiers == type_qualifier_const);
	assert(type_compatible(locals[1]->type, &type_int) && locals[1]->initializer->kind == expression_load);
	load = (struct ast_load_expression *)locals[1]->initializer;
	assert(load->operand->kind == expression_name);
	assert(((struct ast_name_expression *)load->operand)->declaration == locals[0]);
	syntax = (struct ast_inferred_type_syntax *)locals[2]->type_syntax;
	assert(syntax->qualifiers == type_qualifier_const);
	assert(locals[2]->type->qualifiers == type_qualifier_const);
	assert(locals[2]->initializer->kind == expression_binary);
	assert(!locals[2]->initializer->type->qualifiers);
	assert(locals[3]->initializer->kind == expression_array_decay);
	decay = (struct ast_array_decay_expression *)locals[3]->initializer;
	assert(decay->operand->kind == expression_string);
	assert(unit->strings == (struct ast_string_expression *)decay->operand);
	assert(unit->strings->object_id == 0 && !unit->strings->next_string);
	assert(locals[3]->type == locals[3]->initializer->type);
	assert(locals[4]->initializer->kind == expression_function_decay);
	callback = (struct ast_function_decay_expression *)locals[4]->initializer;
	assert(callback->operand->kind == expression_function_designator);
	assert(((struct ast_function_designator_expression *)callback->operand)->function == function->declaration->symbol);
	assert(locals[5]->type->kind == type_kind_array);
	assert(locals[6]->initializer->kind == expression_array_decay);
	decay = (struct ast_array_decay_expression *)locals[6]->initializer;
	assert(decay->operand->kind == expression_name);
	assert(((struct ast_name_expression *)decay->operand)->declaration == locals[5]);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_auto_inference_unavailable_tree(void)
{
	const char *text = "int f(void) { int x=40; { auto x=sizeof(x); } return x; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_statement_item *item;
	struct ast_compound_statement *block;
	struct ast_local_declaration *outer;
	struct ast_local_declaration *inner;
	struct ast_sizeof_expression *size;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	outer = (struct ast_local_declaration *)function->body->items;
	item = (struct ast_statement_item *)outer->item.next;
	block = (struct ast_compound_statement *)item->statement;
	inner = (struct ast_local_declaration *)block->items;
	assert(!sema_translation_unit(unit, &arena, &diagnostics) && diagnostics.errors == 1);
	assert(outer->type == &type_int && !inner->type && !inner->type_syntax->type);
	assert(function->locals == outer && !outer->next_local);
	size = (struct ast_sizeof_expression *)inner->initializer;
	assert(size->expression.kind == expression_sizeof && size->operand->kind == expression_name);
	assert(((struct ast_name_expression *)size->operand)->declaration == inner);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_register_auto_inference_tree(void)
{
	const char *text = "int f(void) { const register auto x=40; auto y=x; "
		"auto register s=\"*\"; auto p=s; return y+2; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { .stream = stream };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	struct ast_function *function;
	struct ast_local_declaration *locals[4];
	struct ast_block_item *item;
	struct ast_array_decay_expression *decay;
	struct ast_load_expression *load;

	assert(stream);
	assert(source_from_bytes(&source, "test.c", (const unsigned char *)text, strlen(text)));
	assert(source_prepare(&source));
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	assert(unit && !diagnostics.errors);
	function = first_function(unit);
	item = function->body->items;
	for (size_t i = 0; i < 4; i++) {
		assert(item && item->kind == block_item_declaration);
		locals[i] = (struct ast_local_declaration *)item;
		assert(locals[i]->type_syntax->kind == type_syntax_inferred);
		assert(locals[i]->is_register == (i == 0 || i == 2));
		assert(!locals[i]->type && !locals[i]->type_syntax->type);
		item = item->next;
	}
	assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
	for (size_t i = 0; i < 4; i++) {
		assert(locals[i]->slot == i && locals[i]->type_syntax->type == locals[i]->type);
		assert(locals[i]->next_local == (i ? locals[i - 1] : NULL));
	}
	assert(function->locals == locals[3]);
	assert(locals[0]->type->qualifiers == type_qualifier_const);
	assert(!locals[1]->type->qualifiers && type_compatible(locals[1]->type, &type_int));
	assert(locals[1]->initializer->kind == expression_load);
	load = (struct ast_load_expression *)locals[1]->initializer;
	assert(load->operand->kind == expression_name);
	assert(((struct ast_name_expression *)load->operand)->declaration == locals[0]);
	assert(locals[2]->initializer->kind == expression_array_decay);
	decay = (struct ast_array_decay_expression *)locals[2]->initializer;
	assert(decay->operand->kind == expression_string);
	assert(unit->strings == (struct ast_string_expression *)decay->operand);
	assert(unit->strings->object_id == 0 && !unit->strings->next_string);
	assert(locals[3]->initializer->kind == expression_load);
	load = (struct ast_load_expression *)locals[3]->initializer;
	assert(load->operand->kind == expression_name);
	assert(((struct ast_name_expression *)load->operand)->declaration == locals[2]);
	assert(locals[2]->type == locals[3]->type);
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	fclose(stream);
}

static void test_inferred_typedef_shadowing_tree(void)
{
	const char *texts[] = {
		"typedef long T; int f(void) { T old=40,*p=&old; auto T=2; typeof(T) copy=T; return *p+copy; }",
		"typedef long T; int f(void) { T old=40,*p=&old; auto ((T))=2; typeof(T) copy=T; return *p+copy; }",
		"typedef long T; int f(void) { T old=40,*p=&old; register auto T=2; typeof(T) copy=T; return *p+copy; }",
	};

	for (size_t form = 0; form < sizeof(texts) / sizeof(texts[0]); form++) {
		struct source source;
		struct arena arena = { 0 };
		FILE *stream = tmpfile();
		struct diagnostics diagnostics = { .stream = stream };
		struct preprocessor preprocessor;
		struct ast_translation_unit *unit;
		struct ast_function *function;
		struct ast_typedef_declaration *alias;
		struct ast_local_declaration *locals[4];
		struct ast_block_item *item;
		struct ast_typeof_expression_syntax *query;
		struct ast_load_expression *load;
		struct ast_address_expression *address;

		assert(stream);
		assert(source_from_bytes(&source, "test.c", (const unsigned char *)texts[form], strlen(texts[form])));
		assert(source_prepare(&source));
		preprocess_init(&preprocessor, &source, &diagnostics);
		unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
		assert(unit && !diagnostics.errors);
		alias = ((struct ast_external_typedef_declaration *)unit->declarations)->declaration;
		function = (struct ast_function *)unit->declarations->next;
		assert(function->external.kind == external_function_definition);
		item = function->body->items;
		for (size_t i = 0; i < 4; i++) {
			assert(item && item->kind == block_item_declaration);
			locals[i] = (struct ast_local_declaration *)item;
			item = item->next;
		}
		assert(locals[0]->type_syntax->kind == type_syntax_typedef_name);
		assert(((struct ast_pointer_type_syntax *)locals[1]->type_syntax)->referent == locals[0]->type_syntax);
		assert(locals[2]->type_syntax->kind == type_syntax_inferred);
		assert(locals[2]->is_register == (form == 2));
		assert(sema_translation_unit(unit, &arena, &diagnostics) && !diagnostics.errors);
		for (size_t i = 0; i < 4; i++) {
			assert(locals[i]->slot == i && locals[i]->type);
			assert(locals[i]->next_local == (i ? locals[i - 1] : NULL));
		}
		assert(function->locals == locals[3]);
		assert(type_compatible(alias->type, &type_long) && locals[0]->type == alias->type);
		assert(type_compatible(locals[2]->type, &type_int));
		assert(locals[2]->type != alias->type && locals[2]->type_syntax->type == locals[2]->type);
		address = (struct ast_address_expression *)locals[1]->initializer;
		assert(address->expression.kind == expression_address && address->operand->kind == expression_name);
		assert(((struct ast_name_expression *)address->operand)->declaration == locals[0]);
		query = (struct ast_typeof_expression_syntax *)locals[3]->type_syntax;
		assert(query->syntax.kind == type_syntax_typeof_expression && query->operand->kind == expression_name);
		assert(((struct ast_name_expression *)query->operand)->declaration == locals[2]);
		load = (struct ast_load_expression *)locals[3]->initializer;
		assert(load->expression.kind == expression_load && load->operand->kind == expression_name);
		assert(((struct ast_name_expression *)load->operand)->declaration == locals[2]);
		assert(!locals[3]->is_register && locals[3]->type == locals[2]->type);
		assert(!unit->strings);
		arena_destroy(&arena);
		preprocess_destroy(&preprocessor);
		source_destroy(&source);
		fclose(stream);
	}
}

static void test_inferred_typedef_unavailable_tree(void)
{
	const char *texts[] = {
		"typedef long T; int f(void) { auto T=sizeof(T); return 0; }",
		"typedef long T; int f(void) { auto ((T))=sizeof(T); return 0; }",
	};

	for (size_t form = 0; form < sizeof(texts) / sizeof(texts[0]); form++) {
		struct source source;
		struct arena arena = { 0 };
		FILE *stream = tmpfile();
		struct diagnostics diagnostics = { .stream = stream };
		struct preprocessor preprocessor;
		struct ast_translation_unit *unit;
		struct ast_function *function;
		struct ast_typedef_declaration *alias;
		struct ast_local_declaration *local;
		struct ast_sizeof_expression *size;

		assert(stream);
		assert(source_from_bytes(&source, "test.c", (const unsigned char *)texts[form], strlen(texts[form])));
		assert(source_prepare(&source));
		preprocess_init(&preprocessor, &source, &diagnostics);
		unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
		assert(unit && !diagnostics.errors);
		alias = ((struct ast_external_typedef_declaration *)unit->declarations)->declaration;
		function = (struct ast_function *)unit->declarations->next;
		local = (struct ast_local_declaration *)function->body->items;
		assert(!sema_translation_unit(unit, &arena, &diagnostics) && diagnostics.errors == 1);
		assert(type_compatible(alias->type, &type_long));
		assert(local->type_syntax->kind == type_syntax_inferred && !local->type && !local->type_syntax->type);
		assert(!function->locals);
		size = (struct ast_sizeof_expression *)local->initializer;
		assert(size->expression.kind == expression_sizeof && size->operand->kind == expression_name);
		assert(((struct ast_name_expression *)size->operand)->declaration == local);
		arena_destroy(&arena);
		preprocess_destroy(&preprocessor);
		source_destroy(&source);
		fclose(stream);
	}
}

int main(void)
{
	test_inferred_typedef_shadowing_tree();
	test_inferred_typedef_unavailable_tree();
	test_register_auto_inference_tree();
	test_auto_inference_tree();
	test_auto_inference_unavailable_tree();
	test_local_binding_phases_tree();
	test_explicit_auto_tree();
	test_register_array_tree();
	test_register_scalar_tree();
	test_typedef_specifier_placement_tree();
	test_parameter_typedef_shadowing_tree();
	test_object_typedef_shadowing_tree();
	test_typedef_object_shadowing_tree();
	test_typedef_function_shadowing_tree();
	test_typedef_shadowing_tree();
	test_for_typedef_tree();
	test_block_typedef_tree();
	test_typedef_declaration_list_tree();
	test_typedef_redeclaration_tree();
	test_typedef_tree();
	test_queried_function_declaration_tree();
	test_nullptr_assignment_conversion_tree();
	test_void_parameter_query_tree();
	test_typeof_expression_tree();
	test_typeof_type_tree();
	test_switch_case_tree();
	test_switch_foundation_tree();
	test_goto_tree();
	test_named_label_tree();
	test_integer_compound_tree();
	test_compound_assignment_tree();
	test_postfix_update_tree();
	test_prefix_update_tree();
	test_nullptr_tree();
	test_null_boolean_tree();
	test_null_constant_tree();
	test_constant_bound_tree();
	test_static_assertion_tree();
	test_sizeof_alignment_tree();
	test_conditional_expression_tree();
	test_conditional_integer_types();
	test_boolean_constant_tree();
	test_const_qualification_tree();
	test_comma_expression_tree();
	test_explicit_pointer_cast_tree();
	test_object_void_conversion_tree();
	test_void_type_and_effect_tree();
	test_function_pointer_expression_tree();
	test_function_declarator_syntax_tree();
	test_unnamed_definition_parameter_tree();
	test_local_declaration_list_tree();
	test_incomplete_object_pointer_composite();
	test_parenthesized_object_declarators();
	test_incomplete_array_parameter();
	test_array_parameter_adjustment();
	test_concatenated_string_tree();
	test_string_expression_tree();
	test_multidimensional_array_tree();
	test_local_array_tree();
	test_pointer_subscript_tree();
	test_pointer_arithmetic_tree();
	test_pointer_equality_tree();
	test_pointer_lvalue_tree();
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
