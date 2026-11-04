# Bounded compiler-provided headers

After explicit include paths have been searched, the x86-64 SysV compiler
provides fallback subsets of `stdbool.h`, `stddef.h`, `stdint.h`, `limits.h`, `float.h`,
`assert.h`, `stdatomic.h`, `stdlib.h`, `string.h`, `stdio.h`, `errno.h` and
`math.h`, `tgmath.h`, `ctype.h`, `inttypes.h` and `time.h`, in addition
to the existing `stdarg.h`. The fallbacks have include guards and explicit
include directories take precedence.

- `stdbool.h` defines `__bool_true_false_are_defined`; `bool`, `true` and
  `false` are C23 keywords.
- `stddef.h` supplies `size_t`, `ptrdiff_t`, `wchar_t`, `nullptr_t`, `NULL`,
  a 16-byte-aligned `max_align_t`, and bounded `offsetof` for named members,
  nested members and constant in-bounds fixed-array indices. The `max_align_t`
  representation is a target-specific 32-byte struct rather than long double.
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
  once when enabled, and calls glibc's `__assert_fail` on failure with source
  and function information. It requires a compatible libc.
- `stdatomic.h` exposes `atomic_int`, `atomic_uint`, `ATOMIC_VAR_INIT`,
  `atomic_init`, `atomic_is_lock_free`, `atomic_load`, `atomic_store`, `atomic_exchange`, `atomic_flag`
  test-and-set and clear,
  strong and weak compare-exchange, and `atomic_fetch_add/sub/and/or/xor`,
  with explicit-order variants of load, store, exchange, compare-exchange
  and fetch operations, for the compiler's bounded
  atomic int/unsigned-int subset. Initialization uses a sequentially consistent
  store; load and store use sequential consistency and require `-latomic`.
  Thread and signal fences use out-of-line libatomic functions. Volatile atomic
  objects, other atomic types,
  other fetch operations are not provided.
- `stdlib.h` and `string.h` declare a bounded set of common allocation,
  conversion, sorting, memory and string functions with x86-64 libc-compatible
  signatures. They omit many standard interfaces and require a compatible
  linked libc; they do not provide implementations.
- `stdio.h` exposes an opaque glibc `FILE` and common stream, file, formatted
  input/output and positioning declarations, including `va_list` variants.
  It omits other standard stdio interfaces and relies on glibc and the
  compiler's limited variadic ABI.
- `errno.h` exposes glibc thread-local `errno` through `__errno_location` and
  a small selection of Linux error constants; other error codes are not provided.
- `math.h` declares a subset of float/double math functions and uses glibc
  classification functions for `isfinite`, `isinf`, `isnan` and `signbit`,
  evaluating each argument once after conversion to double. Long double,
  other classifications and many math interfaces remain unsupported; link
  math functions with `-lm`.
- `tgmath.h` provides the listed unary real functions, plus `atan2`, `pow` and
  `fmod`, as generic macros for float, double and integer arguments. All-float
  arguments select the `f` variant; any double or integer selects the double
  variant. Arguments are evaluated once. Other generic functions, complex and
  long-double generic math are not provided.
- `ctype.h` declares the usual narrow-character classification and conversion
  functions from libc. `inttypes.h` supplies exact-width, pointer-width and
  max-width print format macros plus `imaxabs`, `strtoimax` and `strtoumax`.
  It does not yet provide scanning or least/fast-width format macros.
- `time.h` supplies glibc x86-64 `time_t`, `clock_t` and `struct tm` layout,
  `struct timespec`, `CLOCKS_PER_SEC`, `TIME_UTC`, and common clock, calendar
  and formatting declarations including `timespec_get` and `timespec_getres`.
  It depends on compatible glibc; `timespec_getres` requires glibc 2.34 or
  later. Other time interfaces remain omitted.

These are partial target-specific headers, not a complete hosted C library.
Regression coverage has been added but not run.