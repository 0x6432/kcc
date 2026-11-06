# Bounded compiler-provided headers

After explicit include paths have been searched, the x86-64 SysV compiler
provides fallback subsets of `stdbool.h`, `stdnoreturn.h`, `stddef.h`, `stdint.h`, `limits.h`, `float.h`,
`assert.h`, `stdatomic.h`, `stdlib.h`, `string.h`, `stdio.h`, `errno.h` and
`math.h`, `tgmath.h`, `ctype.h`, `inttypes.h`, `time.h`, `locale.h`, `wchar.h`, `wctype.h`, `uchar.h`, `stdbit.h`, `signal.h`, `fenv.h`, `threads.h`, `stdckdint.h` and `stdalign.h`, in addition
to the existing `stdarg.h`. The fallbacks have include guards and explicit
include directories take precedence. Compiler-owned fallback source objects can
define implementation-reserved guard and compatibility macros; ordinary user
sources cannot acquire that permission by using a similar filename. Predefined
operators and built-in location/clock/embed macros remain protected. A focused
compile covering several guarded headers passed after this fix; the full header
suite remains unrun. Trusted fallback-header declarations and new function
symbols use separate bounded budgets of 1,024 declarations and 512 functions;
user sources retain their existing 512-declaration and 256-function limits.
Source provenance, not a filename, determines which budget is charged.

- `stdbool.h` defines `__bool_true_false_are_defined`; `bool`, `true` and
  `false` are C23 keywords.
- `stdnoreturn.h` provides the deprecated `noreturn` macro as `_Noreturn`.
- `stdalign.h` is an empty compatibility header: C23 uses the `alignas` and
  `alignof` keywords and removed its legacy macros.
- `stddef.h` supplies `size_t`, `ptrdiff_t`, `wchar_t`, `nullptr_t`, `NULL`,
  a 16-byte-aligned `max_align_t`, bounded `offsetof` for named members,
  nested members and constant in-bounds fixed-array indices, and `unreachable()`.
  Reaching `unreachable()` is undefined by C23; this fallback calls `abort`
  through `libkccrt.a` rather than adding optimizer assumptions. The `max_align_t`
  representation is a target-specific 32-byte struct rather than long double.
- `stdint.h` supplies exact-width 8-, 16-, 32- and 64-bit integer types,
  least- and fast-width types, pointer-sized and maximum-width integer types,
  their corresponding limits and C23 width macros, size and pointer-difference
  limits, and constant constructors. The fast-width type choices match Linux x86-64
  glibc. The target `WCHAR_MIN`, `WCHAR_MAX`, `WINT_MIN` and `WINT_MAX` macros are also provided. Other standard macros are not yet provided.
- `limits.h` supplies ordinary integer limits and C23 integer width macros for
  the target's 8-bit signed `char`, 16-bit short, 32-bit int and 64-bit long
  and long long. `MB_LEN_MAX` is 16, matching glibc. Bit-precise limits are
  not provided.
- `float.h` supplies radix, evaluation, rounding and common binary32/binary64
  precision, exponent and normalized-range macros for the default
  round-to-nearest environment, including binary32/binary64 true-minimum and
  subnormal availability macros. Long-double macros are omitted; runtime
  floating-environment changes are not modeled.
- `assert.h` responds to `NDEBUG` at each inclusion, evaluates its condition
  once when enabled, and calls glibc's `__assert_fail` on failure with source
  and function information. It requires a compatible libc.
- `stdatomic.h` supplies bounded atomic integer, boolean, pointer and enum
  operations, plus float/double load, store, exchange and compare-exchange;
  supported operations, typedefs, lock-free assumptions and remaining limits
  are documented in `m24c-atomic-subset.md`. Explicit-order forms and the
  out-of-line fences require a compatible libatomic. These additions have been
  built and smoke-checked, but their runtime and concurrency suites are unrun.
