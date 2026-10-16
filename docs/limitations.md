# Implementation limitations

Current milestone: M14L3A automatic objects hiding typedef names. Read the latest entries together with README.md and
c23-coverage.md; earlier chronological entries describe their own checkpoints.

## M00

- No lexing, parsing, semantic analysis, preprocessing or code generation.
- Only `--help` and `--version` are accepted; C filenames are rejected.
- Tests cover driver behavior and deterministic random CLI arguments.
- Coverage-guided compiler fuzzing starts at M02; CLI random tests are not
  presented as parser/lexer fuzzing.
- CI is configured but a local test pass does not prove a GitHub run passed.
- No claim of C23 conformance or a provided C standard library.

Update this file at every milestone. Separate unsupported features from bugs
in features claimed as implemented. Document impact on other stages.

## M01

Source loading, locations, diagnostics and arenas are implemented and tested.
The driver still does not compile C input. Sources are limited to 16 MiB and
locations are byte-based, not Unicode display-width based. Line splicing and
encoding normalization belong to later translation-phase work. Source creation
requires a fresh or destroyed struct; initialization failure leaves it empty.
Arenas provide max_align_t alignment, not arbitrary over-alignment.

## M02

On-demand lexing handles ASCII identifiers, int/void/return keywords, decimal
integers, initial punctuation, whitespace and comments. No C compilation yet.
Other keywords are ordinary identifier tokens until their feature milestone.
String/character literals, preprocessing, splicing, Unicode identifiers,
nondecimal/suffixed/floating literals and most punctuation are unsupported.
The debug token dump may contain partial output on lexical errors; this is
not compiler IL output. Lexical errors always consume bytes; EOF is stable.
One-token cache keeps parsing independent of whole-file tokenization.

## M03

The first compiled subset is `int main(void) { return decimal_integer; }`.
The integer must fit a signed 32-bit int. Exactly one function and one return
statement; no expressions, variables or other functions yet. Syntax rejection
may stop before reading the rest of the file. There is no error recovery.
Parser owns no memory: the arena owns nodes and the source owns spellings.
Sema annotates types; QBE emission relies on those validated annotations.
The driver emits IL only; users invoke QBE and the host linker explicitly.

## M04

One `int main(void)` containing one `return` of an integer expression.
Supported: decimal int literals, parentheses, unary +/- and binary + - * / %.
No variables, function calls, multiple statements, preprocessing or other
types. Literal values must be <= INT32_MAX; larger literals need future
literal typing even when unary minus would produce an int-range value.
Signed overflow and division by zero retain C's undefined behavior; the
compiler does not invent trapping/constant-folding semantics. Tests execute
only defined programs, and fuzzing never executes generated code.

Nesting and structural AST depth are capped at 128. Sema and codegen rely on
that validated bound. Binary operands are emitted left then right; there are
no side effects in this subset. No claims of optimization or full C23 support.

## M05

One int main(void) with an ordered list of single-object int declarations,
returns, expression statements and empty statements. Initializers are optional.
Local identifiers, simple assignment and the M04 arithmetic subset are
supported. A declaration is visible in its own initializer; forward references
and same-scope redeclarations are errors. Assignment requires a modifiable
lvalue, has an rvalue result and associates right-to-left. Parenthesized names
remain lvalues. Keyword spellings cannot be declared as ordinary locals.

Nested blocks and shadowing are not yet supported. No comma declarations,
compound assignments, increments, if/else, calls, qualifiers or preprocessing.
One function-body scope; at most 256 locals and 4096 block items. Expression
limits remain 128 after sema inserts explicit lvalue-to-rvalue conversions.

Automatic objects without initializers are not zeroed. Reading an indeterminate
int may have undefined behavior; there is no definite-initialization analysis
or warning system yet. Tests execute defined programs only. Sema validates
unreachable source too, while codegen stops after the first return. Reaching
main's closing brace returns zero. These policies are explicit, not missing
semantic checks hidden in codegen.

## M06A

Nested compounds use scoped name bindings separate from the all-local slot list. Lookup walks parent scopes; redeclarations are checked only in the current scope. Combined statement nesting is bounded at 128 and block items are counted across the function.

Only int objects, one main(void), existing arithmetic and simple assignment
are supported. Still unsupported: if/else, comparisons, logical operators, loops, calls and preprocessing. No
zero-fill/definite-initialization analysis for uninitialized locals. Resource
limits: 16 MiB source, 128 expression and statement nesting/depth, 4096
function-wide block items, 256 function-wide locals. Tests execute defined C
only; fuzzing never executes source programs.

## M06B

A distinct if-statement AST node, nearest-if else binding, signed int comparisons, selection/substatement scopes and QBE branch/merge handling are implemented. Both branches are checked semantically. Termination propagates through nested blocks and conditionals; both-return paths have no dead merge block.

Only int objects, one main(void), existing arithmetic and simple assignment
are supported. Still unsupported: logical operators, loops, calls and preprocessing. No
zero-fill/definite-initialization analysis for uninitialized locals. Resource
limits: 16 MiB source, 128 expression and statement nesting/depth, 4096
function-wide block items, 256 function-wide locals. Tests execute defined C
only; fuzzing never executes source programs.

## M06C

Distinct logical-expression AST nodes lower &&/|| through conditional branches and phi values. Unary ! and all comparisons normalize int results to 0/1. The emitter records the current block label so nested RHS phi predecessors remain correct. Sema checks skipped operands too; codegen does not evaluate them at runtime.

Only int objects, one main(void), existing arithmetic and simple assignment
are supported. Still unsupported: loops, calls and preprocessing. No
zero-fill/definite-initialization analysis for uninitialized locals. Resource
limits: 16 MiB source, 128 expression and statement nesting/depth, 4096
function-wide block items, 256 function-wide locals. Tests execute defined C
only; fuzzing never executes source programs.

## M07A

While has a distinct AST node. Jump nodes record the nearest enclosing loop during sema. Scope and loop contexts are independent and restore their parents on failure too. QBE while continue targets the condition; break targets the exit. Only an unterminated body gets an implicit back edge.

One int main(void), int locals, existing arithmetic/assignment/comparisons and
short-circuit logic, scoped blocks and supported control statements. Unsupported:
do/while, for, function calls, comma/update/compound-assignment operators and preprocessing. There is no inference of nontermination or complete reachability
analysis. Jump constraints are checked even in dead source. Runtime tests use
bounded, defined programs; fuzzing never executes user loops. Source remains
limited to 16 MiB, expression/statement nesting to 128, block items to 4096
and locals to 256 per function. Automatic locals are not zero-filled.

## M07B

A distinct do-statement node executes its body before the condition. Continue targets the condition; break and return bypass it. Body scopes do not leak into the condition. Sema still validates unreachable conditions. QBE emits well-formed condition/exit blocks conservatively without claiming whole-loop reachability inference.

One int main(void), int locals, existing arithmetic/assignment/comparisons and
short-circuit logic, scoped blocks and supported control statements. Unsupported:
for, function calls, comma/update/compound-assignment operators and preprocessing. There is no inference of nontermination or complete reachability
analysis. Jump constraints are checked even in dead source. Runtime tests use
bounded, defined programs; fuzzing never executes user loops. Source remains
limited to 16 MiB, expression/statement nesting to 128, block items to 4096
and locals to 256 per function. Automatic locals are not zero-filled.

## M07C

A distinct for-statement node records optional initializer declaration/expression, condition and step. Initializer declarations are visible in condition/body/step but not after the loop. Continue executes the step before the condition; missing condition means unconditional iteration. All loop kinds preserve scoped local initialization, short-circuit conditions and nearest-loop jump targets.

One int main(void), int locals, existing arithmetic/assignment/comparisons and
short-circuit logic, scoped blocks and supported control statements. Unsupported:
function calls/prototypes/parameters, comma/update/compound-assignment operators, other types and preprocessing. There is no inference of nontermination or complete reachability
analysis. Jump constraints are checked even in dead source. Runtime tests use
bounded, defined programs; fuzzing never executes user loops. Source remains
limited to 16 MiB, expression/statement nesting to 128, block items to 4096
and locals to 256 per function. Automatic locals are not zero-filled.

## M08a

Ordered external declarations, compatible zero-argument prototypes and multiple int function definitions are supported. Sema installs canonical symbols in source order; calls resolve visible functions, respect local shadowing and reject duplicate definitions. QBE emits each definition independently and direct w-result calls; prototypes emit no IL.

Only int returns and `(void)` declarations; calls take no arguments. Parameters,
function values/pointers, local prototypes, storage classes, globals, other types
and preprocessing remain unsupported. Library translation units need no main;
declared but undefined functions are left to the host linker. Main fallthrough
returns zero; other functions have an ABI zero filler, not a promised C implicit
return value. No whole-function reachability/missing-return diagnostic.

At most 512 external declarations and 256 distinct functions. Previous limits
apply per function; local/loop contexts and QBE counters do not leak between
definitions. Semantic symbols contain backlinks; do not recursively traverse
them as ownership edges. Syntax/constraint failures produce no compiler IL.

## M08b

Integer parameter and argument lists are implemented with name-independent function signatures, source-order prototype visibility and argument-count checks. Parameters receive the first local slots and share scope with the outermost body declarations. QBE w entry values are stored into those slots; nested call arguments finish emitting before the call line.

Supported signatures: int return, up to 128 int parameters, up to 128 call
arguments. Prototype parameter names are optional; definition names are
required in this subset (C23 unnamed definition parameters are deferred).
Empty () explicitly means zero parameters, not an old-style unspecified list.
Only zero-parameter main is supported until pointer/argv work. Parameters count
against the existing 256-local function limit; 4096 body items do not count them.

Arguments are emitted left to right as an implementation choice, not a C
sequencing guarantee. Runtime/differential tests do not depend on unspecified
ordering or execute unsequenced undefined behavior. No variadics, pointer calls,
function values, globals, local prototypes, storage classes or preprocessing.
Functions are externally visible; unresolved declarations reach the linker.
Non-main fallthrough filler is not a promised defined return value.

## M08c

M08b's supported syntax and limits remain unchanged. Direct/mutual recursion is
validated through bounded executable tests. Integer System V ABI acceptance now
includes separate host/kcc objects, both call directions, register/stack
arguments through 128, signed int boundaries and cross-compiler recursion.
This is not aggregate, pointer, floating, variadic or complete C23 ABI coverage.
No language-level recursion limit or runtime stack guard is added; real programs
can exhaust their runtime stack. Fuzz inputs are compiled but never executed.

CI runs the integer ABI harness with GCC and Clang and sanitized compiler builds.
Parameter mutation affects the local copy, not the caller's int object. Ordinary
argument sequencing still follows C's rules; left-to-right lowering is not a
portable source guarantee. Earlier M08b restrictions still apply, including
named definition parameters and zero-parameter main.

## M09a

Explicit source preparation implements newline normalization and line splicing,
not full preprocessing. Input accepts LF, CRLF and lone CR as line endings.
Only backslash immediately followed by a normalized newline splices; no
whitespace-tolerant extension. A forward pass over physical units does not
rescan output, preserving the last-backslash-only rule. Splicing precedes
comment/token recognition. Comments still separate tokens. No trigraph rewrite.

Prepared data/length and token offsets/lengths are logical. Diagnostics and
--tokens start offsets map to original physical positions. Changed sources
retain raw bytes and a sparse offset map; unchanged sources need neither extra
buffer nor map. At the 16 MiB raw limit, additional storage is bounded by one
logical buffer and at most one checkpoint per offset-changing event. Lone CR
normalization creates no offset checkpoints. No per-token allocations/vector.

Missing final newlines and final splices continue as acceptance extensions;
strict final-line validation and complete encoding/UCN/BOM behavior are deferred.
No preprocessing-token separation, directive handling, macro expansion/includes,
#line presumed locations or macro expansion provenance yet. These are not
implemented by running the host preprocessor. All M08 language restrictions
still apply. source_prepare must run before borrowing any source spelling.
Allocation-failure behavior is handled transactionally but fault-injection tests
remain future work. Fuzzing compiles arbitrary inputs, never executes them.

## M09b

Raw pp tokens are now a distinct on-demand stream, with no numeric values or
keyword classification. Numbers use ASCII pp maximal munch, not early integer
validation. Quoted literal boundaries, prefixes and escaped delimiters are
scanned; this is boundary recognition, not full literal grammar/escape validation.
All C23 punctuators are recognized raw. Language conversion still
supports only the existing int subset and rejects other literals/operators.
Brace digraphs <%/%> map to existing braces. This is not full C23 token support.

