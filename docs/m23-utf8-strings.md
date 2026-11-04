# UTF-8 string literals

C23 `u8` strings produce arrays of `unsigned char`. Raw UTF-8 source sequences in ordinary and `u8` strings
are validated and retained as UTF-8 bytes; simple, octal and hexadecimal byte
escapes use the existing byte decoder. Adjacent ordinary and `u8` fragments
combine into one `u8` string. The existing string length, fragment and storage
limits apply. Character arrays can use the resulting byte sequences as
initializers, and pointer conversion uses the unsigned-character element type.

Fixed-width `\u` and `\U` universal names from U+00A0 through U+10FFFF,
excluding surrogates, encode to UTF-8 in ordinary and `u8` strings. Basic-set
UCNs are conservatively rejected, including the historically allowed special
characters; delimited and named UCNs are unsupported.

UTF-16/UTF-32/wide literals remain unsupported. `u8` character constants
are supported for a single ASCII source character or one byte escape; they
have unsigned-char type, so `u8'\\377'` has value 255. Multibyte source
characters cannot fit a UTF-8 character constant.
A partial `uchar.h` fallback defines `char8_t`, `char16_t`, and `char32_t`
for the target, a glibc-compatible `mbstate_t`, and the `mbrtoc16`, `c16rtomb`,
`mbrtoc32`, and `c32rtomb` interfaces. These functions require compatible libc;
C23 `mbrtoc8` and `c8rtomb` are omitted because the development environment's
glibc 2.34 does not expose them. Explicit include directories override this
fallback.

The compiler was built; new and updated unit, integration and optional runtime
cases have not been run.
