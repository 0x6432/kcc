#ifndef KCC_DIAGNOSTIC_H
#define KCC_DIAGNOSTIC_H

#include "source.h"

#include <stdio.h>

struct diagnostics {
	/* NULL counts errors without writing or resolving line/column. */
	FILE *stream;
	size_t errors;
};

void diagnostic_error(struct diagnostics *diagnostics,
			struct source_location location, const char *message);

#endif
