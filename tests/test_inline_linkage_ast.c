/* Inline specifiers belong to declarations, never function types.  Compile
 * against compiler sources excluding main.c (same as other AST release gates).
 */
#include "parse.h"
#include "sema.h"
#include "consteval.h"
#include "type.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

struct fixture {
	struct source source;
	struct arena arena;
	FILE *stream;
	struct diagnostics diagnostics;
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
};

static void open_fixture(struct fixture *f, const char *text)
{
	memset(f, 0, sizeof *f);
	f->stream = tmpfile();
	assert(f->stream);
	f->diagnostics.stream = f->stream;
	assert(source_from_bytes(&f->source, "inline-ast.c",
		(const unsigned char *)text, strlen(text)));
	assert(source_prepare(&f->source));
	preprocess_init(&f->preprocessor, &f->source, &f->diagnostics);
	f->unit = parse_translation_unit(&f->preprocessor, &f->arena, &f->diagnostics);
	assert(f->unit && f->diagnostics.errors == 0);
}

static void close_fixture(struct fixture *f)
{
	arena_destroy(&f->arena);
	preprocess_destroy(&f->preprocessor);
	source_destroy(&f->source);
	assert(fclose(f->stream) == 0);
}

static struct ast_external_declaration *declaration(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = f->unit->declarations;

	while (index--) {
		assert(d);
		d = d->next;
	}
	assert(d);
	return d;
}

static struct ast_function *function(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = declaration(f, index);

	assert(d->kind == external_function_definition);
	return (struct ast_function *)d;
}

static struct ast_function_declaration *prototype(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = declaration(f, index);

	assert(d->kind == external_function_declaration);
	return (struct ast_function_declaration *)d;
}

static struct ast_external_type_declaration *queried(struct fixture *f, unsigned index)
{
	struct ast_external_declaration *d = declaration(f, index);

	assert(d->kind == external_type_declaration);
	return (struct ast_external_type_declaration *)d;
}

static void check_canonical_identity(void)
{
	struct fixture f;
	struct ast_function_declaration *first, *last;
	struct ast_function *body;
	struct ast_external_object_declaration *pointer;
	struct function_symbol saved;
	struct address_initializer_result result;

	open_fixture(&f, "inline inline int target(int);"
		"inline int target(int x) { return x+2; }"
		"int (*cell)(int)=target; inline int target(int);");
	first = prototype(&f, 0);
	body = function(&f, 1);
	last = prototype(&f, 3);
	assert(first->is_inline && !first->is_extern && !first->is_static);
	assert(body->declaration->is_inline && !body->declaration->is_extern);
	assert(last->is_inline && !last->is_extern);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	assert(first->symbol && first->symbol == last->symbol);
	assert(first->symbol == body->declaration->symbol);
	assert(first->symbol->definition == body);
	assert(first->symbol->has_inline_declaration);
	assert(!first->symbol->has_noninline_file_declaration);
	assert(first->symbol->is_inline_only && !first->symbol->is_internal);
	assert(first->symbol->is_referenced);
	pointer = (struct ast_external_object_declaration *)declaration(&f, 2);
	assert(pointer->external.kind == external_object_declaration);
	assert(pointer->symbol->initializer_value.kind == static_data_address);
	assert(pointer->symbol->initializer_value.address.kind == static_address_function);
	assert(pointer->symbol->initializer_value.address.base.function == first->symbol);
	memcpy(&saved, first->symbol, sizeof saved);
	result = evaluate_address_initializer(pointer->initializer);
	assert(result.status == constant_value && result.address.base.function == first->symbol);
	assert(memcmp(&saved, first->symbol, sizeof saved) == 0);
	close_fixture(&f);
}

static void check_classification(const char *text, unsigned definition_index,
	bool internal, bool inline_only, bool noninline_file)
{
	struct fixture f;
	struct ast_function *body;
	struct function_symbol *symbol;

	open_fixture(&f, text);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	body = function(&f, definition_index);
	symbol = body->declaration->symbol;
	assert(symbol && symbol->definition == body);
	assert(symbol->has_inline_declaration);
	assert(symbol->is_internal == internal);
	assert(symbol->is_inline_only == inline_only);
	assert(symbol->has_noninline_file_declaration == noninline_file);
	close_fixture(&f);
}

