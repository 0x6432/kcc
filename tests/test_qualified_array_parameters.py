"""Fixed-bound C array parameter static contracts and const-adjusted pointers."""
import os
import subprocess
import tempfile
from pathlib import Path

compiler = Path(os.environ.get('KCC', Path(__file__).resolve().parents[1] / 'build/kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
valid = [
    'int f(int a[static const 3][2]); int f(int a[const static 3][2]) { a[1][1]=42; return a[1][1]; } int main(void) { int a[3][2]; return f(a); }',
    'int f(int a[const]); int f(int *a) { return a[0]; } int main(void) { int a[1]; a[0]=42; return f(a); }',
    'int f(int a[static 2]) { a=a+1; return a[0]; } int main(void) { int a[2]; a[1]=42; return f(a); }',
    'int f(register int a[const const 2]) { a[0]=42; return a[0]; } int main(void) { int a[2]; return f(a); }',
    'int f(int *a[static 2]) { return *a[1]; } int main(void) { int x=42; int *a[2]; a[1]=&x; return f(a); }',
    'int f(int a[const 2],typeof(a) b) { return b[0]; } int main(void) { int a[2]; a[0]=42; return f(a,a); }',
]
invalid = [
    ('int f(int a[const 2],int *p) { a=p; return 0; }', 'modifiable'),
    ('int f(int a[static]);', 'requires a bound'),
    ('int f(int a[static static 2]);', 'duplicate static'),
    ('int f(int a[const static const 2]);', 'both sides of static'),
    ('int f(int a[2][const 3]);', 'outermost parameter array'),
    ('int f(int (*a)[static 2]);', 'outermost parameter array'),
    ('int a[const 3];', 'require a parameter'),
    ('int f(int n,int a[static n]);', 'variable-length arrays'),
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
            subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
    for text, diagnostic in invalid:
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 1 and not result.stdout and diagnostic in result.stderr, (text, result.stderr)
print('Qualified/static array parameters: fixed-bound syntax, adjustment and constraints' +
      ('; QBE runtime checked' if qbe else '; runtime requires QBE'))
