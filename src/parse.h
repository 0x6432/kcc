#ifndef KCC_PARSE_H
#define KCC_PARSE_H

#include "ast.h"

struct ast_translation_unit *parse_translation_unit(struct lexer *lexer,
	struct arena *arena, struct diagnostics *diagnostics);

#endif
