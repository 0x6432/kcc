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
	token_character,
	token_string,
	token_int,
	token_signed,
	token_unsigned,
	token_long,
	token_char,
	token_short,
	token_bool,
	token_c23_bool,
	token_true,
	token_false,
	token_void,
	token_const,
	token_sizeof,
	token_alignof,
	token_legacy_alignof,
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
	token_left_bracket,
	token_right_bracket,
	token_left_brace,
	token_right_brace,
	token_semicolon,
	token_comma,
	token_question,
	token_colon,
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
	token_tilde,
	token_ampersand,
	token_caret,
	token_pipe,
	token_shift_left,
	token_shift_right,
	token_and_and,
	token_or_or,
};

/* Spelling only: target type selection belongs to sema/preprocessing. */
struct integer_spelling {
	uint64_t value;
	unsigned base;
	unsigned long_suffix;
	bool unsigned_suffix;
};

/* Explicit byte slice, no allocation/diagnostics; NULL means success. */
const char *parse_integer_spelling(const unsigned char *text, size_t length,
	struct integer_spelling *result);

/* Ordinary single-byte target character, with signed plain-char interpretation.
 * Explicit byte slice; NULL means success. No allocation or diagnostics.
 */
const char *parse_character_spelling(const unsigned char *text, size_t length,
	int64_t *result);

/* Pure byte decoder. NULL output measures; length excludes implicit final NUL.
 * Output on error is discarded. A non-NULL buffer must have enough capacity.
 */
const char *parse_string_spelling(const unsigned char *text, size_t length,
	unsigned char *output, size_t capacity, size_t *decoded_length);

/* Spelling uses spelling_location; location is the diagnostic invocation.
 * Both offsets address prepared source data, with explicit logical length.
 * Spelling may use an arena-owned generated source view, not the input source.
 * Use source_physical_offset() only for physical positions, not spelling reads.
 */
struct token {
	enum token_kind kind;
	struct source_location location;
	struct source_location spelling_location;
	size_t length;
	uint64_t integer;
	int64_t character;
	size_t string_length;
	unsigned integer_base;
	unsigned integer_long_suffix;
	bool integer_unsigned_suffix;
};

enum pp_token_kind {
	pp_eof,
	pp_invalid,
	pp_identifier,
	pp_number,
	pp_character,
	pp_string,
	pp_punctuator,
	pp_other,
	pp_newline,
};

/* Borrowed logical spellings (input or arena view), without language values. */
struct pp_token {
	enum pp_token_kind kind;
	struct source_location location;
	struct source_location expansion_location;
	size_t length;
	bool leading_space;
	bool at_line_start;
	/* VT/FF in leading trivia; comments themselves count as one space. */
	bool has_non_directive_space;
};

struct pp_lexer {
	const struct source *source;
	struct diagnostics *diagnostics;
	size_t offset;
	bool leading_space;
	bool at_line_start;
	/* VT/FF in leading trivia; comments themselves count as one space. */
	bool has_non_directive_space;
	bool has_lookahead;
	struct pp_token lookahead;
};

/* Requires source_prepare() before any source spelling is borrowed. */
void pp_lexer_init(struct pp_lexer *lexer, const struct source *source,
	struct diagnostics *diagnostics);
struct pp_token pp_lexer_next(struct pp_lexer *lexer);
struct pp_token pp_lexer_peek(struct pp_lexer *lexer);
const char *pp_token_kind_name(enum pp_token_kind kind);
/* Input must not be pp_newline. Raw-invalid diagnostics are not repeated. */
struct token token_from_pp(struct pp_token input, struct diagnostics *diagnostics);

const char *token_kind_name(enum token_kind kind);

#endif
