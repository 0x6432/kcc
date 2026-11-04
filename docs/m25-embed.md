# Parameter-free binary embedding

The C23 `#embed` directive accepts one quoted, angle, or macro-computed resource
name using the compiler's bounded include-name and search rules. Quoted resources
search the physical containing file's directory first; angle resources search
configured `-I` directories. Unlike headers, built-in fallback headers are not
embed resources. The raw bytes are emitted as comma-separated decimal integer
preprocessing tokens, with no source text transformations. An empty resource
produces no tokens. A missing or unreadable resource is diagnosed.

Resources are limited to 4,096 bytes each, and share the include-attempt,
input-byte, synthesized-spelling, expansion-work and auxiliary-storage budgets.
The configured loader reads the complete resource before this limit is checked.
Parameter-free `__has_embed` is available in conditional expressions. It
returns `__STDC_EMBED_FOUND__` (1), `__STDC_EMBED_EMPTY__` (2), or
`__STDC_EMBED_NOT_FOUND__` (0); the three names are predefined integer macros.
Resources exceeding 4,096 bytes are reported unavailable. Queries share the
same search rules and budgets, do not use built-in headers, and are not loaded
in short-circuited operands. The loader's boolean interface cannot distinguish
missing from unreadable resources.

Parameters such as `limit`, `prefix`, `suffix`, and `if_empty`, and
implementation-defined embed parameters remain unsupported in both directives
and queries and are rejected rather than ignored. Existing include-name
restrictions, including quoted backslashes and whitespace in angle names, apply.

The compiler builds with this feature; the added positive, negative, search and
optional runtime checks have not been run. This is not full C23 embed support.