Raw streams retain external newlines, leading horizontal/comment spacing,
line-start state and VT/FF trivia metadata. Block comments, including their
internal newlines, replace one space and do not split directives. VT/FF are not
rejected as ordinary whitespace; the metadata is for M09c's directive checks.
Spacing does not claim original whitespace reconstruction. --pp-tokens prints
raw kinds/metadata, not expanded text or C tokens. It can succeed on a numeric
spelling or keyword macro body that the compiler cannot yet consume.

The temporary language adapter discards raw newlines and converts lazily, still
rejecting every directive. No header-name lexical context, UCN/Unicode identifier
support, encoding/escape-value validation, string concatenation, macro expansion,
#include, #line or expansion provenance. Prepared logical spelling and physical
location mappings remain the only provenance. No additional token allocation or
whole-file materialization; all source and AST limits remain in force.

## M09c

The real preprocessor facade owns parser input; no temporary language lexer
wrapper remains. Only null #/%: directives are supported. Other standard names
(including pragma/error/warning), unknown names, malformed directives and
misplaced markers explicitly fail. This is not macro expansion or a complete
preprocessor, and no host preprocessor is invoked. The parser's supported C
subset is unchanged; empty translation units still fail after null removal.

VT/FF before a marker is allowed, but after it outside comments is rejected
using leading-trivia metadata. Such diagnostics point at the following raw
token or terminator, not the exact whitespace byte. EOF is accepted as a null
directive terminator under the existing missing-final-newline extension. Comments
are one replacement space; their internal newlines do not end directives.
Failed directive lines drain as raw tokens before one nonempty invalid language
token is returned; distinct raw lexical errors may add diagnostics. Debug
inspection can continue after a failed line; this is not general parser error
recovery. Compilation rejects errors before emitting any IL.

All earlier source/token/int-language restrictions remain. No definitions,
#undef, conditional sections, include/header-name context, #line, macro expansion
provenance, complete Unicode/UCN/encoding/literal handling or final-line constraint
validation. Raw/processed streams remain on demand with bounded source buffers;
this slice adds no token allocation or macro expansion state.

Diagnostic line/column lookup currently rescans physical source prefixes. Many
lexical errors in one drained line or a debug dump can therefore take
superlinear time; there is no diagnostic-count cap yet. Source size is bounded,
and fuzz cases use their existing input/time limits, but this is not a hostile
large-input CPU guarantee. Review this diagnostic interaction when setting M10
macro expansion/resource budgets.


## M10a

Object-like definitions/undefinitions and rescanning are supported; the earlier
M09c "no macro" limitations are superseded for this slice only. Null directives
remain supported. Macros can replace keywords, numbers, names and punctuation,
including empty replacement lists. Unused unsupported literal spellings are
stored without conversion. Definition/undefinition errors preserve old bindings.
Only raw source markers dispatch directives; generated markers never do.

No function-like definitions/arguments, variadics, stringizing, token pasting,
predefined macros, includes, conditions, pragmas, #line or diagnostic directives.
Function-like definitions and ##/%:%: diagnose explicitly. Define/undef of defined
or implementation-reserved __.../_Upper... names is outside this slice and
rejected. This is a deliberate subset policy, not a claim those uses all violate
the same C23 constraint. Ordinary keywords are allowed as macro names.

Limits: 1024 distinct names including inactive identities, 1024 tokens per
replacement, 65536 arena-retained tokens across attempted definitions (including
compatible duplicates), 128 active frames and 65536 expansion work units per TU
(one push or replacement-token visit). #undef does not reclaim storage. Failures
of limits/allocation latch EOF after one invalid token. Allocation failure paths
are handled but not fault-injection tested. Raw source scanning/diagnostic prefix
rescanning retain their earlier bounds/caveats; these work limits do not promise
a hostile large-input CPU bound. There is still no diagnostic-count cap.

Spelling and outermost invocation locations are distinct. Full expansion-chain
notes, presumed #line positions and header/source stacks remain absent. Object
recursion suppression uses active frames and is tested against GCC/Clang; do not
reuse this as a full function-argument availability/hide-set implementation.
All prior language/type/ABI/encoding restrictions remain; no full-C23 claim.


## M10b

Object plus zero-parameter function-like macros work. No named/variadic
parameters, nonempty invocation arguments, argument prescan or substitution.
Even argument tokens expanding to nothing reject in this slice. Stringizing,
pasting, predefined macros, headers, conditions, #line, non-macro directives and
full expansion-stack notes remain unsupported. All prior C-language/type/ABI
and encoding restrictions remain; there is no full-C23 conformance claim.

Source directives encountered while probing a function invocation/delimiters
are explicitly unsupported; that is a subset policy, not a claim all such
arrangements have undefined behavior. A later object producing '(' does not
retroactively invoke an emitted name. Malformed invocations stop once then latch
EOF. Definition errors remain transactional with line draining. Raw-invalid
lookahead keeps its existing diagnostic without a duplicate.

Token-carried fixed hide sets supersede active-frame suppression. The tested
name/closing-delimiter intersection policy matches both hosts for this subset;
full arguments must preserve/combine per-token availability too. Some C23 rescan
edge cases have unspecified behavior; a unique ISO result is not claimed for
all of them. Macro IDs remain stable through undef/redefine. Depth counts retained
streams, not completed calls. Prior storage/work/source limits and diagnostic
prefix-rescanning caveats remain; no hostile large-input CPU guarantee, error
count cap or allocation-failure injection tests have been added.


## M10c

Fixed parameter lists/arguments, empty arguments, isolated lazy prescan and
suppression-preserving substitution are supported. No variadic definitions,
__VA_ARGS__/__VA_OPT__, stringizing or pasting. No new non-macro directives,
includes/conditions, predefined macros, #line, complete encoding/literals or
full expansion-chain notes. Existing C-language/type/ABI restrictions remain.

Only parentheses protect commas during raw argument collection. Arity is checked
before expansion. Unused arguments are collected/lexed but not macro-expanded;
unsupported language literals may be discarded before final conversion. Source
directive lines during probing/collection explicitly fail; inline # tokens may
be discarded like other raw argument tokens. No speculative directive execution.

Limits added: 128 parameters, 128 nested argument parentheses, 64 active argument
prescans, 65536 retained auxiliary records across parameters, argument array
entries and raw/cached token copies. Rejected/duplicate definitions and completed
invocations do not reclaim arena records. Existing definition-token, name, frame,
source and work limits remain; work also covers argument collection/copying/
prescan/injection. Temporary heap cursors are released on all paths. Fault
injection is not tested. Diagnostic prefix rescanning and other earlier hostile
large-input caveats remain; these are subset policies, not a conformance claim.

Substituted diagnostics use the outermost call, with original spelling retained.
This is not enough provenance for every future predefined-location macro case;
M25 must review __LINE__/__FILE__ semantics rather than reuse diagnostic offsets.
Some rescan cases have unspecified C23 behavior; oracle agreement is scoped
validation, not proof of a unique ISO result or complete preprocessing.


## M10d

Variadic definitions/invocations, __VA_ARGS__ and __VA_OPT__ are supported.
C23 omitted tails and explicit empty tails are accepted; optional regions use
expanded emptiness, so a macro expanding to nothing suppresses them. Variable
arguments retain internal separating commas. Nested optional regions and
malformed definitions reject even if unused. Earlier fixed/object macros remain
supported. GNU named ellipses/comma swallowing, #/##, includes/conditions and
other directives, predefined macros and full C23 preprocessing remain absent.

The named parameter cap remains 128, with one additional variable argument slot.
That slot and raw/cached copies share the 65536 auxiliary-record budget. Definition
and expansion work/frame/prescan/parenthesis/source bounds remain unchanged.
Flat optional annotations allocate no extra records and require no recursive
parsing. Without #/##, optional emptiness emits no tokens; future operators need
placemarker semantics. Raw strings and unsupported C literals can only be stored
or discarded, not compiled merely because macros now accept them.

The parser, sema and QBE interfaces are unchanged: variadic C functions/ABI,
other types/operators, encoding/Unicode/header-name context and full provenance
remain future work. Source directives during invocation lookahead still reject.
Location caveats, unspecified rescan cases, diagnostic prefix scanning and lack
of allocation-failure injection remain as documented above. Oracle agreement
and bounded fuzzing are not a full-conformance or hostile-input CPU guarantee.


## M11a

Raw named/variadic parameter stringizing with #/%: is supported, including
inside selected __VA_OPT__ bodies. #__VA_OPT__ itself remains explicitly
unsupported until M11b. Token pasting, includes/conditions and other directives,
predefined macros, C string expressions/concatenation and the remaining language/
ABI work are not implemented. The expanded-pp test API can inspect generated
strings; that is not language string support. Defined QBE tests generate then
discard strings before conversion, rather than pretending they execute strings.

Generated spellings use arena-owned source views, not slices of the input.
Views share the auxiliary-record limit; buffers including terminating NULs share
a cumulative 1 MiB byte cap. Existing work/storage/prescan/source limits remain.
Raw-token stringizing visits consume work; byte measurement/filling is bounded
by the synthesized byte cap. No allocation-failure injection or hostile-input
CPU guarantee has been added. Consumers must honor the view lifetime and not
call source_destroy on borrowed spelling views. Diagnostics remain outermost
original invocation locations, not a full expansion provenance stack.

Quoted-token quotes/backslashes are escaped; raw nonliteral backslashes are
rejected in the no-UCN subset rather than producing an invalid string. UCN and
complete quoted-literal validation remain later lexical work.

Two-level stringizing exposes observed GCC 11.5 / Clang 15 whitespace differences.
kcc currently follows GCC: preserve separation left by removed internal macros;
ignore whitespace solely inside __VA_OPT__ delimiters. The five policy groups
are isolated from agreement tests and record both observed outputs. This is not
a claim of ISO implementation-defined permission or a settled conformance ruling.
Review the interpretation during the later standards audit; portable programs
should not rely on these disagreeing whitespace cases. Earlier diagnostic prefix
scanning, source-directive lookahead and rescan/provenance caveats still apply.


## M11b (current)

#__VA_OPT__(body), including %:, is supported without token pasting. Selected
bodies receive parameter substitution and inner stringizing, not ordinary body
macro rescanning. Inactive bodies yield "" without named-argument expansion.
The implementation deliberately does not stringify raw operator syntax or use
a full expansion cursor that could consume later tokens. All prior raw # forms
remain supported. Nested optional constructs in one definition remain invalid.

A new limit permits 32 active optional-substitution cursors, independent of the
64 argument-prescan cap. Their heap storage is freed on all success/error paths.
Collected body tokens share auxiliary/work budgets; inner/outer string buffers
share the cumulative 1 MiB spelling cap. Existing source/definition/frame bounds
still apply. Limits are explicit subset policies, not full-C23 conformance.
Allocation-failure injection and hostile-input CPU guarantees remain absent.

Token pasting/placemarker operations, includes/conditions and other directives,
predefined macros and full encoding/literal grammar remain unsupported. C string
expressions/concatenation and other language/ABI features remain later work;
expanded-pp tests and stringize-then-discard QBE programs do not enable them.

The five earlier whitespace disagreements remain tracked. A separate policy
covers wrong-arity macros in named arguments used only by an inactive stringized
optional body: kcc is lazy like Clang 15; GCC 11.5 diagnoses. No cross-host
agreement or ISO permission is claimed for that disagreement. Preserve these
interpretation/conformance audit gaps when implementing token pasting.

## M11c

Token pasting is implemented for object/function replacements, digraph operators,
raw parameter boundaries, empty argument placemarkers and optional regions.
Invalid operator placement is diagnosed before replacing a macro definition.
Invalid concatenations diagnose at the original invocation. Paste order is
left-to-right (the standard leaves the order unspecified). No GNU comma removal.

Only paste-bearing invocations materialize bounded replacement lists; ordinary
expansion remains streaming. Paste-range nesting is limited to 32; generated
spellings share the existing cumulative 1 MiB limit. Generated identifiers,
keywords, numbers and punctuators have compilation-lifetime spelling ownership.
The language converter still rejects unsupported numeric/string expressions.

The C23 H4 optional-paste example retains internal placemarkers until outer
pasting completes. GCC 11.5 disagrees for F(,1); Clang 15 and kcc match N3096
6.10.4.1. This is tested separately, not counted as host agreement. The inherited
five whitespace policies and inactive-argument diagnostic policy remain separate
conformance audit gaps. Includes, conditional/diagnostic directives, predefined
macros and complete C23 remain unsupported.

## M11d

