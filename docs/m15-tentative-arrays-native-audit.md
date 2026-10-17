# M15g2 native storage audit supplement

**Confirmed: the six audited Clang outcomes have actual undersized allocated storage, not merely incorrect ELF `st_size` metadata.** Compiler-emitted `.zero` reservations and the assembled ELF `.bss` section size independently agree on the short extent. No linking or C execution occurred.

## Method and scope

- Reused the exact four frozen owner originals from `m15g2-native-warning-audit-probes.json`; verified their recorded source SHA-256. Each input is the unchanged original plus the same single trailing newline used in the prior audit. No source rewriting or extra storage was introduced.
- Compiled all four with Clang18 and GCC14, and the two keyword-independent originals with Clang15: **10 object compilations and 10 assembly compilations**, all status 0 with empty stdout. Clang15 query originals remain keyword-ineligible; they were not rewritten or compiled here.
- Object flags: `HOST -std=c2x -pedantic-errors -fno-common -c owner.c -o owner.o`. Assembly uses the same common flags with `-S` instead of `-c`.
- Inspected each object using `readelf -SW` and `readelf -sW`. `.bss` is `NOBITS`: its section size is allocated zero-filled address-space extent, not bytes physically stored in the object. The evidence below does not rely on symbol size alone.
- All inputs, assembly, objects, full commands/status/stdout/stderr, section/symbol evidence and hashes remain under the unique outside directory `/data/tools/m15g2-native-storage-nwa1canp`. Machine-readable record: `/data/tools/m15g2-native-storage-nwa1canp/evidence.json`; exact current version output: `versions.json` beside it.
- No repository/shared-build changes, linking, runtime checks, or kcc invocation. These are native compile/storage observations only.

## Exact compiler versions

- `/usr/bin/gcc14-gcc`: `gcc14-gcc (GCC) 14.2.1 20250110 (Red Hat 14.2.1-7)`
- `/usr/bin/clang-18`: `clang version 18.1.8 (AWS 18.1.8-6.amzn2023.0.3)`
- `/usr/bin/clang-15`: `clang version 15.0.7 (AWS 15.0.7-3.amzn2023.0.4)`

## Independent allocation evidence

| Original | Compiler | Required owned allocation | Emitted reservation | Actual entire `.bss` |
| --- | --- | --- | --- | --- |
| A | gcc14-gcc | items=12 bytes | `.zero 12` | 12 bytes |
| B | gcc14-gcc | rows=24 bytes | `.zero 24` | 24 bytes |
| C | gcc14-gcc | items=12 bytes | `.zero 12` | 12 bytes |
| D | gcc14-gcc | items=12, other=4 bytes | `.zero 12 + .zero 4` | 16 bytes |
| A | clang-18 | items=12 bytes | `.zero 4` | 4 bytes |
| B | clang-18 | rows=24 bytes | `.zero 12` | 12 bytes |
| C | clang-18 | items=12 bytes | `.zero 4` | 4 bytes |
| D | clang-18 | items=12, other=4 bytes | `.zero 4 + .zero 4` | 8 bytes |
| A | clang-15 | items=12 bytes | `.zero 4` | 4 bytes |
| B | clang-15 | rows=24 bytes | `.zero 12` | 12 bytes |

For A/C, Clang reserves only 4 bytes for the required 12-byte `items`; for B it reserves only 12 bytes for required 24-byte `rows`. For D it reserves `items=4` and `other=4`, with an entire `.bss` of only 8 bytes versus the required 16. There is no extra `.bss` extent concealing the missing storage. GCC14 emits the full expected extents for the exact same sources.

### Object section lines (`readelf -SW`)

```text
A gcc14-gcc: [ 4] .bss              NOBITS          0000000000000000 0000a0 00000c 00  WA  0   0  8
B gcc14-gcc: [ 4] .bss              NOBITS          0000000000000000 000080 000018 00  WA  0   0 16
C gcc14-gcc: [ 4] .bss              NOBITS          0000000000000000 000088 00000c 00  WA  0   0  8
D gcc14-gcc: [ 4] .bss              NOBITS          0000000000000000 000088 000010 00  WA  0   0  8
A clang-18: [ 4] .bss              NOBITS          0000000000000000 0000e4 000004 00  WA  0   0  4
B clang-18: [ 4] .bss              NOBITS          0000000000000000 000098 00000c 00  WA  0   0  4
C clang-18: [ 4] .bss              NOBITS          0000000000000000 0000c8 000004 00  WA  0   0  4
D clang-18: [ 4] .bss              NOBITS          0000000000000000 0000a0 000008 00  WA  0   0  4
A clang-15: [ 4] .bss              NOBITS          0000000000000000 0000e4 000004 00  WA  0   0  4
B clang-15: [ 4] .bss              NOBITS          0000000000000000 000098 00000c 00  WA  0   0  4
```

