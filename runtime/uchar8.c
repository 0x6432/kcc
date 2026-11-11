/* C23 char8 conversion for the x86-64 glibc C and UTF-8 locale subset.
 * glibc mbstate_t is eight bytes: incomplete native mbrtoc32 sequences remain
 * in its native format; pending UTF-8 code units use private nonzero markers.
 * Stateful execution encodings are outside this runtime's supported subset. */
#include <errno.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <uchar.h>
#include <wchar.h>
#include <limits.h>

#ifndef __GLIBC__
#error "uchar8 runtime requires the supported glibc mbstate_t layout"
#endif
_Static_assert(sizeof(mbstate_t) == 8, "unexpected glibc mbstate_t size");
struct utf8_state { uint32_t tag, data; };
static const uint32_t marker_mask = 0xffff0000u, read_marker = 0xc2380000u, write_marker = 0xc8390000u;

static struct utf8_state state_read(const mbstate_t *state)
{
    struct utf8_state result;
    memcpy(&result, state, sizeof(result));
    return result;
}
static void state_write(mbstate_t *state, uint32_t tag, uint32_t data)
{
    struct utf8_state next = { tag, data };
    memcpy(state, &next, sizeof(next));
}
static void state_clear(mbstate_t *state)
{
    mbstate_t zero = {0};
    *state = zero;
}

size_t mbrtoc8(unsigned char *restrict out, const char *restrict s, size_t n,
               mbstate_t *restrict ps)
{
    static _Thread_local mbstate_t internal;
    if (!ps) ps = &internal;
    if (!s) { s = ""; n = 1; out = NULL; }
    struct utf8_state saved = state_read(ps);
    if ((saved.tag & marker_mask) == read_marker) {
        unsigned count = saved.tag & 0xffu;
        if (out) *out = (unsigned char)saved.data;
        if (--count) state_write(ps, read_marker | count, saved.data >> 8);
        else state_clear(ps);
        return (size_t)-3;
    }
    if ((saved.tag & marker_mask) == write_marker) { errno = EILSEQ; return (size_t)-1; }
    char32_t scalar = 0;
    size_t result = mbrtoc32(&scalar, s, n, ps);
    if (result == (size_t)-1 || result == (size_t)-2) return result;
    /* The supported C and UTF-8 encodings have no shift state after a scalar. */
    if (!mbsinit(ps) || scalar > 0x10ffffu || (scalar >= 0xd800u && scalar <= 0xdfffu)) {
        errno = EILSEQ; return (size_t)-1;
    }
    unsigned char bytes[4]; unsigned count;
    if (scalar < 0x80u) { bytes[0] = scalar; count = 1; }
    else if (scalar < 0x800u) {
        bytes[0] = 0xc0u | (scalar >> 6); bytes[1] = 0x80u | (scalar & 63u); count = 2;
    } else if (scalar < 0x10000u) {
        bytes[0] = 0xe0u | (scalar >> 12); bytes[1] = 0x80u | ((scalar >> 6) & 63u);
        bytes[2] = 0x80u | (scalar & 63u); count = 3;
    } else {
        bytes[0] = 0xf0u | (scalar >> 18); bytes[1] = 0x80u | ((scalar >> 12) & 63u);
        bytes[2] = 0x80u | ((scalar >> 6) & 63u); bytes[3] = 0x80u | (scalar & 63u); count = 4;
    }
    if (out) *out = bytes[0];
    if (count > 1) {
        uint32_t packed = 0;
        for (unsigned i = 1; i < count; i++) packed |= (uint32_t)bytes[i] << (8 * (i - 1));
        state_write(ps, read_marker | (count - 1), packed);
    }
    return result;
}

size_t c8rtomb(char *restrict s, unsigned char c8, mbstate_t *restrict ps)
{
    static _Thread_local mbstate_t internal;
    char scratch[MB_LEN_MAX];
    if (!ps) ps = &internal;
    if (!s) { s = scratch; c8 = 0; }
    struct utf8_state saved = state_read(ps);
    unsigned remaining = 0, length = 0;
    uint32_t scalar = 0;
    if ((saved.tag & marker_mask) == write_marker) {
        remaining = saved.tag & 0xffu; length = (saved.tag >> 8) & 0xffu; scalar = saved.data;
        if ((c8 & 0xc0u) != 0x80u ||
            (remaining == length - 1 &&
             ((length == 3 && scalar == 0 && c8 < 0xa0u) ||
              (length == 3 && scalar == 0xdu && c8 >= 0xa0u) ||
              (length == 4 && scalar == 0 && c8 < 0x90u) ||
              (length == 4 && scalar == 4 && c8 >= 0x90u)))) {
            errno = EILSEQ; return (size_t)-1;
        }
        scalar = (scalar << 6) | (c8 & 0x3fu);
        --remaining;
    } else {
        if (!mbsinit(ps)) { errno = EILSEQ; return (size_t)-1; }
        if (c8 < 0x80u) scalar = c8;
        else if (c8 >= 0xc2u && c8 <= 0xdfu) { scalar = c8 & 0x1fu; remaining = 1; length = 2; }
        else if (c8 >= 0xe0u && c8 <= 0xefu) { scalar = c8 & 0x0fu; remaining = 2; length = 3; }
        else if (c8 >= 0xf0u && c8 <= 0xf4u) { scalar = c8 & 0x07u; remaining = 3; length = 4; }
        else { errno = EILSEQ; return (size_t)-1; }
    }
    if (remaining) { state_write(ps, write_marker | (length << 8) | remaining, scalar); return 0; }
    if ((length == 2 && scalar < 0x80u) || (length == 3 && scalar < 0x800u) ||
        (length == 4 && scalar < 0x10000u) || scalar > 0x10ffffu ||
        (scalar >= 0xd800u && scalar <= 0xdfffu)) { errno = EILSEQ; return (size_t)-1; }
    state_clear(ps);
    return c32rtomb(s, (char32_t)scalar, ps);
}
