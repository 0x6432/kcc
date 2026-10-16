# M14l3b follow-up: exact native for-typedef diagnostics

Design recorded before changing tests. Checkpoint c3cc992 passed local checks,
but GitHub run 38945901266 failed its GCC normal test job. Clang and fuzz passed.
The new parameter-shadowing suite recognized Clang's C23 for-typedef grammar
gap, but not the GCC spelling already recognized by test_for_typedefs.py.

The failing original is the suite's exact final C23 program: a parameter T
hides an outer typedef, a for-initializer typedef briefly hides the parameter,
and typeof(T) after the loop must refer to the restored parameter object.
The CI host rejects the valid for-typedef grammar with the single error:
`declaration of non-variable 'T' in 'for' loop initial declaration`.
This is a native feature gap, not a kcc acceptance bug or native agreement.
Do not rewrite the source, remove the fixture or restore a C17 restriction.

Change only the exact-source native diagnostic classifier and its unit guards.
Accept either the observed GCC single error or the existing Clang single error,
only with ordinary compile-failure status 1 and the exact original fixture.
Reject success, signals, unrelated sources/names and additional error/warning diagnostics.
Keep kcc rejection/acceptance, all C sources and version unchanged. Retain the
GCC named-void warning classifier independently; it is a required diagnostic,
not a strict native rejection or a runtime agreement.

Validate both diagnostic spellings and negative guards, then four-host focused
original/QBE/ABI checks, full normal/QBE regression, both-host targeted sanitizers
and bounded compile-only fuzz against frozen source. Record prior CI failure
and new exact-commit CI separately; no invalid or generated C may execute.

## Completion evidence

Both diagnostic variants and their negative guards passed, including the actual
failed-CI source/error tuple. Full normal/QBE, focused four-host original/ABI,
both-host targeted sanitizers and bounded compile-only fuzz passed on frozen
source. See the latest ledger entry for exact counts, reused-binary source
verification and separate predecessor/new-commit CI status.
