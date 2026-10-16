# M23a2: nullptr constant (design before implementation)

Implement the C23 nullptr keyword and its distinct complete scalar type, not an
alias for integer zero or void *. This small milestone exposes the constant in
expressions; naming nullptr_t objects/parameters remains dependent on typedef,
typeof and the standard-header environment. Do not invent a builtin nullptr_t
keyword or pretend those later declaration/header features work.

Represent the type with type_kind_nullptr and a shared type_nullptr leaf. It is
scalar/complete/object, neither integer nor pointer. Its size/alignment match a
character pointer: 8 bytes on this target. Its sole value has the all-zero void *
null representation chosen for amd64 LP64. Update leaf qualification, identity,
composite and value-width invariants explicitly, rather than falling through to
function_type casts or integer property lookup. Unit-test its distinctions even
though source declarations cannot yet spell the type.

On-demand post-pp keyword conversion gives token_nullptr. Keep raw pp names
identifiers and support macro replacement/defined/undef phase behavior. Add a
concrete ast_nullptr_expression containing the common expression header; no fake
integer/pointer token and no universal union. Parser BNF: nullptr-constant ::=
"nullptr". Sema preserves a depth-one non-lvalue leaf of the dedicated type;
codegen emits an l-width zero value. No static datum or local slot is added.

Distinguish a null pointer constant predicate from values of nullptr_t: a
literal nullptr is a constant, but conditional/comma results of that type need
not be. A wrapper predicate accepts either a traditional constant or any
nullptr_t source where the standard permits both. Any nullptr_t value converts
to a pointer or bool (false), and explicit
void discard is valid. Other integer conversions remain invalid, even explicit
casts. The current type has no source-name spelling, so conversions *to* it are
not added speculatively except the equality normalization described below.
Traditional integer-ICE/void * zero handling from M13m remains unchanged.

Equality admits nullptr_t with itself or any null pointer constant, and pointer
with nullptr_t, in either order (N3096 6.5.9). Normalize a nullptr_t/null-constant
pair with explicit conversion nodes to a shared void * comparison type. Each
conversion retains its original typed operand; do not globally change a nullptr
leaf to void *. This is comparison lowering, not a new source-level implicit
integer conversion or nullptr_t type spelling. Pointer/nullptr pairs normalize
to the exact pointer type, including function/incomplete/qualified pointers.
Relational comparisons and arithmetic reject nullptr_t. Avoid calling pointer
referent or integer properties helpers on this distinct scalar kind.

Conditional arms allow both nullptr_t (result same type), or pointer/nullptr_t
(result exact pointer type), but **not** nullptr_t versus integer zero. N3096
6.5.15 footnote 123 explicitly excludes the latter, even though equality allows
it. This constraint must not be accidentally relaxed by the null-constant helper.
Scalar conditions/logical !/&&/||, comma, discard and sizeof work normally.
sizeof(nullptr) is an unsigned-long ICE of value 8; nullptr itself, !nullptr and
(bool)nullptr are not integer constant expressions in this evaluator subset.
Keep consteval's integer-operand/form checks; no pointer folding is introduced.

Test original source runtime/typing/sequencing, no aliases. Probe native C23
keyword support and use modern hosts when available; legacy host lack of nullptr
is explicitly labelled, never patched with a void * macro as type evidence.
Cover all pointer families, callbacks, conditional results/qualifiers, equality
against integer and void * null constants, arithmetic/cast/statement constraints,
exact AST/promotion/depth bounds, sizeof and static-assert interaction, raw pp
phases and diagnostic source locations. Execute only curated defined programs,
never null dereference/call/arithmetic. Use host C NULL only in separately labelled
cross-object ABI helpers, both directions, not as a replacement for the original
kcc nullptr program. Full regression/QBE, both-host sanitizers, fuzz and CI follow.
