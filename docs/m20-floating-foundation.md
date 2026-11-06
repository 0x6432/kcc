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
constant expression remain limited. The file-scope scalar gate now permits
floating object initializers. These changes have not been tested.

A top-level explicit integer cast of a supported floating constant expression
is also accepted for static integer and boolean initializers, including when
the result is converted again to the object type. This does not relax integer
constant-expression rules, and arbitrary integer arithmetic containing such a
cast remains unsupported. Regression cases were added but not run.

The static floating-to-signed-integer boundary check now accounts for truncation
toward zero below the negative limit. Focused IL and rejection checks were run;
the added regression cases and generated-program runtime remain untested.

## Conditional static floating initializers

Floating static initializers now support conditional expressions whose condition
is an integer constant expression and whose two converted arms are both in the
existing finite floating-constant subset. The selected value retains its target
float/double bits and can also initialize an integer through the existing checked
conversion. This deliberately requires both arms to be foldable, even when one
is not evaluated; floating conditions, broader arithmetic constant expressions,
and general short-circuit form analysis remain unsupported.

The compiler build and focused positive and negative compilation/IL checks were
run; one initializer example was also lowered by pinned QBE 1.2 and assembled.
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
