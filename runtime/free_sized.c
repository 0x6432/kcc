/* C23 sized deallocation fallbacks. As with free, invalid pointers and
 * mismatched size/alignment are caller errors; metadata is not checked. */
#include <stddef.h>
#include <stdlib.h>

void free_sized(void *pointer, size_t size)
{
    (void)size;
    free(pointer);
}

void free_aligned_sized(void *pointer, size_t alignment, size_t size)
{
    (void)alignment;
    (void)size;
    free(pointer);
}
