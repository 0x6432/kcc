#ifndef KCC_ARENA_H
#define KCC_ARENA_H

#include <stddef.h>

struct arena_chunk;

/* Zero-initialize before use. Allocations are uninitialized, maximally aligned. */
struct arena {
	struct arena_chunk *chunks;
};

void *arena_alloc(struct arena *arena, size_t size);
void arena_destroy(struct arena *arena);

#endif
