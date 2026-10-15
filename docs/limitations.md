# Implementation limitations

Current milestone: M09a. The chronological entries below describe what each
checkpoint added; the current supported subset is summarized in M08b/M08c plus the M09a additions.

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

## M09a (current)

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
