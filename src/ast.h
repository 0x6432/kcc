#ifndef KCC_AST_H
#define KCC_AST_H

#include "arena.h"
#include "lex.h"

struct type;

enum expression_kind {
	expression_integer,
	expression_unary,
	expression_binary,
};

enum { ast_max_expression_depth = 128 };

struct ast_expression {
	enum expression_kind kind;
	struct source_location location;
	const struct type *type;
	unsigned depth;
};

struct ast_integer_expression {
	struct ast_expression expression;
	uint64_t value;
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
};

struct ast_binary_expression {
	struct ast_expression expression;
	enum binary_operator operation;
	struct ast_expression *left;
	struct ast_expression *right;
};

enum statement_kind {
	statement_return,
	statement_compound,
};

struct ast_statement {
	enum statement_kind kind;
	struct source_location location;
};

struct ast_return_statement {
	struct ast_statement statement;
	struct ast_expression *value;
};

struct ast_compound_statement {
	struct ast_statement statement;
	struct ast_statement *body;
};

struct ast_function {
	struct source_location location;
	struct token name;
	const struct type *return_type;
	struct ast_compound_statement *body;
};

struct ast_translation_unit {
	struct ast_function *function;
};

struct ast_integer_expression *ast_new_integer(struct arena *arena,
	struct token token);
struct ast_unary_expression *ast_new_unary(struct arena *arena,
	struct source_location location, enum unary_operator operation,
	struct ast_expression *operand);
struct ast_binary_expression *ast_new_binary(struct arena *arena,
	struct source_location location, enum binary_operator operation,
	struct ast_expression *left, struct ast_expression *right);
struct ast_return_statement *ast_new_return(struct arena *arena,
	struct source_location location, struct ast_expression *value);
struct ast_compound_statement *ast_new_compound(struct arena *arena,
	struct source_location location, struct ast_statement *body);
struct ast_function *ast_new_function(struct arena *arena,
	struct source_location location, struct token name,
	struct ast_compound_statement *body);
struct ast_translation_unit *ast_new_translation_unit(struct arena *arena,
	struct ast_function *function);

#endif
