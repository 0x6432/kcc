"""Restrict qualification, parameter adjustment, and type constraints."""
import os
import subprocess
import tempfile
from pathlib import Path

compiler = Path(os.environ.get('KCC', Path(__file__).resolve().parents[1] / 'build/kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
valid = [
    'int f(int a[restrict static 2],int b[static restrict 2]) { a[0]=b[1]; return a[0]; } int main(void) { int a[2],b[2]; b[1]=42; return f(a,b); }',
    'typedef int *P; int f(P restrict p) { return *p; } int main(void) { int n=42; return f(&n); }',
    'typedef int *A[2]; int main(void) { int n=42; restrict A a; a[1]=&n; return *a[1]; }',
    'int main(void) { int n=42; restrict auto p=&n; return *p; }',
    'int f(int *restrict p); int f(int *p) { return *p; } int main(void) { int n=42; return f(&n); }',
    'int main(void) { int n=42; void *restrict p=&n; int *q=p; return *q; }',
    'int f(void) { return 42; } int main(void) { int (*p)(void)=f; int (**restrict q)(void)=&p; return (*q)(); }',
]
invalid = [
    ('restrict int n;', 'restrict requires'),
    ('int (*restrict p)(void);', 'restrict requires'),
    ('typedef int A[2]; restrict A a;', 'restrict requires'),
    ('int f(void) { restrict auto x=1; return x; }', 'restrict requires'),
    ('int f(int a[const restrict 2],int *p) { a=p; return 0; }', 'modifiable'),
    ('int f(int a[2][restrict 3]);', 'outermost parameter array'),
]
with tempfile.TemporaryDirectory(prefix='kcc restrict ') as directory:
    root = Path(directory)
    source, il, assembly, executable = [root / name for name in ('test.c', 'test.ssa', 'test.s', 'test')]
    for text in valid:
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
    for text, diagnostic in invalid:
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 1 and not result.stdout and diagnostic in result.stderr, (text, result.stderr)
print('Restrict qualifiers: pointers, typedef arrays, inference and parameter adjustment' +
      ('; QBE runtime checked' if qbe else '; runtime requires QBE'))
