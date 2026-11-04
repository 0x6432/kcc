# Bounded compiler-provided headers

After explicit include paths have been searched, the x86-64 SysV compiler
provides fallback subsets of `stdbool.h`, `stddef.h`, `stdint.h`, `limits.h`, `float.h`,
`assert.h`, `stdatomic.h`, `stdlib.h`, `string.h` and `stdio.h`, in addition
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
- `float.h` supplies radix, evaluation, rounding and common binary32/binary64
  precision, exponent and normalized-range macros for the default
  round-to-nearest environment. It omits long-double and subnormal limit
  macros; runtime floating-environment changes are not modeled.
- `assert.h` responds to `NDEBUG` at each inclusion, evaluates its condition
  once when enabled, and calls glibc's `__assert_fail` on failure. Because
  `__func__` is not yet available, the failure message uses `(unknown)` for the
  function name. This fallback therefore does not yet provide full standard
  diagnostic behavior and requires a compatible libc.
- `stdatomic.h` exposes `atomic_int`, `atomic_uint`, `ATOMIC_VAR_INIT`,
  `atomic_init`, `atomic_load` and `atomic_store` for the compiler's bounded
  atomic int/unsigned-int subset. Initialization uses a sequentially consistent
  store; load and store use sequential consistency and require `-latomic`.
  Volatile atomic objects, other atomic types, explicit orders, fences,
  exchange/fetch operations and lock-free queries are not provided.
- `stdlib.h` and `string.h` declare a bounded set of common allocation,
  conversion, sorting, memory and string functions with x86-64 libc-compatible
  signatures. They omit many standard interfaces and require a compatible
  linked libc; they do not provide implementations.
- `stdio.h` exposes an opaque glibc `FILE` and common stream, file, formatted
  input/output and positioning declarations. It omits other standard stdio
  interfaces and relies on glibc and the compiler's limited variadic ABI.

These are partial target-specific headers, not a complete hosted C library.
Regression coverage has been added but not run.