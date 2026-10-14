#ifndef KCC_CODEGEN_H
#define KCC_CODEGEN_H

#include "ast.h"

/* Only call after successful sema. False means output I/O failed. */
bool codegen_translation_unit(FILE *stream, const struct ast_translation_unit *unit);

#endif
