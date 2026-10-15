#ifndef KCC_LEX_H
#define KCC_LEX_H

#include "diagnostic.h"

#include <stdbool.h>
#include <stdint.h>

enum token_kind {
	token_eof,
	token_invalid,
	token_identifier,
	token_unsupported_keyword,
	token_integer,
	token_int,
	token_void,
	token_return,
	token_if,
	token_else,
	token_while,
	token_do,
	token_for,
	token_break,
	token_continue,
	token_left_paren,
	token_right_paren,
	token_left_brace,
	token_right_brace,
	token_semicolon,
	token_plus,
	token_minus,
	token_star,
	token_slash,
	token_percent,
	token_equal,
	token_equal_equal,
	token_not_equal,
	token_less,
	token_less_equal,
	token_greater,
	token_greater_equal,
	token_bang,
	token_and_and,
	token_or_or,
};

/* Spelling is source->data + location.offset, with explicit length. */
struct token {
	enum token_kind kind;
	struct source_location location;
	size_t length;
	uint64_t integer;
};

struct lexer {
	const struct source *source;
	struct diagnostics *diagnostics;
	size_t offset;
	bool has_lookahead;
	struct token lookahead;
};

void lexer_init(struct lexer *lexer, const struct source *source,
		struct diagnostics *diagnostics);
struct token lexer_next(struct lexer *lexer);
struct token lexer_peek(struct lexer *lexer);
const char *token_kind_name(enum token_kind kind);

#endif
