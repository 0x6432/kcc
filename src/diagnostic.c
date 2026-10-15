#include "diagnostic.h"

static void write_diagnostic(struct diagnostics *diagnostics,
	struct source_location location, const char *severity, const char *message)
{
	size_t line;
	size_t column;

	if (!diagnostics->stream)
		return;
	source_line_column(location, &line, &column);
	fprintf(diagnostics->stream, "%s:%zu:%zu: %s: %s\n",
		location.source->name, line, column, severity, message);
}

void diagnostic_error(struct diagnostics *diagnostics,
			struct source_location location, const char *message)
{
	write_diagnostic(diagnostics, location, "error", message);
	diagnostics->errors++;
}

void diagnostic_warning(struct diagnostics *diagnostics,
			struct source_location location, const char *message)
{
	write_diagnostic(diagnostics, location, "warning", message);
	diagnostics->warnings++;
}
