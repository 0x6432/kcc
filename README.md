# kcc

An educational compiler written in C, growing from a deliberately small subset
toward C23. Code generation uses QBE. Readability and explicit invariants take
priority over compile-time performance.

## Current checkpoint

M13k: array parameters permit an omitted outer bound, including int a[][3].
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
make test
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
Run executable tests with `make test-codegen QBE="$PWD/tools/qbe-1.2/qbe"`.
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
language conversion. Using it directly as a C expression still diagnoses that
string literals are unsupported. The test-only `build/pp_oracle --pp file.c`
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
