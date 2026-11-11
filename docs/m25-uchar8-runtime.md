# C23 UTF-8 conversion runtime

`libkccrt.a` provides `mbrtoc8` and `c8rtomb` for the supported x86-64 glibc C and UTF-8 locales, including glibc versions without those C23 functions. Link the runtime archive when using them. The functions convert through libc `mbrtoc32` and `c32rtomb`; UTF-8 output or input code units pending between calls are recorded in the glibc-compatible `mbstate_t`. A null state pointer uses a separate thread-local internal state for each function.

Partial input returns `(size_t)-2`; further output code units return `(size_t)-3` without consuming input. Encoding errors return `(size_t)-1` and set `errno` to `EILSEQ`. Incomplete UTF-8 output accumulation returns zero. State objects can be initialized to all zero, copied and passed between calls; `mbsinit` reports pending conversion state. These implementations are specifically for the documented C and UTF-8 locales, not arbitrary stateful execution encodings or non-glibc targets. They rely on the x86-64 glibc eight-byte `mbstate_t` representation and are not a general replacement for a host libc implementation.

`tests/test_uchar8_runtime.py` validates every Unicode scalar value against an independent UTF-8 model, partial calls, invalid byte sequences, null arguments and thread-local state. With QBE configured it also routes calls through KCC-compiled wrappers linked to a native pthread test driver.
