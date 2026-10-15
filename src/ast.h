#ifndef KCC_AST_H
#define KCC_AST_H

#include "arena.h"
#include "lex.h"

struct type;
struct ast_local_declaration;
struct function_symbol;

enum expression_kind {
	expression_integer,
	expression_character,
	expression_name,
	expression_unary,
	expression_binary,
	expression_assignment,
	expression_load,
	expression_conversion,
	expression_cast,
	expression_logical,
	expression_call,
};

enum {
	ast_max_expression_depth = 128,
	ast_max_statement_nesting = 128,
	ast_max_block_items = 4096,
	ast_max_locals = 256,
	ast_max_external_declarations = 512,
	ast_max_functions = 256,
	ast_max_parameters = 128,
	ast_max_arguments = 128,
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
	unsigned base;
	unsigned long_suffix;
	bool unsigned_suffix;
};

struct ast_character_expression {
	struct ast_expression expression;
	int64_t value;
};

struct ast_name_expression {
	struct ast_expression expression;
	struct token name;
	struct ast_local_declaration *declaration;
};

struct ast_argument {
	struct ast_expression *value;
	struct ast_argument *next;
};

struct ast_call_expression {
	struct ast_expression expression;
	struct ast_expression *callee;
	struct ast_argument *arguments;
	size_t argument_count;
	struct function_symbol *function;
};

