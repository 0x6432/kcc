#include "source.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void check_preparation(const char *physical, const char *logical,
	const size_t *offsets, size_t mapping_count)
{
	struct source source;
	unsigned char *prepared_data;
	struct source_mapping *prepared_mappings;
	size_t physical_length = strlen(physical);
	size_t logical_length = strlen(logical);

	assert(source_from_bytes(&source, "phases.c", (const unsigned char *)physical,
		physical_length));
	assert(!source.prepared);
	assert(source_prepare(&source));
	assert(source.prepared && source.length == logical_length);
	assert(source.physical_length == physical_length);
	assert(memcmp(source.data, logical, logical_length + 1) == 0);
	assert(source.mapping_count == mapping_count);
	for (size_t i = 0; i <= logical_length; i++) {
		struct source_location location = { &source, i };

		assert(source_physical_offset(location) == offsets[i]);
	}
	assert(source_physical_offset((struct source_location) { &source, SIZE_MAX }) ==
		physical_length);
	prepared_data = source.data;
	prepared_mappings = source.mappings;
	assert(source_prepare(&source));
	assert(source.data == prepared_data && source.mappings == prepared_mappings);
	assert(source.mapping_count == mapping_count && source.length == logical_length);
	source_destroy(&source);
	assert(!source.data && !source.physical_data && !source.mappings && !source.prepared);
	source_destroy(&source);
}

static void test_spelling_and_offsets(void)
{
	const size_t unchanged[] = { 0, 1, 2, 3 };
	const size_t joined[] = { 0, 1, 4, 5 };
	const size_t crlf_joined[] = { 0, 1, 5, 6 };
	const size_t endings[] = { 0, 1, 3, 4, 5, 6, 7 };
	const size_t only_splices[] = { 5 };
	const size_t not_rescanned[] = { 0, 3, 4 };
	const size_t trailing[] = { 0, 3 };
	const size_t bare_cr[] = { 0, 1, 2 };
	const size_t empty[] = { 0 };
	const size_t whitespace[] = { 0, 1, 2, 3, 4 };

	check_preparation("abc", "abc", unchanged, 0);
	check_preparation("ab\\\nc", "abc", joined, 1);
	check_preparation("ab\\\r\nc", "abc", crlf_joined, 1);
	check_preparation("ab\\\rc", "abc", joined, 1);
	check_preparation("a\r\nb\rc\n", "a\nb\nc\n", endings, 1);
	check_preparation("\\\n\\\r\n", "", only_splices, 1);
	/* Do not splice the first backslash again after deleting the second. */
	check_preparation("\\\\\n\n", "\\\n", not_rescanned, 1);
	check_preparation("a\\\n", "a", trailing, 1);
	check_preparation("\ra", "\na", bare_cr, 0);
	check_preparation("", "", empty, 0);
	check_preparation("\\ \nX", "\\ \nX", whitespace, 0);
}

static void check_position(struct source *source, size_t offset,
	size_t expected_line, size_t expected_column)
{
	size_t line;
	size_t column;

	source_line_column((struct source_location) { source, offset }, &line, &column);
	assert(line == expected_line && column == expected_column);
}

static void test_physical_positions(void)
{
	const unsigned char bytes[] = "\tfoo\\\r\nbar\rZ\n";
	struct source source;

	assert(source_from_bytes(&source, "positions.c", bytes, sizeof(bytes) - 1));
	assert(source_prepare(&source));
	assert(strcmp((const char *)source.data, "\tfoobar\nZ\n") == 0);
	check_position(&source, 1, 1, 9);
	check_position(&source, 4, 2, 1);
	check_position(&source, 7, 2, 4);
	check_position(&source, 8, 3, 1);
	check_position(&source, SIZE_MAX, 4, 1);
	source_destroy(&source);
}

