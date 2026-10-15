#ifndef KCC_AST_H
#define KCC_AST_H

#include "arena.h"
#include "lex.h"

struct type;
struct ast_local_declaration;

enum expression_kind {
	expression_integer,
	expression_name,
	expression_unary,
	expression_binary,
	expression_assignment,
	expression_load,
};

enum {
	ast_max_expression_depth = 128,
	ast_max_statement_nesting = 128,
	ast_max_block_items = 4096,
	ast_max_locals = 256,
};

struct ast_expression {
	enum expression_kind kind;
	struct source_location location;
	const struct type *type;
	unsigned depth;
	bool is_lvalue;
};

struct ast_integer_expression {
	struct ast_expression expression;
	uint64_t value;
};

struct ast_name_expression {
	struct ast_expression expression;
	struct token name;
	struct ast_local_declaration *declaration;
};

enum unary_operator {
	unary_plus,
	unary_minus,
};

struct ast_unary_expression {
	struct ast_expression expression;
	enum unary_operator operation;
	struct ast_expression *operand;
};

enum binary_operator {
	binary_add,
	binary_subtract,
	binary_multiply,
	binary_divide,
	binary_remainder,
	binary_equal,
	binary_not_equal,
	binary_less,
	binary_less_equal,
	binary_greater,
	binary_greater_equal,
};

struct ast_binary_expression {
	struct ast_expression expression;
	enum binary_operator operation;
	struct ast_expression *left;
	struct ast_expression *right;
};

struct ast_assignment_expression {
	struct ast_expression expression;
	struct ast_expression *left;
	struct ast_expression *right;
};

/* Inserted by sema, never by the parser. Operand denotes a local object. */
struct ast_load_expression {
	struct ast_expression expression;
	struct ast_expression *operand;
};

enum statement_kind {
	statement_return,
	statement_expression,
	statement_empty,
	statement_compound,
	statement_if,
};

struct ast_statement {
	enum statement_kind kind;
	struct source_location location;
};

struct ast_return_statement {
	struct ast_statement statement;
	struct ast_expression *value;
};

struct ast_expression_statement {
	struct ast_statement statement;
	struct ast_expression *value;
};

struct ast_empty_statement {
	struct ast_statement statement;
};

struct ast_if_statement {
	struct ast_statement statement;
	struct ast_expression *condition;
	struct ast_statement *then_branch;
	struct ast_statement *else_branch;
};

enum block_item_kind {
	block_item_declaration,
	block_item_statement,
};

struct ast_block_item {
	enum block_item_kind kind;
	struct source_location location;
	struct ast_block_item *next;
};

struct ast_local_declaration {
	struct ast_block_item item;
	struct token name;
	struct ast_expression *initializer;
	const struct type *type;
	size_t slot;
	struct ast_local_declaration *next_local;
};

struct ast_statement_item {
	struct ast_block_item item;
	struct ast_statement *statement;
};

struct ast_compound_statement {
	struct ast_statement statement;
	struct ast_block_item *items;
};

struct ast_function {
	struct source_location location;
	struct token name;
	const struct type *return_type;
	struct ast_compound_statement *body;
	struct ast_local_declaration *locals;
};

struct ast_translation_unit {
	struct ast_function *function;
};

struct ast_integer_expression *ast_new_integer(struct arena *arena,
	struct token token);
struct ast_name_expression *ast_new_name(struct arena *arena, struct token name);
struct ast_unary_expression *ast_new_unary(struct arena *arena,
	struct source_location location, enum unary_operator operation,
	struct ast_expression *operand);
struct ast_binary_expression *ast_new_binary(struct arena *arena,
	struct source_location location, enum binary_operator operation,
	struct ast_expression *left, struct ast_expression *right);
struct ast_assignment_expression *ast_new_assignment(struct arena *arena,
	struct source_location location, struct ast_expression *left,
	struct ast_expression *right);
struct ast_load_expression *ast_new_load(struct arena *arena,
	struct ast_expression *operand);
struct ast_return_statement *ast_new_return(struct arena *arena,
	struct source_location location, struct ast_expression *value);
struct ast_expression_statement *ast_new_expression_statement(struct arena *arena,
	struct source_location location, struct ast_expression *value);
struct ast_empty_statement *ast_new_empty_statement(struct arena *arena,
	struct source_location location);
struct ast_if_statement *ast_new_if(struct arena *arena,
	struct source_location location, struct ast_expression *condition,
	struct ast_statement *then_branch, struct ast_statement *else_branch);
struct ast_local_declaration *ast_new_local(struct arena *arena,
	struct source_location location, struct token name,
	struct ast_expression *initializer);
struct ast_statement_item *ast_new_statement_item(struct arena *arena,
	struct ast_statement *statement);
struct ast_compound_statement *ast_new_compound(struct arena *arena,
	struct source_location location, struct ast_block_item *items);
struct ast_function *ast_new_function(struct arena *arena,
	struct source_location location, struct token name,
	struct ast_compound_statement *body);
struct ast_translation_unit *ast_new_translation_unit(struct arena *arena,
	struct ast_function *function);

#endif
