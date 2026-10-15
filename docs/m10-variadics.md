# M10d: variadic macro arguments

## Decisions before implementation

Reference: WG14 N3096 6.10.4 and 6.10.4.1:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

Extend the existing parameter grammar with a final ellipsis, either alone or
following named parameters. Keep the 128 named-parameter bound; the variadic
slot is separate. Reject GNU named ellipses and misplaced/repeated ellipses.
Compatible redefinition must also agree on variadic form. Definition validation
is transactional, including unused replacement lists.

For a variadic invocation, require at least the named arguments (empty arguments
count). C23 permits omission of the trailing variable arguments: F(x, ...) may
be called F(1) or F(1,). Merge trailing raw arguments, including their separating
commas, into one arena-owned argument slot. Do not expand before identifying
separators. F(...) with F() has an empty variable slot; F(,) contains a comma
and is nonempty. Braces/brackets do not protect separators.

Annotate __VA_ARGS__ as the final argument index. Reuse lazy isolated prescan,
including cached empty results. __VA_OPT__ tests the expanded variable argument,
not its raw length: an argument macro that expands to nothing suppresses it.
Do not prescan unused variable arguments unless __VA_ARGS__ or __VA_OPT__ needs
them. Lexical errors still cannot be discarded.

Keep replacement lists flat. Validate __VA_OPT__(pp-tokens) at definition time,
matching balanced parentheses iteratively. Annotate the marker with a pointer
to its closing token and mark that closing token as a non-emitting boundary.
Nested __VA_OPT__, a missing opener/closer, and either special identifier outside
a variadic function-like replacement list are errors. All bodies are validated,
even when never selected. The ordinary 1024-token definition bound also bounds
this scan; no recursive definition parser or new allocation kind is needed.

During substitution, skip an inactive optional region; otherwise stream its body
through the existing replacement frame, skipping only its structural delimiters.
Parameter substitution and rescan must cross the optional boundary normally,
including calls whose parentheses come from substituted arguments or following
source tokens. Do not pre-expand the selected body in an isolated stream.
No placemarker representation is needed until #/##: for this operator-free subset,
an inactive or empty region contributes no tokens. Raw definition tokens remain
intact for compatible-redefinition comparison and future operator work.

Keep preprocess.c as the sole implementation file for this stage. No lexer,
parser, AST, sema or QBE API changes. Retain per-token hide sets, outermost-call
diagnostics, cache stability, cumulative storage/work limits and EOF behavior.
The extra variadic slot and its raw/cached copies use the existing auxiliary
record budget. Optional-region decisions and boundary visits consume work too.

## Acceptance and next boundaries

Preserve all fixed/object/zero-parameter regressions. Add GCC/Clang kind/spelling
oracle cases for omitted/empty/expanded-empty lists, retained commas, recursion,
forwarding, callbacks and optional-boundary calls. Add definition/arity/location/
cache/limit tests, QBE/reference programs under LF/CRLF/CR and both fuzz seeds.
Run normal and ASan/UBSan GCC/Clang tests, QBE/ABI tests and bounded fuzzing;
push tested checkpoints and verify exact-commit CI. Document implementation
limitations and update the resume handoff before finishing.

M11 still owns stringizing, token pasting, includes and conditional directives.
GNU comma swallowing is not supported. Source directives during invocation
lookahead remain explicitly unsupported. This is not full C23 conformance.
