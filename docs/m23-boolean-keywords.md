# M23a1: C23 bool and boolean constants (design before implementation)

Bring forward the boolean subset of M23a after const integration. Remaining
keyword migrations, storage-class spellings and static assertions stay separate;
this does not claim all M23a or C23. The baseline _Bool type/ABI and const rules
already exist, so no new target representation or boolean truncation shortcut is
needed.

Reference: C23 public draft N3096, 6.4.1, 6.4.4.5, 6.7.2 and 6.10.1p13:
https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3096.pdf

Add distinct language tokens for bool, true and false; retain token_bool as the
existing _Bool spelling so debug token names remain exact. Raw preprocessing
identifiers and expansion stay unchanged. The existing conditional evaluator
already maps the remaining identifier true to signed 1 and other identifiers
(including false/bool) to signed 0 after macro replacement. Preserve and extend
its tests rather than reclassifying raw pp tokens too early. Defined tests still
test actual macros, not whether a spelling is a language keyword.

The builtin scanner accepts bool exactly where _Bool is accepted, including
const permutations. Duplicate bool/_Bool and integer combinations are still
constraints. bool is an alternate spelling of the same canonical semantic type,
not a new rank or user typedef.

boolean-constant ::= "true" | "false"

Construct a distinct ast_boolean_expression with a bool value and ordinary
expression header/source location, rather than pretending a boolean constant is
an int literal. Sema sets type_bool, depth 1, non-lvalue. Existing promotions,
scalar truth/conversions, const handling and bool ABI normalization then apply
unchanged. QBE emits the canonical word value 0/1 without a fabricated load or
integer-literal suffix/rank path. All consuming stages need an explicit kind
case. Keep syntax on demand and preserve budgets.

Tests: exact token kinds after macros/pasting; concrete boolean AST values/types
and explicit promotion nodes; _Bool/bool compatible declarations and callbacks;
all primitive conversions, arithmetic/logical/comma/short-circuit effects; const
bool lvalues; arrays of bool and pointers/function values; both-host QBE/runtime,
all primitive and dirty narrow ABI paths; exact promotion-depth boundaries;
invalid type combinations, reserved identifiers and missing expressions. Test
#if/#elif true/false, macros named true/false, defined guards and skipped errors.
Legacy hosts without C23 keyword support may run explicitly labelled _Bool/0/1
compatibility-macro runtime oracles, never claim native C23 agreement. Always
run original kcc programs with QBE and inspect real semantic types separately.
Do not silently change #undef tests to make a host oracle pass.

No stdbool.h or default headers are supplied. Integer constant evaluation/null
pointer constants remain unfinished: false-to-pointer and nonliteral boolean
array bounds do not gain shortcuts. Other C23 features remain on the ledger.
Full regression, both hosts, sanitizers, bounded nonexecuting fuzz and exact-source
CI remain required at this checkpoint.
