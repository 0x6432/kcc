# Bounded compiler-provided headers

After explicit include paths have been searched, the x86-64 SysV compiler
provides fallback subsets of `stdbool.h`, `stddef.h`, `stdint.h` and `limits.h`, in addition
to the existing `stdarg.h`. The fallbacks have include guards and explicit
include directories take precedence.

- `stdbool.h` defines `__bool_true_false_are_defined`; `bool`, `true` and
  `false` are C23 keywords.
- `stddef.h` supplies `size_t`, `ptrdiff_t`, `wchar_t`, `nullptr_t` and `NULL`.
  It does not yet supply `offsetof` or `max_align_t`.
- `stdint.h` supplies exact-width 8-, 16-, 32- and 64-bit integer types,
  least- and fast-width types, pointer-sized and maximum-width integer types,
  their corresponding limits, size and pointer-difference limits, and
  constant constructors. The fast-width type choices match Linux x86-64
  glibc. Other standard macros are not yet provided.
- `limits.h` supplies ordinary integer limits and C23 integer width macros for
  the target's 8-bit signed `char`, 16-bit short, 32-bit int and 64-bit long
  and long long. `MB_LEN_MAX` is 16, matching glibc. Bit-precise limits are
  not provided.

These are partial target-specific headers, not a complete hosted C library.
Regression coverage has been added but not run.