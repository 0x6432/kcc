/* Bounded C23 checked integer arithmetic for the x86-64 LP64 kcc target.
 * Inputs are 64-bit converted representations plus signedness; compute exact
 * magnitudes in unsigned 128 bits and write wrapped result representation.
 * Build with -fno-strict-aliasing, separately from generated code. */
#include <stdbool.h>
#include <stdint.h>

__extension__ typedef unsigned __int128 uint128;

bool __kcc_ckd(void *result, unsigned int result_kind, unsigned long a,
               unsigned int a_signed, unsigned long b, unsigned int b_signed,
               unsigned int operation)
{
    unsigned int width = result_kind & 255u;
    bool result_signed = (result_kind & 256u) != 0;
    bool aneg = a_signed && (a >> 63), bneg = b_signed && (b >> 63);
    uint128 amag = aneg ? (uint64_t)(0ul - a) : a;
    uint128 bmag = bneg ? (uint64_t)(0ul - b) : b;
    uint128 magnitude;
    bool negative;
    if (operation == 1) bneg = !bneg;
    if (operation == 2) {
        magnitude = amag * bmag;
        negative = aneg != bneg;
    } else if (aneg == bneg) {
        magnitude = amag + bmag;
        negative = aneg;
    } else if (amag >= bmag) {
        magnitude = amag - bmag;
        negative = aneg;
    } else {
        magnitude = bmag - amag;
        negative = bneg;
    }
    if (!magnitude) negative = false;
    uint128 limit = result_signed ? (((uint128)1 << (width - 1)) - !negative)
                                   : (((uint128)1 << width) - 1);
    bool overflow = (negative && !result_signed) || magnitude > limit;
    uint64_t bits = (uint64_t)magnitude;
    if (negative) bits = (uint64_t)(0ul - bits);
    /* Qualified destinations still require one observable/atomic store. */
    if (result_kind & 1024u) {
        switch (width) {
        case 8: __atomic_store_n((volatile unsigned char *)result, (unsigned char)bits, __ATOMIC_SEQ_CST); break;
        case 16: __atomic_store_n((volatile unsigned short *)result, (unsigned short)bits, __ATOMIC_SEQ_CST); break;
        case 32: __atomic_store_n((volatile unsigned int *)result, (unsigned int)bits, __ATOMIC_SEQ_CST); break;
        case 64: __atomic_store_n((volatile unsigned long *)result, (unsigned long)bits, __ATOMIC_SEQ_CST); break;
        }
    } else if (result_kind & 512u) {
        switch (width) {
        case 8: *(volatile unsigned char *)result = (unsigned char)bits; break;
        case 16: *(volatile unsigned short *)result = (unsigned short)bits; break;
        case 32: *(volatile unsigned int *)result = (unsigned int)bits; break;
        case 64: *(volatile unsigned long *)result = (unsigned long)bits; break;
        }
    } else {
        switch (width) {
        case 8: *(unsigned char *)result = (unsigned char)bits; break;
        case 16: *(unsigned short *)result = (unsigned short)bits; break;
        case 32: *(unsigned int *)result = (unsigned int)bits; break;
        case 64: *(unsigned long *)result = (unsigned long)bits; break;
        }
    }
    return overflow;
}
