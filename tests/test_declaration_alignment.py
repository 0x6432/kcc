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
    ('int f(void) { _Alignas(8) char x; return sizeof x; }', 'alloc8 1'),
    ('int f(void) { alignas(1) _Alignas(16) int x; return sizeof x; }', 'alloc16 4'),
    ('int f(void) { alignas(0) long x; return sizeof x; }', 'alloc8 8'),
    ('int f(void) { alignas(long) char x; return sizeof x; }', 'alloc8 1'),
    ('typedef long T; int f(void) { alignas(T) char x; return sizeof x; }', 'alloc8 1'),
    ('int f(void) { alignas(sizeof(int)*4) int x; return sizeof x; }', 'alloc16 4'),
    ('int f(void) { alignas(16) char a[]={1,2,3}; return sizeof a; }', 'alloc16 3'),
    ('#define A alignas\nint f(void) { A(16) char x; return sizeof x; }', 'alloc16 1'),
    ('int f(void) { for (alignas(16) int x=0; x<1; x=x+1) {} return 0; }', 'alloc16 4'),
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
    ('int f(void) { alignas(16) int x,y; return 0; }', 'multiple declarators'),
    ('int f(void) { int alignas(16) x; return 0; }', 'must precede'),
    ('int f(void) { alignas(16) register int x; return 0; }', 'automatic block objects'),
    ('int f(void) { alignas(16) static int x; return 0; }', 'automatic block objects'),
    ('int f(void) { alignas(16) extern int x; return 0; }', 'automatic block objects'),
    ('int f(void) { alignas(16) typedef int T; return 0; }', 'automatic block objects'),
    ('alignas(16) int x;', 'automatic block objects'),
    ('struct S { alignas(16) int x; };', 'automatic block objects'),
    ('int f(alignas(16) int x);', 'automatic block objects'),
    ('int f(void) { alignas(16) int g(void); return 0; }', 'object type'),
    ('int f(void) { alignas(16) auto x=1; return 0; }', 'inferred auto'),
    ('int f(void) { ' + 'alignas(0) '*33 + 'int x; return 0; }', 'limit 32'),
]

runtime = '''int aligned(void *p, int n);
int main(void) {
    alignas(16) int x=3;
    _Alignas(16) char a[3]={1,2,3};
    alignas(long) char b=4;
    if (!aligned(&x,16) || !aligned(a,16) || !aligned(&b,8)) return 1;
    if (sizeof x!=4 || sizeof a!=3 || x!=3 || a[2]!=3 || b!=4) return 2;
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
