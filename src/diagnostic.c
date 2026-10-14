#include "diagnostic.h"

void diagnostic_error(struct diagnostics *diagnostics,
			struct source_location location, const char *message)
{
	size_t line;
	size_t column;

	source_line_column(location, &line, &column);
	fprintf(diagnostics->stream, "%s:%zu:%zu: error: %s\n",
		location.source->name, line, column, message);
	diagnostics->errors++;
}
