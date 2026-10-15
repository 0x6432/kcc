#include "codegen.h"
#include "parse.h"
#include "sema.h"

#include <assert.h>
#include <stdio.h>

/* Fuzz compiler stages, never execute generated programs. */
int LLVMFuzzerTestOneInput(const unsigned char *data, size_t size)
{
	struct source source;
	struct arena arena = { 0 };
	struct lexer lexer;
	struct ast_translation_unit *unit;
	FILE *stream;
	struct diagnostics diagnostics;

	if (size > 65536)
		return 0;
	stream = fopen("/dev/null", "w");
	assert(stream);
	diagnostics = (struct diagnostics) { stream, 0 };
	assert(source_from_bytes(&source, "fuzz.c", data, size));
	lexer_init(&lexer, &source, &diagnostics);
	unit = parse_translation_unit(&lexer, &arena, &diagnostics);
	if (unit && sema_translation_unit(unit, &arena, &diagnostics)) {
		assert(diagnostics.errors == 0);
		assert(codegen_translation_unit(stream, unit));
	}
	arena_destroy(&arena);
	source_destroy(&source);
	assert(fclose(stream) == 0);
	return 0;
}
