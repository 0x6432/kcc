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
	struct diagnostics diagnostics = { stream, 0 };
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
	struct diagnostics diagnostics = { stream, 0 };
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
	struct diagnostics diagnostics = { stream, 0 };
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
	struct diagnostics diagnostics = { stream, 0 };
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
	struct diagnostics diagnostics = { stream, 0 };
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
	struct diagnostics diagnostics = { stream, 0 };
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
	one = type_new_int_function(&arena, 1);
	another_one = type_new_int_function(&arena, 1);
	zero = type_new_int_function(&arena, 0);
	assert(one && another_one && zero);
	assert(type_compatible(&one->type, &another_one->type));
	assert(!type_compatible(&one->type, &zero->type));
	assert(!type_compatible(&one->type, &type_int));
	arena_destroy(&arena);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

int main(void)
{
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