static void test_binary_bytes(void)
{
	const unsigned char physical[] = { 0, '\\', '\n', 255, '\r', '\n', 0 };
	const unsigned char logical[] = { 0, 255, '\n', 0 };
	struct source source;

	assert(source_from_bytes(&source, "binary.c", physical, sizeof(physical)));
	assert(source_prepare(&source));
	assert(source.length == sizeof(logical));
	assert(memcmp(source.data, logical, sizeof(logical)) == 0);
	assert(source.data[source.length] == 0);
	assert(source_physical_offset((struct source_location) { &source, 1 }) == 3);
	assert(source_physical_offset((struct source_location) { &source, 3 }) == 6);
	assert(source_physical_offset((struct source_location) { &source, 4 }) == 7);
	source_destroy(&source);
}

static void test_many_mappings(void)
{
	const size_t count = 8192;
	unsigned char *physical = malloc(count * 4);
	struct source source;

	assert(physical);
	for (size_t i = 0; i < count; i++)
		memcpy(physical + i * 4, "x\\\r\n", 4);
	assert(source_from_bytes(&source, "many.c", physical, count * 4));
	free(physical);
	assert(source_prepare(&source));
	assert(source.length == count && source.mapping_count == count);
	for (size_t i = 0; i <= count; i++)
		assert(source_physical_offset((struct source_location) { &source, i }) == i * 4);
	source_destroy(&source);
}

/* Independent oracle: normalize into a temporary buffer, then splice it.
 * Unlike production, it retains a physical offset for every normalized byte.
 */
static void check_reference(const unsigned char *physical, size_t length)
{
	unsigned char normalized[128];
	size_t positions[128];
	size_t normalized_length = 0;
	size_t logical_offset = 0;
	struct source source;

	assert(length <= sizeof(normalized));
	for (size_t i = 0; i < length; i++) {
		unsigned char byte = physical[i];

		positions[normalized_length] = i;
		if (byte == '\r') {
			byte = '\n';
			if (i + 1 < length && physical[i + 1] == '\n')
				i++;
		}
		normalized[normalized_length++] = byte;
	}
	assert(source_from_bytes(&source, "reference.c", physical, length));
	assert(source_prepare(&source));
	for (size_t i = 0; i < normalized_length; i++) {
		if (normalized[i] == '\\' && i + 1 < normalized_length &&
			normalized[i + 1] == '\n') {
			i++;
			continue;
		}
		assert(logical_offset < source.length);
		assert(source.data[logical_offset] == normalized[i]);
		assert(source_physical_offset((struct source_location) {
			&source, logical_offset }) == positions[i]);
		logical_offset++;
	}
	assert(logical_offset == source.length);
	assert(source_physical_offset((struct source_location) {
		&source, logical_offset }) == length);
	source_destroy(&source);
}

static void test_reference_cases(void)
{
	const unsigned char alphabet[] = { 'x', '\\', '\r', '\n', '\t', 0, 255, '/' };
	uint32_t state = 42;
	unsigned char physical[128];

	for (size_t example = 0; example < 1024; example++) {
		size_t length;

		state = state * 1664525 + 1013904223;
		length = (state >> 16) % (sizeof(physical) + 1);
		for (size_t i = 0; i < length; i++) {
			state = state * 1664525 + 1013904223;
			physical[i] = alphabet[(state >> 24) % sizeof(alphabet)];
		}
		check_reference(physical, length);
	}
}

static void test_source_limit(void)
{
	const size_t limit = 16 * 1024 * 1024;
	unsigned char *physical = malloc(limit);
	struct source source;

	assert(physical);
	memset(physical, '\r', limit);
	assert(source_from_bytes(&source, "limit.c", physical, limit));
	free(physical);
	assert(source_prepare(&source));
	assert(source.length == limit && source.mapping_count == 0);
	assert(source.data[0] == '\n' && source.data[limit - 1] == '\n');
	assert(source_physical_offset((struct source_location) { &source, limit }) == limit);
	source_destroy(&source);
	assert(!source_from_bytes(&source, "oversize.c", NULL, limit + 1));
	assert(!source.data && !source.physical_data && !source.mappings);
}


int main(void)
{
	test_spelling_and_offsets();
	test_physical_positions();
	test_binary_bytes();
	test_many_mappings();
	test_reference_cases();
	test_source_limit();
	puts("Source phase and mapping tests passed");
	return 0;
}
