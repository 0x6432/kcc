#ifndef KCC_CONSTEVAL_H
#define KCC_CONSTEVAL_H

#include "ast.h"

enum constant_status {
	constant_value,
	constant_not_constant,
	constant_invalid,
};

struct constant_result {
	enum constant_status status;
	const struct type *type;
	uint64_t bits;
	struct source_location location;
	const char *message;
};

/* Pure query on an already semantically validated, depth-bounded AST.
 * Success bits are canonical low target-width bits, not host integer values.
 * No diagnostic is emitted; the consumer decides whether a constant is required.
 */
struct constant_result evaluate_integer_constant(const struct ast_expression *expression);

/* A null proof has no integer bits or numeric address representation. */
struct null_initializer_result {
	enum constant_status status;
	struct source_location location;
	const char *message;
};

/* Pure, narrow source-form query: nullptr, strict zero ICE, or checked
 * pointer/nullptr casts thereof. Not a general address-constant evaluator.
 */
struct null_initializer_result evaluate_null_initializer(const struct ast_expression *expression);

/* Stable identities plus a checked byte addend, never numeric pointer bits.
 * Bounds come only from immutable source-point expression types.
 */
enum static_address_base_kind {
	static_address_object,
	static_address_function,
	static_address_string,
	/* Checked but unevaluated static literal: identity without emitted storage. */
	static_address_compound_literal,
};

struct static_address {
	enum static_address_base_kind kind;
	int64_t byte_addend;
	union {
		const struct external_object_symbol *object;
		const struct function_symbol *function;
		const struct ast_string_expression *string;
		const struct ast_compound_literal_expression *compound_literal;
	} base;
};

struct address_initializer_result {
	enum constant_status status;
	struct source_location location;
	const char *message;
	struct static_address address;
	const struct type *origin_type; /* Captured direct address/decay pointer type. */
};

/* Pure checked-AST query. Only direct address/decay bases and compatible,
 * qualifier-preserving conversions and bounded strict-ICE pointer offsets.
 * No loads, inferred later bounds, or unproved pointer reinterpretations.
 */
struct address_initializer_result evaluate_address_initializer(const struct ast_expression *expression);

#endif