#error and C23 #warning are implemented, including digraph markers. Diagnostic
bodies retain raw preprocessing-token spellings without macro expansion;
comments/spacing become single separators while adjoining tokens stay adjoining.
Warnings are counted separately and do not prevent compilation. #error emits a
recoverable invalid token, but compilation emits no IL when any error occurred.
Malformed lexical input and forbidden directive whitespace are rejected before
a user message is emitted. A temporary diagnostic buffer is bounded by remaining
source length plus prefix, immediately freed; it does not use the 1 MiB generated
macro spelling budget. Conditional exclusion is not implemented in this batch.

## M11e

#ifdef/#ifndef/#elifdef/#elifndef/#else/#endif select source groups with a bounded
128-entry stack. Macro names are not expanded, and a macro defined as 0 still
counts as defined. Excluded text bypasses macro expansion and C token conversion;
raw lexical errors remain errors. Excluded definitions, diagnostics, includes and
unknown directives have no effects. Nested excluded #if expressions are balanced
without evaluation. Active #if/#elif evaluation remains explicitly unsupported.

Orphaned/duplicate/misordered controls, bad evaluated operands, trailing tokens
on else/endif and unterminated groups diagnose. EOF reports an open group once
then remains stable. Existing directives-during-macro-invocation-lookahead
restrictions remain; no include-source stack or predefined macros yet.

GCC 11 lacks C23 elifdef/elifndef: it ignores those names in excluded groups and
rejects them in active groups. Four explicit C23 branch cases are independently
asserted, not counted as GCC host agreement. Newer hosts must agree; legacy
expectations are restricted to the observed GCC 11 outputs/statuses.

## M11f

#if/#elif evaluate decimal signed-64 preprocessing arithmetic, parentheses,
unary + - !, * / %, + -, comparisons/equality and short-circuit &&/||. Literal
defined forms test unexpanded macro names; other identifiers become zero, with
C23 true/false treated as 1/0. A defined identifier produced by macro expansion
is explicitly diagnosed instead of guessing at undefined standard behavior.

Unsigned/suffixed/nondecimal literals, characters, shifts/bitwise and ?: are
not supported in this increment. These are expression-subset limitations, not
full C23 preprocessing claims. Malformed and unsupported expressions diagnose.
Only arithmetic evaluation, not macro expansion or syntax checking, short
circuits. Signed overflow, zero division and MIN/-1 are checked without host UB.
Raw expression lines are limited to 1024 pp tokens and syntax nesting to 128;
macro expansion retains all earlier storage/work/owned-spelling limits.

## M11g

The signed preprocessing-expression subset now includes unary ~, << >>, & ^ |,
and right-associative ?: with standard precedence. Ternary operands still parse
and expand, but only the selected branch is evaluated. Shift counts must be
0..63, and evaluated signed left shifts require nonnegative input and a
representable result. Negative right shift follows the target arithmetic policy,
implemented without host negative-shift assumptions. No change to runtime C
expression operators or types. Unsigned/nondecimal/character literals and full
preprocessing remain unfinished in this increment.

## M11h

#if/#elif accept signed octal/hexadecimal/binary integers, C23 digit separators
and signed l/L/ll/LL suffixes, in addition to decimal. Separators must lie between
valid base digits. Missing digits, invalid base digits, unknown/mixed-case
long-long suffixes and uint64 accumulation overflow diagnose explicitly.
All supported values still fit INT64_MAX. Unsigned suffixes and nondecimal values
requiring uintmax_t remain unsupported; no wrapping or negative reinterpretation
is substituted for their missing semantics. Character and bit-precise literals
remain later work. Runtime C expressions remain int/decimal-only as before.

Seven C23 separator values are asserted independently. GCC 11 rejects the new
spelling, so these cases are not counted as GCC agreement; Clang accepts them.
Known legacy behavior is checked explicitly, rather than accepting arbitrary
host differences. Other common literal cases compare directly with both hosts.

## M11i

Preprocessing expressions now model both signed intmax and unsigned uintmax
(64 bits on the chosen target), including U suffix combinations, large
nondecimal constants, usual conversions, modulo unsigned arithmetic and ternary
common type from both branches. Shift result type remains the left operand's;
comparison/logical results are signed 0/1. Signed error checks and short-circuit
syntax/resource behavior are preserved. Decimal constants without U still must
fit INT64_MAX; all spellings must fit UINT64_MAX before evaluation.

This does not implement C runtime unsigned integers, character constants,
_BitInt suffixes or include handling. Character/encoding/predefined-macro work
remains explicit. A uint64 storage representation is not a full-C23 claim.

## M11j

Preprocessing conditions accept ordinary single-byte ASCII character constants
and standard simple/octal/hex escapes. Numeric escapes must fit 0..255; target
signed plain-char interpretation sign-extends bytes 128..255 into intmax.
Preprocessing character values intentionally match that narrow target policy.
Empty/multicharacter, prefixed L/u/U/u8, non-ASCII source bytes, universal names
and unknown escapes diagnose rather than receiving guessed values. This does
not add runtime C char types/character expressions or general encoding support.

## M11k

Direct, unprefixed, nonempty quoted includes load absolute paths or resolve
relative names against the including file's directory. Macro-computed names,
angle names, -I/system search, backslashes/escaped names and general header-name
lexing remain later work. Excluded includes perform no loading. Source loading
is opt-in; the default preprocessor cannot open files. Driver and pp oracle use
file loading, while pipeline fuzzing uses a memory-only callback.

Child sources are retained until compilation ends for borrowed spelling/location
ownership. Active includes are capped at 32, attempts at 128, cumulative child
raw bytes at 64 MiB and constructed paths at 4096 bytes including the terminator;
each loaded source retains the earlier 16 MiB limit. File EOF is not transparent
to macro invocation probing: incomplete calls cannot continue into a parent.
Conditional groups cannot cross file boundaries. Root public EOF stays stable.
These are bounded subset semantics, not a claim of complete C23 include search.

## M11l

Quoted include operands may be macro-computed, including aliases, function
arguments, stringizing/pasting and optional replacements. The raw operand line
is bounded to 1024 pp tokens and rescans in isolation, with shared macro limits.
The result must be exactly one nonempty unprefixed quoted token; it is not C
string concatenation. Relative search remains anchored to the #include source.
Angle names/search paths, system headers and general header-name encoding remain
unimplemented. Backslashes in names retain M11k's explicit rejection policy.

Failed expanded operands never consume the following source line or call the
loader. Directive tokens keep individual invocation diagnostics instead of all
pointing at #. Malformed raw quoted text now produces its lexical diagnostic
without an extra obsolete unsupported-directive error; this intentional change
is regression-tested separately from expansion-format errors.

## M11m

Up to 32 explicit -I directories (attached/separate options) are searched in
order. Quoted names try the including source directory first; angle names use
only configured directories. Absolute names bypass both lists. Empty directory
strings mean cwd, and resolution never changes cwd. No default system include
paths, compiler-provided headers, -iquote/-isystem or environment variables yet.
One logical include uses one of the existing 128 attempts, with at most 33
loader candidates. Failed candidates are destroyed before retrying; preparation
and retained-byte failures after successful loading are fatal. The loader's bool
interface does not distinguish missing files from other open/read failures.

Direct angles bypass macro expansion; computed names rescan in isolation.
Angle paths currently allow only ASCII letters/digits/_./-+ with no internal
whitespace/comments, backslashes, quotes or other punctuation. This explicit
subset is not contextual header-name lexing. Direct quoted tokens retain the
M11l trailing-empty-macro extension pending a final header-context audit.
All prior source-lifetime, macro EOF, conditional-base and diagnostic contracts
remain. The directory list and strings are borrowed until destruction.

M11l's first sanitizer matrix exposed a GCC format-overflow warning in a test
fixture builder, not a compiler-source failure. Repair 37857c4 uses explicit
bounded writes; original 0ffd06c verification is not claimed successful.

## M12a

Runtime expressions now support unary ~ and binary & ^ | << >> with C precedence
and associativity. Operands/results remain signed 32-bit int; promotions are
identity, and sema still inserts explicit lvalue loads. QBE uses word bitwise
instructions, shl and arithmetic sar. Negative right shifts follow the chosen
arithmetic target policy. Shift counts outside 0..31, negative signed left-shift
operands and unrepresentable signed left-shift results are not defined by this
subset. No constant UB checker or runtime shift masking guarantee is claimed.

Other integer types/literal spellings, explicit conversions/casts and compound
assignments remain later increments. Existing AST depth, symbol/type validation,
short-circuit effects and ABI contracts are unchanged. Tests compare full 32-bit
values inside C, not just exit-status low bits, using defined generated inputs.

## M12b

lex.c now owns a pure bounded integer spelling decoder shared by language
conversion and preprocessing. It returns base/value/U/long-count metadata and a
static error string, without diagnosing, allocating or selecting a type.
Preprocessing applies unchanged intmax/uintmax semantics; spelling diagnostic
wording is now context-neutral (e.g. unsupported integer suffix), with original
invocation locations preserved. Character decoding remains independent.

Runtime unsuffixed decimal/octal/hex/binary literals and C23 separators are
accepted only when each literal fits signed 32-bit int. Valid U/L/LL suffixes
still diagnose as unsupported until typed runtime support. Nondecimal high-bit
values cannot silently become signed int; unary minus does not rescue a positive
literal requiring a wider type. No declarations/types/ABI change is implied.
GCC 11 separator rejection is counted separately, with model/QBE and Clang
coverage rather than being mislabeled host agreement.

## M12c

Runtime signed/unsigned 32-bit int declarations, parameters and return types are
supported, with int/signed/unsigned specifiers in either valid order and no
repeated/conflicting specifiers. main still requires signed int and no args.
U literals fit UINT32_MAX; unsuffixed nondecimal picks int then uint, while
unsuffixed decimal still must fit INT32_MAX. L/LL and wider types remain absent.

Sema introduces explicit int/uint conversion nodes for usual arithmetic,
assignment, initialization, calls and returns; loads retain object type.
Comparisons/logical results remain int, shifts retain left type. Both types have
identity promotions. Unsigned arithmetic wraps modulo 2^32 and signed/unsigned
conversion preserves target two's-complement bits; signed overflow/invalid
shifts remain undefined inputs. QBE selects unsigned division/remainder,
comparisons and logical right shift from operand types, never spelling.

Function compatibility distinguishes signed/unsigned signatures; slots and ABI
remain four-byte/QBE word. Typed depths include all newly inserted conversions.
No explicit cast syntax, other integer ranks/promotions, void objects/returns,
float/pointer types or full C23 claim is included in this increment.

## M12d

Explicit (int), (signed [int]), (unsigned [int]) and int signed/int unsigned
casts now produce distinct concrete cast nodes, separate from sema-inserted
conversions. One-token parsing consumes an opening parenthesis before selecting
type syntax or a grouped expression. Shared postfix suffix parsing preserves
named calls through groups; cast operands bind at prefix power. Parenthesized
expressions retain their prior AST identity/lvalue behavior, while casts never
produce lvalues. Sema value-loads operands, assigns requested types and checks
post-load depths. QBE word copies preserve the implemented 32-bit bit pattern.

No void/wider/pointer casts, compound literals or typedef-name disambiguation is
included. Those need their respective future grammar/type milestones. C casts
do not define signed-overflow/invalid-shift programs or relax literal typing.

## M12e

Signed/unsigned long are distinct 64-bit LP64 types, with optional int/sign
specifier orderings and U/L literal suffixes. Long long/LL remain explicit later
work. A central target property table drives widths/ranks/signedness; candidate
lists select the first representable implemented literal type without truncation.
Unsigned decimal literals can select ulong, while unsuffixed decimal beyond
INT64_MAX still fails. Mixed long+uint selects signed long; long+ulong selects
ulong. Narrowing and unsigned-to-signed follow target two's-complement bits.

AST conversion nodes now lower to signed/unsigned extension from 32 bits, low-
word narrowing, or same-width bit copies. QBE width selection covers arithmetic,
comparisons, slots, parameters/returns, calls and shift counts. Every condition
normalizes its whole word/long value before branching; a high-only-bit long is
true. Long/ulong storage is eight bytes with eight-byte alignment. No char/short,
long long, floats, pointers or full C23 claim accompanies this increment.

## M12f

Signed/unsigned long long have distinct type identity and rank above long, though
all four long types use 64-bit LP64 values. Declaration permutations allow two
long specifiers, never three. Runtime LL/ULL suffixes now participate in standard
candidate selection; mixed lL/Ll remain malformed. Decimal magnitudes exceeding
INT64_MAX without U remain unrepresentable. Equal width never makes long and
long long function signatures compatible. Shared QBE width/storage/ABI machinery
needs no new instruction selection for these types.

