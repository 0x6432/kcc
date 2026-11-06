# M20: bounded floating-point foundation

Target: Linux amd64 SysV, QBE scalar `s`/`d`; assumes an IEEE binary32/binary64 host and the C numeric locale. This is a deliberately incomplete C floating-point implementation, not milestone approval.

Supported: `float` and `double` types, qualifiers, typedefs, pointers, arrays, record layout, `sizeof` and `alignof`; automatic storage, scalar loads/stores, arithmetic conversions and assignments, prototyped calls and returns, and indirect calls. Decimal and hexadecimal float/double literals (including `f`/`F`) are rounded using the host's `strtof`/`strtod` and encoded by their exact bit patterns. Subnormal literals and values rounded to zero are accepted even if the host reports underflow; overflow remains rejected. The spelling limit is 4096 bytes. C23 digit separators between digits of the significand or exponent are supported. Arithmetic `+ - * /`, comparisons, mixed float/integer and float/double conversions, floating updates and arithmetic compound assignments are supported. Float variadic arguments are promoted to double. Unary `+ - !`, conditions, short-circuit operators, comma, and arithmetic conditional values are supported. Negative zero is preserved by unary negation.

Static floating objects and aggregate subobjects can be initialized by a
literal with optional unary plus or minus, including float/double precision
conversions, an integer constant expression converted to float/double, or
finite `+`, `-`, `*`, `/` expressions built from those forms. Division by zero
and non-finite arithmetic results are rejected. Folding uses the host's
target-matching IEEE formats and rounding environment. This expanded subset
has not yet been tested.

An integer constant expression can additionally contain a floating literal
immediately cast to an integer type, subject to range checks. Broader
floating-to-integer constant folding is not supported and this addition is
untested.

Not supported: `long double`, `_Complex`, decimal floats, floating suffixes beyond `f`, and general floating constant-expression evaluation beyond the subsets above. File-scope tentative objects and zero-filled aggregates use zero bytes. The preprocessor continues to require integer `#if` expressions. Aggregate ABI is outside this scope. The recently restored conversions and updates have not been integration-tested. Unsupported operations must be diagnosed rather than approximated. Host/target rounding modes and subnormal/exception behavior beyond what the host converter and QBE supply are not modeled; literal conversion uses the host rounding environment and remains target-dependent.

Static integer and boolean initializers can also convert the supported finite
floating-expression subset, including scalar globals and aggregate elements.
The conversion truncates toward zero and diagnoses non-finite or out-of-range
results. Signed values slightly below the negative limit are accepted when
truncation toward zero makes them representable. This is a static
initializer extension only: it does not broaden integer constant expressions
in array bounds or case labels. Floating-to-integer casts nested inside a larger
constant expression are supported only within the bounded subset below. The file-scope scalar gate now permits
floating object initializers. These changes have not been tested.

A top-level explicit integer cast of a supported floating constant expression
is also accepted for static integer and boolean initializers, including when
the result is converted again to the object type. This does not relax integer
constant-expression rules, and nested arithmetic is supported within the bounded subset below. Regression cases were added but not run.

The static floating-to-signed-integer boundary check now accounts for truncation
toward zero below the negative limit. Focused IL and rejection checks were run;
the added regression cases and generated-program runtime remain untested.

## Conditional static floating initializers

Floating static initializers now support conditional expressions whose condition
is a supported arithmetic constant. The selected arm must fold within the
existing finite floating-constant subset; a skipped arm must have supported
arithmetic-constant form but need not be evaluated. The selected value retains
its target float/double bits and can also initialize an integer through the
existing checked conversion. Conditions can be integer constant expressions, supported
finite floating expressions, a logical negation of a supported floating
expression, or a
comparison of supported floating expressions. Broader arithmetic constant
expressions and general arithmetic-constant form analysis remain unsupported.

The compiler build and focused positive and negative compilation/IL checks were
run; integer- and floating-conditioned examples were also lowered by pinned
QBE 1.2 and assembled.
Added regression fixtures, generated-program runtime, ABI and fuzzing remain
unrun; this does not complete M20 or imply conformance.

## Floating literals rounded to zero

Decimal and hexadecimal float/double literals that the host conversion rounds
to zero are accepted, including conversions that report underflow. The stored
bits come from the host conversion; unary negation preserves negative zero.
Overflow, other conversion errors, long double and decimal floating types
remain unsupported. As before, parsing assumes a target-matching IEEE host,
the C locale and the host rounding environment; non-default rounding and host
error-reporting edge cases have not been established.

The compiler build and focused literal-bit/negative checks were run. One
example also lowered through pinned QBE 1.2 and assembled. Regression fixtures,
generated-program execution, ABI and fuzzing remain unrun.

## Floating comparisons in static initializers

A direct comparison of two supported finite floating constant expressions,
or logical negation of one, can initialize an integer, boolean or floating
static object or aggregate subobject. Mixed integer/floating comparisons use
the semantically converted operand types. This does not turn floating
comparisons into integer constant expressions. Integer arithmetic around these
values is supported within the bounded subset described below.

