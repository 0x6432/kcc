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
Parameters such as `limit`, `prefix`, `suffix`, and `if_empty`, the
`__has_embed` operator, and implementation-defined embed parameters remain
unsupported and are rejected rather than ignored. Existing include-name
restrictions, including quoted backslashes and whitespace in angle names, apply.

The compiler builds with this feature; the added positive, negative, search and
optional runtime checks have not been run. This is not full C23 embed support.
