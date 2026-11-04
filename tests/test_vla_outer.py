"""M24f1: declaration-time VLA evaluation, checked stack use and restrictions."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

valid = [
    'int main(void) { int n=3; int a[n++]; a[2]=42; if(n!=4 || sizeof a!=12) return 1; n=7; if(sizeof a!=12) return 2; return a[2]; }',
    'int main(void) { int n=3; auto unsigned char a[(n=2)]; a[1]=42; if(n!=2 || sizeof a!=2) return 1; return a[1]; }',
    'int main(void) { int n=1; long a[(n++,2)]; a[1]=42; if(n!=2 || sizeof a!=16) return 1; return a[1]; }',
    'int main(void) { int n=2; int a[n]; int *p=a; p[1]=42; if(sizeof a[0]!=4 || sizeof a!=8) return 1; return a[1]; }',
    'int main(void) { int n=3; const int a[n]; if(sizeof a!=12) return 1; return 42; }',
    'int f(int n) { int a[n]; a[n-1]=42; return a[n-1]; } int main(void) { return f(1); }',
    'int main(void) { int n=2; int a[n]; int i=0; while(i<2) { a[i]=42; i++; } return a[1]; }',
    'int main(void) { int n=2; int a[n++]; long b[n++]; a[1]=20; b[2]=22; return n==4 && sizeof a==8 && sizeof b==24 ? a[1]+b[2] : 1; }',
    'int main(void) { int n=2; char a[n], b[n+1]; a[1]=20; b[2]=22; return sizeof a==2 && sizeof b==3 ? a[1]+b[2] : 1; }',
    'int main(void) { int n=2; int x=42; int *a[n]; a[1]=&x; return sizeof a==16 ? *a[1] : 1; }',
    'int main(void) { int n=2; double a[n]; a[1]=42.0; return sizeof a==16 ? (int)a[1] : 1; }',
    'struct S { int x; int y; }; int main(void) { int n=2; struct S a[n]; a[1].x=20; a[1].y=22; return sizeof a==16 ? a[1].x+a[1].y : 1; }',
    'int main(void) { int n=2; int a[n++][3]; a[1][2]=42; return n==3 && sizeof a==24 && sizeof a[0]==12 ? a[1][2] : 1; }',
    'int main(void) { int n=2; char a[n][2][3]; a[1][1][2]=42; return sizeof a==12 && sizeof a[0]==6 ? a[1][1][2] : 1; }',
    'struct S { int x; }; int main(void) { int n=2; struct S a[n][3]; a[1][2].x=42; return sizeof a==24 ? a[1][2].x : 1; }',
]
rejected = [
    ('int f(int n) { { int a[n]; } return 0; }', 'variable-length arrays'),
    ('int f(int n) { while(n) { int a[n]; n--; } return 0; }', 'variable-length arrays'),
    ('int f(int n) { int a[n]={0}; return 0; }', 'must be uninitialized'),
    ('int f(int n) { int a[n]; goto done; done: return 0; }', 'goto in a function'),
    ('int f(int n) { goto done; int a[n]; done: return 0; }', 'goto in a function'),
    ('int f(int n) { again:; int a[n]; goto again; }', 'goto in a function'),
    ('int f(int n) { int a[n]; return sizeof(&a); }', 'address of variable-length'),
    ('int f(int n) { int a[n]; typeof(a) b; return 0; }', 'typeof of variable-length'),
    ('int f(int n) { int a[n]; static_assert(sizeof a, "x"); return 0; }', 'constant expression'),
    ('int f(int n) { int (*p)[n]; return 0; }', 'variable-length arrays'),
    ('int f(int n) { typedef int A[n]; return 0; }', 'variable-length arrays'),
    ('int f(int n) { static int a[n]; return 0; }', 'variable-length arrays'),
    ('int f(int n) { int a[2][n]; return 0; }', 'variable-length arrays'),
    ('int f(int n, int a[n]);', 'variable-length arrays'),
]
# Bounds fail before allocation, including a negative signed input, unsigned
# overflow, zero and remaining-budget exhaustion. No particular signal is required.
traps = [
    'int main(void) { int n=0; int a[n]; return 42; }',
    'int main(void) { int n=-1; int a[n]; return 42; }',
    'int main(void) { unsigned long n=18446744073709551615UL; char a[n]; return 42; }',
    'int main(void) { int n=262144; int a[n]; return 42; }',
    'int main(void) { int n=140000; int a[n]; int b[n]; return 42; }',
]
with tempfile.TemporaryDirectory(prefix='kcc vla ') as tmp:
    tmp = Path(tmp)
    source, il, assembly, executable = [tmp / n for n in ('input.c', 'out.ssa', 'out.s', 'out')]
    def compile_source(text, success=True, message=''):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        if success:
            assert result.returncode == 0 and not result.stderr, (text, result.stderr)
            assert 'call $abort()' in result.stdout and ' =l alloc' in result.stdout
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
        return result.stdout
    def run(output):
        il.write_text(output)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
        subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
        return subprocess.run([str(executable)], capture_output=True, timeout=5).returncode
    for text in valid:
        output = compile_source(text)
        if qbe:
            assert run(output) == 42, text
    for text, message in rejected:
        compile_source(text, False, message)
    for text in traps:
        output = compile_source(text)
        if qbe:
            assert run(output) != 42, text
print('M24f1 VLA subset: compile checks' + (' and runtime checks' if qbe else ''))
