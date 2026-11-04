# Bounded binary embedding

The C23 `#embed` directive accepts one quoted, angle, or macro-computed resource
name using the compiler's bounded include-name and search rules. Quoted resources
search the physical containing file's directory first; angle resources search
configured `-I` directories. Unlike headers, built-in fallback headers are not
embed resources. The raw bytes are emitted as comma-separated decimal integer
preprocessing tokens, with no source text transformations. An empty resource
produces no tokens. A missing or unreadable resource is diagnosed.

The optional `limit(expression)` or `__limit__(expression)` parameter selects at most that many bytes; its
nonnegative preprocessing integer expression uses the existing bounded #if
expression rules and may use macro expansion. A zero limit emits no tokens.
After applying the limit, resources are limited to 4,096 emitted bytes and share the include-attempt,
input-byte, synthesized-spelling, expansion-work and auxiliary-storage budgets.
The configured loader reads the complete resource before this limit is checked.
`__has_embed` with the same optional limit is available in conditional expressions. It
returns `__STDC_EMBED_FOUND__` (1), `__STDC_EMBED_EMPTY__` (2), or
`__STDC_EMBED_NOT_FOUND__` (0); the three names are predefined integer macros.
Resources exceeding 4,096 bytes after applying the limit are reported unavailable.
A zero effective length is reported empty. Queries share the
same search rules and budgets, do not use built-in headers, and are not loaded
in short-circuited operands. The loader's boolean interface cannot distinguish
missing from unreadable resources.

`prefix(...)` and `suffix(...)` insert their token sequences around a nonempty
resource. `if_empty(...)` supplies tokens when the effective resource is empty;
prefix and suffix are then suppressed. Parameters can appear in any order, and
`__prefix__`, `__suffix__` and `__if_empty__` spellings are accepted. Token
parameters are macro-expanded within the isolated directive and rescanned on
output; duplicate parameters are rejected. Queries accept these parameters.
Implementation-defined parameters remain unsupported: directives reject them,
while syntactically valid queries return `__STDC_EMBED_NOT_FOUND__`.
Balanced parameter tokens are limited to 128 levels. Existing include-name
restrictions, including quoted backslashes and whitespace in angle names, apply.

The compiler builds with this feature; the added positive, negative, search and
optional runtime checks have not been run. This is not full C23 embed support.
