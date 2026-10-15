# C23 coverage

Status vocabulary: absent, subset, implemented, validated. Implemented means
code exists, not that conformance has been established. Validated requires
recorded tests and a stated target. This is a coverage inventory, not a claim
of complete ISO conformance.

| Area | Current status | Owning milestones |
| --- | --- | --- |
| Source/translation phases | absent | M01, M09-M11, M25 |
| Tokens and literals | subset (M02) | M02, M12, M20, M23 |
| Declarations/types | subset (M05) | M03, M08, M12-M18, M23-M24 |
| Expressions/statements | subset (M05) | M03-M08, M13, M19 |
| Constraint diagnostics | subset (M05) | every semantic milestone |
| Preprocessing | absent | M09-M11, M25 |
| Object layout and ABI | subset (int locals, M05) | M12-M17, M20-M22, M24 |
| C23 additions | absent | M23a-M23h, M24a-M24g |
| Required library/header environment | absent | M25a-M25d |
| Self-hosting | absent | M26 |

Implementation-defined target choices: Linux x86-64 System V ABI; LP64;
little endian; eight-bit bytes; signed plain char. Other choices remain
unresolved until their milestone. Unsupported constructs must produce a clear
error, not a guessed meaning.

Before the final audit, map this inventory to the chosen public C23 draft or
licensed standard clause by clause. Differential tests exclude undefined,
unspecified and incompatible implementation-defined behavior. Standard-library
coverage and compiler-language coverage are reported separately.
