#ifndef KCC_CODEGEN_H
#define KCC_CODEGEN_H

#include "ast.h"

struct codegen_options {
	bool legacy_clang_abi;
};

/* Options must match successful sema. False means output I/O failed. */
bool codegen_translation_unit_with_options(FILE *stream, const struct ast_translation_unit *unit,
	const struct codegen_options *options);
/* Default API uses the GCC-compatible target. */
bool codegen_translation_unit(FILE *stream, const struct ast_translation_unit *unit);

#endif
