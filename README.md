# kcc

An educational compiler written in C, growing from a deliberately small subset
toward C23. Code generation uses QBE. Readability and explicit invariants take
priority over compile-time performance.

## Current checkpoint

M09b: raw preprocessing tokens are now distinct from language tokens. The raw stream preserves newline/spacing state and scans numbers without assigning values. Keyword, integer and supported-punctuator conversion is a separate lazy step. Parser grammar and M08 code generation stay unchanged; directives and macro expansion remain unimplemented.

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
locations, decimal int literals, int locals, simple assignment, arithmetic,
comparisons, !/&&/||, scoped blocks, if/else, while/do/for, break/continue,
int function prototypes/definitions/parameters, direct calls and recursion.
Both (void) and C23 empty () specify zero parameters. Prototype names are
optional; definition parameter names are required in this subset.

Unsupported: directives/macros, other types, globals/storage classes, local
prototypes, function values/pointers, variadics, comma/update/compound-assignment
operators. This is not a complete C23 compiler. Main takes no parameters yet.

Loops use `i = i + 1`; ++ and compound assignments are not supported yet.
Limits: 16 MiB source, 128 expression/statement nesting and typed expression
depth, 512 external declarations, 256 distinct functions, 128 parameters/call
arguments, 4096 body items and 256 parameter/local slots per function.

`make test-codegen` also runs separate-object ABI tests with the selected host
compiler. Use `HOST_CC=clang make test-codegen QBE=/path/to/qbe` for Clang.
CI runs GCC and Clang, compiler sanitizers, generated executables, ABI tests
and bounded lexer/pipeline fuzzing. Fuzzing never runs generated arbitrary code.

## Raw token inspection

`--tokens file.c` still dumps converted language-token kinds and physical starts.
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
or conformance check. Header-name context, Unicode/UCNs and macro provenance
remain future work. Both debug dumps may show partial output on lexical errors.
