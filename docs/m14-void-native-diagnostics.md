# M14k1 native named-void diagnostic severity

Public runs 38922632027 (0c17148) and 38922740646 (c9642c0) passed fuzz but
GCC reference jobs failed the test assertion that every invalid source must
produce a nonzero exit status. Their first failure was int f(typeof(void) x);.
A local GCC 14.1.0 audit of all twelve original fixtures confirms two prototype
forms emit only the precise named-void warning; the other ten reject. Clang 18
rejects all twelve. C diagnostic requirements do not require error severity.
N3096 6.7p8 requires a named no-linkage object's adjusted type to be complete;
6.7.6.3p9's zero-argument marker is sole and unnamed. Prototype incomplete-type
permission does not turn a named void into that zero-argument marker. No compiler
acceptance, normalization, lowering, original source, or constraint fixture changes.

Recognize only the two exact original sources, zero status and precisely one
matching GCC parameter-1 void-type warning, with no error or additional warning.
Count these as diagnosed native forms, not strict rejection or runtime agreement.
Accept a future strict rejection normally. Classifier units reject unrelated
sources/status/empty/extra diagnostics. Invalid sources are never executed.
This is a test-only severity correction, not a general native acceptance skip.


Focused validation passed against frozen c9642c0 compiler source: GCC 11 / Clang
15, native GCC 14.1.0 and Clang 18.1.8, all QBE runtime/ABI arrangements and
classifier units. Modern GCC has 38 native original agreements, ten strict
rejections and two exact warnings; modern Clang has 38 native agreements and
twelve strict rejections. Both prior frozen GCC/Clang ASan/UBSan kcc binaries
passed with both modern native oracles. No compiler source changed for this
correction; M14l1 remains an independently uncommitted working-tree feature.
Full prior regression is not claimed as a fresh run for this test-only commit.
Public CI remains pending. All invalid sources were compile-only.
