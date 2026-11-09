# Bounded preprocessing resource names

`#include`, `#embed`, `__has_include` and `__has_embed` use the same resource
name construction and search policy. Direct angle names preserve each space or
tab byte between `<` and `>`, including leading and trailing whitespace. In
macro-computed angle names, each preprocessing-token whitespace boundary is
represented by one space. This is the chosen implementation-defined spelling
policy for computed names, not a promise of byte-for-byte preservation.
Parentheses, brackets, braces, `*`, and `$` join the previously supported ASCII
letters, digits and punctuation. In availability queries a `)` within an angle
name is part of the name rather than the end of the query. Direct angle names
continue to suppress identifier macro expansion.

Quoted names retain backslashes as literal filename bytes, not C string escapes;
this is an implementation-specific extension and is not portable ISO C usage.
A quote inside a quoted name is rejected. The existing quoted-token lexer still
interprets a backslash before a quote when locating the token's end, so some
names (including a name ending in a backslash) cannot be represented. Source
line splicing occurs first.

This is not general contextual header-name lexing: direct angle names are still
formed from ordinary preprocessing tokens. Comment sequences in direct angle
names are rejected; quote and backslash bytes there, non-ASCII/UCN spelling,
and cases where maximal-munch tokenization absorbs a closing `>` are not
supported. Newlines and vertical-tab/form-feed directive whitespace are rejected
as before. Empty names are rejected. Name paths (including whitespace and the
terminating NUL) retain the 4096-byte bound, and existing include-attempt,
source-byte and expansion limits still apply. Missing and unreadable files remain
indistinguishable through the loader. There are no default system include paths;
compiler-provided fallback headers apply only to includes and include queries.

The focused regressions in `tests/test_includes.py`, `tests/test_include_search.py`,
`tests/test_builtin_headers.py` and `tests/test_embed.py` cover direct and
computed names, whitespace and punctuation, literal backslashes, query/directive
consistency, bounds and errors. Supported include cases are compared against the
local host preprocessor, with executable tests through QBE when configured;
embed cases use compiler and QBE runtime checks. Host agreement does not prove
complete C23 conformance.
