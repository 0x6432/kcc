# Block-local pointers to runtime-bound arrays

This is a bounded extension, not general C variably modified (VM) type support.
Inside a function, an automatic or register pointer may be declared directly to
an array with one runtime bound and complete, fixed-size element type, including
fixed inner array dimensions. For example:

```c
int n = 3;
int matrix[2][3] = {{0}, {0, 0, 42}};
int (*p)[n++] = matrix;
int answer = p[1][2];  /* saved row stride: 3 * sizeof(int) */
unsigned long bytes = sizeof *p; /* 12; does not evaluate n again */
```

Each execution of the declaration evaluates its bound exactly once, before the
initializer, and saves the byte size for the lifetime of that declaration.
Re-entering a loop or jumping back before the declaration reevaluates it.
`p + i`, `i + p`, `p - i`, `p[i]`, prefix/postfix `++` and `--`, and
`p += i` / `p -= i` use the saved runtime stride. Offset and update results can
be indexed or used in further tracked offsets. Updates require the direct local
pointer lvalue; they evaluate the lvalue and right operand once and return the
correct old or new value. Volatile accesses use the existing helpers and atomic
pointer updates use the existing sequentially consistent libatomic operations.
Indexing within the resulting array uses the fixed element size.

Pointer subtraction accepts tracked VM pointer expressions and compatible
fixed-size array pointers, in either order, when every VM operand has tracked
size provenance. It divides the signed byte difference by the saved runtime
stride. When two VM pointers participate, the left size is used. As in C, the
program must satisfy pointer-subtraction and array-type compatibility rules,
including equal evaluated bounds where required; this compiler does not check
that equality at runtime. A pointer object may be reassigned, but its stride
remains the size captured by its declaration. Direct addresses of supported VLA
objects (`&a`) also carry the captured size through offsets, subscripting and
pointer differences, for example `(&a + 1) - &a`. The ordinary C bounds and
compatibility requirements still apply.

`sizeof` of a tracked VM row uses its saved size and evaluates the row
expression, including indices, calls, pointer updates and volatile or atomic
accesses. Supported forms include `sizeof *p`, `sizeof p[i++]`,
`sizeof *(p + i)`, `sizeof *(p++)`, and `sizeof *(&a + i)` for a
  supported VLA object. It is not an integer constant expression. It does
not dereference the resulting pointer to read array elements. Nested unevaluated
contexts, such as `sizeof(sizeof *p)`, do not perform that load. Ordinary
pointer size, conversion, comparison, and calls retain the existing x86-64
SysV pointer representation; no VM parameter or new function ABI is introduced.
Qualifiers on the pointer and fixed-size referent elements remain supported
within the compiler's existing qualifier restrictions.

Invalid nonpositive bounds and bounds whose referent array exceeds 1 MiB call
`abort` at declaration, before initialization. The division-based limit check
prevents multiplication overflow. Unlike a VLA object, this declaration allocates
only an ordinary pointer slot, not array storage, and does not consume the
cumulative dynamic VLA budget. The ordinary pointer slot still counts toward the
existing fixed-local storage limit. Existing VLA object allocation and alignment
budget checks are unchanged.

A direct `goto` or switch dispatch may not enter the scope of such an identifier;
leaving the scope or returning to a point before the declaration is permitted.
The runtime bound is evaluated on each actual entry through the declaration.

## Deliberate limits

- Runtime inner dimensions of VLA **objects**, multiple runtime dimensions,
  general VM typedefs, VM parameters, pointer chains, file-scope declarations,
  and static, thread-local or extern VM pointers remain unsupported.
- Runtime-stride pointer arithmetic and subtraction require tracked VM pointer
  provenance: a direct supported local pointer, or an offset or update result
  rooted in one. Update lvalues must be the direct local identifier. Arithmetic
  and subtraction involving a conditional, cast, call, indirect, or other VM
  expression without tracked provenance are rejected. A conditional combining a VM and a fixed array
  pointer keeps the runtime marker instead of assuming a fixed stride.
- `sizeof` on a VLA expression supports existing direct VLA-object forms and
  tracked pointer indirection, offsets, subscripts and updates. Untracked
  expressions (including conditional and cast-based VM pointers) remain rejected
  rather than suppressing side effects. `typeof` and inferred `auto` cannot rebind a
  VM type. This avoids losing captured size and jump-scope information.
- The existing 1 MiB type-size and local-storage limits, cumulative VLA storage
  policy, and requirement to link `abort` and any used runtime helpers apply.
  This is not a claim of full C11/C23 VM or VLA conformance.

Runtime inner VLA object dimensions remain a separate architectural task: the
current array type models a runtime bound as incomplete, while object allocation,
size queries and indexing generally assume complete, fixed-size element types.
Supporting them safely requires captured per-dimension sizes, checked products,
stride propagation through expressions and VM scopes, and allocation/lifetime
integration; this extension does not weaken those checks.

`tests/test_vla_pointer.py` and `tests/test_vla_pointer_updates.py` cover defined
programs against GCC and Clang, QBE execution, mixed native/kcc pointer ABI in both directions, size/stride
capture, bounds failures, qualifiers, loops, jumps, switch, unsupported forms,
and type-provenance safeguards. Clang 15 rejects four atomic pointer compound
assignment reference cases; they are explicitly counted as native oracle gaps,
while kcc/QBE and GCC still run them. These are focused regressions, not a full
suite.
