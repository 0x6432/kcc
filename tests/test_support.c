#include "arena.h"
#include "diagnostic.h"
#include "source.h"

#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void test_source(void)
{
	const unsigned char bytes[] = { 'a', '\t', 'b', '\n', 0, 'c' };
	struct source source;
	struct source_location location;
	size_t line;
	size_t column;

	assert(source_from_bytes(&source, "input.c", bytes, sizeof(bytes)));
	assert(source.length == sizeof(bytes));
	assert(memcmp(source.data, bytes, sizeof(bytes)) == 0);
	location = (struct source_location) { &source, 2 };
	source_line_column(location, &line, &column);
	assert(line == 1 && column == 9);
	location.offset = 5;
	source_line_column(location, &line, &column);
	assert(line == 2 && column == 2);
	location.offset = SIZE_MAX;
	source_line_column(location, &line, &column);
	assert(line == 2 && column == 3);
	source_destroy(&source);
	assert(!source.data && !source.name && source.length == 0);
	source_destroy(&source);
	assert(source_from_bytes(&source, "empty.c", NULL, 0));
	assert(source.length == 0 && source.data[0] == 0);
	source_destroy(&source);
	assert(!source_from_bytes(&source, "large.c", NULL, SIZE_MAX));
	assert(errno == EFBIG);
	assert(!source.data && !source.name);
}

static void test_source_file(void)
{
	struct source source;
	FILE *stream = fopen("build/source-test.bin", "wb");

	assert(stream);
	for (size_t i = 0; i < 9000; i++)
		assert(fputc((int)(i % 256), stream) != EOF);
	assert(fclose(stream) == 0);
	assert(source_load(&source, "build/source-test.bin"));
	assert(source.length == 9000);
	for (size_t i = 0; i < source.length; i++)
		assert(source.data[i] == i % 256);
	source_destroy(&source);
	assert(remove("build/source-test.bin") == 0);
	assert(!source_load(&source, "build/does-not-exist.c"));
	assert(!source.data && !source.name);
}

static void test_diagnostic(void)
{
	struct source source;
	FILE *stream = tmpfile();
	struct diagnostics diagnostics = { stream, 0 };
	char message[128];

	assert(stream);
	assert(source_from_bytes(&source, "test.c",
					(const unsigned char *)"a\nb", 3));
	diagnostic_error(&diagnostics,
				(struct source_location) { &source, 2 }, "test error");
	assert(diagnostics.errors == 1);
	rewind(stream);
	assert(fgets(message, sizeof(message), stream));
	assert(strcmp(message, "test.c:2:1: error: test error\n") == 0);
	assert(fclose(stream) == 0);
	source_destroy(&source);
}

static void test_arena(void)
{
	struct arena arena = { 0 };
	unsigned char *first = arena_alloc(&arena, 3);

	assert(first);
	memcpy(first, "abc", 3);
	for (size_t size = 0; size < 256; size++) {
		void *allocation = arena_alloc(&arena, size);

		assert(allocation);
		assert((uintptr_t)allocation % _Alignof(max_align_t) == 0);
	}
	assert(arena_alloc(&arena, 8192));
	assert(memcmp(first, "abc", 3) == 0);
	assert(!arena_alloc(&arena, SIZE_MAX));
	assert(!arena_alloc(&arena, SIZE_MAX - _Alignof(max_align_t)));
	arena_destroy(&arena);
	assert(!arena.chunks);
	arena_destroy(&arena);
}

int main(void)
{
	test_source();
	test_source_file();
	test_diagnostic();
	test_arena();
	puts("Support tests passed");
	return 0;
}
