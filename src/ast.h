#ifndef KCC_AST_H
#define KCC_AST_H

#include "arena.h"
#include "lex.h"

struct type;
struct ast_local_declaration;
struct function_symbol;
struct external_object_symbol;

enum expression_kind {
	expression_integer,
	expression_boolean,
	expression_nullptr,
	expression_character,
	expression_string,
	expression_address,
	expression_indirection,
	expression_subscript,
	expression_name,
	expression_function_designator,
	expression_external_object,
	expression_function_decay,
	expression_postfix_update,
	expression_prefix_update,
	expression_unary,
	expression_binary,
	expression_pointer_offset,
	expression_pointer_difference,
	expression_assignment,
	expression_compound_assignment,
	expression_load,
	expression_array_decay,
	expression_conversion,
	expression_cast,
	expression_logical,
	expression_comma,
	expression_conditional,
	expression_sizeof,
	expression_sizeof_type,
	expression_alignof,
	expression_call,
	expression_member,
};

enum {
	ast_max_record_nesting = 64,
	ast_max_record_temporaries = 256,
	ast_max_record_members = 1024,
	ast_max_record_declarations = 4096,
	ast_max_expression_depth = 128,
	ast_max_statement_nesting = 128,
	ast_max_type_queries = 64,
	ast_max_labels = 512,
	ast_max_switch_labels = 1024,
	ast_max_function_switch_labels = 4096,
	ast_max_gotos = 4096,
	ast_max_block_items = 4096,
	ast_max_locals = 256,
	ast_max_local_storage = 1024 * 1024,
	ast_max_external_declarations = 512,
	ast_max_functions = 256,
	ast_max_external_objects = 256,
	ast_max_parameters = 128,
	ast_max_arguments = 128,
	ast_max_pointer_depth = 64,
	ast_max_array_dimensions = 64,
	ast_max_declarator_nesting = 64,
	ast_max_function_layers = 64,
	ast_max_string_length = 1024 * 1024,
	ast_max_string_storage = 8 * 1024 * 1024,
	ast_max_string_literals = 4096,
	ast_max_string_fragments = 4096,
	ast_max_total_string_fragments = 16384,
};

struct ast_expression {
	enum expression_kind kind;
	struct source_location location;
	const struct type *type;
	unsigned depth;
	bool is_lvalue;
};

struct ast_sizeof_expression {
	struct ast_expression expression;
	struct ast_expression *operand;
	uint64_t size;
};

struct ast_sizeof_type_expression {
	struct ast_expression expression;
	struct ast_type_syntax *type_syntax;
	uint64_t size;
};

struct ast_alignof_expression {
	struct ast_expression expression;
	struct ast_type_syntax *type_syntax;
	uint64_t alignment;
};

struct ast_nullptr_expression {
	struct ast_expression expression;
};