Ordinary runtime character constants, char/short, floating types and pointers
remain absent. M12g character constants are designed separately. Earlier LL
rejection fixtures now use malformed LLL or unsupported floating literals; their
diagnostic purpose and invocation locations remain covered.

## M12g

Ordinary character constants now produce int expressions with their own concrete
AST nodes. Preprocessing and runtime share a pure explicit-slice decoder in lex.c:
one ASCII character or simple/octal/hex escape <=255, with signed plain-char
target interpretation (-128..127). Prefixes, multi-character constants, Unicode/
UCN, non-ASCII source bytes, oversized escapes and strings remain unsupported.
This implementation-defined character policy is tested using hosts configured
with -fsigned-char; it is not a claim about every C implementation's encoding.

The decoder rejects empty/truncated/unclosed slices before indexing, embedded
NUL/newline/unescaped quote bytes and unknown escapes. Diagnostics are context-
neutral, preserving macro invocation locations. Character constants are never
lvalues. Char/short declaration types are still absent; M12h char types and
promotions have a separate design and successful QBE byte-ABI mechanics probe.

## M12h

Plain char, signed char and unsigned char are distinct 8-bit types; plain char
is signed on this target. Optional sign may precede/follow char, but char cannot
combine with int/long or duplicate itself. Ordinary character constants remain
int. Unary arithmetic and each binary/shift operand promote byte types to int;
assignment/init/fixed arguments/returns retain exact declared byte types.

Values are canonical in QBE words: signed bytes sign-extend, unsigned bytes
zero-extend. Narrow casts/conversions normalize low bits; byte-to-long extension
uses source signedness. Byte calls use sb/ub and immediately normalize return
values because upper bits are unspecified. Parameters spill their low byte and
loads use loadsb/loadub; stores use storeb. Local slots use alloc4 1 with stronger
stack alignment, not a claim that the C byte type has alignment 4. No pointer/
aggregate layout exists yet. Signed narrowing follows the target two's-complement
low-byte policy, tested against these hosts.

Short/bool, floating types, pointer types and full C23 remain absent. Byte ABI
tests include both-direction eight mixed arguments and assembly returns with
deliberately dirty upper bits; same-compiler-only calls are not the sole oracle.

## M12i

Short and unsigned short are distinct 16-bit LP64 types with rank between char
and int; short/signed short alias the same type. A single short combines with
optional int/sign in any order, never char/long or a second short. Both promote
to int, so unsigned short 65535+1 is signed int 65536, not wrapping halfword math.
Literal candidate lists remain int and larger; short is not a suffix type.

Halfword values are canonical QBE words. Narrowing uses extsh/extuh; sh/uh ABI
results normalize immediately, memory uses loadsh/loaduh/storeh and two-byte
locals use stronger alloc4 alignment. C short alignment remains 2 for future
layout. Byte/halfword crossings honor source sign extension before target low-
bit conversion. Signed narrowing retains the documented target bit policy.

Bool, enums, extended/bit-precise integers, sizeof/alignof, floating and pointers
remain unfinished. Other expression operators and full C23 are not implied by
adding the standard integer ranks.

## M12j

_Bool is a distinct unsigned integer type, rank below char, storage one byte and
only values 0/1. It promotes to int. Declaration syntax accepts _Bool alone, not
signed/unsigned/char/short/int/long combinations. Conversions and casts from any
implemented integer compare the complete source value to zero: 256 and a high-
only-bit long become 1, not 0. Every operand is evaluated once.

Byte memory and ub ABI carry canonical 0/1. Narrow ABI return normalization drops
unspecified upper register bits before any truth/cast/use; that boundary operation
is deliberately different from full-value scalar-to-bool conversion. Test dirty
ABI values have valid low-byte 0/1; invalid boolean object representations are
not made defined by this implementation. Bool is incompatible with unsigned char.

C23 bool/true/false language spellings remain planned M23a; #if true support was
already implemented separately. Enums, bit-precise integers, remaining operators,
sizeof/alignof, pointers and floating types remain future milestones. Supporting
_Bool does not imply a provided stdbool.h or a complete hosted C23 environment.

## M13a

Integer-object pointers and pointers to such pointers support local objects,
fixed parameters/returns, compatible assignment/initialization/casts, passing/
returning values and scalar truth, including conversion to _Bool. Pointer width/
size/alignment is eight bytes on the selected target. Referent compatibility
is recursive; int*/unsigned*/char* are not interchangeable.

Restricted type-name grammar is integer-type followed by up to 64 stars, with
a name appended in declarations. Concrete AST integer/pointer syntax nodes
resolve/cache a separate semantic type graph. A shared scalar-width helper
serves pointers without treating them as unsigned integer ranks. QBE uses long
values/storage/ABI; integer promotion helpers reject pointer operands first.

No address-of/dereference, arithmetic/comparison, integer-pointer conversion,
null pointer constant, void/function pointer, qualifier, array or parenthesized
declarator support yet. Even zero is not silently accepted as a pointer; null
constant semantics need their own increment. Host-driven tests supply real
live objects and valid host-created null pointers to exercise this subset.
Uninitialized/dangling pointers are never executed to fabricate test coverage.

## M13b

Address-of object lvalues and indirection through implemented object pointers
are supported. Dereference yields a modifiable lvalue; value contexts insert
explicit loads. Assignment through pointers converts to the referent type first,
including signed/unsigned byte/halfword storage and 0/1 boolean normalization.
Pointer-to-pointer objects can be loaded/assigned indirectly.

General lvalue-address lowering separates address computation from memory loads.
&*E evaluates E once without a pointee load, even for a host-supplied null pointer.
Actual dereference of null/dangling/uninitialized pointers is still undefined,
never executed by tests. Address-of rvalues and indirection of integers diagnose.
Operand evaluation uses a C-permitted order; unspecified relative order is not a
new promise. Function designators/pointers and qualifiers remain unsupported.

Typed-expression limits include inserted dereference loads: a 63-layer parameter
with 63 dereferences reaches depth 128; 64 exceeds it despite legal type syntax.
The separate declaration/cast pointer-syntax limit stays 64 layers. Inferred
address types may extend a declared type; expression depth bounds that growth.
Pointer comparison/arithmetic, null constants and arrays/strings remain later work.

## M13c

Equality/inequality compare full-width values of recursively compatible object
pointers and produce int. Operands load once without integer promotion or rank
queries. Host-supplied null pointers compare correctly, including deep pointer
values. Source null pointer constants and void-pointer compatibility are still
unsupported. Ordering/arithmetic remain next; unrelated live object equality is
not confused with an integer comparison. No lifetime or dereference rule changed.

## M13d

Object pointers support p+n, n+p and p-n with any implemented integer type;
indices undergo integer promotion. Compatible p-q produces target ptrdiff_t
(signed long). All six compatible pointer comparisons produce int. Target
scalar object sizes are explicit (1/2/4/8 bytes); pointer referents stride eight,
not the size of their ultimate pointee. No language sizeof or array declarations
are added. Arithmetic/comparison operands are each evaluated once.

Defined pointer arithmetic/order requires the same live array, including its
one-past position; a scalar acts as a one-element array. One-past may be formed
but not loaded/stored. Unrelated subtraction/order, out-of-bounds arithmetic and
nonrepresentable differences remain undefined; tests never execute them. No
runtime bound checks are promised. Null+0 is not silently made defined. Source
null constants, subscripting, array/string declarations, void/function pointers,
qualifiers and full declarators remain future work.

## M13e

Postfix subscripts support pointer[integer] and integer[pointer], with the same
integer promotions and complete scalar referents as pointer addition. Chained
pointer-to-pointer indexing, assignment results, address-of and alternating
call/subscript suffixes preserve normal precedence. Bracket digraphs <:/:> map
to the same language tokens; raw pp spellings remain unchanged.

Subscript syntax lowers to explicit pointer offset and indirection, then a load
only in value contexts. Address-of a one-past subscript computes its address
without loading it; invalid/null/out-of-bounds arithmetic and actual invalid
loads remain undefined and are not executed. Every lowering node/promotion/load
counts toward typed depth: 42 chained pointer subscripts reach depth 128, 43
exceed it. The parser separately bounds recursive index nesting. Local array
and string declarations, decay, null constants and full declarators remain later.

## M13f

Local arrays with one positive literal-token bound support every implemented
scalar element, including pointers. Existing base/suffix/separator spellings
and macro-expanded integer tokens work. This is deliberately not a general
integer constant-expression bound parser: expressions, VLA/incomplete bounds,
multiple dimensions, parameter array adjustment and all array/string initializers
remain unsupported. Uninitialized arrays are not implicitly zeroed.

Array types preserve count/element compatibility and target size/alignment.
Ordinary array expressions explicitly decay one level to pointer-to-element;
address-of retains pointer-to-array and scales by whole-array size. Subscripts/
indirection yielding arrays follow the same decay rule. Arrays are nonmodifiable
lvalues: assignment and initialization diagnose before scalar conversion helpers.
Full pointer-to-array declarator spelling remains unsupported despite inferred
&a types. No general object-pointer cast shortcut is introduced.

Per function, at most 1 MiB of declared object bytes is permitted, including
parameter spills and all nested scopes; the existing 256-local limit remains.
Overflow-safe size validation precedes multiplication. This resource budget is
not a C language limit or an exact bound on backend temporaries/padded frame size.
Slots allocate at function entry using target size and at least QBE four-byte
alignment. Tests initialize every executed element before reading it; large limit
fixtures are compile-only. Dangling array-pointer lifetimes are not made defined.

## M13g

Local literal-bound arrays accept up to 64 dimensions. Source-order bounds wrap
right-to-left into recursive array types: a[2][3] has two rows of three elements.
Leaves may be any implemented scalar/pointer type. Compatibility preserves every
bound and element type, even for shapes with identical byte counts. Ordinary
decay drops exactly one array level; &array retains the entire shape. Row and
whole-array pointer arithmetic use the correct complete referent size.

The 1 MiB declared-object budget and positive literal-only bounds remain. General
constant expressions, VLA/incomplete dimensions, parameter array adjustment,
initializers and full pointer-to-array declarators are still unsupported. Crossing
a row via an element pointer remains undefined even when storage is contiguous;
tests use proper row pointers and do not flatten a matrix into int**. The separate
64 pointer-syntax and 128 typed-expression limits remain. Fully indexing 42 unit
array dimensions reaches typed depth 128; 43 exceeds it.

## M13h

One ordinary unprefixed string literal is a static array of signed plain char,
with decoded ASCII/simple/octal/hex byte escapes and one implicit final NUL.
Embedded NUL is retained; ordinary value use explicitly decays to char*. Strings
can be indexed/passed/returned with static lifetime. Address-of retains the entire
array type. Raw non-ASCII/NUL/newline/CR, prefixes/Unicode/UCNs, adjacent literal
concatenation and all array/string initializers remain unsupported.

Literal modification is undefined and never tested; writable target data is not
a promise to permit it. Each occurrence has its own object; no inter-occurrence
equality/ordering/subtraction promise is made. Private unexported QBE symbols
cannot collide with C identifiers or separately compiled units. Target bytes
128..255 load as negative plain chars; explicit unsigned-char casts recover bits.

Before decoded allocation, parser limits one literal to 1 MiB decoded bytes,
all literal object bytes (including final NULs) to 8 MiB and objects to 4096 per
TU. These static-object budgets are separate from local storage. Every decay
counts in typed depth. Lexer measurement allocates no decoded token buffer.

## M13i

Adjacent ordinary string fragments concatenate after preprocessing, including
macro/comment/directive/include-separated fragments. Escapes decode independently
per token, embedded NULs remain and exactly one final NUL is appended. Postfix
indexing applies to the combined literal. One expression creates one static array,
not one per fragment; its location is the first fragment's invocation location.
Prefixes/Unicode/mixed encodings, array initializers and null constants remain
unsupported. No inter-occurrence pointer equality/order promise is introduced.

Existing 1 MiB decoded-result, 8 MiB total object-byte and 4096 result-object
budgets remain. Additionally, at most 4096 fragments per sequence and 16384 per TU
bound temporary records, including empty fragments. Limits are checked before
decoded allocation and apply across functions. Only a bounded sequence is buffered,
not the translation unit; included/macro spelling views retain normal lifetimes.

## M13j

Positive literal-bound array parameter declarators adjust their outermost array
to a pointer to its element type, including unnamed prototypes and matrix rows.
The declared syntax/cache remains an array; signatures and parameter spills use
a separate effective pointer type. Different outer counts are compatible after
adjustment; inner row counts must still match. Inside the function the parameter
is a modifiable pointer object, not an allocated array or a minimum-size promise.

