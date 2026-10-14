# Architecture decisions

Approved: Linux x86-64 ELF/System V; compiler implementation in portable C11;
strict, expanding C23 subset; own on-demand preprocessor; external QBE,
assembler/linker and system libc; self-hosting later; GitHub Actions CI.

## Pipeline and stage boundaries

`source -> lexer -> preprocessor -> parser -> sema -> QBE IL`

The initial no-directive subset bypasses preprocessing explicitly. It does not
invoke the host preprocessor. M09 inserts preprocessing without changing the
parser's token-stream contract. Translation-phase behavior is incomplete until
then and must be reported as such.

One implementation file per stage: `source.c`, `lex.c`, `preprocess.c`, `ast.c`,
`parse.c`, `type.c`, `sema.c`, `codegen.c`. Supporting files are `main.c`,
`diagnostic.c`, and `arena.c`. Add files only when there is working behavior to
put in them. Public declarations are in corresponding headers.

Sources are read into bounded byte buffers. Tokens are generated on demand, not
as a whole-file vector. Lookahead caches at most two parser-visible tokens.
Macro expansion uses explicit streams and rescan state; it must not force an
entire translation unit into a token vector.

Each concrete AST construct is a distinct struct. A common header contains the
kind and location; dispatch uses that kind and casts to the corresponding
struct. No universal union holding every construct and no typedefs. The arena
owns AST memory until the compilation completes. Source slices remain valid for
that lifetime. Typed AST annotations are written by sema, never by codegen.

Recursive descent handles declarations and statements. Pratt parsing handles
expressions, with one visible binding-power table. Every parsing routine has a
BNF comment; expression documentation explains associativity as well as binding
power. Typedef-name classification uses parser scope information only as needed
for syntactic ambiguity. Sema independently validates names and declarations.

The driver initially emits QBE IL on stdout. QBE and the host compiler driver
perform assembly/linking outside kcc. Process orchestration comes later; avoid
shell interpolation of user paths. Diagnostics go to stderr. A failed compile
must not emit usable-looking partial IL; complete validation precedes output.

## Target model and QBE limits

LP64: char 8 bits, short 16, int 32, long/pointer 64. Plain char is signed.
Little endian. Additional implementation-defined choices must be added to the
coverage matrix before their first use.

QBE has `w`/`l` integer and `s`/`d` floating temporaries; no pointer type.
Pointers lower to `l`. Aggregate types and subword ABI types exist, as do
variadic call/function conventions. This is not automatic C23 coverage.
Wide integers, long double, atomics, complex arithmetic, VLAs, bit-field layout
and some ABI cases require explicit lowering or runtime support and focused
cross-compiler tests. Never silently map them to a smaller/different type.

Backend baseline: QBE 1.2 official release, SHA256
`a6d50eb952525a234bf76ba151861f73b7a382ac952d985f2b9af1df5368225d`.
Reference: https://c9x.me/compile/doc/il.html
Release: https://c9x.me/compile/release/qbe-1.2.tar.xz

## Coding rules

Snake_case, no typedefs, Linux brace placement, tabs at eight-column stops for
indentation and alignment. No braces around single-statement bodies unless
needed to avoid dangling-else ambiguity. Prefer named intermediate values and
explicit branches. Check allocation, arithmetic bounds and I/O failures.
Use only small explanatory helpers; do not hide behavior in clever macros.
Test/library-mandated entry point names are the only naming exceptions.

## Resource limits

Stay comfortably below the stated 4 GB sandbox budget. Build dependencies
outside the repository; never commit binaries or fuzz corpora generated during
runs. Fuzz runs have time, input-size and memory limits. Track retained corpus
size. Add limits for parser nesting and macro expansion before fuzzing those
features, and report limit failures rather than crash.