struct ast_boolean_expression {
	struct ast_expression expression;
	bool value;
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

struct ast_string_expression {
	struct ast_expression expression;
	const unsigned char *bytes;
	size_t length;
	size_t object_id;
	struct ast_string_expression *next_string;
};

struct ast_address_expression {
	struct ast_expression expression;
	struct ast_expression *operand;
};

struct ast_indirection_expression {
	struct ast_expression expression;
	struct ast_expression *operand;
};

struct ast_subscript_expression {
	struct ast_expression expression;
	struct ast_expression *left;
	struct ast_expression *right;
};

struct ast_name_expression {
	struct ast_expression expression;
	struct token name;
	struct ast_local_declaration *declaration;
};

struct ast_external_object_expression {
	struct ast_expression expression;
	struct external_object_symbol *object;
};

struct ast_function_designator_expression {
	struct ast_expression expression;
	struct function_symbol *function;
};

struct ast_function_decay_expression {
	struct ast_expression expression;
	struct ast_expression *operand;
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
	struct function_symbol *function; /* Non-NULL only for a pure direct target. */
	const struct function_type *signature;
};

enum update_operator {
	update_increment,
	update_decrement,
};

struct ast_postfix_update_expression {
	struct ast_expression expression;
	enum update_operator operation;
	struct ast_expression *operand;
	const struct type *calculation_type;
	uint64_t element_size; /* Zero for integers; checked stride for pointers. */
};

struct ast_prefix_update_expression {
	struct ast_expression expression;
	enum update_operator operation;
	struct ast_expression *operand;
	const struct type *calculation_type;
	uint64_t element_size; /* Zero for integers; checked stride for pointers. */
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

struct ast_conditional_expression {
	struct ast_expression expression;
	struct ast_expression *condition;
	struct ast_expression *then_value;
	struct ast_expression *else_value;
};

struct ast_comma_expression {
	struct ast_expression expression;
	struct ast_expression *left;
	struct ast_expression *right;
};

struct ast_binary_expression {
	struct ast_expression expression;
	enum binary_operator operation;
	struct ast_expression *left;
	struct ast_expression *right;
};

/* Inserted by sema after operand analysis; never parsed directly. */
struct ast_pointer_offset_expression {
	struct ast_expression expression;
	struct ast_expression *base;
	struct ast_expression *index;
	uint64_t element_size;
	bool subtract;
};

struct ast_pointer_difference_expression {
	struct ast_expression expression;
	struct ast_expression *left;
	struct ast_expression *right;
	uint64_t element_size;
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

/* The left remains one lvalue, not an expression duplicated into an assignment.
 * Sema records promoted arithmetic or a complete-pointer stride (zero for ints).
 */
struct ast_compound_assignment_expression {
	struct ast_expression expression;
	enum binary_operator operation;
	struct ast_expression *left;
	struct ast_expression *right;
	const struct type *calculation_type;
	uint64_t element_size;
};

/* Inserted by sema, never by the parser. Operand denotes an object lvalue. */
struct ast_load_expression {
	struct ast_expression expression;
	struct ast_expression *operand;
	size_t record_temporary_slot;
	struct ast_load_expression *next_record_temporary;
};

/* Inserted by sema in ordinary array value contexts, never an array load. */
struct ast_array_decay_expression {
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

enum type_syntax_kind {
	type_syntax_inferred,
	type_syntax_typedef_name,
	type_syntax_void,
	type_syntax_qualified,
	type_syntax_typeof_type,
	type_syntax_typeof_expression,
	type_syntax_integer,
	type_syntax_pointer,
	type_syntax_array,
	type_syntax_function,
	type_syntax_record,
};

struct ast_type_syntax {
	enum type_syntax_kind kind;
	struct source_location location;
	const struct type *type;
};

/* Syntax only: tags belong to sema's separate namespace, never parser aliases. */
struct ast_record_type_syntax {
	struct ast_type_syntax syntax;
	struct token tag;
	bool is_union;
	bool has_definition;
	struct ast_record_member_declaration *members;
	size_t member_declaration_count;
};

struct ast_record_member_declaration {
	struct ast_type_syntax *type_syntax;
	struct token name;
	bool anonymous;
	struct ast_record_member_declaration *next;
	struct ast_static_assertion *static_assertion;
};

struct ast_member_expression {
	struct ast_expression expression;
	struct ast_expression *operand;
	struct token name;
	bool indirect;
	uint64_t offset;
	const struct record_member *member;
};

struct ast_tag_declaration {
	struct ast_type_syntax *type_syntax;
	struct source_location location;
};

struct ast_typedef_name_type_syntax {
	struct ast_type_syntax syntax;
	struct token name;
};

struct ast_inferred_type_syntax {
	struct ast_type_syntax syntax;
	unsigned qualifiers;
};

struct ast_qualified_type_syntax {
	struct ast_type_syntax syntax;
	struct ast_type_syntax *base;
	unsigned qualifiers;
};

struct ast_typeof_type_syntax {
	struct ast_type_syntax syntax;
	struct ast_type_syntax *operand;
	bool unqualify;
};

struct ast_typeof_expression_syntax {
	struct ast_type_syntax syntax;
	struct ast_expression *operand;
	bool unqualify;
};

struct ast_void_type_syntax {
	struct ast_type_syntax syntax;
};

struct ast_integer_type_syntax {
	struct ast_type_syntax syntax;
	enum integer_specifier specifier;
};

struct ast_pointer_type_syntax {
	struct ast_type_syntax syntax;
	struct ast_type_syntax *referent;
};

struct ast_array_type_syntax {
	struct ast_type_syntax syntax;
	struct ast_type_syntax *element;
	struct ast_expression *bound; /* NULL is an unspecified bound, never zero. */
};

struct ast_function_type_syntax {
	struct ast_type_syntax syntax;
	struct ast_type_syntax *return_syntax;
	struct ast_parameter *parameters;
	size_t parameter_count; /* Written nodes, not the resolved ABI count. */
};

struct ast_cast_expression {
	struct ast_expression expression;
	struct ast_type_syntax *type_syntax;
	struct ast_expression *operand;
};

enum statement_kind {
	statement_labeled,
	statement_goto,
	statement_return,
	statement_expression,
	statement_empty,
	statement_compound,
	statement_if,
	statement_case,
	statement_default,
	statement_switch,
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

/* Labels use the function's separate label namespace, never an object type. */
struct ast_label {
	struct token name;
	size_t index;
};

struct ast_goto_statement {
	struct ast_statement statement;
	struct token name;
	struct ast_label *target;
};

struct ast_labeled_statement {
	struct ast_statement statement;
	struct ast_label *label;
	struct ast_statement *body;
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

struct ast_case_label {
	struct source_location location;
	struct ast_expression *value;
	uint64_t bits;
	size_t index;
	struct ast_switch_statement *owner;
	struct ast_case_label *next;
};

struct ast_default_label {
	struct source_location location;
	size_t index;
	struct ast_switch_statement *owner;
};

struct ast_case_statement {
	struct ast_statement statement;
	struct ast_case_label *label;
	struct ast_statement *body;
};

struct ast_default_statement {
	struct ast_statement statement;
	struct ast_default_label *label;
	struct ast_statement *body;
};

struct ast_switch_statement {
	struct ast_statement statement;
	struct ast_expression *control;
	struct ast_statement *body;
	struct ast_case_label *cases;
	struct ast_default_label *default_label;
	size_t label_count;
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
	struct ast_block_item *initializer_declarations;
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

struct ast_static_assertion {
	struct source_location location;
	struct ast_expression *condition;
	struct ast_string_expression *message;
};

enum block_item_kind {
	block_item_case,
	block_item_default,
	block_item_label,
	block_item_declaration,
	block_item_statement,
	block_item_static_assertion,
	block_item_typedef_declaration,
	block_item_tag_declaration,
};

struct ast_block_item {
	enum block_item_kind kind;
	struct source_location location;
	struct ast_block_item *next;
};

/* C23 block labels stand alone, also before declarations or at block end. */
struct ast_block_case {
	struct ast_block_item item;
	struct ast_case_label *label;
};

struct ast_block_default {
	struct ast_block_item item;
	struct ast_default_label *label;
};

struct ast_block_label {
	struct ast_block_item item;
	struct ast_label *label;
};

struct ast_block_static_assertion {
	struct ast_block_item item;
	struct ast_static_assertion *declaration;
};

struct ast_block_typedef_declaration {
	struct ast_block_item item;
	struct ast_typedef_declaration *declaration;
};

struct ast_block_tag_declaration {
	struct ast_block_item item;
	struct ast_tag_declaration *declaration;
};

struct ast_local_declaration {
	struct ast_block_item item;
	struct ast_type_syntax *type_syntax;
	struct token name;
	struct ast_expression *initializer;
	bool is_register;
	bool is_auto; /* Written auto; explicit auto still requires an object. */
	bool is_extern;
	bool is_static;
	bool is_inline;
	bool is_thread_local;
	struct external_object_symbol *object_symbol;
	struct function_symbol *function_symbol;
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
	external_static_assertion,
	external_type_declaration,
	external_object_declaration,
	external_typedef_declaration,
	external_declaration_tag,
};

struct ast_external_declaration {
	enum external_declaration_kind kind;
	struct source_location location;
	struct ast_external_declaration *next;
};

struct ast_external_tag_declaration {
	struct ast_external_declaration external;
	struct ast_tag_declaration *declaration;
};

struct ast_typedef_declaration {
	struct source_location location;
	struct ast_type_syntax *type_syntax;
	struct token name;
	const struct type *type;
};

struct ast_external_typedef_declaration {
	struct ast_external_declaration external;
	struct ast_typedef_declaration *declaration;
};

struct ast_external_static_assertion {
	struct ast_external_declaration external;
	struct ast_static_assertion *declaration;
};

struct ast_external_object_declaration {
	struct ast_external_declaration external;
	bool is_extern;
	bool is_inline;
	bool is_thread_local;
	bool is_static; /* Written linkage, not part of the object type. */
	struct ast_type_syntax *type_syntax;
	struct token name;
	const struct type *type;
	struct external_object_symbol *symbol;
	struct ast_expression *initializer;
};

/* Written alias/query root; sema classifies the resolved function/object type. */
struct ast_external_type_declaration {
	struct ast_external_declaration external;
	bool is_extern;
	struct external_object_symbol *object_symbol;
	bool is_inline;
	bool is_thread_local;
	bool is_static; /* Written linkage, not part of the function type. */
	struct ast_type_syntax *type_syntax;
	struct token name;
	const struct type *type;
	struct function_symbol *symbol;
	struct ast_expression *initializer;
};

struct ast_parameter {
	struct ast_type_syntax *type_syntax;
	const struct type *type;
	struct source_location location;
	struct token name;
	bool has_name;
	bool is_register; /* Written storage, not part of the adjusted function type. */
	bool is_void_marker; /* Checked sole unnamed void, not an ABI parameter. */
	struct ast_local_declaration *local; /* NULL for prototypes and unnamed parameters. */
	struct ast_parameter *next;
};

struct ast_function_declaration {
	struct ast_external_declaration external;
	bool is_extern;
	bool is_inline;
	bool is_thread_local;
	bool is_static; /* Written linkage, not part of the function type. */
	struct ast_function_type_syntax *type_syntax;
	struct ast_type_syntax *return_syntax;
	struct token name;
	struct function_symbol *symbol;
	struct ast_parameter *parameters;
	size_t parameter_count; /* Written nodes, not the resolved ABI count. */
};

struct ast_function {
	struct ast_external_declaration external;
	bool inline_has_internal_reference;
	bool inline_has_modifiable_static;
	struct source_location inline_reference_location;
	struct source_location inline_static_location;
	struct ast_function_declaration *declaration;
	const struct type *return_type;
	struct ast_compound_statement *body;
	struct ast_local_declaration *locals;
	size_t label_count;
	size_t switch_label_count;
	struct ast_load_expression *record_temporaries;
	size_t record_temporary_count;
};

struct ast_translation_unit {
	/* Synthetic static-duration local definitions, emitted after source declarations. */
	struct ast_external_declaration *static_declarations;
	struct ast_external_declaration *declarations;
	struct ast_string_expression *strings;
};

struct ast_record_type_syntax *ast_new_record_type_syntax(struct arena *arena,
	struct token keyword, struct token tag);
struct ast_member_expression *ast_new_member(struct arena *arena,
	struct ast_expression *operand, struct token operation, struct token name);
struct ast_tag_declaration *ast_new_tag_declaration(struct arena *arena,
	struct ast_type_syntax *type_syntax, struct source_location location);
struct ast_block_tag_declaration *ast_new_block_tag_declaration(struct arena *arena,
	struct ast_tag_declaration *declaration);
struct ast_external_tag_declaration *ast_new_external_tag_declaration(struct arena *arena,
	struct ast_tag_declaration *declaration);

struct ast_static_assertion *ast_new_static_assertion(struct arena *arena,
	struct source_location location, struct ast_expression *condition,
	struct ast_string_expression *message);
struct ast_block_static_assertion *ast_new_block_static_assertion(struct arena *arena,
	struct ast_static_assertion *declaration);
struct ast_external_static_assertion *ast_new_external_static_assertion(struct arena *arena,
	struct ast_static_assertion *declaration);
struct ast_inferred_type_syntax *ast_new_inferred_type_syntax(struct arena *arena,
	struct source_location location, unsigned qualifiers);
struct ast_qualified_type_syntax *ast_new_qualified_type_syntax(struct arena *arena,
	struct source_location location, struct ast_type_syntax *base, unsigned qualifiers);
struct ast_typeof_type_syntax *ast_new_typeof_type_syntax(struct arena *arena,
	struct source_location location, struct ast_type_syntax *operand, bool unqualify);
struct ast_typeof_expression_syntax *ast_new_typeof_expression_syntax(struct arena *arena,
	struct source_location location, struct ast_expression *operand, bool unqualify);
struct ast_void_type_syntax *ast_new_void_type_syntax(struct arena *arena,
	struct source_location location);
struct ast_integer_type_syntax *ast_new_integer_type_syntax(struct arena *arena,
	struct source_location location, enum integer_specifier specifier);
struct ast_pointer_type_syntax *ast_new_pointer_type_syntax(struct arena *arena,
	struct source_location location, struct ast_type_syntax *referent);
struct ast_function_type_syntax *ast_new_function_type_syntax(struct arena *arena,
	struct source_location location, struct ast_type_syntax *return_syntax);
struct ast_array_type_syntax *ast_new_array_type_syntax(struct arena *arena,
	struct source_location location, struct ast_type_syntax *element, struct ast_expression *bound);
struct ast_external_object_expression *ast_new_external_object(struct arena *arena,
	struct source_location location, struct external_object_symbol *object);
struct ast_function_designator_expression *ast_new_function_designator(struct arena *arena,
	struct source_location location, struct function_symbol *function);
struct ast_function_decay_expression *ast_new_function_decay(struct arena *arena,
	struct ast_expression *operand, const struct type *pointer_type);
struct ast_array_decay_expression *ast_new_array_decay(struct arena *arena,
	struct ast_expression *operand, const struct type *pointer_type);
struct ast_call_expression *ast_new_call(struct arena *arena,
	struct ast_expression *callee, struct ast_argument *arguments, size_t argument_count);
struct ast_argument *ast_new_argument(struct arena *arena, struct ast_expression *value);
struct ast_parameter *ast_new_parameter(struct arena *arena,
	struct source_location location, struct token name, bool has_name);
struct ast_typedef_name_type_syntax *ast_new_typedef_name_type_syntax(struct arena *arena, struct token name);
struct ast_typedef_declaration *ast_new_typedef_declaration(struct arena *arena,
	struct source_location location, struct ast_type_syntax *type_syntax, struct token name);
struct ast_block_typedef_declaration *ast_new_block_typedef_declaration(struct arena *arena,
	struct ast_typedef_declaration *declaration);
struct ast_external_typedef_declaration *ast_new_external_typedef_declaration(struct arena *arena,
	struct ast_typedef_declaration *declaration);
struct ast_external_object_declaration *ast_new_external_object_declaration(struct arena *arena,
	struct source_location location, struct ast_type_syntax *type_syntax, struct token name, bool is_extern);
struct ast_external_type_declaration *ast_new_external_type_declaration(struct arena *arena,
	struct source_location location, struct ast_type_syntax *type_syntax, struct token name);
struct ast_function_declaration *ast_new_function_declaration(struct arena *arena,
	struct source_location location, struct token name);
struct ast_sizeof_expression *ast_new_sizeof(struct arena *arena,
	struct source_location location, struct ast_expression *operand);
struct ast_sizeof_type_expression *ast_new_sizeof_type(struct arena *arena,
	struct source_location location, struct ast_type_syntax *type_syntax);
struct ast_alignof_expression *ast_new_alignof(struct arena *arena,
	struct source_location location, struct ast_type_syntax *type_syntax);
struct ast_nullptr_expression *ast_new_nullptr(struct arena *arena, struct source_location location);
struct ast_boolean_expression *ast_new_boolean(struct arena *arena, struct token token);
struct ast_integer_expression *ast_new_integer(struct arena *arena,
	struct token token);
struct ast_character_expression *ast_new_character(struct arena *arena,
	struct token token);
struct ast_string_expression *ast_new_string(struct arena *arena,
	struct source_location location, const unsigned char *bytes, size_t length);
struct ast_address_expression *ast_new_address(struct arena *arena,
	struct source_location location, struct ast_expression *operand);
struct ast_indirection_expression *ast_new_indirection(struct arena *arena,
	struct source_location location, struct ast_expression *operand);
struct ast_subscript_expression *ast_new_subscript(struct arena *arena,
	struct source_location location, struct ast_expression *left,
	struct ast_expression *right);
struct ast_name_expression *ast_new_name(struct arena *arena, struct token name);
struct ast_postfix_update_expression *ast_new_postfix_update(struct arena *arena,
	struct source_location location, enum update_operator operation, struct ast_expression *operand);
struct ast_prefix_update_expression *ast_new_prefix_update(struct arena *arena,
	struct source_location location, enum update_operator operation, struct ast_expression *operand);
struct ast_unary_expression *ast_new_unary(struct arena *arena,
	struct source_location location, enum unary_operator operation,
	struct ast_expression *operand);
struct ast_conditional_expression *ast_new_conditional(struct arena *arena,
	struct source_location location, struct ast_expression *condition,
	struct ast_expression *then_value, struct ast_expression *else_value);
struct ast_comma_expression *ast_new_comma(struct arena *arena,
	struct source_location location, struct ast_expression *left, struct ast_expression *right);
struct ast_binary_expression *ast_new_binary(struct arena *arena,
	struct source_location location, enum binary_operator operation,
	struct ast_expression *left, struct ast_expression *right);
struct ast_pointer_offset_expression *ast_new_pointer_offset(struct arena *arena,
	struct source_location location, struct ast_expression *base,
	struct ast_expression *index, uint64_t element_size, bool subtract);
struct ast_pointer_difference_expression *ast_new_pointer_difference(struct arena *arena,
	struct source_location location, struct ast_expression *left,
	struct ast_expression *right, uint64_t element_size);
struct ast_logical_expression *ast_new_logical(struct arena *arena,
	struct source_location location, enum logical_operator operation,
	struct ast_expression *left, struct ast_expression *right);
struct ast_assignment_expression *ast_new_assignment(struct arena *arena,
	struct source_location location, struct ast_expression *left,
	struct ast_expression *right);
struct ast_compound_assignment_expression *ast_new_compound_assignment(struct arena *arena,
	struct source_location location, enum binary_operator operation,
	struct ast_expression *left, struct ast_expression *right);
struct ast_load_expression *ast_new_load(struct arena *arena,
	struct ast_expression *operand);
struct ast_cast_expression *ast_new_cast(struct arena *arena,
	struct source_location location, struct ast_type_syntax *type_syntax,
	struct ast_expression *operand);
struct ast_conversion_expression *ast_new_conversion(struct arena *arena,
	struct ast_expression *operand, const struct type *target);
struct ast_goto_statement *ast_new_goto(struct arena *arena,
	struct source_location location, struct token name);
struct ast_label *ast_new_label(struct arena *arena, struct token name);
struct ast_labeled_statement *ast_new_labeled_statement(struct arena *arena,
	struct ast_label *label, struct ast_statement *body);
struct ast_block_label *ast_new_block_label(struct arena *arena, struct ast_label *label);
struct ast_return_statement *ast_new_return(struct arena *arena,
	struct source_location location, struct ast_expression *value);
struct ast_expression_statement *ast_new_expression_statement(struct arena *arena,
	struct source_location location, struct ast_expression *value);
struct ast_empty_statement *ast_new_empty_statement(struct arena *arena,
	struct source_location location);
struct ast_if_statement *ast_new_if(struct arena *arena,
	struct source_location location, struct ast_expression *condition,
	struct ast_statement *then_branch, struct ast_statement *else_branch);
struct ast_case_label *ast_new_case_label(struct arena *arena,
	struct source_location location, struct ast_expression *value);
struct ast_block_case *ast_new_block_case(struct arena *arena, struct ast_case_label *label);
struct ast_case_statement *ast_new_case_statement(struct arena *arena,
	struct ast_case_label *label, struct ast_statement *body);
struct ast_default_label *ast_new_default_label(struct arena *arena,
	struct source_location location);
struct ast_block_default *ast_new_block_default(struct arena *arena, struct ast_default_label *label);
struct ast_default_statement *ast_new_default_statement(struct arena *arena,
	struct ast_default_label *label, struct ast_statement *body);
struct ast_switch_statement *ast_new_switch(struct arena *arena,
	struct source_location location, struct ast_expression *control,
	struct ast_statement *body);
struct ast_while_statement *ast_new_while(struct arena *arena,
	struct source_location location, struct ast_expression *condition,
	struct ast_statement *body);
struct ast_do_statement *ast_new_do(struct arena *arena,
	struct source_location location, struct ast_statement *body,
	struct ast_expression *condition);
struct ast_for_statement *ast_new_for(struct arena *arena,
	struct source_location location,
	struct ast_block_item *initializer_declarations,
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
