#include "parse.h"
#include "sema.h"
#include "type.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void test_resolved_tree(void)
{
	const char *text = "int main(void) { int x=1; int y=x; x=y=7; return x; }";
	struct source source;
	struct arena arena = { 0 };
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { stream, 0 };
	struct lexer lexer;
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
	lexer_init(&lexer, &source, &diagnostics);
	unit = parse_translation_unit(&lexer, &arena, &diagnostics);
	assert(unit && diagnostics.errors == 0);
	assert(sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);

	x = (struct ast_local_declaration *)unit->function->body->items;
	y = (struct ast_local_declaration *)x->item.next;
	assert(x->item.kind == block_item_declaration);
	assert(y->item.kind == block_item_declaration);
	assert(x->type == &type_int && y->type == &type_int);
	assert(x->slot == 0 && y->slot == 1);
	assert(unit->function->locals == y && y->next_local == x);
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
	struct lexer lexer;
	struct ast_translation_unit *unit;
	struct ast_local_declaration *local;
	struct ast_load_expression *load;

	assert(stream);
	assert(source_from_bytes(&source, "test.c",
		(const unsigned char *)text, strlen(text)));
	lexer_init(&lexer, &source, &diagnostics);
	unit = parse_translation_unit(&lexer, &arena, &diagnostics);
	assert(unit && sema_translation_unit(unit, &arena, &diagnostics));
	assert(diagnostics.errors == 0);
	local = (struct ast_local_declaration *)unit->function->body->items;
	assert(local->initializer->kind == expression_load);
	load = (struct ast_load_expression *)local->initializer;
	assert(((struct ast_name_expression *)load->operand)->declaration == local);
	arena_destroy(&arena);
	source_destroy(&source);
	assert(fclose(stream) == 0);
}

int main(void)
{
	test_resolved_tree();
	test_point_of_declaration();
	puts("Semantic AST tests passed");
	return 0;
}