Omitted bounds, static/qualified/VLA/general expression bounds and parenthesized
declarators remain unsupported. The declared type still has a 1 MiB resource cap,
while actual pointer-sized spills alone contribute to local object storage. No
backend special case or bound-based access check has been introduced.

## M13k

Only the outermost parameter array bound may be absent, as int a[] or a[][3].
The declared array has unknown cardinality and is incomplete; it never receives
a fabricated positive bound or object size zero. One-level adjustment yields
an ordinary pointer to the complete element/row type, so parameter storage and
ABI remain pointer-sized. Explicit zero remains invalid. Inner/local omitted
bounds, pointers to incomplete arrays, general expression/VLA/static/qualified
bounds and full parenthesized declarators remain unsupported. Array compatibility
accepts unknown/known counts only when their element types are compatible; this
is not support for allocating incomplete objects.

## M14a

Local objects, parameters and abstract cast types share a single-pass object
declarator parser. Parentheses distinguish pointer-to-array, array-of-pointers
and alternating shapes, without rewinding tokens. Named/unnamed parameter forms
retain one-level adjustment; casts still permit only implemented scalar target
conversions. An array cast is diagnosed, not sent to scalar conversion assertions.

Function suffixes/pointers, typedef names, qualifiers, comma-separated objects
and general external declarators remain unsupported. Fixed external functions
still use the restricted return-prefix/name form. Pointers to incomplete arrays
are not yet exposed; only outer parameter array bounds may be omitted. Bounds
remain positive integer tokens. Total pointer/array layers are each bounded to
64 across grouping, plus a separate 64-group nesting limit; typed expression
depth and local object storage limits remain unchanged.

## M14b

Pointers may refer to unknown-bound arrays, including arrays of such pointers.
Unknown arrays are object types but remain incomplete: no local unknown array
object or incomplete array element can be allocated. Dereference yields an array
lvalue supporting address-of and element decay, so (*p)[i] is usable with known
element size. p[i], p+0, p-0 and pointer subtraction require complete referents;
zero offsets do not bypass that constraint. Compatible comparison/truth/casts
use pointer representation without requesting unknown layout.

Compatible function redeclarations form recursive composite types, retaining
known bounds through pointer/array/parameter layers. Later unknown declarations
do not erase them; definition locals retain their own declared parameter shape.
Void/function pointers, full function/external declarators, qualifiers, typedefs,
general bounds and initializer lists remain unsupported. Existing local [] and
inner incomplete array cases now reject in sema before layout, not only parsing.

## M14c

Local declarations and declaration-form for headers allow comma-separated
init-declarators. Specifiers are parsed once but every pointer/array shape is
independent. Each name binds before its initializer, in declaration order; later
names are not prematurely visible. For-header names share one loop scope and
are not visible afterward. Initializers execute once in source order.

The for AST now owns an initializer-declarations list rather than one local
node. Every concrete local, including header declarations, counts toward the
4096 function-wide block-item budget. Actual 256-local and 1 MiB object-storage
budgets remain separate. Comma expressions, braced/array initializers, global
object groups, function/typedef/qualifier declarators and unnamed definition
parameters remain later work. Commas nested in call arguments remain expressions.

## M14d

C23 function definitions accept unnamed parameters of the implemented types,
including abstract/adjusted array forms. They remain part of the fixed signature
and call argument count/evaluation, but have no invented name, binding or spill.
Named duplicates and references to nonexistent identifiers remain constraints.
ABI %pN positions advance for every parameter; only named positions are stored.

The 128-parameter budget still counts unnamed entries. The actual 256-local and
1 MiB storage budgets count named parameter spills and local objects, not unused
ABI positions. Void remains only the existing sole empty-list marker. General
function/void types, function pointers, variadics, typedefs, qualifiers and other
C23 additions remain unsupported; this is not complete C23 conformance.

## M14e

General fixed-function suffixes join the shared declarator chain. Parenthesized
external names and functions returning complete/unknown array pointers are
supported, including compatible composite return declarations. One concrete
function syntax owns return/parameter syntax and its cache; declaration fields
are views, not separately parsed trees. Array/function returns are rejected
before scalar ABI helpers. Empty () denotes a C23 zero-parameter function type.

Function pointer values and function-typed parameter adjustment are still
explicitly unsupported; so are block-scope function declarations, file-scope
objects/groups, general void types, variadics, qualifiers and typedefs. Function
suffix layers are bounded to 64. Shared declarator recursion also covers nested
parameter types, so new parameter lists cannot reset the 64 nested-edge budget.
The existing local 64/65 grouping, pointer and dimension boundaries remain tested.

## M14f

Function designators and explicit decay support compatible function pointer
values, adjusted function parameters, callbacks/factories and indirect fixed
calls. Function pointers have no arithmetic, ordering or object stride. No
object/function pointer conversions, integer null constants or incompatible
function casts are added. Void, variadics, qualifiers, typedefs, block function
declarations and file objects remain unsupported. Typed expression depth stays
128; explicit callee decay participates rather than raising the bound.

## M14g

Void is a real incomplete object type, never a scalar or zero-sized object.
Functions/callbacks may return void; sole unnamed void means zero parameters.
Void locals/parameters/array elements remain constraints. Void calls, casts and
indirections may be discarded; scalar contexts reject their nonexistent values.
A void return accepts no expression, even another void expression. Void fallthrough
emits bare ret; prior nonvoid fallthrough behavior is unchanged. &* cancellation
accepts void pointers without loading them. Compatible void-pointer values are
supported, but object/void conversions and mixed equality are next M14h. Null
constants, variadics, qualifiers, typedefs and remaining C23 stay unfinished.

## M14h

Object pointers convert to/from void * in assignment-like contexts and explicit
casts. Mixed equality converts the object pointer to void *, in either source
order. Compatibility is unchanged: signatures with int * versus void * still
conflict. This rule inspects only immediate referents, not recursively nested
void **/int **. Function pointers cannot bridge to void *, but pointers to
function-pointer objects can. Mixed ordering, integer null constants, incomplete
strides, other incompatible explicit pointer casts, qualifiers and typedefs are
not added. M14i explicit object/function pointer casts is designed separately.

## M14i

Explicit casts between object pointers and, separately, between function pointers
are supported. This includes nested object-pointer casts; implicit compatibility
and assignment/call/return rules are unchanged. Object/function bridges and
integer/pointer mapping remain unsupported. Character pointers can access object
representation; runtime alignment/effective-type requirements remain the source
program's obligations. A function-pointer cast is not an ABI adapter: calling
through an incompatible function type has undefined behavior and is never used
in curated runtime tests. Qualifiers, typedefs and full declarators remain work.
Next bring forward M19a sequenced comma expressions, using the new effect-only
path and explicit argument/declaration separator floors; M14 stays incomplete.

## M19a

Comma is a real left-associative sequenced expression, including void results.
Arguments and unparenthesized initializers use assignment-expression floors;
parentheses, subscripts, returns and loop/condition expressions accept commas.
The result is never an lvalue. This brings forward one independent M19 operator,
not switch, labels, goto, conditional expressions or constant-expression support.
Typed depth stays 128. M14 const/other qualifiers, typedefs and the remaining
C23 features are not implied. Next split const into an immutable type-model
increment (M14j1), then syntax and semantic enforcement (M14j2), with tests at
both boundaries; see m14-const-qualification.md before changing the type graph.

## M14j1

The semantic type header records const qualification. Immutable qualification
and root-only unqualification preserve concrete pointer/array shapes and shared
inputs. C23 arrays inherit the immediate element qualifier set; pointer referents
remain separate levels. Strict compatibility checks every qualifier level;
root-unqualified compatibility is a distinct operation and does not erase nested
pointer qualifiers. Composites preserve pointer qualifiers and known bounds.

This checkpoint exposes no const syntax or modification/conversion enforcement.
No source type can acquire qualifiers yet, so bounded pipeline fuzz checks the
unchanged language paths, not new qualified source semantics. Dedicated both-host
normal/sanitized units exercise qualified graphs directly. M14j2 adds the planned
language integration before claiming source-level const support. Volatile,
restrict, atomic, bracket qualifiers, typedefs and full C23 remain later work.

## M14j2

Const is accepted in builtin specifier permutations and after pointer stars,
including grouped/abstract forms. Repeats are idempotent; no implicit int is
introduced. Ordinary loads and cast results drop only top-level qualifiers;
declared objects, pointees and syntax caches retain them. Assigning through a
const lvalue is a constraint. Initialization is allowed without changing the
binding's qualified storage type. Function signatures normalize return/top-level
parameter qualification while definition parameter locals stay qualified.

Implicit pointer conversion can add immediate pointee qualifiers, not remove
or recursively add them. Mixed comparisons construct explicitly typed common
pointers; differences require compatible unqualified referents and both complete
objects. Explicit casts may remove const, but modifying actually const-defined
objects remains undefined and is never executed by tests. No automatic storage
is falsely advertised as read-only QBE memory.

Bracket parameter qualifiers, volatile/restrict/atomic, typedefs, general array
bounds/initializers, integer null constants and full C23 remain unfinished.
Clang 15 rejects three exact C23 top-level-return-qualification redeclarations.
Those original kcc programs run with QBE; tests count the native host gaps rather
than changing their source or claiming agreement. GCC 11 accepts all 39 new
runtime programs. Bring forward M23a1 bool/true/false spellings next, using the
existing _Bool model; other M14 and M23a work stays incomplete.

## M23a1 boolean keywords and constants

bool and _Bool denote one canonical semantic type. true/false are concrete bool
constant expressions, not fabricated int literals or predefined object macros.
Raw preprocessing can define/undef/paste these spellings before language token
conversion; remaining #if true maps to 1 and other identifiers to 0 as before.
Ordinary bool promotion, whole-scalar truth conversion and narrow ABI handling
remain shared with _Bool. No stdbool.h/default header is supplied. Integer
constant evaluation/null constants remain unimplemented: false-to-pointer and
boolean array bounds still diagnose. Other M23a keywords remain unfinished.

Both-host tests run 32 original kcc programs, 22 constraints, exact promotion
bounds, 26 cross-object ABI arrangements and dirty-upper-bit returns. Clang 15
has native C23 keyword/type agreement. GCC 11 only runs explicitly labelled
compatibility-macro runtime oracles; three defined/undef programs have no such
native host oracle and still execute unchanged through kcc/QBE. Semantic units
inspect real bool constants, source qualifiers and explicit bool->int promotion.
Full normal regression/QBE and both-host sanitized semantic units passed.

M23a1 bounded sanitized fuzz: 23,176 lexer and 68,839 pipeline inputs in
26 seconds each, without reported failures. Generated C was never executed.

## M19b conditional expressions

?: supports implemented integer types, compatible/qualified/composite pointers,
object/void pointer pairs and two void arms. Both arms satisfy constraints even
when skipped. Result is never an lvalue. Integer arms use usual conversions
(including bool/bool to int). Pointer composites retain known array bounds and
immediate qualifier union without changing earlier types. Only the selected arm
executes, after the condition, including when the result is discarded. Nested
branch predecessors are recorded for scalar QBE phi; void uses no result phi.

Pointer/integer null constants remain unimplemented (even literal 0); floating,
aggregate and nullptr_t cases depend on future types. Other remaining operators,
switch, labels and goto stay separate M19 increments. Clang 15 rejects exactly
two C23 array-qualification conditional programs (6.7.3p10); kcc/QBE runs the
unchanged originals, and no fake native host agreements are counted.

M19b bounded sanitized fuzz: 23,373 lexer and 68,010 pipeline inputs in
26 seconds each without reported failures; generated C was never executed.

## M18a fixed sizeof and alignment

sizeof accepts unary operands and parenthesized implemented type names; alignof
and _Alignof accept type names only. Complete fixed object types use the existing
LP64 layout and unsigned-long result type. Function, void and unknown-bound array
operands reject; pointer types remain complete regardless of their referents.
Expression operands are checked without immediate load/decay and never emitted.
Nested constraints/conversions still apply; strings may remain harmless unused
private data. Adjusted parameter locals have pointer size, not declared array size.

No VLA, bit-field, expression-alignof extension, size_t/header exposure, static
assertion or general constant evaluator is implemented. Array bounds still require
positive literal tokens, including when sizeof could mathematically be constant.
Legacy GCC 11 and Clang 15 lack the alignof spelling; labelled _Alignof macro
oracles validate its runtime/layout behavior without claiming native keyword support.

