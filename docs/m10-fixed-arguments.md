# M10c: fixed macro arguments

## Decisions before implementation

Extend M10b with fixed parameter lists (maximum 128) and invocation arguments.
No variadics/__VA_ARGS__/__VA_OPT__, stringizing, pasting, includes or conditions.
Keep one implementation file, preprocess.c, and no whole-TU token vector.
Definitions remain transactional; redefinition compares parameter spelling/order,
macro form, replacement kind/spelling and inter-token whitespace. Parameter
references are indexed on definition tokens, before keyword conversion.

Collect arguments as UNEXPANDED pp tokens. Only nested parentheses protect a
comma; brackets/braces do not. Preserve empty arguments. F() is zero arguments
for a zero-parameter macro, but one empty argument for a one-parameter macro.
Arity is checked before any argument expansion. Source directives during call
probing/collection remain explicitly unsupported rather than executed; raw
lexical failures retain their original diagnostics and stop once.

Split cursor state from the preprocessor's source/table/arena/work counters.
The main cursor can read source; a prescan cursor can only read its argument
list and ends at a synthetic EOF. It cannot steal following source tokens.
An argument is prescanned lazily when first substituted and cached, including
empty results. Unused arguments are lexed/collected but not macro-expanded.
Prescan must not add the outer macro's identity prematurely: F(F(1)) is valid.

Arena-owned concrete parameter, argument and argument-token records outlive
frames that borrow them. Each invocation owns an argument array. Frames stream
borrowed definition tokens or argument tokens; parameter occurrences inject a
prescanned argument stream without flattening the whole replacement. Argument
tokens retain their hide sets; substitution unions those sets with the invocation
base. The base still uses name/closing-parenthesis intersection plus current ID.
All substituted diagnostic locations use the outermost invocation; spelling
continues to address the borrowed prepared-source slice. No language conversion
occurs in prescan, so a later unused parameter can discard unsupported literals.

Prescan cursors are temporary heap allocations freed on every return path.
Bound nested prescans at 64, nested argument parentheses at 128, fixed parameters
at 128 and total auxiliary records at 65536 (parameters, argument array elements,
raw/cached argument tokens across attempted definitions/invocations). Existing
1024 names, 1024 definition tokens, 65536 retained definition tokens, 128 retained
frames and 65536 work units remain. Work now also charges argument collection,
prescan input/output and injected streams. Definition/object-only accounting is
otherwise unchanged. Arena records are retained until preprocess_destroy, not
reclaimed at #undef. This bounds retained argument memory as well as output;
resource/allocation failure returns an invalid token then stable EOF.

## Acceptance and next boundaries

Reference: WG14 N3096 6.10.4, 6.10.4.1 and 6.10.4.4:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

Add kind/spelling host-oracle cases for empty arguments, nesting/commas,
callbacks/cross-stream calls, argument prescan isolation, self/mutual recursion,
unused arguments, parameter shadowing, arity and redefinitions. Add real
QBE/reference programs, error/provenance/cache/limit tests and both fuzz seeds.
Run GCC/Clang normal/sanitized, runtime/ABI and remote CI. Preserve old object
and zero-parameter regressions. This is not full M10 or C23 completion; variadics
are M10d and macro operators/directive integration remain M11. Source directives
inside invocation probing remain a tracked subset policy, not a blanket C23 UB
claim. Allocation-failure paths are handled but not fault-injection tested.
