#ifndef KCC_PREPROCESS_H
#define KCC_PREPROCESS_H

#include "lex.h"

/* Owns raw input. Do not read input independently after initialization.
 * Source must be prepared and outlive all borrowed token spellings.
 */
struct preprocessor {
	struct pp_lexer input;
	struct diagnostics *diagnostics;
	bool has_lookahead;
	struct token lookahead;
};

void preprocess_init(struct preprocessor *preprocessor, const struct source *source,
	struct diagnostics *diagnostics);
struct token preprocess_next(struct preprocessor *preprocessor);
struct token preprocess_peek(struct preprocessor *preprocessor);

#endif
