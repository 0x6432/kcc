# Conditional header availability

`__has_include` is available in preprocessing `#if` and `#elif` expressions,
including through macro expansion. It accepts the same bounded quoted and angle
header-name subset as `#include`: quoted names search the physical including
file's directory first, then configured `-I` directories; angle names search
configured directories. Compiler-provided fallback headers are considered after
explicit directories. Direct angle names are not macro-expanded internally;
computed header operands are macro-expanded. `defined(__has_include)` is true.

Each evaluated query uses the configured source loader and consumes an include
attempt and, if successful, the source's bytes from the existing per-translation
limits. A failed lookup yields zero without an include-not-found diagnostic;
malformed names and resource errors are diagnosed. Queries in short-circuited
operands are syntax-checked but do not load a source. The loader's boolean
interface does not distinguish missing files from other read failures, so such
failures yield zero. Quoted backslashes and whitespace or non-path bytes inside
angle names remain unsupported, as for ordinary includes.

The compiler build succeeds with this implementation. Its added checks have not
been run; this is not a claim of complete preprocessing conformance.
