#include "source.h"

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* An explicit educational-compiler resource limit, not a C language limit. */
#define SOURCE_MAX_BYTES (16 * 1024 * 1024)

/* Between checkpoints, logical and physical byte offsets advance equally. */
struct source_mapping {
	size_t logical_offset;
	size_t physical_offset;
};

static char *copy_name(const char *name)
{
	size_t length = strlen(name);
	char *copy = malloc(length + 1);

	if (copy)
		memcpy(copy, name, length + 1);
	return copy;
}

bool source_from_bytes(struct source *source, const char *name,
			const unsigned char *data, size_t length)
{
	*source = (struct source) { 0 };
	if (length > SOURCE_MAX_BYTES) {
		errno = EFBIG;
		return false;
	}

	source->name = copy_name(name);
	source->data = malloc(length + 1);
	if (!source->name || !source->data) {
		source_destroy(source);
		errno = ENOMEM;
		return false;
	}

	if (length)
		memcpy(source->data, data, length);
	/* Convenience terminator only: embedded NUL is not end of source. */
	source->data[length] = 0;
	source->length = length;
	return true;
}

bool source_load(struct source *source, const char *path)
{
	FILE *stream;
	unsigned char *data = NULL;
	size_t capacity = 4096;
	size_t length = 0;
	int saved_errno;

	*source = (struct source) { 0 };
	stream = fopen(path, "rb");
	if (!stream)
		return false;

	data = malloc(capacity + 1);
	if (!data)
		goto failure;

	for (;;) {
		size_t bytes = fread(data + length, 1, capacity - length, stream);

		length += bytes;
		if (ferror(stream)) {
			if (!errno)
				errno = EIO;
			goto failure;
		}
		if (feof(stream))
			break;

		if (length == capacity) {
			unsigned char *grown;

			if (capacity == SOURCE_MAX_BYTES) {
				int next = fgetc(stream);

				if (next == EOF && !ferror(stream))
					break;
				errno = next == EOF ? EIO : EFBIG;
				goto failure;
			}
			capacity *= 2;
			grown = realloc(data, capacity + 1);
			if (!grown)
				goto failure;
			data = grown;
		}
	}

	if (fclose(stream) != 0) {
		free(data);
		return false;
	}

	source->name = copy_name(path);
	if (!source->name) {
		free(data);
		return false;
	}
	data[length] = 0;
	source->data = data;
	source->length = length;
	return true;

failure:
	saved_errno = errno ? errno : ENOMEM;
	free(data);
	fclose(stream);
	errno = saved_errno;
	return false;
}

/* Phase-1 policy: CRLF and lone CR both denote one newline, as does LF. */
static size_t line_ending_width(const unsigned char *data, size_t length, size_t offset)
{
	if (offset >= length)
		return 0;
	if (data[offset] == '\n')
		return 1;
	if (data[offset] != '\r')
		return 0;
	if (length - offset >= 2 && data[offset + 1] == '\n')
		return 2;
	return 1;
}

struct source_changes {
	bool needed;
	size_t mapping_capacity;
};

/* Count only offset changes: lone CR changes spelling, but not byte offsets. */
static struct source_changes count_source_changes(const unsigned char *data, size_t length)
{
	struct source_changes changes = { 0 };
	size_t offset = 0;

	while (offset < length) {
		size_t ending = line_ending_width(data, length, offset + 1);

		if (data[offset] == '\\' && ending) {
			offset += 1 + ending;
			changes.needed = true;
			changes.mapping_capacity++;
		} else if (data[offset] == '\r') {
			ending = line_ending_width(data, length, offset);
			offset += ending;
			changes.needed = true;
			if (ending == 2)
				changes.mapping_capacity++;
		} else {
			offset++;
		}
	}
	return changes;
}

