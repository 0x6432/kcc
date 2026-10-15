# kcc

An educational compiler written in C, growing from a deliberately small subset
toward C23. Code generation uses QBE. Readability and explicit invariants take
priority over compile-time performance.

## Current checkpoint

M08b: Integer parameter and argument lists are implemented with name-independent function signatures, source-order prototype visibility and argument-count checks. Parameters receive the first local slots and share scope with the outermost body declarations. QBE w entry values are stored into those slots; nested call arguments finish emitting before the call line.

See `docs/milestones.md`, `docs/limitations.md` and `docs/handoff.md`.

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
	int sum = 0;

	for (int i = 0; i < 5; i = i + 1) {
		if (i == 2)
			continue;
		sum = sum + i;
	}
	return sum;
}
EOF
./build/kcc build/example.c > build/example.ssa
tools/qbe-1.2/qbe -t amd64_sysv -o build/example.s build/example.ssa
cc build/example.s -o build/example
./build/example
# Exit status: 8
```

Supported: decimal int literals, int locals, simple assignment, arithmetic,
comparisons, !/&&/||, nested blocks/shadowing, if/else, while, break/continue, do/while, and for (including int initializer declarations).
Unsupported: function calls/prototypes/parameters, comma/update/compound-assignment operators, other types and preprocessing. This is not a complete C23 compiler.

Loops use `i = i + 1`; ++ and compound assignments are not supported yet.
Limits: 16 MiB source, 128 expression/statement nesting, 4096 block items
and 256 locals across the function.