M18a bounded sanitized fuzz: 23,465 lexer and 66,857 pipeline inputs in
26 seconds each without reported failures; generated C was never executed.
Exact-source M14j2 b26ff3b CI run 38863255999 passed. M23a1 fe26eb4 run
38864340577 and M19b 0c0ef33 run 38865164586 were still running.

## M18b1 tested source checkpoint

Added a pure consteval.c stage over checked bounded integer ASTs. Results preserve
canonical target bits/type/location or distinguish nonconstant forms from invalid
arithmetic. Portable checked operations never depend on signed host overflow,
negative signed shifts or large unsigned-to-signed casts. Short-circuit arms are
form-checked without arithmetic, and comma is allowed only when unevaluated.
sizeof/alignof are opaque typed leaves; queries do not emit diagnostics, mutate
ASTs, allocate or change runtime compilation acceptance.

Full normal GCC regression and QBE suites passed. Both GCC/Clang native oracles
agree on 958 curated strict ICE forms/values, with six C23 boolean queries,
34 nonexecuted invalid-arithmetic cases, 19 nonconstant forms and eight strict
native form rejections. Both-host ASan/UBSan evaluator oracles passed the same
checks. One exploratory predefined-macro test correctly exposed that __STDC__
is not yet provided; it was not disguised as a supported feature. Fuzz now queries
checked expression/initializer/return roots without executing generated C.
Bounded fuzz totals follow. Full isolated/remote exact-source checks are pending.

This is a shared foundation, not new declaration acceptance. Static assertions,
enums/constexpr, constant array bounds and null pointer constants are not yet
consumers. Next: M18b2 static assertions, designed in m18-static-assertions.md.

M18b1 bounded sanitized fuzz: 23,575 lexer and 64,254 pipeline inputs in
26 seconds each, without reported failures. Generated C was never executed.
Exact-source M23a1 fe26eb4 CI run 38864340577 passed; M19b/M18a were still running.

## M18b2 tested source checkpoint

static_assert and _Static_assert are on-demand post-pp keywords and concrete
assertion declarations with separate external/block wrappers. Parser accepts
conditional-expression and optional concatenated ordinary-string messages.
Sema checks all source-order scopes/unreachable items and consumes the pure ICE
query, preserving located invalid-arithmetic versus nonconstant diagnostics.
False values include quoted messages with all control/NUL/high bytes escaped,
never printf-interpreted. Messages allocate no local slots or QBE static objects;
successful assertions emit no runtime code, even in for initializers.

A standards audit corrected an initial design assumption: N3096 declarations
include static assertions in for clause-1. GCC 11 accepts them; Clang 15 rejects
with its exact identifier/parser diagnostic. Tests follow the draft and record
the host gap instead of rewriting the original source. Both hosts lack the C23
static_assert spelling and receive labelled _Static_assert oracle macros only.
Raw pp defined/undef behavior is checked on the original kcc program; legacy
host keyword-macro differences are not claimed as native agreements.

Full normal GCC regression and QBE suites passed. Targeted both-host tests cover
26 original QBE programs, 25 GCC and 24 Clang strict native runtime agreements,
39 constraints, four strict native ICE rejections, every diagnostic byte, message
concatenation/NUL/provenance, AST/scope/no-allocation invariants and exact syntax/
typed/item/external/message length/fragment limits. Both-host ASan/UBSan semantic
units and complete targeted assertion suites passed. Initial tests needed fixes
for the existing reverse local list, native diagnostic wording, unary '+' token
separation and trailing newlines in strict host feature probes; no compiler
failure was hidden. Bounded fuzz totals follow; no generated C was executed.
Full isolated/remote exact-source checks remain pending.

Next: M13l1 fixed ICE array bounds, designed in m13-constant-array-bounds.md.
Enums/constexpr/floating ICE casts, VLA, typedef/aggregates, null constants and
initializer/optimizer consumers remain unfinished.

M18b2 bounded sanitized fuzz: 21,256 lexer and 59,937 pipeline inputs in
26 seconds each, without reported failures. Generated C was never executed.
Exact-source M19b 0c0ef33 CI run 38865164586 and M18a ea59892 run
38865929894 passed. M18b1 5b71941 run 38866954105 remained in progress.

## M13l1 tested source checkpoint

Array syntax now retains an optional bound expression AST (NULL for unspecified)
instead of duplicate token/has_bound fields. On-demand Pratt assignment-expression
parsing feeds normal sema and the pure ICE query; signedness-aware positivity,
overflow-safe per-type bounds and aggregate local-storage limits are enforced.
No VLA/runtime bound or global folding is implied. Bounds emit no evaluations.

Function-type resolution now creates/restores ephemeral prototype scopes, resolves
parameters left-to-right and binds adjusted names only after their declarators.
Type-only name bindings consume no runtime slots/list entries; real definition
parameter locals remain separate. Nested callbacks, own-name outer lookup and
scope restoration are typed-tested. A pre-implementation host probe corrected a
return-scope assumption: parameters are not visible in trailing derived return
syntax, so return types continue resolving before entering the prototype scope.

Full normal GCC regression and QBE suites passed. Both-host targeted tests cover
31 original strict native/QBE programs, 34 constraints, 24 adjusted-array ABI
arrangements, exact syntax/typed/cross-type recursion and compile-only storage
boundaries. Both-host ASan/UBSan semantic units and targeted bound suites passed.
The cross-type recursion boundary is the existing 64 nested declarator edges,
not 128 independent expression nodes. Tests replace obsolete [true], [sizeof],
[1+2] rejections with variable-length/unparenthesized-comma cases; unsupported
static bracket diagnostic expectations now reflect expression parsing. No
rejection coverage was silently removed. Initial tests also corrected existing
local-object-storage wording. Bounded fuzz totals follow; generated C was never
executed. Full isolated/remote exact-source checks remain pending.

Next: M13m traditional null pointer constants, designed in
m13-null-pointer-constants.md. C23 nullptr/nullptr_t, VLA, typedef/qualifiers,
enums/constexpr and other constant consumers remain later work.

CI correction preceding this checkpoint: cade2cd's Clang CI run 38868636910
failed because the native host applies an unevaluated-string numeric-escape
restriction to a valid C23 assertion message. N3096 6.4.5/6.7.11 were rechecked;
kcc's acceptance and every diagnostic-byte test remain unchanged. Correction
5ce95d6 recognizes only that exact single-error host diagnostic for the original
numeric-message program, does not count it as a native agreement, and still
runs the original through kcc/QBE. Other native failures remain fatal. Both
local host assertion/QBE suites passed the correction. Remote CI is pending;
do not call the failed earlier checkpoint green. M18b1 5b71941 CI run
38866954105 did pass. A sandbox reset erased installed Clang and queued process
handles; Clang/compiler-rt were reinstalled. Old matrix source archives/logs
remain, but pending jobs are not claimed as successful.

M13l1 final post-reset full normal regression and QBE suites passed again;
bounded sanitized fuzz ran 22,845 lexer and 61,791 pipeline inputs in 26 seconds
each. Both-host focused ASan/
UBSan semantic, bound and assertion suites also passed with QBE runtime/ABI.
No fuzz-generated C was executed. Version-only driver change was rebuilt/smoke
checked after these suites. Remote/full isolated matrix status remains separate.
The first native-oracle correction's remote Clang job progressed to the separate
keyword-macro warning policy; a second exact-diagnostic/same-source warning
control fixes that test, documented in m18-static-assertions.md. Neither compiler
language acceptance nor warning policy for other tests was weakened.

## M13m traditional null pointer constants

Sema recognizes checked integer constant expressions with value zero, and
explicit casts of those expressions to unqualified void *. A zero-valued local,
assignment/comma result, arbitrary pointer, typed int * null value or pointer
conditional result does not gain null-constant status. Invalid constant arithmetic
is not proof of zero. C23 nullptr/nullptr_t remain a separate next milestone.

Assignment-like conversions (initialization/assignment/call/return), explicit
pointer casts, equality in both orders and conditional arms share the predicate.
Equality handles null constants before compatible/common pointer types; relational
comparisons still reject pointer/integer zero. Conditional arms select the exact
other pointer type before the object/void common-type rule, preserving qualified
objects, functions and incomplete-array pointers. Pointer+0 remains ordinary
pointer offset arithmetic, not a null conversion. Function/object bridges and
nonzero integer/pointer casts stay unsupported; the latter are implementation
limits, not claimed C constraints. Pointer-to-bool conversion remains available.

Existing concrete conversion/cast ASTs retain original operands, source locations,
resolved types and depth checks. No token vectors, synthetic literal rewrites,
extra local slots, global folding or runtime ABI adapters were added. Existing
QBE integer extension/copy lowering was audited: this amd64 LP64 target uses
all-zero 64-bit null pointers for implemented object/function pointer types.
That is an explicit target representation choice, not a portable C assumption.

Both-host focused tests cover 37 original curated programs, 36 strict GCC and 37
strict Clang native agreements, 25 compile-only constraints/implementation limits,
11 strict native constraint rejections, concrete AST/type/slot/depth invariants
and 24 mixed-register/stack/callback cross-object ABI arrangements. Once-only
non-null effects and selected conditional arms are checked without null calls,
dereferences, arithmetic or incompatible calls. Existing obsolete zero-rejection
fixtures were replaced with nonzero forms, not dropped. The ABI failure path uses
a live caller-owned sentinel, so an argument mismatch cannot accidentally return
null and pass. Both-host ASan/UBSan semantic/targeted results and full regression/
fuzz outcomes follow once complete; no generated fuzz C is ever executed.

A native-oracle audit found GCC 11 rejects a zero _Bool ICE in initialization,
assignment and return, despite C23 6.3.2.3/6.6 permitting it. Clang accepts the
same original program. Tests recognize only those three exact GCC errors, keep
the original kcc/QBE run, report the gap and do not count a native agreement.
An early test-generation failure was a missing parenthesis around interpolated
conditional zero forms; grouping was fixed, not compiler precedence. Strict
native rejection tests explicitly exclude legal-but-unimplemented cast forms.

M13m final validation: full normal regression and QBE suites passed. Both-host
ASan/UBSan semantic units and final targeted null suites passed, including the
extra original C23 false-leaf QBE program and its exact typed conversion unit.
Bounded sanitized fuzz ran 22,403 lexer and 63,128 pipeline inputs in
26/26 seconds without reported failures; generated C was never executed.
The full-suite audit found two additional obsolete zero/false rejections in void
function and boolean tests. Both were replaced with nonzero/true cases, retaining
constraint coverage, then the entire regression/QBE/fuzz chain was rerun.
No partial early run was called a full pass. Full isolated and remote exact-source
checks for this checkpoint are pending. Next: M23a2 nullptr constant with its own
scalar type, designed before implementation in m23-nullptr-constant.md.

## M23a2 boundary

nullptr expressions now work with a distinct complete scalar type. Source
nullptr_t is still an ordinary identifier, not a builtin spelling; typedef,
typeof, inference and required header exposure remain future increments.
Current target size/alignment is 8 with all-zero void-pointer null representation.
Conversions to non-bool integers, arithmetic and relational operations are
constraints, not missing cast implementations. nullptr/zero conditional arms
are invalid C23; nullptr equality with zero is valid. Evaluated nullptr forms
are not ICEs; sizeof(nullptr) is. Local legacy hosts lack the keyword, so their
native comparison count is zero; QBE runtime and separate-pointer ABI validation
are still run on every original positive program. This does not validate a
source-spellable nullptr_t parameter/return ABI yet. Next: prefix updates.

## M19c1 prefix update boundary

Prefix ++/-- support current integer and complete-object pointer lvalues.
Postfix updates and compound assignments are not in this increment. No atomic
or floating update behavior is claimed. Updating a pointer to void/function/
incomplete array is invalid; const referents do not forbid updating a mutable
pointer object. Runtime signed overflow/null or out-of-array pointer arithmetic
remains undefined C behavior, not a runtime bounds-checking feature. Bool updates
use promoted arithmetic followed by truth conversion. VLA bounds containing an
update are valid C23 syntax but remain our explicit runtime-bound subset limit.

## M19c2 postfix boundary

Postfix ++/-- now support the same integer/complete-object pointer subset as
prefix. Compound assignment, float and atomic updates remain later work. C's
unsequenced side-effect rules still apply: x++ + x, x=x++ and similar sources are
not made defined by a chosen backend order. The compiler does not diagnose all
such runtime undefined behavior. Tests only execute curated defined cases.

## M19d1 additive compound assignment boundary

