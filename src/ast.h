#ifndef KCC_AST_H
#define KCC_AST_H

#include "arena.h"
#include "lex.h"

struct type;

enum expression_kind {
	expression_integer,
};

struct ast_expression {
	enum expression_kind kind;
	struct source_location location;
	const struct type *type;
};

struct ast_integer_expression {
	struct ast_expression expression;
	uint64_t value;
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
