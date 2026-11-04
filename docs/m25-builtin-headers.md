# Bounded compiler-provided headers

After explicit include paths have been searched, the x86-64 SysV compiler
provides fallback subsets of `stdbool.h`, `stddef.h` and `stdint.h`, in addition
to the existing `stdarg.h`. The fallbacks have include guards and explicit
include directories take precedence.

- `stdbool.h` defines `__bool_true_false_are_defined`; `bool`, `true` and
  `false` are C23 keywords.
- `stddef.h` supplies `size_t`, `ptrdiff_t`, `wchar_t`, `nullptr_t` and `NULL`.
  It does not yet supply `offsetof` or `max_align_t`.
- `stdint.h` supplies exact-width 8-, 16-, 32- and 64-bit integer types,
  pointer-sized and maximum-width integer types, and their corresponding
  limits plus size and pointer-difference limits. Least/fast-width types,
  constant constructors and other standard macros are not yet provided.

These are partial target-specific headers, not a complete hosted C library.
Regression coverage has been added but not run.