+=/-= now support current integer and complete-object pointer modifiable lvalues.
Remaining compound operators, floats and atomic semantics remain later work.
Pointer RHS must be integer; void/function/incomplete referents are rejected.
The stored result is not an lvalue. Runtime signed overflow, invalid pointer
ranges and unsequenced conflicting effects remain undefined, not safety checks.
Tests choose defined inputs without imposing an unspecified operand order.
Evaluated updates are not ICEs; VLA bounds remain a separate subset limitation.

## M19d2 integer compound boundary

All ten compound assignments support current integer types; only +=/-= accept
current complete-object pointers. Float/atomic/aggregate semantics remain later.
Division/remainder by zero, signed arithmetic overflow, out-of-range or negative
shift counts and invalid signed left shifts remain runtime undefined behavior,
not compiler-defined wrapping behavior. Such curated sources are compiled only;
fuzz-generated source is never executed. Negative signed right shift follows
the existing Linux amd64 arithmetic-shift target choice. Native test agreements
use matching target assumptions, not a claim of universal implementation behavior.

## M19e1 named-label boundary

Identifier labels are supported, not goto/case/default/switch or attributes yet.
C23 standalone labels are valid before declarations and at compound-block end;
a label in secondary-statement position still requires a following statement.
Function-wide uniqueness uses a separate namespace. A function is limited to
512 labels; standalone items also count toward the existing 4096 block-item
limit and secondary label chains toward 128 statement nesting. These are resource
limits, not C constraints. No extra object or runtime target is allocated.
Native Clang 15 lacks the two C23 placement forms: exact expected-expression/
expected-statement diagnostics are labelled grammar gaps, never native agreements.
Original sources still compile/run through kcc/QBE; no null-statement rewrite
is used to manufacture native C23 support.

## M19e2 direct goto

Concrete goto nodes keep identifier locations and resolve original label pointers
after the whole function body is checked, including dead syntax. Labels receive
source-order indices; functions retain their checked label count. References are
bounded to 4096 per function, independently of 512 labels and block-item limits.
Codegen reserves target IDs, tracks the current numeric block for phi nodes and
continues after terminators using predecessor-free blocks, preserving nested
targets without inventing fallthrough. Initializers execute only when reached.
Computed goto, switch/case/default, attributes and VLA jump-scope rules remain
unsupported; this does not claim full C23 control-flow support.

## M19f1 switch foundation

Case-free switches evaluate an integer control exactly once with explicit integer
promotion, then skip the body. Full body checking and predecessor-free backend
traversal preserve named goto targets; goto entry bypasses control evaluation.
One enclosing-control context stack binds break to the closest loop/switch and
continue to the closest loop across switches. AST jumps retain exact target
identity and backend target lookup follows it. Scope and context parents restore
on failure. Case/default dispatch, attributes and VLA jump-scope constraints
remain unsupported and are not implied by this foundation. Existing loops and
function/ABI contracts are unchanged; no new runtime storage is introduced.

## M19f2 case/default labels and dispatch

Separate concrete case/default labels have block-item and secondary-statement
wrappers. C23 block labels can precede declarations or end a block; secondary
labels require a child statement. Case conditional expressions stop at the outer
colon with Pratt floor 2. Sema assigns the nearest switch across nested loops,
checks integer ICEs after explicit conversion to promoted control type, detects
duplicate converted bits and rejects multiple defaults. Nested switches have
independent collections. Cases never emit runtime operand evaluation.

Named goto indices/counts remain unchanged; function switch-label indices reserve
a separate QBE target range after named targets. Bounds: 1024 labels per switch
and 4096 per function, each including default. Linear equality dispatch evaluates
control once; ordered label emission gives fallthrough without false edges after
terminators. Current block IDs still track phi predecessors. Attributes, GNU case
ranges, VLA jump constraints and jump-table optimization remain unsupported.

## M23d1 typeof type-name operands

Demand keyword conversion recognizes typeof/typeof_unqual only after macro
expansion. A concrete ast_typeof_type_syntax owns its type-name operand; RDP
parses the documented subset BNF with a separate restored 64-query nesting guard.
Sema caches immutable resolved types: typeof preserves the operand identity,
typeof_unqual removes root qualification (including C23 array element qualifiers
until a pointer) without stripping referent qualifiers. Function qualification
is diagnosed before the old qualifier-helper assertion. Declarations, casts,
sizeof/alignof, static assertions, fixed bounds, adjusted parameters and callbacks
reuse their existing checks and backend; queries introduce no runtime operation.

Expression operands, GNU aliases, typedef/atomic/VLA/bit-field cases and
alias-derived bare function declarations remain unsupported. A sole typeof(void)
parameter is not yet normalized to an empty signature; existing literal void
syntax remains supported. These are documented subset gaps, not C constraints.
The current file-scope bare-function alias path reports the existing unsupported
file-scope-object diagnostic; it does not guess a function AST.

## M23d2 typeof expression operands

A distinct ast_typeof_expression_syntax keeps one Pratt floor-zero expression
operand, source location and unqualification flag. One demand peek selects the
existing type-name path; both forms share the restored 64-query bound. Sema checks
the operand in its lexical/prototype scope with only root load/array/function
decay suppressed. Child conversions and constraints remain checked. typeof
shares its actual immutable type; typeof_unqual uses root unqualification.
Previous prototype names remain type-only bindings; query operands allocate no
extra runtime locals. The backend never visits query syntax, so calls, updates,
assignments and comma/conditional effects in non-VM operands do not execute.
Existing string registration may retain static data for an unevaluated literal.

Query expressions now name the existing nullptr type, including objects, pointers,
parameters and results. N3096 6.3.2.4 / 6.5.4 explicit casts to that type accept
only null pointer constants or nullptr values. The later M23d2 null-conversion
correction also admits checked null constants in initialization/assignment/
argument/return, as required by the normative 6.5.16.1 constraint. Its contradictory
footnote 127 was stale; N3220 retains the normative rule and removes that footnote.
Nonconstant integer/pointer zero values and non-ICE zero forms remain rejected.

Typedef ambiguity, atomic/bit-field/variably modified operands, required VM
evaluation, GNU aliases, alias-derived bare function declarations and sole
query-derived void-parameter normalization remain separate work. sizeof(void)
and void objects are still invalid; typeof of a void expression itself is valid.
No stddef.h exposure or full C23 conformance is implied.

## M14k1 query-derived void parameter normalization

A sole unnamed unqualified resolved void parameter is annotated is_void_marker,
retaining its written query syntax and checked type. It contributes no semantic
function parameter, prototype binding, local spill or ABI operand. Parsed counts
still describe written AST nodes (literal void keeps the existing zero-node
parser fast path); semantic function_type counts describe the actual ABI. Named,
qualified or mixed void parameters remain errors. Main's supported zero-parameter
check now uses the resolved signature instead of the written node count.

Backend definition-header and spill traversals skip the checked marker before
querying its width or incrementing ABI indices. Real unnamed C23 parameters keep
their ABI positions; no synthetic parameters or names are introduced. Direct/
indirect calls, nested signatures, prototypes and definition compatibility reuse
the existing semantic function types. Root query non-evaluation still applies in
local callback declarators. This adds no new runtime storage or resource bound.

Bare query-derived function declarations, block-scope function declarations,
typedef/storage/variadic/VM work remain unsupported. Qualified void is not an
empty-list marker unless typeof_unqual first removes its qualification. No full
C23 declaration-normalization claim is made.

## M14k2 query-derived file-scope function declarations

A separate concrete ast_external_type_declaration retains a query-root type
syntax, its source name and checked type/symbol annotations. Parsing only accepts
a semicolon-terminated declaration and does not resolve the query or manufacture
function syntax, parameter lists, names or a definition. Sema resolves the query
in source order and currently accepts only a function type. Query-derived object,
pointer, array and void declarations retain the explicit file-scope-object subset
diagnostic; query-derived bare definitions, comma lists and initializers remain
unsupported. Block function declarations, typedef/storage/variadic/VM work remain
separate. This does not make typeof a symbol-alias facility.

Both ordinary function declarators and query-root declarations use one shared
registration helper for main checks, symbol bounds, compatibility, immutable
composite types and redefinition checks. Query caches remain immutable snapshots:
a later prototype can strengthen a symbol's incomplete array bound without
rewriting an earlier query's cached type. Definition parameter nodes/bindings and
recursion installation retain their existing path. Queried declarations add no
parameters, locals, data, function definitions, runtime query operations or QBE
alias instructions. Calls/addresses use the existing shared symbol and ABI.
The existing 256 unique-function / 512 external-declaration bounds still apply;
repeated compatible queries do not consume additional function-symbol slots.

## M14l1 unshadowed file-scope typedef foundation

A language typedef keyword is converted only at token demand; raw preprocessing
identifiers/macros retain their old behavior. Concrete ast_typedef_declaration,
ast_external_typedef_declaration and ast_typedef_name_type_syntax retain each
written declaration/name. Parser aliases are bounded syntax-only name bindings;
sema independently resolves earlier aliases in source order and shares immutable
types, never a new nominal type or synthetic runtime declaration.

Aliases participate in all existing declaration/type-name ambiguities: local and
for declarations, qualifiers, pointers, arrays, adjusted parameters, signatures,
casts, sizeof/alignof and type queries. Alias-derived bare function declarations
reuse M14k2 registration. Identifier-plus-colon is classified before alias local
declarations, preserving the label namespace. Alias-named labels still consume
one block item; consumed alias declarations reuse a shared specifier/declarator
tail without token replay, vectors or semantic resolution during parsing.

This increment supports one unique file-scope alias per typedef declaration.
Block typedefs, typedef redeclarations, comma typedef lists, shadowing visible
aliases, bare alias-derived function definitions and remaining storage classes
are explicit subset limits, not newly invented C constraints. Actual ordinary
file-scope function/typedef namespace collisions are rejected by sema. Existing
VM, aggregate, floating, atomic and other unsupported types remain unsupported.

Aliases share DAGs that could encode exponentially expanded function signatures.
Sema caches shape metrics by immutable type identity before publishing an alias,
with explicit expanded-node 4096 and depth 128 limits (each leaf counts as one).
These bounded valid-C subsets protect existing recursive type operations; they
are not incompatibility diagnostics. The existing 512 external declarations,
256 function symbols and 4096 block items remain independently enforced. Alias
names do not emit storage, data, functions, QBE aliases or runtime query effects.

## M14l1b same-type file-scope typedef redeclarations

Already-visible aliases may be redeclared for the same non-VM type. The type
stage exposes type_same separately from compatibility: array counts must match,
including unknown versus known bounds, recursively through pointers and normalized
function signatures. Existing compatibility and immutable composite construction
are unchanged. Typedef equality never strengthens an unknown-bound array.

The parser reuses its syntax-only name binding. Sema checks the expanded alias
shape before comparison, annotates a valid redeclaration with the first canonical
immutable alias type, and leaves each separately written syntax cache intact.
A different type is a genuine constraint; function/typedef ordinary-namespace
collisions remain errors. No additional alias binding, storage, QBE alias,
parameter or emitted function is introduced by a same-type redeclaration.

Block typedefs, shadowing, comma typedef lists, VM/aggregate types and bare
alias-derived definitions remain deferred at this checkpoint. The existing 512
external items, 256 function symbols, 4096 block items and 4096-node/128-level
expanded alias limits are unchanged. Each repeated declaration still consumes an
external item; canonical type reuse does not bypass resource accounting.

## M14l1c file-scope typedef declaration lists

A file-scope typedef declaration may contain comma-separated declarators. One
written specifier base is shared by distinct derived syntax chains; each alias
retains a concrete typedef declaration and external wrapper in source order. The
parser publishes each syntax-only name after its complete declarator, so later
names in the same group can use it in bounds, parameters, casts and type queries.
Sema still resolves the external chain independently; no new backend path exists.

Each concrete alias, including a repeated name, consumes one external item. The
parser checks the remaining 512-item budget before constructing another declarator,
not merely once per group. Mixed ordinary function/static-assert/typedef groups
therefore cannot bypass the bound. Existing function-symbol, block-item and alias
expanded shape limits are unchanged. Typedef initializers receive an explicit
constraint diagnostic. Alias-only translation units emit no function or data.

Block scope, alias shadowing, storage-specifier permutations, VM/aggregate types
and bare alias-derived function definitions remain deferred at this checkpoint.

## M14l2 block-scope typedef foundation

Compound blocks now accept typedef declaration lists through a concrete
ast_block_typedef_declaration wrapper. Every alias charges one block item; shared
written specifiers and distinct derived declarators retain source order. The
complete-declarator syntax-name publication helper is shared with external
aliases, without making either representation an automatic object.

