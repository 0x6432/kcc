#ifndef KCC_SOURCE_H
#define KCC_SOURCE_H

#include <stdbool.h>
#include <stddef.h>

/* A source owns its filename and bytes until source_destroy(). */
struct source {
	char *name;
	unsigned char *data;
	size_t length;
};

struct source_location {
	const struct source *source;
	size_t offset;
};

bool source_from_bytes(struct source *source, const char *name,
			const unsigned char *data, size_t length);
bool source_load(struct source *source, const char *path);
void source_destroy(struct source *source);
void source_line_column(struct source_location location,
			size_t *line, size_t *column);

#endif