static void record_mapping(struct source_mapping *mappings, size_t *count,
	size_t logical_offset, size_t physical_offset)
{
	/* Consecutive splices at one logical offset need only the last mapping. */
	if (*count && mappings[*count - 1].logical_offset == logical_offset) {
		mappings[*count - 1].physical_offset = physical_offset;
		return;
	}
	mappings[*count] = (struct source_mapping) { logical_offset, physical_offset };
	(*count)++;
}

bool source_prepare(struct source *source)
{
	unsigned char *logical_data;
	struct source_mapping *mappings = NULL;
	struct source_changes changes;
	size_t mapping_count = 0;
	size_t physical_offset = 0;
	size_t logical_offset = 0;

	if (source->prepared)
		return true;
	changes = count_source_changes(source->data, source->length);
	if (!changes.needed) {
		source->physical_length = source->length;
		source->prepared = true;
		return true;
	}
	if (changes.mapping_capacity > SIZE_MAX / sizeof(*mappings)) {
		errno = ENOMEM;
		return false;
	}
	logical_data = malloc(source->length + 1);
	if (changes.mapping_capacity)
		mappings = malloc(changes.mapping_capacity * sizeof(*mappings));
	if (!logical_data || (changes.mapping_capacity && !mappings)) {
		free(logical_data);
		free(mappings);
		errno = ENOMEM;
		return false;
	}
	while (physical_offset < source->length) {
		unsigned char byte = source->data[physical_offset];
		size_t ending = line_ending_width(source->data, source->length,
			physical_offset + 1);

		if (byte == '\\' && ending) {
			physical_offset += 1 + ending;
			record_mapping(mappings, &mapping_count,
				logical_offset, physical_offset);
			continue;
		}
		if (byte == '\r') {
			logical_data[logical_offset++] = '\n';
			ending = line_ending_width(source->data, source->length, physical_offset);
			physical_offset += ending;
			if (ending == 2)
				record_mapping(mappings, &mapping_count,
					logical_offset, physical_offset);
			continue;
		}
		logical_data[logical_offset++] = byte;
		physical_offset++;
	}
	logical_data[logical_offset] = 0;
	/* Commit only after every allocation and transformation has succeeded. */
	source->physical_data = source->data;
	source->physical_length = source->length;
	source->data = logical_data;
	source->length = logical_offset;
	source->mappings = mappings;
	source->mapping_count = mapping_count;
	source->prepared = true;
	return true;
}

void source_destroy(struct source *source)
{
	free(source->name);
	free(source->data);
	free(source->physical_data);
	free(source->mappings);
	*source = (struct source) { 0 };
}

size_t source_physical_offset(struct source_location location)
{
	const struct source *source = location.source;
	size_t offset = location.offset;
	size_t low = 0;
	size_t high = source->mapping_count;

	if (offset > source->length)
		offset = source->length;
	/* Upper bound: find the last checkpoint not after the requested byte. */
	while (low < high) {
		size_t middle = low + (high - low) / 2;

		if (source->mappings[middle].logical_offset <= offset)
			low = middle + 1;
		else
			high = middle;
	}
	if (low) {
		const struct source_mapping *mapping = &source->mappings[low - 1];

		return mapping->physical_offset + (offset - mapping->logical_offset);
	}
	return offset;
}

void source_line_column(struct source_location location,
			size_t *line, size_t *column)
{
	const struct source *source = location.source;
	const unsigned char *data = source->physical_data ? source->physical_data : source->data;
	size_t length = source->physical_data ? source->physical_length : source->length;
	size_t offset = source_physical_offset(location);

	*line = 1;
	*column = 1;
	for (size_t i = 0; i < offset; i++) {
		size_t ending = line_ending_width(data, length, i);

		if (ending) {
			(*line)++;
			*column = 1;
			if (ending == 2 && i + 1 < offset)
				i++;
		} else if (data[i] == '\t') {
			*column += 8 - (*column - 1) % 8;
		} else {
			(*column)++;
		}
	}
}
