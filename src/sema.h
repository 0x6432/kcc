#ifndef KCC_SEMA_H
#define KCC_SEMA_H

#include "consteval.h"

enum static_data_kind {
	static_data_integer,
	static_data_null_pointer,
	static_data_address,
	static_data_zero,
};

/* A validated target data value, never a host pointer or a relocation sentinel. */
struct static_data_value {
	enum static_data_kind kind;
	uint64_t integer_bits; /* Used only by static_data_integer. */
	struct static_address address; /* Used only by static_data_address. */
};

/* Bounded semantic work, including overridden/split stores. */
enum { sema_max_initializer_stores = 65536 };

/* Pure validation of an already checked source and its assignment conversion.
 * Does not analyze either tree again. */
bool sema_validate_static_initializer(const struct ast_expression *source,
	const struct ast_expression *converted, struct static_data_value *value,
	struct diagnostics *diagnostics);

struct external_object_symbol {
	struct token name;
	const struct type *type;
	const struct type *file_type; /* NULL until declared at file scope. */
	bool is_thread_local;
	bool is_block_static; /* Local object has no C linkage, despite private emission. */
	bool is_internal;
	/* First successful tentative declaration; NULL for extern-only symbols. */
	struct ast_external_declaration *tentative_definition;
	/* Explicit initialized definition supersedes tentative emission only. */
	struct ast_external_declaration *definition;
	struct static_data_value initializer_value;
	struct ast_initializer_plan *initializer_plan;
	struct external_object_symbol *next;
};

struct function_symbol {
	bool has_inline_declaration;
	bool has_noninline_file_declaration;
	bool is_inline_only;
	struct token name;
	const struct function_type *type;
	const struct function_type *file_type;
	struct ast_function *definition;
	bool is_internal;
	bool is_referenced;
	struct function_symbol *next;
};

/* Run once on a freshly parsed unit. Arena owns inserted conversion nodes. */
bool sema_translation_unit(struct ast_translation_unit *unit, struct arena *arena,
	struct diagnostics *diagnostics);

#endif
