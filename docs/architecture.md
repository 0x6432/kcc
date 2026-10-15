# Architecture decisions

Approved: Linux x86-64 ELF/System V; compiler implementation in portable C11;
strict, expanding C23 subset; own on-demand preprocessor; external QBE,
assembler/linker and system libc; self-hosting later; GitHub Actions CI.

## Pipeline and stage boundaries

`raw source -> source_prepare -> pp_lexer -> preprocessor -> token_from_pp -> parser -> sema -> QBE IL`

M09a implements the input-newline policy and line splicing before lexing, not
full preprocessing. source_prepare is explicit/fallible and runs before any
borrowed token spelling exists. CRLF and lone CR normalize to LF; only an
immediate backslash-newline pair is deleted, without rescanning output. Source
bytes remain bounded buffers; token generation is still on demand. Changed
sources retain original bytes plus sparse offset checkpoints for physical
locations. Prepared token offsets index logical bytes; diagnostics translate
those offsets, while name lookup/codegen read logical spelling slices.

M10d dispatches null/define/undef directives and rescans object/fixed/variadic
function-like replacements before language conversion. Includes remain
unsupported; the host preprocessor is not invoked by the compiler. Complete phase ordering, encoding/UCNs and final-line constraints are
not claimed. Missing terminal newlines remain an acceptance extension; no
synthetic newline is appended. Reference: WG14 N3096 5.1.1.2 and 6.10,
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

One implementation file per stage: `source.c`, `lex.c`, `preprocess.c`, `ast.c`,
`parse.c`, `type.c`, `sema.c`, `codegen.c`. Supporting files are `main.c`,
`diagnostic.c`, and `arena.c`. Add files only when there is working behavior to
put in them. Public declarations are in corresponding headers.

Sources are read into bounded byte buffers. Tokens are generated on demand, not
as a whole-file vector. Lookahead currently caches one parser-visible token.
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

## M09b raw/language token boundary

lex.c owns raw preprocessing-token scanning and the separate token_from_pp
conversion. pp_token contains no numeric value or keyword category. It retains
logical spelling, leading_space, at_line_start and has_non_directive_space
(VT/FF outside comments). Horizontal spacing may be collapsed to flags; external
newlines are explicit tokens. Block comments become one space and never create
directive ends from their internal newlines. Physical locations remain mapped
by source.c. Header-name context/Unicode/UCNs/macro provenance are not complete.

## M09c preprocessor ownership

preprocess.c owns the sole parser-facing input path. struct preprocessor owns
raw input and caches one language token. Its next/peek APIs remove null
#/%: directives and external newlines before token_from_pp performs conversion.
Parser input changed from struct lexer to struct preprocessor; every consumer
was updated, and the temporary lexer adapter was removed. AST/sema/codegen
interfaces and parser grammar remain unchanged. There is no token vector.

Only a raw marker with at_line_start starts a directive; block-comment internal
newlines do not reset it. Null directives contain only allowed trivia through
newline or the existing EOF extension. VT/FF are allowed before a marker, but
not after it outside comments. Known unsupported directives, unknown names,
malformed names and misplaced markers diagnose; no directive is silently
expanded/ignored as if implemented. Failed lines are drained as raw tokens so
their bodies cannot leak into normal C conversion. A nonempty error token marks
the directive, even if the bad separator is at EOF. Distinct raw lexical errors
remain diagnostics; repeated peek/EOF never repeats them. Debug token inspection
can resume after a bad line, while compilation rejects it before any IL.

M10a extends this stage, not the parser grammar. The preprocessor owns its macro
arena; destroy it after AST use, before destroying source. Raw token location
addresses spelling and expansion_location addresses the outermost invocation.
Language token spelling_location addresses spelling; location is for diagnostics.
Sema name comparison and codegen symbol spelling must never use location as text.
M10b replaces active-frame suppression with fixed-size token-carried hide sets.
A stable macro identity is one bit in that set. Object expansion inherits the
name's set and adds its own bit; function expansion intersects the name/closing
parenthesis sets before adding its bit. A cursor owns one pending unexpanded
token separate from the cached language token. Lookahead can pop completed
streams without losing availability information. Only source-origin tokens
can dispatch directives. Generated # never does; source directives encountered
during invocation probing are explicitly unsupported.

M10c adds fixed parameter indexes on definition tokens. Concrete arena-owned
parameter, argument and argument-token records outlive frames borrowing them.
The main expansion_cursor reads source; isolated argument cursors end at their
own EOF, never the following source. Used arguments are prescanned once, without
prematurely hiding the outer macro. Substitution streams union each cached
token's hide set with the invocation base. Unused arguments are not expanded;
language conversion happens only on final output, not prescan. Temporary heap
cursors are freed on success/error; all retained records/work are bounded.

M10d adds one argument slot after the named parameters, retaining raw separator
commas in its token list. __VA_ARGS__ indexes that slot. __VA_OPT__ markers and
closing boundaries are annotated on the flat immutable replacement list after
balanced definition-time validation. The variable slot's cached prescan decides
presence; selected bodies stay in the current replacement stream so rescan can
cross optional boundaries. No recursive optional-body cursor or new record kind.

See m10-variadics.md and m10-fixed-arguments.md for current contracts. Earlier
M10 documents describe the incremental checkpoints. Parser/AST/sema/QBE APIs are
unchanged. Headers, conditions and macro operators remain later checkpoints. Predefined location
macros will require richer provenance than the current outermost diagnostic
location; do not implement __LINE__ by guessing from definition spelling.

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
