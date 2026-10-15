# M11m: bounded -I and basic angle include search (design before implementation)

Add repeatable -Idir / -I dir driver options (up to 32, in order), accepted with
compile and token-dump modes. Preserve exclusive --help/--version behavior and
reject extra source files/unknown options. Filenames/directories remain argv
strings, never shell commands. The pp test oracle needs corresponding -I support.

Expose a bounded directory-list configuration on the preprocessor, borrowed until
its destruction and set before reading. Quoted names search the including file's
directory first, then -I directories in order. Angle names search only -I dirs.
Absolute names load directly. No default system directories or compiler-provided
headers yet; those remain explicit environment work. Empty -I directory means
current working directory; never change process cwd while resolving headers.

Extend isolated operand rescanning with a private include-name struct containing
validated path bytes, the invocation token and quote/angle search mode. Do not
invent a C string AST node or generated source merely to hold a header path.
Quoted names retain M11l's semantics. Initially angle names accept ASCII path
components made of letters/digits/_./-+ with no internal whitespace, comments,
backslashes or other punctuation. Reject unsupported names explicitly rather
than silently removing comments/whitespace from a different filename. The method
of combining computed header pp tokens is a documented subset policy; complete
contextual header-name lexing/encoding remains an audit gap.

One logical include increments the existing 128-attempt budget once; each has
at most 33 bounded search candidates. Loader failures clean the fresh temporary
source before trying the next candidate. A found source that fails preparation
or byte limits is an error, not a reason to hide it behind a later directory.
Constructed path lengths remain bounded; stop on an over-budget candidate.
Successful buffers retain existing compilation lifetime and conditional bases.
File EOF/macro boundaries and isolated-line recovery must remain unchanged.

Tests: quote-vs-angle order, ordered multiple dirs, -I forms/space-containing
paths, missing/overflow options, no-system-path behavior, absolute and nested
computed names, unsupported angle spelling, source diagnostics and all newline
policies. Compare driver/oracle with GCC/Clang using the same explicit directories,
run QBE/reference cases, and add memory-only search/failure fuzz coverage. Use
full normal/sanitizer snapshot tests; do not imply libc/header conformance.
