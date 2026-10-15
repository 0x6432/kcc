#ifndef KCC_SEMA_H
#define KCC_SEMA_H

#include "ast.h"

/* Run once on a freshly parsed unit. Arena owns inserted conversion nodes. */
bool sema_translation_unit(struct ast_translation_unit *unit, struct arena *arena,
	struct diagnostics *diagnostics);

#endif
