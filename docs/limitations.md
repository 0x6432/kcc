# Implementation limitations

Current milestone: M11h. The chronological entries below describe what each
checkpoint added; the current supported subset is summarized in M08b/M08c plus the M09/M10 additions.

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
