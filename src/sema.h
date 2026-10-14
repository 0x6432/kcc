#ifndef KCC_SEMA_H
#define KCC_SEMA_H

#include "ast.h"

bool sema_translation_unit(struct ast_translation_unit *unit,
	struct diagnostics *diagnostics);

#endif
