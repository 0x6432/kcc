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
`p + i`, `i + p`, `p - i`, `p[i]`, and chains of these operations rooted in
that local pointer use its saved runtime stride; indexing within the resulting
array uses the fixed element size. A pointer object may be reassigned, but its
stride remains the size captured by its declaration. Normal C restrictions on
compatible array sizes and pointer arithmetic still apply to the program.

`sizeof *p` uses that saved size, evaluates the direct pointer operand (including
volatile or atomic loads), and is not an integer constant expression. It does
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
- Runtime-stride pointer arithmetic requires a direct supported local pointer or
  an offset expression rooted in one. Updates (`++`, `--`, `+=`, `-=`), pointer
  subtraction, and arithmetic on conditional, cast, call, indirect, or other
  expressions lacking tracked size provenance are rejected. Arithmetic on
  `&vla` still has no tracked size. A conditional combining a VM and a fixed
  array pointer keeps the runtime marker instead of assuming a fixed stride.
- `sizeof` on a VLA expression supports the existing direct VLA-object forms
  and direct `sizeof *p` only; `sizeof p[i]`, `sizeof *(p+i)`, and other
  expressions requiring evaluated subexpressions are rejected rather than
  suppressing their side effects. `typeof` and inferred `auto` cannot rebind a
  VM type. This avoids losing captured size and jump-scope information.
- The existing 1 MiB type-size and local-storage limits, cumulative VLA storage
  policy, and requirement to link `abort` and any used runtime helpers apply.
  This is not a claim of full C11/C23 VM or VLA conformance.

`tests/test_vla_pointer.py` covers defined programs against GCC and Clang,
QBE execution, mixed native/kcc pointer ABI in both directions, size/stride
capture, bounds failures, qualifiers, loops, jumps, switch, unsupported forms,
and type-provenance safeguards. It is a focused regression, not a full suite.
