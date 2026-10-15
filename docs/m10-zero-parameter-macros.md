# M10b: zero-parameter function-like macros

## Decisions before implementation

Keep this checkpoint small: define and invoke F() macros, but reject named or
variadic parameter lists and nonempty invocation arguments explicitly. M10c
will add fixed parameters, argument collection/prescan and substitution. M10d
can handle variadics if needed. Stringizing/pasting/includes/conditions stay M11.
This sequencing replaces the earlier tentative single function/argument batch.
The design and code were reconstructed after a sandbox reset during validation;
all recovered files are tested again before the checkpoint is marked complete.

An immediately adjacent '(' after a definition name selects function-like form;
whitespace/comments before '(' keep an object-like definition. Empty parameter
lists allow space/tab/comments. Whitespace after ')' is not required. A function
name without a following unexpanded '(' is not expanded. Newlines/comments may
separate invocation name, '(' and ')'. An object macro producing '(' does NOT
retroactively invoke a preceding bare function name. The name and delimiters
may cross replacement/source stream boundaries. Redefinition compares macro
form and body; definition and undefinition remain transactional.

Replace active-frame suppression with token-carried hide sets. A hide set records
macro identities unavailable for further replacement of that token. Object
expansion adds its identity to the invoking token's set. Function expansion adds
its identity to the intersection of the name and closing-parenthesis sets. This
allows consumed source parentheses to end an alias's suppression context, while
preserving suppression when both delimiters belong to that context. This is an
explicit rescan policy checked against GCC/Clang for the zero-parameter subset,
not a claim of complete argument-expansion semantics or uniquely specified ISO
behavior in all rescan corner cases.

Macro identities are stable indexes below the existing 1024-name limit. Hide
sets use a fixed array of 64-bit words (one bit per identity), copied by value.
No unbounded persistent hide-node allocation or whole-TU token list. Replacement
frames carry a hide set; borrowed replacement tokens inherit it. Later argument
substitution must combine argument token sets as well, not discard them.

rescan_token carries a pp_token, hide set and source-origin flag. The cursor
owns one pending unexpanded token, separate from the cached language token.
Looking for '(' may pop exhausted frames and cross stream boundaries; token
availability cannot depend on which frames remain. A pending token is not
charged twice. Only source-origin '#' can dispatch directives. During invocation
probing/delimiters, source directive markers are explicitly unsupported; do not
execute directives speculatively or silently miscompile a changing binding.

Keep spelling/invocation provenance, deferred conversion and arena ownership.
Work accounting stays one push or replacement-token visit; raw lookahead is
bounded by source size. Depth counts retained streams, not completed logical
calls. Fixed hide sets and the work bound also cover chains after frame popping.
Malformed invocation/argument/directive-boundary errors return one invalid token
then stable EOF. Raw-invalid input retains its lexical diagnostic without a
duplicate. Definition errors retain line draining and leave old bindings intact.

## Evidence and acceptance

WG14 N3096 6.10.4: definition form, redefinition, invocation next-token rule,
argument counts; 6.10.4.4: rescan with following tokens and unavailability.
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

Tests cover zero/empty replacements, comments/newlines/splices, uninvoked names,
keyword names, source/expansion boundary calls, mutual/self recursion,
non-retroactive '(' expansion, form-changing redefinition/undef, malformed
parameter lists, nonempty/unterminated calls, generated '#', directive boundary
policy and resource/cache/ownership invariants. The kind/spelling oracle has
198 GCC/Clang cases. Run QBE/reference/ABI, strict normal and sanitized builds,
and both seeded fuzz paths; verify exact pushed-commit CI independently.
