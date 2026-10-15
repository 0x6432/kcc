# M11d: diagnostic directives (design before implementation)

Accept `#error pp-tokens?` and C23 `#warning pp-tokens?`, including `%:`.
Only source directives execute; macro-produced markers remain ordinary tokens.
The directive name and body are not macro-expanded. Consume through the logical
newline/EOF, treating comments as whitespace and normalizing inter-token spacing
to one space. Diagnostics include the directive spelling and raw token spellings.
A body can contain pp numbers or strings unsupported as C expressions.

An error emits one error diagnostic and a recoverable invalid stream token;
compilation fails and emits no IL. A warning emits one warning diagnostic,
increments a separate warning count, contributes no parser token and does not
block otherwise valid compilation. Peeking must not repeat either diagnostic.
Lexical/forbidden-directive-whitespace errors take precedence over emitting a
partial user message. `#error` is not a fatal stream-stop policy: unit consumers
can read following tokens, matching existing malformed-directive recovery.

Use a temporary buffer bounded by remaining input length plus a small prefix;
free it on every exit. No persistent arena storage or generated spelling budget
is consumed. Error/warning output shares one diagnostic formatter; a NULL stream
counts without locating or printing. Existing diagnostics initializers become
explicit designated initializers so new counters cannot be silently confused.

Acceptance: unit tests for severity/counts, raw spelling, comments, empty bodies,
EOF, splicing/physical locations, digraphs, cache stability, recovery and lexical
errors. CLI tests cover all dump/compile modes, no IL on errors and successful
warning-bearing QBE/reference execution under LF/CRLF/CR. Both fuzz targets gain
seeds. Run normal/sanitizer GCC/Clang and host/QBE/ABI tests and bounded fuzzing.
Conditional exclusion remains a subsequent milestone; do not claim it here.
