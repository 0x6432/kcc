#ifndef KCC_DIAGNOSTIC_H
#define KCC_DIAGNOSTIC_H

#include "source.h"

#include <stdio.h>

struct diagnostics {
	/* NULL counts diagnostics without writing or resolving line/column. */
	FILE *stream;
	size_t errors;
	size_t warnings;
};

void diagnostic_error(struct diagnostics *diagnostics,
			struct source_location location, const char *message);

void diagnostic_warning(struct diagnostics *diagnostics,
			struct source_location location, const char *message);

#endif
