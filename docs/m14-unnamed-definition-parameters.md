# M14d: C23 unnamed definition parameters (design before implementation)

Allow the parameter declarators already accepted in prototypes to omit names in
function definitions, as C23 permits. This includes absent integer declarators,
abstract pointer/row forms and adjusted array parameters. Do not invent names or
bindings for omitted identifiers. Named duplicates remain invalid, and an absent
name cannot be referenced. Void remains only the existing sole zero-parameter
marker; general void types, function pointers, variadics, typedefs and qualifiers
remain later work.

Every parameter still has its declared syntax and effective semantic type and
counts toward the 128-parameter limit. A definition creates a local spill/binding
only for a named parameter; parameter.local is NULL for an unnamed definition
parameter, just as no prototype parameter owns a local. Unnamed parameters do
not consume actual local-object slots/storage. Definitions retain the complete
ABI parameter list regardless of whether a source binding exists.

Codegen emits each parameter's effective type and its original positional %pN
name. Only named parameters are stored to local slots, but the positional index
advances for every parameter. Never delete an ABI argument or renumber following
named parameters when omitting a spill. Existing caller argument evaluation,
conversion and fixed signature compatibility remain unchanged. Unused argument
expressions must still execute and be checked semantically.

Test every primitive/pointer effective type, mixed named/unnamed positions before
and after the six register arguments, both linkage directions, full-width return
values, all-unnamed definitions and array/row adjustment. Verify actual caller
side effects for unused arguments. Add AST units asserting missing bindings and
preserved declared/effective type/signature positions; inspect IL for no unused
spills. Check 128/129 parameters, named-local versus unnamed-parameter storage
budgets, duplicate names, argument counts/conversions and unreachable invalid
argument expressions. Replace the former now-valid unnamed-definition rejection
with a genuine invalid abstract declarator; add a positive ordinary regression.
Run all regressions, GCC/Clang/QBE runtime/ABI, bounded sanitized fuzz, isolated
matrices and exact-source CI. C23 syntax acceptance is not full C23 conformance;
record host behavior without treating legacy extensions as normative evidence.
