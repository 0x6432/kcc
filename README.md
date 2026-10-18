# kcc

An educational compiler written in C, growing from a deliberately small subset
toward C23. Code generation uses QBE. Readability and explicit invariants take
priority over compile-time performance.

## Current checkpoint

M16 adds struct/union definitions, natural layout, member access, zero record
storage, checked subobject addresses and address-backed aggregate copies. Existing
storage/linkage features compose with records. See `docs/m16-records.md` for the
precise target and resource contracts. General initializers remain M17,
aggregate-by-value ABI M21, bit-fields/flexible arrays M22, and C23 expanded tag
compatibility/redefinitions M23h. No ISO C23 conformance claim is made.

### Previous checkpoint

M15 storage/linkage closure: block extern objects/functions, persistent static
locals, real thread-local storage, TU-end inline linkage, and checked symbolic
address offsets for existing types are integrated. Lexical visibility remains
separate from canonical identities and immutable source-point types. No test or
sanitizer lane is removed. Read `docs/m15-completion.md` for exact target coverage,
quality gates and the explicit M17/general-initializer and later-type dependencies.
This remains an incomplete C23 compiler, not all initialization syntax or hosted
conformance. Earlier checkpoints below are historical.


M15I3: Direct zero-addend pointer initializers name canonical objects/functions
or stable string objects, using a distinct static address tag and ELF
relocations. Null and integer initializers retain their own pure proofs and tags.
Compatible pointer/ordinary void endpoints preserve origin type and qualifiers;
void detours do not legalize incompatible reinterpretation. Pointer arithmetic,
subscripts, conditionals, arbitrary reinterpretation and aggregate initializers
remain deferred. Read `docs/m15-direct-address-initializers.md`.

M15I2: Explicit pointer objects now accept proved null initializers: strict zero
ICEs, `nullptr`, and semantically valid pointer/nullptr cast chains. A tagged
static-data value keeps null separate from integer bits; existing definition
ownership and rollback remain unchanged. Linux amd64 data uses eight zero bytes
without relocations or runtime stores. Addresses, pointer arithmetic, pointer
conditionals, nullptr_t targets and aggregate initialization remain deferred.
Read `docs/m15-null-initializers.md` for the precise source and validation gates.

M15I1: File-scope integer objects now support checked integer constant
initializers, including `static`, initialized `extern`, qualified/typedef/query
types and mixed lists. One explicit definition supersedes tentative storage in
either source order; cached target-width bits drive aligned data emission.
Symbolic pointers, arrays, braces and block storage remain separate increments.
Read `docs/m15-integer-initializers.md` for scope and validation status.

M15H2: Complete fixed file-scope `static` arrays now reuse canonical internal
object linkage and one aligned zero-storage anchor. Visible prior composites
allow a later omitted bound; an initially incomplete internal tentative array is
rejected immediately, never repaired at TU end. Rows, pointer/callback elements,
immutable captures and existing budgets remain intact. Read
`docs/m15-static-objects.md` for scope and validation requirements.

M15H1: File-scope static tentative scalars now emit local, non-exported data.
`extern` inherits prior internal object linkage; an unadorned object declaration
does not. Mixed-linkage chains are conservatively refused. Broader initializers
and block storage remain separate work; this is still an incomplete C23 compiler.


M15G2: Tentative fixed/unknown-outer arrays now own zero-initialized storage.
TU-end completion creates one element only for still-unknown owned canonical
arrays; known composites and immutable source captures remain distinct. Existing
anchors/QBE data emission are reused. Exact native layout guards keep audited
Clang underallocations compile-only. Initializers/static objects remain deferred.
Read docs/m15-tentative-arrays.md for scope and frozen validation.

M15G1: File-scope tentative scalar definitions now own exactly one aligned,
zero-initialized exported datum. Written extern provenance and the first tentative
anchor preserve extern-only behavior, captured types and source-order identity.
Both-direction sole-owner ABI tests avoid common merging and companion double
definitions. Initializers, tentative arrays and static objects remain deferred.
Read docs/m15-tentative-scalars.md for scope and exact frozen validation.

