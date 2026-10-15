#ifndef KCC_SOURCE_H
#define KCC_SOURCE_H

#include <stdbool.h>
#include <stddef.h>

struct source_mapping;

/* Owns raw bytes until preparation, then logical bytes and optional originals.
 * Prepare before borrowing tokens; all borrowed offsets index logical data.
 */
struct source {
	char *name;
	unsigned char *data;
	size_t length;
	unsigned char *physical_data;
	size_t physical_length;
	struct source_mapping *mappings;
	size_t mapping_count;
	bool prepared;
};

/* Offset indexes source.data, not the optional physical/original buffer. */
struct source_location {
	const struct source *source;
	size_t offset;
};

bool source_from_bytes(struct source *source, const char *name,
			const unsigned char *data, size_t length);
bool source_load(struct source *source, const char *path);
/* Requires a loaded/initialized source. On failure leave raw bytes unchanged.
 * Successful repeat calls are no-ops. Call before borrowing source spellings.
 */
bool source_prepare(struct source *source);
void source_destroy(struct source *source);
size_t source_physical_offset(struct source_location location);
void source_line_column(struct source_location location,
			size_t *line, size_t *column);

#endif
