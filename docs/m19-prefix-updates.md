# M19c1: prefix increment/decrement (design before implementation)

Add prefix ++ and -- for the currently implemented integer and complete-object
pointer lvalues. Postfix updates are a separate immediately following increment;
compound assignments, floats and atomics remain separate features. Follow C23
N3096 6.5.3.1 and 6.5.16.2, not a textual x=x+1 expansion that evaluates x twice.

Post-pp token conversion recognizes ++/--; raw preprocessing already preserves
these longest-match punctuators. A concrete ast_prefix_update_expression owns
its lvalue operand, an increment/decrement enum, resolved calculation type and
pointer element size (zero for integer updates). The common expression header
carries the unqualified result type, location, non-lvalue status and depth.
No custom typedef or generic payload is needed.

Parser BNF: prefix-update-expression ::= ("++" | "--") unary-expression.
Use the existing prefix binding power and depth guard. Reject a cast/literal/
assignment/update result as a nonmodifiable operand during normal semantic
checking. Nested prefix forms parse, but updating another update's result is
invalid. Maximal munch must distinguish ++x from + +x and --x from - -x.

Sema checks the operand with root load/decay suppressed. Require a modifiable
non-const integer or pointer lvalue; reject arrays, functions, nullptr_t, void and
non-lvalues. Pointer referents must be complete objects before reading layout:
void/function/incomplete-array pointer updates are invalid. Const referents do
not prevent updating the pointer object. Record the integer promotion type (or
unchanged pointer type) and full target element stride without introducing a
second evaluation of the operand address. The result is the operand's
unqualified type, not the promoted arithmetic type. Querying an update through
consteval is not an ICE; sizeof(update) still checks constraints but emits no
address/load/update.

QBE computes the lvalue address exactly once, loads the old canonical scalar,
adds/subtracts one in the recorded calculation type (pointer step is the checked
stride), converts back to the stored type, stores once and yields the new value.
Narrow signed/unsigned values use the existing canonicalization. _Bool needs
truth conversion after promoted arithmetic, NOT truncation modulo two:
++true is true, --false is true and --true is false. Runtime signed overflow and
out-of-array pointer arithmetic remain C undefined behavior, not newly checked
runtime exceptions. Curated tests must not execute either.

Tests cover every integer category, unsigned wrap, narrow conversion, boolean
corners, all implemented object-pointer strides/one-past transitions, once-only
indirection/subscript/call addresses, short circuit/conditional/sizeof, return/
argument ABI in both directions, depth edges and compile-only constraints.
Replace obsolete lexical ++/-- negatives with still-unsupported punctuators,
not missing coverage. Keep postfix fixtures rejected until M19c2. Run normal/
QBE suites, both-host sanitizers and bounded lexer/pipeline fuzz before commit.
