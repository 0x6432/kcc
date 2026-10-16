/* Test-only pure-query oracle; never execute the input program. */
#include "consteval.h"
#include "parse.h"
#include "sema.h"
#include "type.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static bool print_constant(const struct ast_expression *expression)
{
	unsigned char before[sizeof(*expression)];
	struct constant_result result;

	memcpy(before, expression, sizeof(before));
	result = evaluate_integer_constant(expression);
	struct constant_result again = evaluate_integer_constant(expression);

	assert(memcmp(before, expression, sizeof(before)) == 0);
	assert(result.status == again.status && result.type == again.type && result.bits == again.bits);
	assert(result.location.source == again.location.source && result.location.offset == again.location.offset);
	assert(result.message == again.message);
	if (result.status != constant_value) {
		assert(result.message && result.location.source);
		return printf("%s\n", result.status == constant_invalid ? "invalid" : "not_constant") >= 0;
	}
	assert(result.type == expression->type && result.location.source == expression->location.source);
	assert(result.location.offset == expression->location.offset && !result.message);
	return printf("value %ju %u %u\n", (uintmax_t)result.bits,
		type_integer_width(result.type), type_is_unsigned(result.type) ? 1u : 0u) >= 0;
}

int main(int argc, char **argv)
{
	struct source source;
	struct arena arena = { 0 };
	struct diagnostics diagnostics = { .stream = stderr };
	struct preprocessor preprocessor;
	struct ast_translation_unit *unit;
	bool success;

	if (argc != 2 || !source_load(&source, argv[1]))
		return 1;
	if (!source_prepare(&source)) {
		source_destroy(&source);
		return 1;
	}
	preprocess_init(&preprocessor, &source, &diagnostics);
	unit = parse_translation_unit(&preprocessor, &arena, &diagnostics);
	success = unit && sema_translation_unit(unit, &arena, &diagnostics);
	if (success)
		for (struct ast_external_declaration *external = unit->declarations; external; external = external->next) {
			struct ast_function *function;

			if (external->kind != external_function_definition)
				continue;
			function = (struct ast_function *)external;
			for (struct ast_block_item *item = function->body->items; item; item = item->next) {
				struct ast_statement *statement;

				if (item->kind != block_item_statement)
					continue;
				statement = ((struct ast_statement_item *)item)->statement;
				if (statement->kind == statement_expression)
					success = print_constant(((struct ast_expression_statement *)statement)->value) && success;
			}
		}
	success = fflush(stdout) == 0 && success;
	arena_destroy(&arena);
	preprocess_destroy(&preprocessor);
	source_destroy(&source);
	return success ? 0 : 1;
}