### Clang data reservations

**A — clang-18**

```asm
	.type	items,@object                   # @items
	.bss
	.globl	items
	.p2align	2, 0x0
items:
	.zero	4
	.size	items, 4

	.ident	"clang version 18.1.8 (AWS 18.1.8-6.amzn2023.0.3)"
```

**B — clang-18**

```asm
	.type	rows,@object                    # @rows
	.bss
	.globl	rows
	.p2align	2, 0x0
rows:
	.zero	12
	.size	rows, 12

	.ident	"clang version 18.1.8 (AWS 18.1.8-6.amzn2023.0.3)"
```

**C — clang-18**

```asm
	.type	items,@object                   # @items
	.bss
	.globl	items
	.p2align	2, 0x0
items:
	.zero	4
	.size	items, 4

	.ident	"clang version 18.1.8 (AWS 18.1.8-6.amzn2023.0.3)"
```

**D — clang-18**

```asm
	.type	items,@object                   # @items
	.bss
	.globl	items
	.p2align	2, 0x0
items:
	.zero	4
	.size	items, 4

	.type	other,@object                   # @other
	.globl	other
	.p2align	2, 0x0
other:
	.zero	4
	.size	other, 4

	.ident	"clang version 18.1.8 (AWS 18.1.8-6.amzn2023.0.3)"
```

**A — clang-15**

```asm
	.type	items,@object                   # @items
	.bss
	.globl	items
	.p2align	2
items:
	.zero	4
	.size	items, 4

	.ident	"clang version 15.0.7 (AWS 15.0.7-3.amzn2023.0.4)"
```

**B — clang-15**

```asm
	.type	rows,@object                    # @rows
	.bss
	.globl	rows
	.p2align	2
rows:
	.zero	12
	.size	rows, 12

	.ident	"clang version 15.0.7 (AWS 15.0.7-3.amzn2023.0.4)"
```

## Exact unchanged originals

### A: earlier decay then visible known outer completion

Original SHA-256: `aaa9f5e9c2741ed5710de800d8ad0fd3bdc58d0fdfcc4e8b32a9ddfc2b861095`.

```c
int items[]; int *earlier(void) { return items; } extern int items[3]; int main(void) { if(sizeof items!=12 || items[0] || items[1] || items[2]) return 1; items[2]=42; return earlier()==items?earlier()[2]:2; }
```

### B: unknown rows gain two rows before runtime second-row access

Original SHA-256: `da781d28946a787c39e903ddca78b29ef5f09e72649bd78ab67a27ec54e2089e`.

```c
int rows[][3]; int (*earlier(void))[3] { return rows; } extern int rows[2][3]; int main(void) { if(sizeof rows!=24 || rows[1][2]) return 1; rows[1][2]=42; return earlier()[1][2]; }
```

### C: earlier unknown array query preserves pointer identity after completion

Original SHA-256: `6a3f97677ec5b9404b820e3cd776223f6e1a9d2814a098f585bca93e224f4f5f`.

```c
int items[]; typedef typeof(items) Saved; Saved *earlier(void) { return &items; } extern int items[3]; int main(void) { if(sizeof items!=12 || items[2]) return 1; items[2]=42; return earlier()==&items?(*earlier())[2]:2; }
```

### D: captured unknown alias independently finalizes separate object to one

Original SHA-256: `9edcea02e3a5a9b12e45319261424469b704d219741c3a9cfaeb9fc821b161ba`.

```c
int items[]; typedef typeof(items) Saved; Saved other; extern int items[3]; int main(void) { if(items[2] || other[0]) return 1; items[2]=40; other[0]=2; return items[2]+other[0]; }
```

## Interpretation / classifier consequence

N3096 6.9.2p2 requires the final composite type for tentative storage; 6.2.7 and 6.7.6.2 preserve the later known compatible bound. Only a still-unknown final outer bound becomes one. All four `items`/`rows` canonicals have a later known bound; D’s independently captured `other` remains unknown and correctly defaults to one element. The prior normative audit in `m15g2-native-warning-audit.md` cites the locally available N3096 text/PDF.

Therefore the existing exact Clang cases are genuinely native storage-underallocation bugs. Keep their originals compile-only and exclude those particular undersized native objects from linking, execution, and runtime-agreement counts. This finding is materially different from QBE ELF objects that omit `.size` but reserve the correct bytes: the native Clang `.zero` directives **and actual `.bss` extent are both too small**. A future corrected layout is not the old bug and must satisfy the separately approved correct-layout guards.

No native runtime agreement, actual Ubuntu CI result, or g2 focused-suite pass is claimed.