M15F2: Explicit file-scope `extern` arrays now support fixed or unknown outer
bounds, rows, qualified/pointer/callback elements and mixed declaration lists.
Existing decay/address lowering references native-owned storage; no new data or
local slots. Immutable captured types survive canonical bound completion, and
the 1 MiB per-array-type ceiling remains. Definitions and VM arrays stay deferred.
Read docs/m15-extern-arrays.md for exact native gaps and frozen validation.

M15F1: Explicit file-scope `extern` scalar objects now support native-owned
storage references, mixed function/object lists, typed reads/writes/addresses and
indirect callbacks. Canonical object identity and immutable captured types survive
compatible redeclarations; globals add no data or runtime local slots. Definitions,
initializers, object arrays and block extern remain deferred. Read
docs/m15-extern-objects.md for exact scope and frozen validation evidence.

M15E1: File-scope `static` functions now have canonical internal linkage, retained
through later `extern` or unadorned declarations and definitions. QBE emits local
rather than exported symbols. Referenced internal functions require definitions;
unused and non-VM `sizeof`/`typeof`-only prototypes remain valid. Read
docs/m15-static-functions.md for source/AST/ABI/diagnostic and frozen-matrix evidence.
Objects, block storage, inline/thread and full C23 remain unsupported.

M15D2: File-scope function declarations can share specifiers in comma lists,
including extern and alias/query-derived prototypes. Each concrete declarator
keeps its own syntax/parameter scope and counts once toward the existing budget;
later queries see earlier function symbols without mutating shared type caches.
Only a sole direct declarator may define a function. Read
docs/m15-function-declaration-lists.md for native gap, AST/ABI and frozen matrix
evidence. Global objects, block functions and new linkage remain deferred.

M15D1: Explicit `extern` is supported on single file-scope function prototypes
and definitions, including alias/query-derived declarations and register/adjusted
parameters. It reuses existing external function symbols and QBE exports; no new
linkage or global-object support is implied. Local extern, static/inline/thread
storage, inferred extern objects and function declaration lists remain deferred.
Read docs/m15-extern-functions.md for original-source, symbol/cache, ABI/export
and frozen full-matrix evidence. Still not full C23 conformance.

M15C1: Written `register` is now supported on named/unnamed parameters, prototypes
and nested callbacks. Each actual parameter spill retains its own definition's
address restriction; prototype-only names allocate no runtime storage. Array and
function parameters are adjusted pointer objects, not register arrays/functions;
ordinary copied types and compatible signatures carry no register flag. Read
docs/m15-register-parameters.md for source/AST/ABI/budget evidence and the explicit
register-void subset refusal. Other storage/globals/linkage remain incomplete.

M23E3: Inferred `auto T = ...` and `auto (T) = ...` may now hide an outer typedef
T at block/for scope, including register inference. One demand peek disambiguates
bare names; a dedicated balanced-identifier grammar preserves nesting limits.
The name hides the alias but is unavailable in its initializer; completed uses
see the inferred object, and scope exit restores the typedef. Explicit auto T x
and old comma-list caches are unchanged. Read
docs/m23-inferred-typedef-shadowing.md. GCC 14's exact typedef-inference grammar
gap is reported separately; original sources are not rewritten. Still not full C23.

M23E2: C23 inferred `auto` may now combine with `register` at block/for scope,
in either order and with const qualifiers. The existing real local retains the
register address restriction; inferred copies do not inherit it. Combined auto/
register with an EXPLICIT type is still a constraint violation (C23 6.7.1p4).
No semantic/backend type, extra local or ABI change. Read
docs/m23-register-auto-inference.md; other storage/globals/register parameters,
visible-typedef ambiguities and complete C23 remain unsupported.

M23E1: C23 inferred `auto` now supports one bare/parenthesized identifier with an
assignment initializer at block/for scope, optionally const-qualified. Type
inference follows ordinary value conversions, including array/function decay.
The new name hides outer namesakes but is unavailable throughout its initializer;
subsequent items see its completed type. Initializers are analyzed exactly once,
with ordinary slots and unchanged QBE/ABI. Read docs/m23-auto-inference.md.
Visible-typedef ambiguities, inferred derived declarators, braced initializers,
auto/register combinations and file scope remain unsupported; not full C23.

