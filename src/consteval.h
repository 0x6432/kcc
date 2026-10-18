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

#endif
