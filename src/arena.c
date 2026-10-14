#include "arena.h"

#include <stdint.h>
#include <stdlib.h>

struct arena_chunk {
	struct arena_chunk *next;
	size_t used;
	size_t capacity;
	max_align_t data[];
};

void *arena_alloc(struct arena *arena, size_t size)
{
	const size_t alignment = _Alignof(max_align_t);
	struct arena_chunk *chunk = arena->chunks;
	size_t padding;
	size_t rounded;
	size_t capacity;
	void *allocation;

	if (!size)
		size = 1;
	padding = (alignment - size % alignment) % alignment;
	if (size > SIZE_MAX - padding)
		return NULL;
	rounded = size + padding;

	if (!chunk || rounded > chunk->capacity - chunk->used) {
		capacity = rounded > 4096 ? rounded : 4096;
		if (capacity > SIZE_MAX - sizeof(*chunk))
			return NULL;
		chunk = malloc(sizeof(*chunk) + capacity);
		if (!chunk)
			return NULL;
		chunk->next = arena->chunks;
		chunk->used = 0;
		chunk->capacity = capacity;
		arena->chunks = chunk;
	}

	allocation = (unsigned char *)chunk->data + chunk->used;
	chunk->used += rounded;
	return allocation;
}

void arena_destroy(struct arena *arena)
{
	struct arena_chunk *chunk = arena->chunks;

	while (chunk) {
		struct arena_chunk *next = chunk->next;

		free(chunk);
		chunk = next;
	}
	arena->chunks = NULL;
}
