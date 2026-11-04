# UTF-8 string literals

C23 `u8` strings produce arrays of `unsigned char`. Raw UTF-8 source sequences
are validated and retained as UTF-8 bytes; simple, octal and hexadecimal byte
escapes use the existing byte decoder. Adjacent ordinary and `u8` fragments
combine into one `u8` string. The existing string length, fragment and storage
limits apply. Character arrays can use the resulting byte sequences as
initializers, and pointer conversion uses the unsigned-character element type.

Universal character names, non-ASCII bytes in ordinary string fragments,
`u8` character constants, and UTF-16/UTF-32/wide literals remain unsupported.
The compiler was built; new and updated unit, integration and optional runtime
cases have not been run.
