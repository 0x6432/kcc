# kcc

An educational compiler written in C, growing from a deliberately small subset
toward C23. Code generation uses QBE. Readability and explicit invariants take
priority over compile-time performance.

## Current checkpoint

M02: on-demand lexer, token inspection, regression tests and fuzz CI. No C
program can be compiled yet. Unsupported input is rejected, never silently
accepted. See `docs/milestones.md` and `docs/limitations.md`.

## Build and test

Requires a C11 compiler, Make and Python 3 for tests.

```sh
make
make test
./build/kcc --help
./build/kcc --tokens tests/corpus/lex/basic.c
make fuzz-lex FUZZ_SECONDS=10
```

The implementation initially targets Linux x86-64, System V ABI, LP64.
QBE 1.2 is the initial backend baseline; it is not needed until M03.
The compiler itself will not depend on LLVM. CI may use Clang and libFuzzer.

## Reading order

1. `docs/architecture.md`
2. `docs/component-contracts.md`
3. `docs/milestones.md`
4. `docs/c23-coverage.md`
5. `docs/handoff.md`

All compiler stages will have one implementation file each. Each AST construct
has its own struct. Parser functions will document their BNF productions.