enum unary_operator {
	unary_plus,
	unary_minus,
	unary_not,
	unary_complement,
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
	binary_bit_and,
	binary_bit_xor,
	binary_bit_or,
	binary_shift_left,
	binary_shift_right,
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

enum logical_operator {
	logical_and,
	logical_or,
};

struct ast_logical_expression {
	struct ast_expression expression;
	enum logical_operator operation;
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

/* Inserted by sema for arithmetic/assignment/call/return conversion contexts. */
struct ast_conversion_expression {
	struct ast_expression expression;
	struct ast_expression *operand;
};

enum integer_specifier {
	integer_specifier_char,
	integer_specifier_signed_char,
	integer_specifier_unsigned_char,
	integer_specifier_short,
	integer_specifier_unsigned_short,
	integer_specifier_int,
	integer_specifier_unsigned,
	integer_specifier_long,
	integer_specifier_unsigned_long,
	integer_specifier_long_long,
	integer_specifier_unsigned_long_long,
	integer_specifier_bool,
};

struct ast_cast_expression {
	struct ast_expression expression;
	enum integer_specifier specifier;
	struct ast_expression *operand;
};

enum statement_kind {
	statement_return,
	statement_expression,
	statement_empty,
	statement_compound,
	statement_if,
	statement_while,
	statement_do,
	statement_for,
	statement_break,
	statement_continue,
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

struct ast_while_statement {
	struct ast_statement statement;
	struct ast_expression *condition;
	struct ast_statement *body;
};

struct ast_do_statement {
	struct ast_statement statement;
	struct ast_statement *body;
	struct ast_expression *condition;
};

struct ast_for_statement {
	struct ast_statement statement;
	struct ast_local_declaration *initializer_declaration;
	struct ast_expression *initializer_expression;
	struct ast_expression *condition;
	struct ast_expression *step;
	struct ast_statement *body;
};

struct ast_break_statement {
	struct ast_statement statement;
	struct ast_statement *target;
};

struct ast_continue_statement {
	struct ast_statement statement;
	struct ast_statement *target;
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
	enum integer_specifier specifier;
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

enum external_declaration_kind {
	external_function_declaration,
	external_function_definition,
};

struct ast_external_declaration {
	enum external_declaration_kind kind;
	struct source_location location;
	struct ast_external_declaration *next;
};

struct ast_parameter {
	enum integer_specifier specifier;
	struct source_location location;
	struct token name;
	bool has_name;
	struct ast_local_declaration *local;
	struct ast_parameter *next;
};

struct ast_function_declaration {
	struct ast_external_declaration external;
	enum integer_specifier return_specifier;
	struct token name;
	struct function_symbol *symbol;
	struct ast_parameter *parameters;
	size_t parameter_count;
};

struct ast_function {
	struct ast_external_declaration external;
	struct ast_function_declaration *declaration;
	const struct type *return_type;
	struct ast_compound_statement *body;
	struct ast_local_declaration *locals;
};

struct ast_translation_unit {
	struct ast_external_declaration *declarations;
};

struct ast_call_expression *ast_new_call(struct arena *arena,
	struct ast_expression *callee, struct ast_argument *arguments, size_t argument_count);
struct ast_argument *ast_new_argument(struct arena *arena, struct ast_expression *value);
struct ast_parameter *ast_new_parameter(struct arena *arena,
	struct source_location location, struct token name, bool has_name);
struct ast_function_declaration *ast_new_function_declaration(struct arena *arena,
	struct source_location location, struct token name);
struct ast_integer_expression *ast_new_integer(struct arena *arena,
	struct token token);
struct ast_character_expression *ast_new_character(struct arena *arena,
	struct token token);
struct ast_name_expression *ast_new_name(struct arena *arena, struct token name);
struct ast_unary_expression *ast_new_unary(struct arena *arena,
	struct source_location location, enum unary_operator operation,
	struct ast_expression *operand);
struct ast_binary_expression *ast_new_binary(struct arena *arena,
	struct source_location location, enum binary_operator operation,
	struct ast_expression *left, struct ast_expression *right);
struct ast_logical_expression *ast_new_logical(struct arena *arena,
	struct source_location location, enum logical_operator operation,
	struct ast_expression *left, struct ast_expression *right);
struct ast_assignment_expression *ast_new_assignment(struct arena *arena,
	struct source_location location, struct ast_expression *left,
	struct ast_expression *right);
struct ast_load_expression *ast_new_load(struct arena *arena,
	struct ast_expression *operand);
struct ast_cast_expression *ast_new_cast(struct arena *arena,
	struct source_location location, enum integer_specifier specifier,
	struct ast_expression *operand);
struct ast_conversion_expression *ast_new_conversion(struct arena *arena,
	struct ast_expression *operand, const struct type *target);
struct ast_return_statement *ast_new_return(struct arena *arena,
	struct source_location location, struct ast_expression *value);
struct ast_expression_statement *ast_new_expression_statement(struct arena *arena,
	struct source_location location, struct ast_expression *value);
struct ast_empty_statement *ast_new_empty_statement(struct arena *arena,
	struct source_location location);
struct ast_if_statement *ast_new_if(struct arena *arena,
	struct source_location location, struct ast_expression *condition,
	struct ast_statement *then_branch, struct ast_statement *else_branch);
struct ast_while_statement *ast_new_while(struct arena *arena,
	struct source_location location, struct ast_expression *condition,
	struct ast_statement *body);
struct ast_do_statement *ast_new_do(struct arena *arena,
	struct source_location location, struct ast_statement *body,
	struct ast_expression *condition);
struct ast_for_statement *ast_new_for(struct arena *arena,
	struct source_location location,
	struct ast_local_declaration *initializer_declaration,
	struct ast_expression *initializer_expression, struct ast_expression *condition,
	struct ast_expression *step, struct ast_statement *body);
struct ast_break_statement *ast_new_break(struct arena *arena,
	struct source_location location);
struct ast_continue_statement *ast_new_continue(struct arena *arena,
	struct source_location location);
struct ast_local_declaration *ast_new_local(struct arena *arena,
	struct source_location location, struct token name,
	struct ast_expression *initializer);
struct ast_statement_item *ast_new_statement_item(struct arena *arena,
	struct ast_statement *statement);
struct ast_compound_statement *ast_new_compound(struct arena *arena,
	struct source_location location, struct ast_block_item *items);
struct ast_function *ast_new_function(struct arena *arena,
	struct ast_function_declaration *declaration, struct ast_compound_statement *body);
struct ast_translation_unit *ast_new_translation_unit(struct arena *arena,
	struct ast_external_declaration *declarations);

#endif
