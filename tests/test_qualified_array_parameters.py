"""Fixed-bound C array parameter static contracts and const-adjusted pointers."""
import os
import subprocess
import tempfile
from pathlib import Path

compiler = Path(os.environ.get('KCC', Path(__file__).resolve().parents[1] / 'build/kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
valid = [
    'int unused(int a["not-published"[0]]); int f(int a["A"[0]]) { return a[0]; } int main(void) { int a[65]; a[0]=42; return f(a); }',
    'struct S { int n; }; int f(struct S *s,int a[s->n++]) { return s->n+a[0]; } int main(void) { struct S s={1}; int a[1]; a[0]=40; return f(&s,a); }',
    'int f(int n,int a[_Generic(n,int: n++,default: 1)+sizeof n]) { return n+a[0]; } int main(void) { int a[5]; a[0]=40; return f(1,a); }',
    '#include <stdatomic.h>\nint f(_Atomic int *p,int a[atomic_fetch_add(p,1)]) { return *p+a[0]; } int main(void) { _Atomic int n=1; int a[1]; a[0]=40; return f(&n,a); }',
    'int bump(int n) { return n; } int f(int *p,int (*cb)(int),int a[cb((*p)++)]) { return *p+a[0]; } int main(void) { int n=1; int a[1]; a[0]=40; return f(&n,bump,a); }',
    'int f(int *p,int a[p[0]]) { return a[0]; } int main(void) { int n=1; int a[1]; a[0]=42; return f(&n,a); }',
    'int f(_Atomic int n,int a[n]) { return a[0]; } int main(void) { int a[1]; a[0]=42; return f(1,a); }',
    'int c; int bump(int n) { c+=1; return n; } int f(int n,int a[bump((int)n)]) { return c+a[0]; } int main(void) { int a[1]; a[0]=41; return f(1,a); }',
    'int count; int f(int a[++count]) { return count+a[0]; } int main(void) { int a[1]; a[0]=41; return f(a); }',
    'int f(int n,int a[static n++]) { return n+a[0]; } int main(void) { int a[2]; a[0]=40; return f(1,a); }',
    'int f(int n,int m,int a[(n+=1)],int b[(m=3)]) { return n+m+a[0]+b[0]; } int main(void) { int a[2],b[3]; a[0]=20; b[0]=17; return f(1,1,a,b); }',
    'int f(int n,int a[n?++n:1]) { return n+a[0]; } int main(void) { int a[2]; a[0]=40; return f(1,a); }',
    'enum { K=1 }; int f(int n,int a[static restrict (n>0?n+K:1)]) { return a[n]; } int main(void) { int a[2]; a[1]=42; return f(1,a); }',
    'int f(int n,int m,int a[(n && m)?n*m:1]) { return a[0]; } int main(void) { int a[2]; a[0]=42; return f(1,2,a); }',
    'int f(int n,int a[static restrict n][2]) { return a[n-1][1]; } int main(void) { int a[2][2]; a[1][1]=42; return f(2,a); }',
    'int f(register int n,int a[n]) { return a[0]; } int main(void) { int a[1]; a[0]=42; return f(1,a); }',
    'int f(int n,int a[static restrict n]); int f(int n,int *a) { return a[0]; } int main(void) { int a[1]; a[0]=42; return f(1,a); }',
    'int f(int n,int a[n++]); int f(int n,int *a) { return n+a[0]; } int main(void) { int a[1]; a[0]=41; return f(1,a); }',
    'int f(int (*cb)(int n,int a[n]),int *p) { return cb(1,p); } int g(int n,int *p) { return p[0]; } int main(void) { int a[1]; a[0]=42; return f(g,a); }',
    'int f(int a[const *]); int f(int *a) { return a[0]; } int main(void) { int a[1]; a[0]=42; return f(a); }',
    'int f(int a[restrict *][2]); int f(int a[][2]) { return a[0][0]; } int main(void) { int a[1][2]; a[0][0]=42; return f(a); }',
    'int f(int a[static const 3][2]); int f(int a[const static 3][2]) { a[1][1]=42; return a[1][1]; } int main(void) { int a[3][2]; return f(a); }',
    'int f(int a[const]); int f(int *a) { return a[0]; } int main(void) { int a[1]; a[0]=42; return f(a); }',
    'int f(int a[static 2]) { a=a+1; return a[0]; } int main(void) { int a[2]; a[1]=42; return f(a); }',
    'int f(register int a[const const 2]) { a[0]=42; return a[0]; } int main(void) { int a[2]; return f(a); }',
    'int f(int *a[static 2]) { return *a[1]; } int main(void) { int x=42; int *a[2]; a[1]=&x; return f(a); }',
    'int f(int a[const 2],typeof(a) b) { return b[0]; } int main(void) { int a[2]; a[0]=42; return f(a,a); }',
]
invalid = [
    ('int f(int n,int a[2][n]);', 'variable-length arrays'),  # Valid C; subset not implemented.
    ('int f(double n,int a[n]);', 'integer constant expression'),
    ('int f(int a[*]) { return 0; }', 'function prototype scope'),
    ('int f(int a[static *]);', 'non-static prototype parameter'),
    ('int f(int a[2][*]);', 'outermost parameter array'),  # Valid C; subset not implemented.
    ('int f(int a[const 2],int *p) { a=p; return 0; }', 'modifiable'),
    ('int f(int a[static]);', 'requires a bound'),
    ('int f(int a[static static 2]);', 'duplicate static'),
    ('int f(int a[const static const 2]);', 'both sides of static'),
    ('int f(int a[2][const 3]);', 'outermost parameter array'),
    ('int f(int (*a)[static 2]);', 'outermost parameter array'),
    ('int a[const 3];', 'require a parameter'),
    ('int f(int n,int a[static ((int){n})]) { return 0; }', 'variable-length arrays'),
    ('int f(int a[static 0]);', 'array bound must be positive'),
]
with tempfile.TemporaryDirectory(prefix='kcc qualified array parameters ') as directory:
    root = Path(directory)
    source, il, assembly, executable = [root / name for name in ('test.c', 'test.ssa', 'test.s', 'test')]
    for text in valid:
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            subprocess.run([host, str(assembly), '-latomic', '-o', str(executable)], check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
    source.write_text('int unused(int a["not-published"[0]]); int f(int a["A"[0]]) { return a[0]; }\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and result.stdout.count('data $.Lkcc.string.') == 1, result.stderr
    for text, diagnostic in invalid:
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 1 and not result.stdout and diagnostic in result.stderr, (text, result.stderr)
print('Qualified/static array parameters: fixed-bound syntax, adjustment and constraints' +
      ('; QBE runtime checked' if qbe else '; runtime requires QBE'))