The compiler build and focused compile/IL and rejection checks were run; one
example was lowered by pinned QBE 1.2 and assembled. Regression, generated-program
runtime, ABI and fuzz validation remain pending.

## Bounded floating logical initializers

Logical AND, OR and nested negation with supported finite floating operands and
integer constant operands can initialize integer, boolean or floating static
objects and can serve as conditions in supported floating conditional
initializers. A short-circuited right operand must have supported arithmetic
constant form, but is not evaluated. This does not extend integer constant
expression rules. Arithmetic containing these results is supported only within
the bounded subset described below.

The compiler rebuilt; eight values were checked in emitted IL, lowered by pinned
QBE 1.2 and assembled. Seven invalid or unsupported focused examples were
rejected. Regression, generated-program runtime, ABI and fuzz checks remain
pending.

## Floating-conditioned integer initializers

An integer-valued conditional with a supported finite floating condition and
integer-constant-expression arms can initialize static integer, boolean, or
floating objects and aggregate elements. The selected arm must fold; a skipped
arm must have supported arithmetic-constant form. Usual arithmetic conversions
on the arms and the destination conversion
are retained. This is initializer-only support; it does not make these
expressions integer constant expressions; support for arithmetic around them
is bounded as described below.

The compiler rebuilt. Six focused scalar/aggregate values were inspected in
emitted IL, lowered with pinned QBE 1.2, and assembled; seven invalid or
unsupported examples were rejected. Regression, runtime, ABI, sanitizer and
fuzz checks remain pending; this does not complete M20.

Floating-conditioned integer conditionals may also nest in supported conditions,
logical operands, or integer arms, provided every arm is either a strict ICE or
another supported conditional and conversions do not introduce unsupported
forms. Skipped branches need only pass the bounded arithmetic form check; ICE
rules are unchanged.

The compiler rebuilt; six nested initializer values were inspected in IL,
lowered with pinned QBE 1.2 and assembled, and five invalid or unsupported
forms were rejected. Regression fixtures, generated-program runtime, ABI,
sanitizer and fuzz checks remain unrun.

## Short-circuited static arithmetic forms

Supported floating conditionals, floating logical expressions and integer-valued
conditionals with floating conditions now validate skipped operands without
evaluating them. Thus an unselected `1.0/0.0` or `1/0` can be accepted while
nonconstant operands such as object loads and calls remain conservatively
rejected, even when skipped. Evaluated operations must still meet the existing
finite/range checks. Form support is bounded, not a general implementation of
all C arithmetic constant expressions, and strict ICE classification is unchanged.

The compiler rebuilt; twelve focused values were checked in emitted IL, lowered
with pinned QBE 1.2 and assembled, and ten invalid or unsupported examples were
rejected. Added regression fixtures, generated-program execution, ABI, sanitizer
and fuzz checks remain unrun. This does not complete M20.

## Integer arithmetic around floating-derived constants

Static initializers can apply checked integer unary, binary and integer-cast
operations to supported floating comparisons, logical results, and
floating-conditioned integer choices. Nested conversion to float/double and
aggregate subobjects use the same support. Integer operators reuse the strict
ICE evaluator's width, signed-overflow, division, and shift checks on typed
intermediate values, without classifying the original expression as an ICE.
This is still a bounded subset; unsupported forms, host rounding subtleties and
broader constant-expression coverage remain unresolved.

The compiler rebuilt; ten scalar values and two aggregate fields were checked
in IL, lowered with pinned QBE 1.2 and assembled. Eight invalid or unsupported
examples were rejected. Regression fixtures, generated-program runtime, ABI,
sanitizer and fuzz checks remain unrun. M20 remains incomplete.

## Nested floating casts and arithmetic conditions

A checked cast from a supported finite floating expression to an integer type
can be used within supported integer arithmetic, conversions, logical operands,
and conditional values and conditions for static initialization. The cast is
checked at its own target width before further integer arithmetic or conversion.
Short-circuited operands are validated for supported form without evaluation.
These initializer-only rules do not make such casts ICEs; unsupported forms and
non-finite or out-of-range evaluated casts are rejected.

The compiler rebuilt; eleven focused values were checked in emitted IL, lowered
with pinned QBE 1.2 and assembled, and eight invalid or unsupported examples were
rejected. Added regression fixtures, generated-program runtime, ABI, sanitizer
and fuzz checks remain unrun. M20 and general arithmetic constant-expression
coverage remain incomplete.

## Additional skipped arithmetic forms

The skipped-operand shape check also accepts supported integer remainder,
bitwise and shift operations, bitwise complement, and comma expressions whose
operands themselves have supported arithmetic-constant form. The comma is only
accepted by this path when the entire expression is unevaluated. Nonconstant
loads or calls remain conservatively rejected even when skipped; evaluated
comma expressions do not become constants.

The compiler rebuilt; eight focused values were checked in IL, lowered through
pinned QBE 1.2 and assembled; the host accepted equivalent C11 syntax. Six
invalid or unsupported examples were rejected. Regression fixtures,
generated-program runtime, ABI, sanitizer and fuzz checks remain unrun. M20
and general arithmetic constant-expression coverage remain incomplete.
