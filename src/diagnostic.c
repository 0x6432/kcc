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

void diagnostic_warning_with_detail(struct diagnostics *diagnostics,
	struct source_location location, const char *message, const char *detail)
{
	if (diagnostics->stream) {
		size_t line, column;
		source_line_column(location, &line, &column);
		fprintf(diagnostics->stream, "%s:%zu:%zu: warning: %s%s%s\n",
			location.source->name, line, column, message,
			detail ? ": " : "", detail ? detail : "");
	}
	diagnostics->warnings++;
}