Parser compound scopes restore their syntax-only alias-list head on success and
failure. Sema independently restores its bindings around nested compounds and the
outer function body, tagging each binding with its semantic scope. Same-scope
same-type redeclarations preserve canonical immutable types. Names cannot leak
into sibling blocks, later functions or subsequent external declarations.

Codegen skips the new item kind. Aliases create no locals, stack slots, strings,
runtime initialization or QBE data/function aliases. Expanded type limits remain
4096 nodes / 128 levels; each alias still counts toward 4096 function block items,
independently of the 512 external items and 256 function symbols.

Typedef/typedef, typedef/object and typedef/function shadowing remain explicit
subset restrictions at this checkpoint; same-scope object/parameter conflicts
and different-type typedef redeclarations are genuine constraints. C23 permits
for-initializer typedefs: those are deferred to M14l2b, not labelled invalid C.
Storage-class permutations, VM/aggregate types and general ordinary-namespace
hiding remain unsupported. Read m14-block-typedef-foundation.md, including its
normative draft correction, before changing scoped lookup or parser classification.

M14l2 validation: complete normal/QBE regression, complete normal regressions with
original-source GCC 14.1.0 and Clang 18.1.8 native oracles, both GCC 11 / Clang 15
targeted ASan/UBSan lexer/sema/typedef/query/nullptr/local-list/assertion/control
suites and bounded sanitized fuzz passed. Fuzz executed 4,845 lexer / 14,954
pipeline inputs in 26/26 seconds; no generated or invalid curated C ran. Focused
suite: 36 standard + 4 C23 originals, 6 strict native constraints, 24 mixed-stack
primitive ABI arrangements per host, concrete AST scope/wrapper/type identity,
no alias locals and exact block/external/expanded-depth boundaries. Legacy hosts
agree on 36 originals, modern hosts on all 40 without rewriting. Frozen manifest
/data/tools/m14l2-source.sha256 matched before and after integration. Remote CI
is separate from these local passes.

## M14l2b C23 for-initializer typedefs

For clause-1 accepts the existing block typedef declaration group, preserving its
concrete AST wrappers, per-declarator source order and single-semicolon parser
contract. Each alias consumes one function block item, independently of the
containing for statement. A bare return loop body is not a compound block item.

The guarded parser for wrapper restores syntax-only alias names on success and
failure. Sema_for independently restores semantic aliases around its existing
loop scope. Aliases are visible after their complete declarator through the
remaining initializer, condition, step and body, but not after the loop. Compound
bodies retain their own nested scopes. No new AST representation or backend path
is required: initializer item emission already skips compile-time-only aliases.

N3096 6.8.5 / 6.8.5.3 and N3220 6.8.6.4 permit these declarations; do not revive
C17's removed object/storage constraint. GCC 14 accepts original C23 sources.
GCC 11, Clang 15 and Clang 18 reject an exact minimal for-typedef probe; tests
recognize only those specific sole diagnostics, report a feature gap separately
and still execute original defined kcc/QBE programs and primitive ABI comparisons.
They never rewrite aliases into objects or move declarations to fake agreements.

Shadowing, storage-class permutations, VM/aggregate types and prototype scopes
remain outside this increment. Existing item/alias-expanded budgets and semantic
same-scope constraints remain unchanged. Read m14-for-typedefs.md.

M14l2b validation: complete normal/QBE regression, complete normal regressions
with original-source GCC 14.1.0 and Clang 18.1.8 native oracles, both GCC 11 /
Clang 15 targeted ASan/UBSan lexer/sema/typedef/query/nullptr/control suites and
bounded sanitized fuzz passed. Fuzz executed 3,394 lexer / 9,630 pipeline inputs
in 26/26 seconds; no generated or invalid curated C ran. Focused suite: 34
base-type + 4 query originals, all 38 strict native agreements / 4 constraints
with GCC 14; exact for-typedef grammar gaps, not agreements, on GCC 11 / Clang 15 /
Clang 18. All four hosts passed original kcc/QBE runs and 24 mixed-stack primitive
ABI arrangements each. AST tests verify scoped aliases, canonical repeats and
independent post-loop names with no alias locals. Exact 4096-item and alias-only
IL checks passed. Frozen manifest /data/tools/m14l2b-source.sha256 matched before
and after integration. Earlier interrupted helper-build-race runs are not passes;
all final normal helpers were built serially before parallel tests. Remote CI
remains separate from these local results.

## M14l2c nested typedef-to-typedef shadowing

An inner typedef can hide an outer typedef with either the same or a different
type. Sema applies same-type redeclaration checking only when the nearest alias
binding belongs to the current scope; otherwise it prepends an independent
binding after resolving the written type. Thus typedef T *T uses the outer T in
its specifiers, not its own unfinished declaration. A repeated name within the
new scope must still name the same non-VM type, not merely a compatible type.

No parser/lexer classification change is needed: both visible meanings are type
names. Existing compound/function/for save-and-restore contracts reveal the outer
alias after inner scope exit. Syntax caches and canonical types remain immutable;
typedefs still create no runtime locals, slots or data. Item and expanded-type
limits are unchanged. Typedef/object/function hiding in either direction,
prototype scopes, storage-class permutations, VM and aggregate types remain
unsupported. Read m14-typedef-shadowing.md before broadening ordinary-name lookup.


M14L2C validation: complete normal/QBE regressions, complete normal
regressions with original-source GCC 14.1.0 and Clang 18.1.8 oracles, and both
GCC 11 / Clang 15 targeted ASan/UBSan lexer/sema/typedef/query/nullptr/control
suites passed. Bounded sanitized fuzz executed 3,927 lexer /
6,164 pipeline inputs in 26/26 seconds. No invalid or generated C
was executed. Four-host focused checks: 46 standard + 4 C23 originals, 6 native constraint rejections, and 24 both-direction
mixed-stack primitive ABI arrangements per host passed. Expanded for suite: 39+4
originals; GCC 14 agrees on all 43 / 4 constraints; other hosts report exact grammar
gaps separately. AST tests verify canonical same-scope repeats, independent nested
bindings, scope restoration and no alias storage.
Frozen manifest /data/tools/m14l2c-source.sha256 matched before and after
integration. Normal test helpers were built serially before parallel validation.
Remote GitHub CI is tracked separately; local passes do not prove remote success.

## M14l2d block typedefs hiding file-scope functions

Block and loop typedef bindings may hide a file-scope function, including their
own containing function. Sema keeps the original function symbol unchanged and
rejects visible typedef names in expressions before trying local/function lookup.
Bare calls bypass the undeclared-function shortcut for visible typedefs, giving
the same not-an-expression diagnostic. This closes the otherwise incorrect path
that could call or take the address of a hidden outer function.

Type-name uses refer to the alias. Captured function pointers remain valid and
scope exit restores subsequent calls/designators to the original function.
File-scope function/typedef collisions and same-scope differing aliases remain
constraints. Typedef/object hiding is still explicitly unsupported in both
directions: the typedef-first value-name guard relies on this invariant, and must
not be broadened to object shadowing without scope-aware namespace lookup.

No new type, AST form, parser classification, local slot or backend operation is
introduced. Existing expanded-type and declaration/item budgets remain. Storage
specifier permutations, prototype scopes, block function declarations, VM and
aggregate types are not implemented here. Read m14-typedef-function-shadowing.md.


M14L2D validation: complete normal/QBE regressions, complete normal
regressions with original-source GCC 14.1.0 and Clang 18.1.8 oracles, and both
GCC 11 / Clang 15 targeted ASan/UBSan lexer/sema/typedef/query/nullptr/control
suites passed. Bounded sanitized fuzz executed 3,408 lexer /
8,153 pipeline inputs in 26/26 seconds. No invalid or generated C
was executed. Four-host focused checks: 35 standard + 4 C23 originals, 11 native constraint rejections, and 24 both-direction
mixed-stack primitive ABI arrangements per host passed. Expanded for suite: 41+4
originals; GCC 14 agrees on all 45 / 4 constraints; other hosts report exact grammar
gaps separately. AST tests preserve captured/restored function-symbol identity and
verify no alias locals.
Frozen manifest /data/tools/m14l2d-source.sha256 matched before and after
integration. Normal test helpers were built serially before parallel validation.
Remote GitHub CI is tracked separately; local passes do not prove remote success.

## M14l2e typedefs hiding outer automatic objects and parameters

A block or for typedef may hide an automatic object or parameter from an outer
scope. Sema rejects only same-scope object/parameter collisions, resolves written
types before alias publication, and otherwise prepends the scoped alias binding.
The outermost function body still shares parameter scope; nested blocks do not.

The visible-typedef expression guard prevents calls, addresses, loads and
unevaluated value uses from falling through to the hidden outer object. Captured
addresses and earlier AST names retain their exact object declarations and slots;
restoring scope reveals subsequent object uses again. No object is removed from
the function-local storage list and no alias slot is created. Type queries in a
typedef's own specifiers may inspect the still-visible outer object.

Objects or parameters hiding visible typedefs in the opposite direction remain
explicitly unsupported. The typedef-first value-name guard relies on that parser
restriction; scope-aware unified ordinary-name lookup is required before removing
it. File globals, block function declarations, storage-class permutations, VM,
aggregate types and prototype-scope changes remain unsupported. Type-shape/item
budgets are unchanged. Read m14-typedef-object-shadowing.md.


M14L2E validation: complete normal/QBE regressions, complete normal
regressions with original-source GCC 14.1.0 and Clang 18.1.8 oracles, and both
GCC 11 / Clang 15 targeted ASan/UBSan lexer/sema/typedef/query/nullptr/control
suites passed. Bounded sanitized fuzz executed 6,665 lexer /
36,413 pipeline inputs in 26/26 seconds. No invalid or generated C
was executed. Four-host focused checks: 33 standard + 4 C23 originals, 8 native constraint rejections, and 24 both-direction
mixed-stack primitive ABI arrangements per host passed. Expanded for suite: 43+4
originals; GCC 14 agrees on all 47 / 4 constraints; other hosts report exact grammar
gaps separately. AST tests preserve captured parameter addresses, restored object
identity and original object slots; aliases allocate no local storage.
Frozen manifest /data/tools/m14l2e-source.sha256 matched before and after
integration. Normal test helpers were built serially before parallel validation.
Remote GitHub CI is tracked separately; local passes do not prove remote success.

## M14l3a automatic objects hiding typedef names

The parser maintains one syntax-only ordinary-name chain, recording typedef or
object kind. Nearest matching names control type/expression disambiguation. An
object publishes after its complete declarator and before its initializer; each
comma declarator publishes independently. Compound/for scope restoration handles
both kinds. No token buffering, backtracking, lexer change or new AST kind occurs.

Semantic typedef lookup honors nearer object scopes rather than falling through
to a hidden alias. Same-scope alias/object declarations remain constraints. Type
resolution precedes object binding, which precedes initializer analysis. Shared
specifier caches preserve the written base in T T=40,*P=&T while later value uses
bind to the object T. Existing typed conversion/load nodes and storage slots keep
their provenance. Alias/object nesting in both directions restores prior meanings.

Tests cover initializers, own-declarator array bounds, comma lists, parentheses
versus casts, sizeof/typeof, for lifetimes, labels, captured addresses, same-scope
constraints and no alias storage. Named parameters hiding visible aliases remain
explicitly unsupported pending a separate prototype-scope design. Globals,
block function declarations, VM/aggregate types and storage-class permutations
are not added. Existing item/local/storage/expanded-type budgets remain unchanged.
Read m14-object-typedef-shadowing.md before broadening prototype name lifetimes.


M14L3A validation: complete normal/QBE regressions, complete normal
regressions with original-source GCC 14.1.0 and Clang 18.1.8 oracles, and both
GCC 11 / Clang 15 targeted ASan/UBSan lexer/sema/typedef/query/nullptr/control
suites passed. Bounded sanitized fuzz executed 20,122 lexer /
90,589 pipeline inputs in 26/26 seconds. No invalid or generated C
was executed. Four-host focused checks: 44 standard + 5 C23 originals, 8 native constraint rejections, and 24 both-direction
mixed-stack primitive ABI arrangements per host passed. Legacy hosts agree on 44
originals; modern hosts agree on all 49. Expanded for suite: 45+4 originals; GCC 14
agrees on all 49 / 4 constraints; other hosts report exact grammar gaps separately.
AST assertions verify shared written base syntax, captured object identity, nested
alias/object restoration, the implicit long-to-int return conversion and four
object slots with no alias storage.
Frozen manifest /data/tools/m14l3a-source.sha256 matched before and after
integration. Normal test helpers were built serially before parallel validation.
Remote GitHub CI is tracked separately; local passes do not prove remote success.
