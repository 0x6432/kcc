# kcc

An educational compiler written in C, growing from a deliberately small subset
toward C23. Code generation uses QBE. Readability and explicit invariants take
priority over compile-time performance.

## Current checkpoint

M05: compile local `int` declarations, assignment and expression statements
inside a single `int main(void)`.
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
cat > build/example.c <<'EOF'
int main(void)
{
	int x = 3;
	int y = x * 4;

	x = y = 7;
	return x + y;
}
EOF
./build/kcc build/example.c > build/example.ssa
tools/qbe-1.2/qbe -t amd64_sysv -o build/example.s build/example.ssa
cc build/example.s -o build/example
./build/example
# Exit status: 14
```

Supported expressions: decimal int literals, local names, parentheses, unary
`+`/`-`, binary `+`, `-`, `*`, `/`, `%`, and right-associative `=`. Declarations
introduce one int object with an optional initializer. Empty statements and
falling off main (returning zero) are supported.

Nested blocks, shadowing, if/else, calls and preprocessing are not supported yet.
Source limit: 16 MiB; expression nesting/typed-tree depth: 128; function-body
items: 4096; locals: 256. This is not a complete C23 compiler.
