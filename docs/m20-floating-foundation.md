# M20: bounded floating-point foundation

Target: Linux amd64 SysV, QBE scalar `s`/`d`; assumes an IEEE binary32/binary64 host and the C numeric locale. This is a deliberately incomplete C floating-point implementation, not milestone approval.

Supported: `float` and `double` types, qualifiers, typedefs, pointers, arrays, record layout, `sizeof` and `alignof`; automatic storage, scalar loads/stores, arithmetic conversions and assignments, prototyped calls and returns, and indirect calls. Decimal and hexadecimal float/double literals (including `f`/`F`) are rounded using the host's `strtof`/`strtod` and encoded by their exact bit patterns. Literal overflow and underflow reported by the host are rejected. The spelling limit is 4096 bytes. C23 digit separators between digits of the significand or exponent are supported. Arithmetic `+ - * /`, comparisons, mixed float/integer and float/double conversions, floating updates and arithmetic compound assignments are supported. Float variadic arguments are promoted to double. Unary `+ - !`, conditions, short-circuit operators, comma, and arithmetic conditional values are supported. Negative zero is preserved by unary negation.

Static floating objects and aggregate subobjects can be initialized by a
literal with optional unary plus or minus, including float/double precision
conversions, an integer constant expression converted to float/double, or
finite `+`, `-`, `*`, `/` expressions built from those forms. Division by zero
and non-finite arithmetic results are rejected. Folding uses the host's
target-matching IEEE formats and rounding environment. This expanded subset
has not yet been tested.

Not supported: `long double`, `_Complex`, decimal floats, floating suffixes beyond `f`, and general floating constant-expression evaluation beyond the subset above. Floating expressions are not integer constant expressions. File-scope tentative objects and zero-filled aggregates use zero bytes. The preprocessor continues to require integer `#if` expressions. Aggregate ABI is outside this scope. The recently restored conversions and updates have not been integration-tested. Unsupported operations must be diagnosed rather than approximated. Host/target rounding modes and subnormal/exception behavior beyond what the host converter and QBE supply are not modeled; literal underflow is conservatively rejected.
