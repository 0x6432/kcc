#ifndef KCC_PREPROCESS_H
#define KCC_PREPROCESS_H

#include "arena.h"
#include "lex.h"

#define preprocess_macro_limit 1024
#define preprocess_replacement_limit 1024
#define preprocess_storage_limit 65536
#define preprocess_depth_limit 128
#define preprocess_work_limit 65536

struct macro;
struct macro_token;

struct expansion_frame {
	struct macro *macro;
	struct macro_token *next;
	struct source_location invocation;
};

/* Owns raw input and macro storage. Do not read input independently.
 * Prepared source outlives borrowed spellings; destroy after all AST use.
 */
struct preprocessor {
	struct pp_lexer input;
	struct diagnostics *diagnostics;
	struct arena storage;
	struct macro *macros;
	size_t macro_count;
	size_t stored_tokens;
	size_t expansion_work;
	struct expansion_frame frames[preprocess_depth_limit];
	size_t frame_count;
	bool stopped;
	bool has_lookahead;
	struct token lookahead;
};

void preprocess_init(struct preprocessor *preprocessor, const struct source *source,
	struct diagnostics *diagnostics);
void preprocess_destroy(struct preprocessor *preprocessor);
struct token preprocess_next(struct preprocessor *preprocessor);
struct token preprocess_peek(struct preprocessor *preprocessor);

#endif