Earlier checkpoint entries below are chronological, not current exclusions.

M23E0: Semantic preparation only—local name reservation, storage completion and
initializer analysis are now explicit ordered phases. Ordinary declarations
still bind before their initializer, and parameters retain their adjusted spill
types. No inferred `auto` support or language behavior has been added. Read
docs/m23-auto-binding-phases.md and the latest ledger/contracts; inferred-name
visibility and one-pass initialization need the separate design recorded in
the accompanying research notes before implementation.

M15A2: Traditional `auto` objects with explicit types are supported at block/for
scope in any declaration-specifier position, including aliases and query bases.
They are ordinary addressable automatic objects with unchanged slots and ABI;
no new AST storage/type/backend flag is needed. C23 inferred `auto`, file scope
and storage-class combinations remain explicit subset limits. Read
docs/m15-auto-explicit.md. Native Clang 18 C23 parser gaps are counted separately
on unchanged originals; C11 corroboration is never counted as C23 agreement.

M15B1: Complete fixed `register` arrays may be declared and used in direct
`sizeof`/`typeof` queries without decay. They use ordinary bounded local storage;
`typeof` copies are ordinary arrays unless separately declared register. Taking
the register array's address remains a constraint; array-to-pointer conversion
is explicitly refused, even in queries requiring an inner decay. Register
parameters, VM types and array initializers remain unsupported. Read
docs/m15-register-arrays.md and the latest ledger/contracts/limitations.

M15A1: Scalar block/for objects may use `register` in any declaration-specifier
position. The hint uses ordinary QBE local slots; taking the declared object's
address is rejected, even in unevaluated queries. Pointee addresses through
register pointers remain valid. Storage class is not a type qualifier and does
not propagate through `typeof`. Register parameters remain an explicit subset
limit; arrays are extended by M15b1. Read docs/m15-register-scalars.md and the latest ledger/contracts.
Beyond these explicit auto/register subsets, other storage classes, globals and
full C23 remain unsupported.

M14L4: The typedef storage class may appear anywhere among declaration
specifiers at file, block and C23 for scope, including alias/query-derived bases.
Declarations still use the existing concrete ASTs and shared comma-list bases;
parameters/type names reject typedef, and aliases allocate no runtime storage.
Read docs/m14-typedef-specifier-placement.md and the latest ledger/limitations.
Earlier ordinary-name shadowing, including parameter/prototype lifetimes, remains
supported. Beyond the M15a1/M15b1 register and M15a2 explicit-auto subsets, other
storage classes, VM types and full C23 remain unsupported.
Native for-typedef grammar gaps remain separately classified on unchanged source.

M14k2: semicolon-terminated query-derived file-scope function declarations now
share ordinary prototype registration, compatibility and immutable composite
types. They declare distinct function symbols, not aliases to the query operand.
Query-derived objects and bare definitions remain outside the subset.

M23d2 null-conversion correction: initialization, assignment, arguments and returns
accept checked null pointer constants for query-named nullptr types. Nonconstant
zero objects remain invalid. Explicit null casts remain accepted; exact native
Clang cast gaps are labelled separately, never counted as agreements.

M14k1: a sole unnamed query-derived void parameter now denotes a zero-argument
function, including main, callbacks and compatible prototypes/definitions. Its
written syntax is preserved without creating a runtime parameter or spill slot.
Named, qualified or mixed void parameters remain errors. Bare query-derived definitions,
typedef scopes and other declaration-normalization work remain incomplete.

M23d2: `typeof` and `typeof_unqual` also accept expression operands, preserving
root const/array/function types without operand evaluation. Children still have
their normal constraints and conversions. Existing nullptr types become nameable;
explicit casts obey the null-constant rule including checked implicit null pointer constant
conversion to nullptr objects. VM/atomic/bit-field and alias normalization work
remain unsupported.