static void check_alias_and_query_captures(void)
{
	struct fixture f;
	struct ast_external_typedef_declaration *alias;
	struct ast_external_type_declaration *first, *last;
	struct ast_function *body;
	const struct type *captured;

	open_fixture(&f, "typedef int F(int); inline F target;"
		"inline int target(int x) { return x+2; } inline typeof(target) target;");
	alias = (struct ast_external_typedef_declaration *)declaration(&f, 0);
	assert(alias->external.kind == external_typedef_declaration);
	first = queried(&f, 1);
	last = queried(&f, 3);
	body = function(&f, 2);
	assert(first->is_inline && !first->is_extern);
	assert(last->is_inline && !last->is_extern);
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 0);
	assert(first->symbol == body->declaration->symbol && first->symbol == last->symbol);
	assert(first->symbol->is_inline_only);
	assert(first->symbol->has_inline_declaration && !first->symbol->has_noninline_file_declaration);
	assert(!first->object_symbol && !last->object_symbol);
	captured = alias->declaration->type;
	assert(captured && captured->kind == type_kind_function);
	assert(first->type == captured); /* Specifier cannot mutate the alias type. */
	assert(type_compatible(first->type, last->type));
	close_fixture(&f);

	open_fixture(&f, "typedef int F(int); inline int target(int x) { return x; } F target;");
	assert(sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	body = function(&f, 1);
	last = queried(&f, 2);
	assert(!last->is_inline && !last->is_extern);
	assert(last->symbol == body->declaration->symbol);
	assert(last->symbol->has_noninline_file_declaration && !last->symbol->is_inline_only);
	close_fixture(&f);
}

static void check_deferred_rejection(const char *text)
{
	struct fixture f;

	open_fixture(&f, text);
	assert(!sema_translation_unit(f.unit, &f.arena, &f.diagnostics));
	assert(f.diagnostics.errors == 1);
	close_fixture(&f);
}

int main(void)
{
	check_canonical_identity();
	check_alias_and_query_captures();
	check_classification("inline int f(void) { return 42; }", 0, false, true, false);
	check_classification("inline int f(void); inline int f(void) { return 42; }"
		"inline int f(void);", 1, false, true, false);
	check_classification("extern int f(void); inline int f(void) { return 42; }",
		1, false, false, true);
	check_classification("inline int f(void) { return 42; } extern int f(void);",
		0, false, false, true);
	check_classification("int f(void); inline int f(void) { return 42; }",
		1, false, false, true);
	check_classification("inline int f(void) { return 42; } int f(void);",
		0, false, false, true);
	check_classification("inline int f(void) { return 42; } extern inline int f(void);",
		0, false, false, true);
	check_classification("extern inline int f(void) { return 42; }",
		0, false, false, true);
	check_classification("inline int f(void); int f(void) { return 42; }",
		1, false, false, true);
	check_classification("inline int f(void) { return 42; }"
		"int use(void) { extern int f(void); return f(); }", 0, false, true, false);
	check_classification("inline int f(void) { return 42; }"
		"int use(void) { inline int f(void); return f(); }", 0, false, true, false);
	check_classification("static inline int f(void) { return 42; }",
		0, true, false, false);
	check_classification("static inline int f(void); extern inline int f(void) { return 42; }",
		1, true, false, true);
	check_classification("inline int f(void) { static int n=42; return n; } int f(void);",
		0, false, false, true);
	check_classification("static int n=42; inline int f(void) { return n; } extern int f(void);",
		1, false, false, true);
	check_deferred_rejection("inline int f(void);");
	check_deferred_rejection("inline int f(void) { static int n=42; return n; }");
	check_deferred_rejection("static int n; inline int f(void) { return sizeof n; }");
	check_deferred_rejection("static int n; inline int f(void) { typeof(n) value=42; return value; }");
	puts("Inline AST identity, alias captures, TU-end ownership and deferred restrictions passed");
	return 0;
}
