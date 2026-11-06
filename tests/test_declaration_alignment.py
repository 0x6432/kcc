"""Bounded declaration alignments: syntax, constraints, storage and QBE runtime."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
kcc = root / 'build' / 'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')

accepted = [
    ('int f(void) { alignas(16) int x=1; return x; }', 'alloc16 4'),
    ('int f(void) { int alignas(16) x=1; return x; }', 'alloc16 4'),
    ('int f(void) { unsigned alignas(8) long _Alignas(16) int x=1; return x; }', 'alloc16 8'),
    ('int f(void) { double alignas(16) x; return sizeof x; }', 'alloc16 8'),
    ('int f(void) { const int alignas(16) x=1; return x; }', 'alloc16 4'),
    ('typedef int T; int f(void) { T alignas(16) x; return sizeof x; }', 'alloc16 4'),
    ('int f(void) { enum E { N=16 } alignas(N) x; return sizeof x; }', 'alloc16 4'),
    ('typedef int T; int f(void) { T alignas(sizeof(enum { T=8 })) x; return T; }', 'alloc4 4'),
    ('int f(void) { alignas(sizeof(enum E { N=16 })) enum E alignas(N) x; return N; }', 'alloc16 4'),
    ('int f(void) { int alignas(sizeof(enum E { A=8 })) x; return A; }', 'alloc4 4'),
    ('int f(void) { alignas(16) auto x=1; return x; }', 'alloc16 4'),
    ('int f(void) { for (alignas(16) auto x=0; x<1; x=x+1) {} return 0; }', 'alloc16 4'),
    ('int f(void) { _Alignas(8) char x; return sizeof x; }', 'alloc8 1'),
    ('int f(void) { alignas(1) _Alignas(16) int x; return sizeof x; }', 'alloc16 4'),
    ('int f(void) { alignas(0) long x; return sizeof x; }', 'alloc8 8'),
    ('int f(void) { alignas(long) char x; return sizeof x; }', 'alloc8 1'),
    ('int f(void) { alignas(16) int x,y; return sizeof x+sizeof y; }', 'alloc16 4'),
    ('typedef long T; int f(void) { alignas(T) char x; return sizeof x; }', 'alloc8 1'),
    ('int f(void) { alignas(sizeof(int)*4) int x; return sizeof x; }', 'alloc16 4'),
    ('int f(void) { alignas(16) char a[]={1,2,3}; return sizeof a; }', 'alloc16 3'),
    ('#define A alignas\nint f(void) { A(16) char x; return sizeof x; }', 'alloc16 1'),
    ('int f(void) { for (alignas(16) int x=0; x<1; x=x+1) {} return 0; }', 'alloc16 4'),
    ('int f(alignas(16) int x) { return x; }', 'alloc16 4'),
    ('int f(int alignas(16) x) { return x; }', 'alloc16 4'),
    ('int f(alignas(16) int x[3]) { return x[0]; }', 'alloc16 8'),
    ('int f(alignas(16) int); int f(int x) { return x; }', 'alloc4 4'),
    ('int f(enum { N=16 } a, alignas(N) int b) { return a+b; }', 'alloc16 4'),
    ('int f(void) { ' + 'alignas(0) '*32 + 'int x; return 0; }', 'alloc4 4'),
]
rejected = [
    ('int f(void) { alignas(3) int x; return 0; }', 'supported alignments'),
    ('int f(void) { alignas(32) int x; return 0; }', 'supported alignments'),
    ('int f(void) { alignas(-1) int x; return 0; }', 'nonnegative'),
    ('int f(void) { alignas(2) int x; return 0; }', 'weaken'),
    ('int f(void) { int n=4; alignas(n) int x; return 0; }', 'constant expression'),
    ('int f(void) { alignas(1/0) int x; return 0; }', 'zero'),
    ('int f(void) { alignas(void) int x; return 0; }', 'complete object'),
    ('int f(void) { alignas(int[]) int x; return 0; }', 'complete object'),
    ('int f(void) { alignas(16 int x; return 0; }', "expected ')'"),
    ('int f(void) { alignas(1, 2) int x; return 0; }', "expected ')'"),
    ('int f(void) { alignas(sizeof(struct S)) struct S { int x; } x; return 0; }', 'complete'),
    ('int f(void) { int alignas(2) x; return 0; }', 'weaken'),
    ('int f(void) { int alignas(16) register x; return 0; }', 'typedef or register'),
    ('int f(void) { alignas(16) register int x; return 0; }', 'typedef or register'),
    ('int f(void) { alignas(16) typedef int T; return 0; }', 'typedef or register'),
    ('int f(alignas(2) int x);', 'weaken'),
    ('int f(alignas(4) int x[3]);', 'weaken'),
    ('int f(alignas(16) register int x);', 'typedef or register'),
    ('int f(alignas(16) void);', 'parameter cannot have void type'),
    ('int f(alignas(3) int x);', 'supported alignments'),
    ('int f(void) { alignas(16) int g(void); return 0; }', 'object type'),
    ('int f(void) { alignas(2) auto x=1; return 0; }', 'weaken'),
    ('int f(void) { alignas(32) auto x=1; return 0; }', 'supported alignments'),
    ('int f(void) { ' + 'alignas(0) '*33 + 'int x; return 0; }', 'limit 32'),
]

runtime = '''int aligned(void *p, int n);
int parameter_aligned(alignas(16) int n) { return aligned(&n,16) && n==7; }
int main(void) {
    int alignas(16) x=3;
    alignas(16) auto inferred=5;
    _Alignas(16) char a[3]={1,2,3};
    alignas(long) char b=4;
    if (!aligned(&x,16) || !aligned(a,16) || !aligned(&b,8) || !aligned(&inferred,16)) return 1;
    if (sizeof x!=4 || sizeof a!=3 || x!=3 || a[2]!=3 || b!=4 || inferred!=5) return 2;
    if (!parameter_aligned(7)) return 3;
    return 42;
}'''
with tempfile.TemporaryDirectory(prefix='kcc-align-') as directory:
    d = Path(directory)
    source, il, assembly, helper, obj, exe = [d / n for n in
        ('source.c', 'source.ssa', 'source.s', 'helper.c', 'helper.o', 'program')]

    def compile_source(text):
        source.write_text(text + '\n')
        return subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)

    for text, expected in accepted:
        result = compile_source(text)
        assert result.returncode == 0 and not result.stderr and expected in result.stdout, (text, result.stderr, result.stdout)
    for text, expected in rejected:
        result = compile_source(text)
        assert result.returncode == 1 and not result.stdout and expected in result.stderr, (text, result.stderr)

    result = compile_source(runtime)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
        helper.write_text('#include <stdint.h>\nint aligned(void *p, int n) { return (uintptr_t)p % (unsigned)n == 0; }\n')
        subprocess.run([host, '-std=c11', '-c', str(helper), '-o', str(obj)], check=True, timeout=10)
        subprocess.run([host, str(assembly), str(obj), '-o', str(exe)], check=True, timeout=10)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42

print('Declaration alignment checks passed' + (' with QBE runtime' if qbe else ' (QBE runtime not requested)'))