M23d1: C23 `typeof` and `typeof_unqual` accept type-name operands. Immutable
qualifiers, arrays and function pointers compose with declarations, casts, layout
queries and fixed signatures. Expression operands, alias-derived bare function
declarations and sole query-derived void parameter normalization remain separate
increments. This remains an explicitly incomplete C23 compiler.

M19f2: switch supports case/default labels, converted integer constant values,
duplicate checking and fallthrough. Linear QBE dispatch evaluates control once;
nested branch/loop targets and C23 standalone labels are supported. Attributes,
GNU case ranges and variably modified types remain unsupported.

M19f1: switch foundation supports integer control and case-free bodies. Break
selects the nearest loop/switch; continue skips switches to its enclosing loop.
Goto into a switch body is supported. Case/default dispatch is implemented in M19f2.

M19e2: direct `goto` resolves function-local labels after the complete body is
checked. Forward/backward jumps and targets inside nested control flow retain
correct fallthrough and loop contexts. Unreachable syntax remains checked and
codegen continues through terminators to preserve later targets. Computed goto,
switch/case/default and variably modified types remain unsupported.

M19e1: named labels have a separate function-wide namespace. C23 standalone
block labels can precede declarations or end a block; secondary labeled
statements still require a child statement. Demand parsing keeps one peek and
resumes postfix/Pratt parsing from consumed identifiers. Switch/case/default
remain separate increments; goto builds on this label foundation.

M19d2: remaining integer `*=`, `/=`, `%=`, `&=`, `^=`, `|=`, `<<=` and `>>=`
are supported. Shifts promote operands independently; all other integer compound
operators use usual arithmetic conversions. All retain one left lvalue and
convert the result back to its stored type. Float/atomic cases remain later work.

M19d1: `+=`/`-=` support current integers and complete-object pointers. One
lvalue address/load/store, usual arithmetic conversions and stored-type results
are explicit; bool uses truth conversion after calculation. Other compound operators are now supported for integers;
floats and atomics are later work.

M19c1/c2: prefix and postfix `++`/`--` update integer and complete-object pointer
lvalues. Operand addresses are evaluated once; narrow/bool conversion and pointer
strides are explicit. Postfix yields the old value, prefix the new. Additive compound
assignment is now supported separately.

M23a2: C23 `nullptr` has its own complete scalar type, neither integer nor
pointer. It converts to pointers and bool, supports equality, scalar control,
comma and valid conditional forms, and has target size/alignment 8. `nullptr_t`
is not a builtin keyword; source naming and header exposure remain later work.

M13m: traditional integer-ICE-zero and `(void *)` null constants now convert to
implemented object/function pointers in initialization, assignment, calls,
returns, equality and conditional expressions. Nonconstant zero is not a null
constant. Nonzero integer/pointer casts and VLAs remain later work.

M13l1: fixed array bounds use checked integer constant expressions, including
sizeof/alignof and short-circuit arithmetic. Prototype parameter names resolve
in explicit temporary scopes without allocating runtime slots. Positive/storage
constraints and adjusted-array ABI behavior remain enforced; VLAs are rejected.

M18b2: static_assert/_Static_assert declarations consume checked integer constant
expressions at file/block scope and in for initializers. Optional ordinary-string
messages preserve all diagnostic bytes safely. Successful assertions emit no
runtime code or message data; VLA/enums/constexpr remain later work.

M18b1: a pure, checked integer constant evaluator preserves target bits/types and
locations, distinguishes nonconstant forms from invalid arithmetic, and handles
short-circuit forms without evaluating skipped arithmetic. Tests/fuzz query this
stage; assertions, fixed bounds and traditional null constants now consume it.

M18a: fixed sizeof expressions/types and alignof/_Alignof type queries use
target layout and unsigned-long results. Operands remain semantically checked
but generate no evaluation, root load or array/function decay. No VLA or general
constant-evaluation support is implied.

M19b: conditional expressions use right-associative Pratt parsing, explicit
arithmetic/pointer common types and selected QBE branches with correct nested
phi predecessors. Void conditionals have effects without dummy values.

