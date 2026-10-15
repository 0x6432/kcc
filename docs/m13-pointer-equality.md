# M13c: compatible object-pointer equality (design before implementation)

Extend existing binary ==/!= AST operations to compatible object pointers.
Analyze/load operands first, then either apply the unchanged integer promotion/
conversion path or accept two recursively compatible pointer types and produce
int. Do not feed pointers into integer rank/signedness helpers. Other pointer
binary operators remain explicit later work. Scalar truth is already supported.

QBE pointer equality compares full l values, producing a w boolean (ceql/cnel).
Dispatch this case before querying integer signedness. No address truncation,
integer type tagging or new implicit pointer/integer conversion is allowed.
Null-pointer constants and void/qualified pointers remain separate increments;
source p==0 is still unsupported, not guessed from a runtime integer value.

Test local address identity and inequality, compatible casts, pointer-to-pointer,
assignment side effects evaluated once, short-circuit pointer comparisons and
host-supplied null pointers. Cover true/false comparisons across real live objects
and both-host QBE runtime. Incompatible referents, pointer/integer comparison,
bitwise/arithmetic and relational pointer operators must still diagnose. Replace
M13a's now-valid p==p rejection fixture with p&p (permanently invalid C), recording
its changed purpose rather than silently deleting coverage. Retain full integer/
pointer regressions, sanitizers, fuzz and exact-source CI.
