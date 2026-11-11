# C23 tagged record redefinitions

A complete tagged struct or union may be defined again in the same scope when its ordered members have the same names, types, bit-field widths and alignment. Nested anonymous struct and union members are matched recursively by their ordered definitions, including nested anonymous members, bit-fields and layout. The first definition remains the canonical type and member identity, so initializers, promoted access, function calls and constexpr copies continue to use it. This includes the anonymous-member redeclaration in ISO C 2024 N3220 6.7.3.4p7.

A named member whose type is a freshly defined anonymous record still has a different type, and is not accepted as the same-type redeclaration. Recursive matching is bounded. Cross-scope tagged compatibility and layout restrictions remain as documented in the milestone; flexible-array versus fixed-array compatibility is conservatively refused. These changes do not claim full C23 conformance.
