#ifndef KCC_SEMA_H
#define KCC_SEMA_H

#include "ast.h"

enum static_data_kind {
	static_data_integer,
	static_data_null_pointer,
};

/* A validated target data value, never a host pointer or a relocation sentinel. */
struct static_data_value {
	enum static_data_kind kind;
	uint64_t integer_bits; /* Used only by static_data_integer. */
};

struct external_object_symbol {
	struct token name;
	const struct type *type;
	bool is_internal;
	/* First successful tentative declaration; NULL for extern-only symbols. */
	struct ast_external_declaration *tentative_definition;
	/* Explicit initialized definition supersedes tentative emission only. */
	struct ast_external_declaration *definition;
	struct static_data_value initializer_value;
	struct external_object_symbol *next;
};

struct function_symbol {
	struct token name;
	const struct function_type *type;
	struct ast_function *definition;
	bool is_internal;
	bool is_referenced;
	struct function_symbol *next;
};

/* Run once on a freshly parsed unit. Arena owns inserted conversion nodes. */
bool sema_translation_unit(struct ast_translation_unit *unit, struct arena *arena,
	struct diagnostics *diagnostics);

#endif
