# UTF-8 string literals

C23 `u8` strings produce arrays of `unsigned char`. Raw UTF-8 source sequences in ordinary and `u8` strings
are validated and retained as UTF-8 bytes; simple, octal and hexadecimal byte
escapes use the existing byte decoder. Adjacent ordinary and `u8` fragments
combine into one `u8` string. The existing string length, fragment and storage
limits apply. Character arrays can use the resulting byte sequences as
initializers, and pointer conversion uses the unsigned-character element type.

Fixed-width `\u` and `\U` universal names from U+00A0 through U+10FFFF,
excluding surrogates, encode to UTF-8 in ordinary and `u8` strings. The
permitted special basic-set UCNs for `$`, `@`, and backtick are also accepted; other basic-set UCNs and delimited or named UCNs are rejected.

Bounded `u`, `U`, and `L` strings produce UTF-16, UTF-32, and 32-bit
wide code units respectively on the little-endian target. Raw UTF-8 scalars and
fixed-width UCNs are transcoded, including UTF-16 surrogate pairs; numeric
escapes directly represent one target code unit and must fit its supported
range. Matching-prefixed and ordinary fragments concatenate in the selected
encoding; different nonordinary prefixes are rejected. As with ordinary
strings, ordinary fragments are initially validated as byte strings, so an
ordinary numeric escape above 255 is rejected even beside a wide fragment.
Strings initialize matching unsigned-short, unsigned-int, or int arrays, with
inferred bounds and optional omitted terminating code unit. Wide assertion
messages are not supported. Other C23 literal and UCN extensions remain incomplete.

Bounded `u`, `U`, and `L`
character constants have unsigned-short, unsigned-int, and int types
respectively. They accept one UTF-8 source character or fixed-width UCN in the
range U+00A0–U+10FFFF (excluding surrogates), the three permitted special
UCNs, and ASCII characters.
`u` rejects characters requiring a UTF-16 surrogate pair. Octal and
hexadecimal escapes are accepted up to the target character type maximum:
65535 for `u`, 4294967295 for `U`, and 2147483647 for `L`.
`u8` character constants
are supported for a single ASCII source character or one byte escape; they
have unsigned-char type, so `u8'\\377'` has value 255. Multibyte source
characters cannot fit a UTF-8 character constant.
A partial `uchar.h` fallback defines `char8_t`, `char16_t`, and `char32_t`
for the target, a glibc-compatible `mbstate_t`, and the `mbrtoc16`, `c16rtomb`,
`mbrtoc32`, and `c32rtomb` interfaces. These functions require compatible libc;
C23 `mbrtoc8` and `c8rtomb` are provided by `libkccrt.a` for the supported x86-64 glibc C and UTF-8 locales, including glibc 2.34. See `m25-uchar8-runtime.md` for state, linkage, and locale limitations. Explicit include directories override this fallback.

The compiler was built; new and updated unit, integration and optional runtime
cases have not been run.
