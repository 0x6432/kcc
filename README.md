# kcc

An educational compiler written in C, growing from a deliberately small subset
toward C23. Code generation uses QBE. Readability and explicit invariants take
priority over compile-time performance.

## Current checkpoint

M04: compile a single `int main(void)` returning an integer arithmetic expression.
On-demand lexing, BNF-documented recursive descent and Pratt expressions,
separate AST structs, semantic analysis and QBE emission are in place.
Unsupported input is rejected. See `docs/milestones.md` and
`docs/limitations.md`.

## Build and test

Requires a C11 compiler, Make and Python 3 for tests.

```sh
make
make test
./build/kcc --help
./build/kcc --tokens tests/corpus/lex/basic.c
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
printf 'int main(void) { return (2 + 3) * 4; }\n' > build/example.c
./build/kcc build/example.c > build/example.ssa
tools/qbe-1.2/qbe -t amd64_sysv -o build/example.s build/example.ssa
cc build/example.s -o build/example
./build/example
# Exit status: 20
```

Supported expressions: decimal int literals, parentheses, unary `+`/`-`, and
binary `+`, `-`, `*`, `/`, `%`. No variables, declarations, calls or control
flow yet. Nesting and AST depth are limited to 128, sources to 16 MiB. This is
not a complete C23 compiler.
