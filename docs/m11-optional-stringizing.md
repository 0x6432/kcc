# M11b: stringizing optional replacement operands

## Decisions before implementation

Reference: WG14 N3096 6.10.4.1 paragraphs 4/7 and 6.10.4.2:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

Accept #__VA_OPT__(body), including the %: operator spelling. The optional
construct is itself a stringizing operand. First prescan the variable argument
to determine presence, using its existing lazy cache. An absent/expanded-empty
variable argument contributes no stringizing tokens and therefore yields "".
Do not substitute named parameters in an inactive body. Lexical and definition
constraint errors still cannot be discarded.

For a selected body, perform parameter substitution and inner # operations as
for the current function-like replacement list, but do not rescan ordinary body
macro names/calls before the outer stringizing operation. Ordinary parameters
use expanded argument caches; inner #parameter uses raw argument tokens.
__VA_ARGS__ uses the same expanded variable slot that decided presence. For
example, with A defined as 7, #__VA_OPT__(x A) called with x=A yields "7 A", not
"A A" or "7 7". A literal body call with wrong arity is text, not an invocation.

Add an exclusive replacement_end pointer to expansion frames. A temporary heap
cursor streams only the selected definition range through read_rescan_token,
not read_expanded_token, into an arena-owned argument-token list. It cannot
consume a suffix/next optional region/source token or macro-expand ordinary body
names. The caller's invocation argument array and hide set are borrowed. Injected
argument streams still use isolated prescan and the existing spacing rules.
The ordinary spelling builder then stringizes the substituted list, including
escaping generated inner strings, before the parent frame skips the whole operand.
Empty optional operands need no placemarker node without ##; M11c must implement
real token-pasting/placemarker interactions separately.

Bound simultaneously active optional-substitution cursors at 32 (in addition to
64 argument prescans and existing frame/work/storage limits). Nested optional
constructs in a single definition remain invalid; recursion through macro
arguments can still nest these helper cursors. Allocate/free cursors on every
success/error path, restore the active counter on all exits, charge range pushes,
visits and token copies to existing work/auxiliary budgets, and reuse the 1 MiB
cumulative generated-spelling cap. No parser/AST/sema/QBE changes; all production
implementation remains in preprocess.c, with cursor fields declared in its header.

Retain the five M11a whitespace-policy groups, not host-agreement claims. A probe
also found that GCC 11.5 diagnoses a wrong-arity named-argument macro even when
#__VA_OPT__ is inactive, whereas Clang 15 discards that argument. kcc chooses lazy
inactive-body substitution and tests it explicitly; do not count that diagnostic
disagreement as cross-host agreement or a settled ISO conformance determination.

## Acceptance and next boundaries

Add expanded-pp host comparisons for empty/omitted/expanded-empty tails, ordinary
body names versus expanded parameters, inner #, escaping, variadic commas,
callbacks, recursion and suffix/source isolation. Add unit tests for definition
recovery, cache/diagnostic/lifetime/resource behavior and exact 32/33 helper
nesting; extend fuzz counter invariants and both seed corpora. Add defined QBE
programs that generate/discard these strings before language conversion, with
LF/CRLF/CR. Validate GCC/Clang normal/ASan/UBSan, oracle, QBE/ABI, bounded fuzzing
and exact pushed-commit CI. Push tested checkpoints and update the handoff.

Still unsupported: ##/%:%:, includes/conditions and other directives, predefined
macros, complete encoding/literal grammar and C string expressions/concatenation.
M11c token pasting requires a separately reviewed re-lex/placemarker design.
