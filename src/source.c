#include "source.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* An explicit educational-compiler resource limit, not a C language limit. */
#define SOURCE_MAX_BYTES (16 * 1024 * 1024)

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

void source_destroy(struct source *source)
{
	free(source->name);
	free(source->data);
	*source = (struct source) { 0 };
}

void source_line_column(struct source_location location,
			size_t *line, size_t *column)
{
	size_t offset = location.offset;

	*line = 1;
	*column = 1;
	if (offset > location.source->length)
		offset = location.source->length;
	for (size_t i = 0; i < offset; i++) {
		if (location.source->data[i] == '\n') {
			(*line)++;
			*column = 1;
		} else if (location.source->data[i] == '\t') {
			*column += 8 - (*column - 1) % 8;
		} else {
			(*column)++;
		}
	}
}