- `stdlib.h` and `string.h` declare a bounded set of common allocation,
  conversion, sorting, memory and string functions with x86-64 libc-compatible
  signatures, including C23 `strdup`, `strndup` and `memset_explicit` declarations.
  They omit other interfaces and generally require a compatible linked libc.
  The runtime archive provides a separate `memset_explicit` fallback using
  volatile byte stores; link `build/libkccrt.a` after generated objects. It
  must be compiled without LTO. It does not erase register copies, swap, or
  other copies of the data. The archive also supplies C23 `free_sized` and
  `free_aligned_sized` wrappers over libc `free`; callers must satisfy the
  standard matching size, alignment, and allocation requirements. They do not
  validate metadata. Generated-program runtime checks remain unrun.
- `stdio.h` exposes an opaque glibc `FILE` and common stream, file, formatted
  input/output and positioning declarations, including `va_list` variants and
  buffering controls. It omits other standard stdio interfaces and relies on glibc and the
  compiler's limited variadic ABI.
- `errno.h` exposes glibc thread-local `errno` through `__errno_location` and
  a small selection of Linux error constants; other error codes are not provided.
- `math.h` declares a subset of float/double math functions and uses glibc
  classification functions for `isfinite`, `isinf`, `isnan` and `signbit`,
  evaluating each argument once after conversion to double. `fpclassify`,
  `isnormal`, `issubnormal`, `iszero` and `issignaling` dispatch float and
  double to glibc helpers, preserving float subnormal classification. The six ordered/unordered comparison macros evaluate each argument once,
  dispatch to float or double helpers, and link through `build/libkccrt.a`.
  The helpers rely on a matching IEEE host and are built without fast-math or
  LTO; they do not add full floating-environment semantics to the compiler.
  C23 `roundeven`, `fromfp`/`ufromfp` and `fromfpx`/`ufromfpx`,
  `canonicalize`, `totalorder`/`totalordermag`, and NaN payload functions are
  declared for float and double, with glibc rounding-mode constants. These
  functions require glibc libm 2.31 or newer and have not been runtime-tested.
  `tgmath.h` adds generic `roundeven` and the four conversion families.
  Long double and many other math interfaces remain unsupported; link math
  functions with `-lm`. A host-only helper smoke check covered a quiet NaN and ordinary comparison;
  generated-program runtime behavior has not been tested.
- `tgmath.h` provides bounded unary real functions, `atan2`, `pow`, `fmod`,
  `hypot`, `copysign`, `fdim`, `fmax`, `fmin`, `remainder`, `nextafter` and
  `fma` as generic macros for float, double and integer arguments. All-float
  arguments select the `f` variant; any double or integer selects the double
  variant. Arguments are evaluated once. Other generic functions, complex and
  long-double generic math are not provided.
- `ctype.h` declares the usual narrow-character classification and conversion
  functions from libc. `inttypes.h` supplies exact-width, pointer-width and
  max-width print format macros plus `imaxabs`, `strtoimax` and `strtoumax`.
  It also supplies scanning and least/fast-width format macros for the target
  integer types, and `wcstoimax`/`wcstoumax` declarations. `stdlib.h` declares
  `strfromf`/`strfromd`, which require glibc 2.25 or newer; long-double
  conversion remains unavailable. These conversion calls are compile-checked,
  not runtime-tested.
- `locale.h` provides standard locale categories, the x86-64 glibc `lconv`
  layout, and `setlocale`/`localeconv` declarations. Runtime locale handling
  depends on compatible libc; the compiler's own numeric literal conversion
  retains its documented C-locale assumption.
- `wchar.h` supplies glibc-compatible `wchar_t`, `wint_t`, `mbstate_t`, wide
  string and memory operations, and basic multibyte conversion declarations.
  Wide I/O, formatted wide I/O, numeric conversion, tokenization, collation and
  `wcsftime` declarations are also supplied; they depend on the fallback
  `FILE` and limited variadic ABI and a compatible libc. `long double`
  conversion and other interfaces remain omitted. Bounded wide string
  literals are described in `m23-utf8-strings.md`. New declarations have only
  been compile-checked, not runtime-tested.
