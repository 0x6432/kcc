# M13g: fixed multidimensional local arrays (design before implementation)

Extend local declarator suffixes to one or more literal-bound dimensions, keeping
all M13f restrictions on constant-expression/VLA/incomplete bounds, parameter
adjustment, initializers and full parenthesized declarators. Scalar and pointer
elements are still the leaves. This increment is shape composition, not a new
flat-pointer interpretation of multidimensional arrays.

Read dimension bounds in source order into a bounded parser-local list, then
wrap concrete ast_array_type_syntax nodes right-to-left. Thus int *a[2][3] is an
array of two arrays of three pointers to int, not a reversed shape or pointer to
an array. Each dimension retains its opening location/bound token. Limit array
dimensions to 64 independently of the existing pointer-syntax limit. Use no
translation-unit token vector and retain the existing on-demand cache.

Semantic array types already recursively hold element type/count and use checked
object-size multiplication. Keep compatibility recursive and shape-sensitive:
equal total byte counts do not imply compatible arrays. The per-function 1 MiB
object-storage budget stays unchanged; each resolver level checks its bound by
dividing the budget by the complete element size before construction. Codegen's
recursive size/alignment and ordinary decay/address helpers should need no
special multidimensional operations.

Each ordinary array expression decays by one level only. a decays to pointer-to-
row, a[i] denotes a row then decays to pointer-to-element in value contexts, and
&a remains pointer-to-the-entire-array. Arithmetic therefore scales by row or
whole-array size as appropriate. Subscripting a row is valid only within that
row; never test crossing a row boundary through a flattened element pointer even
if target storage is contiguous. Use row pointers/indices within their proper
array objects instead. One-past addresses remain address-only.

Test unequal dimensions and recursive type-cache/shape units, all primitive and
pointer leaves, nested loops and multiple decays, row/whole-array differences,
subarray addresses and valid one-past row arithmetic. Both ABI directions borrow
selected rows through existing scalar-pointer parameters; do not fake an int**
ABI for an int[][] matrix. Include exact 64/65 dimension, product/storage and
42/43 fully indexed typed-depth limits. Replace the earlier multidimensional
rejection with a permanently unsupported incomplete inner bound and document its
constraint purpose. Keep all regressions, both hosts, sanitized bounded fuzz,
isolated normal/sanitizer matrices and exact-source CI.
