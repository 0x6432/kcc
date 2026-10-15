#ifndef KCC_PREPROCESS_H
#define KCC_PREPROCESS_H

#include "arena.h"
#include "lex.h"

#define preprocess_macro_limit 1024
#define preprocess_replacement_limit 1024
#define preprocess_storage_limit 65536
#define preprocess_depth_limit 128
#define preprocess_work_limit 65536
#define preprocess_parameter_limit 128
#define preprocess_auxiliary_limit 65536
#define preprocess_prescan_limit 64
#define preprocess_parentheses_limit 128

struct macro;
struct macro_token;
struct macro_argument;
struct argument_token;

/* A bit per stable macro identity; sets travel with tokens, not the C AST. */
struct macro_hide_set {
	uint64_t words[(preprocess_macro_limit + 63) / 64];
};

struct rescan_token {
	struct pp_token token;
	struct macro_hide_set hide;
	bool from_source;
};

struct expansion_frame {
	struct macro_token *replacement;
	struct argument_token *argument;
	struct macro_argument *arguments;
	struct source_location invocation;
	struct macro_hide_set hide;
};

/* Main input may read source; isolated argument input must stop at its own EOF. */
struct expansion_cursor {
	struct expansion_frame frames[preprocess_depth_limit];
	size_t frame_count;
	struct argument_token *input;
	struct source_location end;
	bool source_input;
	bool has_pending;
	struct rescan_token pending;
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
	struct expansion_cursor cursor;
	size_t auxiliary_records;
	size_t prescan_depth;
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
