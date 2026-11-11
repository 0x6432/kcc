/* kcc x86-64 scalar volatile access helpers.
 * Compile separately with -fno-strict-aliasing and without LTO. Each call
 * performs exactly one naturally aligned volatile access of the stated width.
 * The frontend bitcasts floating and pointer representations around the call. */
unsigned int __kcc_volatile_load_1(const volatile void *p) { return *(const volatile unsigned char *)p; }
unsigned int __kcc_volatile_load_2(const volatile void *p) { return *(const volatile unsigned short *)p; }
unsigned int __kcc_volatile_load_4(const volatile void *p) { return *(const volatile unsigned int *)p; }
unsigned long __kcc_volatile_load_8(const volatile void *p) { return *(const volatile unsigned long *)p; }
void __kcc_volatile_store_1(volatile void *p, unsigned int v) { *(volatile unsigned char *)p = (unsigned char)v; }
void __kcc_volatile_store_2(volatile void *p, unsigned int v) { *(volatile unsigned short *)p = (unsigned short)v; }
void __kcc_volatile_store_4(volatile void *p, unsigned int v) { *(volatile unsigned int *)p = v; }
void __kcc_volatile_store_8(volatile void *p, unsigned long v) { *(volatile unsigned long *)p = v; }

/* Bytewise aggregate accesses, including padding; no accesses exceed n bytes.
 * These helpers are separately compiled and never optimized through QBE. */
void __kcc_volatile_copy(void *d, const void *s, unsigned long n, unsigned int flags)
{
    unsigned char *dst = d; const unsigned char *src = s;
    for (unsigned long i = 0; i < n; i++) {
        unsigned char byte = flags & 1 ? ((const volatile unsigned char *)src)[i] : src[i];
        if (flags & 2) ((volatile unsigned char *)dst)[i] = byte; else dst[i] = byte;
    }
}
void __kcc_volatile_zero(void *d, unsigned long n)
{
    volatile unsigned char *dst = d;
    for (unsigned long i = 0; i < n; i++) dst[i] = 0;
}