- `wctype.h` declares wide classification and case-conversion functions and
  glibc-compatible classification and transformation descriptor types.
- `uchar.h` supplies the C23 character typedefs, glibc-compatible `mbstate_t`,
  and 8/16/32-bit conversion function declarations. The C23 8-bit conversion
  declarations require a libc exporting those symbols; the development glibc
  2.34 does not.
- `signal.h` provides Linux x86-64 signal numbers, `sig_atomic_t`, `SIG_DFL`,
  `SIG_IGN`, `SIG_ERR`, and declarations for `signal` and `raise`. The signal
  sentinel expressions use the target's integer/function-pointer mapping,
  including direct static initialization. `stdint.h` also
  supplies `SIG_ATOMIC_MIN` and `SIG_ATOMIC_MAX`. These declarations depend on
  compatible libc. Bounded `volatile sig_atomic_t` accesses now require the
  separately linked `libkccrt.a`; see `m14-volatile-scalars.md`. The header does
  not make arbitrary asynchronous communication safe. Focused compile checks
  only; signal behavior has not been runtime-tested.
- `stdckdint.h` supplies `ckd_add`, `ckd_sub` and `ckd_mul` for the ten ordinary
  signed/unsigned integer types, with single evaluation and wrapped result bits.
  Link `build/libkccrt.a` after the generated object. The helper depends on the
  host compiler's unsigned 128-bit arithmetic and the target's LP64 layout.
  Plain `char`, `_Bool`, qualified result objects and noninteger operands are
  rejected; enum and character typedef restrictions cannot all be distinguished
  by this `_Generic` implementation. Bit-precise types are not supported.
  Compiler-output and host-helper smoke checks do not replace runtime or
  cross-compiler conformance tests.
- `threads.h` declares the C thread, mutex, condition, once and thread-specific
  storage functions using bounded x86-64 glibc ABI-compatible opaque layouts.
  Link with `-pthread` and use a compatible glibc with C thread symbols. Thread
  execution, synchronization, interoperation and teardown have not been tested;
  declarations alone do not establish correct concurrency semantics.
- `fenv.h` supplies x86-64 glibc-compatible opaque environment and mode
  storage, exception and rounding macros, and floating-environment function
  declarations. Link with `-lm`; C23 mode/exception functions require a
  compatible glibc. The compiler does not implement floating-environment access
  semantics or promise arithmetic observes a changed rounding mode; this header
  only exposes library calls. No floating-environment runtime test has run.
- `stdbit.h` supplies the C23 leading/trailing counts, first-bit positions,
  zero/one counts, single-bit predicate, bit width, floor and ceiling for the
  five ordinary unsigned integer types, with `_Generic` dispatch evaluating
  arguments once. Endianness macros describe the little-endian target. The
  functions are static inline implementations, not external libc symbols;
  including the header consumes 70 compiler-header function slots. Extended unsigned and bit-precise types are not supported; the header
  version macro is not advertised. An unrepresentable bit ceiling yields zero,
  though programs cannot rely on that value for the standard's undefined case.
  Only a focused compile/IL check has been run; runtime coverage is pending.
- `time.h` supplies glibc x86-64 `time_t`, `clock_t` and `struct tm` layout,
  `struct timespec`, `CLOCKS_PER_SEC`, `TIME_UTC`, and common clock, calendar
  and formatting declarations including `timespec_get` and `timespec_getres`.
  It depends on compatible glibc; `timespec_getres` requires glibc 2.34 or
  later. Other time interfaces remain omitted.

These are partial target-specific headers, not a complete hosted C library.
Regression coverage has been added but not run.
The fallback `stdio.h` also supplies an x86-64 glibc-shaped `fpos_t` and
`fgetpos`/`fsetpos` declarations. The fallback `stdlib.h` exposes `system` and
implements the locale-dependent `MB_CUR_MAX` through glibc's
`__ctype_get_mb_cur_max`. These require a compatible libc; only layout and
focused compilation checks have run, not file-position or locale runtime tests.