M23a1: C23 bool/true/false language keywords use the existing _Bool model
and distinct typed boolean constant ASTs. Preprocessing identifiers remain raw
until expansion; #if true/false and actual macro defined/undef rules stay separate.
Only the boolean subset of M23a is complete.

M14j2: const syntax and modification/conversion constraints preserve qualified
objects and pointees, strip only value-level qualifiers, and normalize function
signatures without making const parameter locals mutable. Immutable type graphs,
C23 array qualification and explicit common pointer conversions are tested.
M19a sequenced comma expressions preserve scalar/void/pointer results without
confusing call arguments or declaration separators. M14i explicit object/object and function/function pointer casts preserve
addresses without granting implicit compatibility or adapting call ABIs. Object/void pointer conversions and mixed equality preserve real types
and explicit conversion nodes, including arrays and pointer objects. Real void types, void-returning functions/callbacks, bare returns and
effect-only casts/discards emit no dummy QBE result. Function designators decay explicitly to function pointers; compatible
callback values, factories and indirect fixed calls preserve once-only target
evaluation and canonical narrow returns. Fixed function suffixes share the single-pass declarator parser, including
parenthesized function names and functions returning array pointers.
C23 definitions may omit parameter names without removing ABI arguments
or caller-side evaluation. Only named parameters receive local spills.
Comma-separated local declarations and for-header declaration lists keep
independent derived types, source-order bindings and initializer evaluation.
Compatible pointers to unknown-bound arrays preserve incomplete referents
without inventing a stride. Composite redeclarations retain known bounds.
Parenthesized local/parameter object declarators and abstract cast types
preserve pointer/array precedence, including int (*p)[3] and int (*p[2])[3].
Integer/pointer casts, typedef names and other qualifiers remain later increments.
Array parameters permit an omitted outer bound, including int a[][3].
Declared incomplete shape remains distinct from the effective pointer.
Literal-bound array parameters retain their declared shape but adjust once
to effective element pointers for signatures, calls and local parameter storage.
Adjacent ordinary string fragments concatenate decoded bytes into one
static array with one trailing NUL, explicit decay and private QBE byte data. Fixed multidimensional
local arrays preserve shape, row strides and one-level decay. Bounds are positive integer literal tokens;
array initializers and general constant-expression bounds remain later work.
Pointer subscripts, scaled offsets, compatible differences/comparisons and
object lvalue addresses share the same typed lowering. Separate concrete typed offset/difference ASTs use target
object sizes and preserve promoted index signedness. Address-of and indirection
use general lvalue-address lowering. Integer/pointer objects
support loads, mutations, compatible values, fixed calls/returns/casts and
scalar truth. Null cancellation &*p evaluates p once without touching its
pointee. All baseline primitive integer types, ordinary byte characters,
explicit promotions/conversions and canonical byte/halfword ABIs remain
supported. String encodings, null constants and full declarators
remain later increments. C23 bool/true/false spelling and full C23 are
unfinished. Includes retain bounded explicit search and direct/computed
quoted/basic angle support.

Preprocessing supports integer/ordinary-byte character conditions and the prior
macro operators. Repeatable -I dir/-Idir adds ordered explicit search paths; quoted
names first search beside the including source. No default system paths or
provided headers exist. General encodings and full C23 remain unfinished. See `docs/m11-quoted-includes.md`,
`docs/milestones.md`, `docs/limitations.md` and `docs/handoff.md`.

## Build and test

Requires a C11 compiler, Make and Python 3 for tests.

```sh
make
sh scripts/build_qbe.sh tools
make test QBE="$PWD/tools/qbe-1.2/qbe"
./build/kcc --help
# Explicit include directories (no default system headers):
# ./build/kcc -I include -Ivendor/include example.c
./build/kcc --tokens tests/corpus/lex/basic.c
./build/kcc --pp-tokens tests/corpus/lex/pp-tokens.c
make fuzz-lex FUZZ_SECONDS=10
make fuzz-compile FUZZ_SECONDS=10
```

