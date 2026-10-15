# kcc

An educational compiler written in C, growing from a deliberately small subset
toward C23. Code generation uses QBE. Readability and explicit invariants take
priority over compile-time performance.

## Current checkpoint

M10c: fixed-parameter function-like macros now collect raw arguments, prescan
used arguments in isolated streams, and substitute with per-token suppression
preserved. Empty arguments, nested calls and callbacks are supported. Variadics,
macro operators and full C23 coverage remain unfinished.

See `docs/m10-fixed-arguments.md` for ownership, limits and subset policy.
Previous M10a/M10b design documents remain as historical checkpoints.

See `docs/milestones.md`, `docs/limitations.md` and `docs/handoff.md`.

## Build and test

Requires a C11 compiler, Make and Python 3 for tests.

```sh
make
make test
./build/kcc --help
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
locations, null directives (#/%:), object-like and fixed-parameter function-like
macros, decimal int literals, int locals, simple assignment, arithmetic,
comparisons, !/&&/||, scoped blocks, if/else, while/do/for, break/continue,
int function prototypes/definitions/parameters, direct calls and recursion.
Both (void) and C23 empty () specify zero parameters. Prototype names are
optional; definition parameter names are required in this subset.

Unsupported: variadic macro parameters/arguments and __VA_OPT__,
token pasting, stringizing, includes,
conditional directives, predefined/reserved macro names, other types, globals/storage classes, local
prototypes, function values/pointers, variadics, comma/update/compound-assignment
operators. This is not a complete C23 compiler. Main takes no parameters yet.

Loops use `i = i + 1`; ++ and compound assignments are not supported yet.
Limits: 16 MiB source, 128 expression/statement nesting and typed expression
depth, 512 external declarations, 256 distinct functions, 128 parameters/call
arguments, 4096 body items and 256 parameter/local slots per function. Macros:
1024 distinct names, 1024 tokens/definition, 65536 retained replacement tokens,
128 retained expansion frames and 65536 work units (pushes, visits, argument
collection/copies). Arguments: 128 fixed parameters, 128 nested parentheses,
64 nested prescans and 65536 auxiliary records (parameters/arguments/token copies).

`make test-codegen` also runs separate-object ABI tests with the selected host
compiler. Use `HOST_CC=clang make test-codegen QBE=/path/to/qbe` for Clang.
CI runs GCC and Clang, compiler sanitizers, 374 host-preprocessor token/spelling oracle cases, generated
executables, ABI tests
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
Header-name context, Unicode/UCNs, full expansion-stack diagnostic notes and
variadic macros remain future work. Both debug dumps may show partial output on lexical errors.


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
cannot consume the source after the enclosing invocation. Variadics are next.
