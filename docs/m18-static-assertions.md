# M18b2: static assertions (design before implementation)

Consume the pure M18b1 integer constant evaluator in file-scope and block-scope
static_assert/_Static_assert declarations (N3096 6.7.11). Both spellings accept
C23's optional message. Assertions are declarations, including for-loop initializers, but not statements.
Structure members remain unavailable with the existing aggregate subset.

Grammar:
static-assert-declaration ::= ("static_assert" | "_Static_assert") "("
    conditional-expression [ "," ordinary-string-token { ordinary-string-token } ] ")" ";"
Parenthesized full expressions still parse normally and sema enforces ICE rules.
A bare assignment/comma cannot consume the declaration's message separator.
Lexical keywords are converted after macro expansion, not in the raw pp lexer.
No built-in macro definitions or header support are implied.

Use a concrete ast_static_assertion with location, condition and optional decoded
ast_string_expression message. Separate concrete external/block wrappers start
with their existing common list header and point to the assertion. This avoids
an untagged shared header or universal union. Constructors live in ast.c; parser,
sema and codegen remain single-file stages. Parser on-demand lookahead and current
expression/item/external/string quotas remain intact, including message storage.

Parse messages with the shared bounded ordinary-string concatenation decoder.
Message ASTs are diagnostic strings only: do not semantically turn them into
static data objects, consume local slots, bind identifiers or emit QBE. Sema checks
assertions in source order and the existing lexical scope, even after returns or
in branches never executed. Fully check the condition normally, then query ICE;
not_constant and invalid get the evaluator's located reason. Value zero fails
regardless of integer width; any other value passes. sizeof conditions remain
opaque to evaluation but semantically checked, including names in their operands.

A zero assertion emits a source-located failure and includes an optional quoted
message. Render decoded printable ASCII directly; quote/backslash and all other
bytes are escaped (hex for controls/NUL/high bytes), preserving embedded NUL and
preventing terminal/newline injection. Use a length-bounded arena buffer, not a
user-controlled printf format. Handle allocation failure explicitly. No call,
load, branch, string datum or runtime effect is emitted for a successful assertion.

Tests: both spellings and optional messages; concatenation/escape/provenance;
file/block scopes, local sizeof and function visibility in sizeof; macro names
remaining pp identifiers; all supported integer categories, negative/nonzero/high
unsigned values, short-circuit ICE arithmetic/comma rules; invalid arithmetic and
nonconstant forms are compile-only tests, never executed. Check malformed grammar,
for-init declaration acceptance and statement exclusion, unknown/late names, pointer operands, depth/item/
external limits, messages after NUL and no QBE symbol/message emission. Typed units
verify concrete AST/wrappers, inserted conversions, scope lookup and no local/data
allocation. Full regression/QBE, both-host sanitizers, bounded fuzz and CI follow.

Non-goals: enums/named constants/constexpr, floating ICE casts, typedef/aggregates,
generalized bounds, null conversions, static storage initializers or optimizer
folding. These must deliberately integrate this shared evaluator in later steps.

Grammar audit: N3096 6.7 includes static-assert-declaration in declaration, and
6.8.5 admits declaration in for clause-1 without excluding assertions. GCC 11
accepts this form; Clang 15 rejects it. Follow the draft, not the legacy Clang
parser, and explicitly label that exact host-oracle gap. This corrects the initial
planning assumption before the for-initializer implementation/tests.

CI oracle audit: exact-source cade2cd failed Clang CI run 38868636910 because
its host rejected the message's numeric \0 escape as an "unevaluated string
literal" escape. N3096 6.4.5 permits these escapes and 6.7.11 does not impose the
C++ unevaluated-string restriction. Keep kcc's decoded message behavior and all
256 diagnostic-byte checks. Recognize only that exact one-error host diagnostic
for the original numeric-message program, report an oracle gap, and do not count
it as a native agreement. The original source is still compiled/run with QBE;
other host failures remain failures. Do not rewrite the message or constrain C23
to satisfy a host compiler's C++ rule.

Follow-up: run 38877229675 passed the numeric-message check, then exposed a
second newer-Clang oracle policy: -pedantic-errors promotes -Wkeyword-macro on
the original pp defined/define/undef program. C preprocessing identifiers include
later keywords. After verifying only that exact single-error diagnostic, retry
the identical source with only -Wno-keyword-macro; still require native execution
and report the warning control. Never globally disable warnings or rewrite C.