The implementation initially targets Linux x86-64, System V ABI, LP64.
QBE 1.2 is the backend baseline. Build it with `sh scripts/build_qbe.sh tools`.
Both full gates now include mandatory M16 executable/ELF evidence. Run
`make test QBE="$PWD/tools/qbe-1.2/qbe"` and
`make test-codegen QBE="$PWD/tools/qbe-1.2/qbe"`.
The compiler itself will not depend on LLVM. CI may use Clang and libFuzzer.

## Reading order

1. `docs/architecture.md`
2. `docs/component-contracts.md`
3. `docs/milestones.md`
4. `docs/c23-coverage.md`
5. `docs/handoff.md`

All compiler stages will have one implementation file each. Each AST construct
has its own struct. Parser functions will document their BNF productions.

## Compile the current subset

```sh
cat > build/example.c <<'EOF'
int factorial(int n);

int main(void)
{
	return factorial(5);
}

int factorial(int n)
{
	if (n < 2)
		return 1;
	return n * factorial(n - 1);
}
EOF
./build/kcc build/example.c > build/example.ssa
tools/qbe-1.2/qbe -t amd64_sysv -o build/example.s build/example.ssa
cc build/example.s -o build/example
./build/example
# Exit status: 120
```

Supported: normalized line endings, backslash-newline splicing, physical source
locations, null directives (#/%:), object-like, fixed-parameter and variadic function-like
macros, diagnostic directives (including #warning), macro operators (including __VA_ARGS__/__VA_OPT__ and raw parameter/optional stringizing and token pasting), int/unsigned/long/ulong literals and locals in four bases with separators, simple assignment, arithmetic,
comparisons, !/&&/||, ~ and bitwise/shift operators, scoped blocks, if/else, while/do/for, break/continue,
implemented integer function prototypes/definitions/parameters, direct calls and recursion.
Both (void) and C23 empty () specify zero parameters. Prototype names are
optional; definition parameter names are required in this subset.

Unsupported: C string expressions, general header-name encoding/system headers,
full conditional expressions, predefined/reserved macro names, wider/other types, globals/storage classes, local
prototypes, function values/pointers, variadic functions, comma/update/compound-assignment
operators. Runtime arithmetic supports int/unsigned/long/ulong; invalid shifts have C
undefined behavior, not a defined masked-count extension. This is not a complete C23 compiler. Main takes no parameters yet.

Loops use `i = i + 1`; ++ and compound assignments are not supported yet.
Limits: 16 MiB source, 128 expression/statement nesting and typed expression
depth, 512 external declarations, 256 distinct functions, 128 parameters/call
arguments, 4096 body items and 256 parameter/local slots per function. Macros:
1024 distinct names, 1024 tokens/definition, 65536 retained replacement tokens,
128 retained expansion frames and 65536 work units (pushes, visits, argument
collection/copies). Arguments: 128 named parameters plus one variadic slot, 128 nested parentheses,
64 nested prescans, 32 active optional-substitution cursors and 65536 auxiliary records (parameters/arguments/token copies
and synthesized spelling views). Generated spelling bytes, including NULs, are
cumulatively capped at 1 MiB per translation unit.

`make test-codegen` also runs separate-object ABI tests with the selected host
compiler. Use `HOST_CC=clang make test-codegen QBE=/path/to/qbe` for Clang.
CI runs GCC and Clang, compiler sanitizers, 564 language-token plus 276 expanded-pp token/spelling agreement cases,
five separate whitespace-policy groups, one inactive-argument diagnostic policy,
generated executables and ABI tests
and bounded lexer/pipeline fuzzing. Fuzzing never runs generated arbitrary code.

## Raw token inspection

`--tokens file.c` dumps language-token kinds and physical starts after null
directives are removed and supported macros expanded. Expansion tokens print
the outermost invocation position, not their definition position.
`--pp-tokens file.c` dumps the raw stream without dispatching directives or
converting numbers/keywords. Each line has:

```text
physical_offset:kind:logical_length:leading_space:at_line_start:non_directive_space
```

The last three fields are 0/1 flags. The final flag records VT/FF in leading
trivia outside comments, for future directive whitespace checks. A block comment
is one separating space; its internal newlines do not end a directive. Newlines
outside comments are explicit raw tokens. Spliced newlines are already removed.

Raw scanning recognizes quoted/prefixed literal boundaries, ASCII pp numbers and
all C23 punctuator spellings (including :: and digraphs). This does not implement
those language features: conversion still rejects unsupported constants, types
and operators. Brace digraphs <%/%> are accepted by the current grammar. Raw
inspection can succeed for text the compiler rejects; it is not a preprocessor
or conformance check. Null/define/undef directives are handled by the compiler.
Header-name context, Unicode/UCNs, full expansion-stack diagnostic notes remain future work. Both debug dumps may show partial output on lexical errors.


## Zero-parameter macro example

```c
#define VALUE() 21
#define ALIAS VALUE
int main(void) { return ALIAS() + VALUE(); }
```

The program exits 42 through the same QBE workflow above. Whitespace/comments/newlines may separate a name from its invocation parentheses.
A bare function-like macro name is not expanded. Source directive lines during
invocation probing/collection remain explicitly unsupported, not speculative.

## Fixed-argument macro example

```c
#define ID(x) x
#define ADD(a, b) ((a) + (b))
int main(void) { return ADD(ID(ID(20)), 22); }
```

This also exits 42. Arguments are collected before expansion; only parentheses
protect commas. An unused argument is not macro-expanded. Argument prescan
cannot consume the source after the enclosing invocation.


## Variadic macro example

```c
#define PLUS(x, ...) x __VA_OPT__(+ __VA_ARGS__)
#define EMPTY
int main(void) { return PLUS(20, 22) + PLUS(0, EMPTY); }
```

This exits 42 through the QBE workflow above. `PLUS(42)`, `PLUS(42,)` and
`PLUS(42, EMPTY)` all expand to `42`. The optional region depends on whether
the variable arguments expand to any tokens, not whether their raw text is empty.
Trailing variable arguments retain separator commas; only parentheses protect
commas during collection. Nested `__VA_OPT__` is rejected at definition time.
GNU named ellipses and comma-swallowing extensions are not implemented.
Variadic macros do not enable variadic C functions or their ABI.


## Stringizing checkpoint

```c
#define DISCARD(x) 42
#define DESCRIBE(x) DISCARD(#x)
int main(void) { return DESCRIBE(a + b); }
```

This exits 42 through QBE: the generated string token is discarded before C
language conversion. The string token may also be used directly as an ordinary string-array
expression in the current compiler. The test-only `build/pp_oracle --pp file.c`
prints expanded preprocessing token kinds and spellings; `--pp-tokens` on the
compiler remains the unexpanded raw inspection mode.

`#x` uses raw arguments, trims outside trivia, collapses separating whitespace
and escapes quotes/backslashes in literal tokens. It does not expand `x` first.
Two-level stringizing exposes whitespace differences between GCC and Clang in
some empty-expansion cases. kcc currently follows the documented GCC behavior;
those five regression groups are not counted as cross-host agreement or an ISO
conformance determination. See the design/limitations before relying on them.


## Stringizing an optional operand

```c
#define DISCARD(x) 42
#define A 7
#define DESCRIBE(x, ...) DISCARD(#__VA_OPT__(x A))
int main(void) { return DESCRIBE(A, 1); }
```

The optional operand becomes the string token `"7 A"`: parameter `x` is
expanded, but the ordinary body name `A` is not rescanned before stringizing.
`DISCARD` then removes the string, so this exits 42 through QBE without requiring
C string expressions. `DESCRIBE(A)` generates `""` and is discarded similarly.
Inner `#parameter` still uses raw arguments and its resulting string is escaped
again by the outer operation. The selected body cannot consume following tokens.

Inactive optional bodies do not expand named arguments. GCC and Clang disagree
on a wrong-arity macro call in such an unused argument; the lazy kcc policy is
tracked separately, not counted as host agreement or a settled ISO ruling.
