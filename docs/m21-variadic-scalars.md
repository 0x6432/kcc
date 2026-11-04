# M21 scalar variadic calling subset

C23 variadic prototypes and definitions accept a final ellipsis, including
`(...)`. Function type compatibility and composite types retain the ellipsis;
fixed arguments use the existing parameter conversions and trailing arguments
receive integer promotions or retain their pointer type. Direct and indirect
calls emit QBE's variadic marker at the fixed/variable boundary, including an
empty tail. The target remains x86-64 SysV, and existing parameter/argument
limits apply. This increment does not claim M21 completion.

Only integer and pointer variable arguments are supported. `nullptr_t` and void
arguments are rejected, as are evaluated aggregate arguments and aggregate
returns by the existing ABI restrictions. Floating types and floating default
promotions are not implemented in this baseline. No `va_list`, `va_start`,
`va_arg`, `va_copy`, or `va_end` interface is provided; variadic definitions can
use named parameters but cannot access the tail. Calls to host variadic
functions are supported only for the stated scalar subset. Aggregate ABI and
complete C23/hosted conformance remain future work. Do not rely on a cast to
adapt incompatible function types or ABIs.
