# M10a: object-like macro checkpoint

## Decisions before implementation

Implement only object-like `#define` and `#undef` in preprocess.c. Keep the
on-demand raw lexer, one language-token cache and existing parser interface.
Never substitute strings, re-lex replacements, or collect a whole translation
unit. Function-like definitions are diagnosed, not silently treated as objects.
Whitespace before a replacement is required; an immediately adjacent `(` marks
a function-like definition. Empty replacements are valid.

The preprocessor owns an arena, a linked macro table and linked replacement
lists. Names and tokens borrow prepared source slices. Each distinct name keeps
one table identity through undefinition/redefinition. Bind only after a complete
valid directive; invalid definitions/undefinitions leave the old binding intact.
Compatible redefinitions compare kind, spelling and inter-token whitespace
presence (not amount); leading/trailing whitespace is immaterial.

An explicit stack rescans replacement tokens before returning language tokens.
A macro is disabled while its frame remains active, including while its last
replacement token is rescanned. Exhausted frames are popped only when requesting
the next input token. This handles direct/mutual recursion for object macros;
it is NOT a complete hide-set design for future argument substitution.
Only raw source tokens can dispatch directives. Replacement `#` never does.
Directive names, definition bodies and undefinition operands are not expanded.

Raw token location remains its spelling location. Add expansion_location to raw
tokens and spelling_location to language tokens: diagnostics use the outermost
invocation, while name matching, numeric conversion and codegen read the original
spelling. Full expansion-stack diagnostic notes remain deferred.

Limits (compiler policy, not C23 constraints): 1024 distinct macro identities,
1024 replacement tokens per definition, 65536 retained replacement tokens across
all attempted definitions, depth 128, 65536 expansion work units per translation
unit. A work unit is one frame push or one replacement-token visit. Source token
scanning is separately bounded by the existing 16 MiB source limit. Limit or
allocation failure emits one invalid token and latches EOF; repeated peeks do
not repeat errors. Arena ownership ends at preprocess_destroy, after AST use.

Unsupported: function-like macros, `##`/`%:%:`, directives other than define,
undef and null, predefined macros, argument substitution, stringizing, include
and conditions. This slice rejects `defined` and implementation-reserved names
(`__...`, `_` followed by an uppercase letter) in define/undef rather than
pretending to implement predefined/reserved-identifier semantics. Ordinary C
keywords may be macro names. Unused replacement pp-numbers/quotes are not
prematurely converted to language tokens.

## Standard and validation basis

C23 working draft N3096, 6.10.4 (object definition, required whitespace,
identical replacement lists), 6.10.4.4 (rescan and self-reference suppression),
6.10.4.5 (undefinition), 6.10.9 (predefined-name restrictions):
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

Test token/cache/EOF behavior, source ordering, aliases, empty replacements,
self/mutual recursion, last-token suppression, transactional errors, whitespace
redefinition and all limits. Compare defined token streams with GCC and Clang,
then test real programs through parse/sema/QBE and separate-object ABI. Extend
both existing sanitizer fuzz paths with macro seeds and macro-aware provenance
and progress assertions. Run normal and sanitized regression suites before push.
