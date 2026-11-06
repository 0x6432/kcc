/* C23 explicit erasure fallback for the x86-64 runtime archive. Separate
 * compilation without LTO preserves the call, and volatile byte stores prevent
 * the implementation from removing the memory writes. */
#include <stddef.h>

void *memset_explicit(void *destination, int value, size_t length)
{
    volatile unsigned char *bytes = destination;
    for (size_t i = 0; i < length; i++)
        bytes[i] = (unsigned char)value;
    return destination;
}
