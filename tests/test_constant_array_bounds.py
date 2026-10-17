"""Fixed ICE bounds, prototype name scopes and unchanged adjusted-array ABI."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')


def accepts(text):
    return subprocess.run([host, '-std=c2x', '-pedantic-errors', '-x', 'c', '-fsyntax-only', '-'],
                          input=text + '\n', capture_output=True, text=True, timeout=10).returncode == 0


prefix = '' if accepts('static_assert(1);') else '#define static_assert _Static_assert\n'
if not accepts('_Static_assert(sizeof(true)==1,"bool"); bool x;'):
    prefix += '#define bool _Bool\n#define true ((_Bool)1)\n#define false ((_Bool)0)\n'
if not accepts('_Static_assert(alignof(int)==4,"align");'):
    prefix += '#define alignof _Alignof\n'
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short', 'unsigned short',
            'int', 'unsigned', 'long', 'unsigned long', 'long long', 'unsigned long long']
programs = [f'int main(void) {{ {name} a[1+1]; a[0]=0; a[1]=1; '
            f'static_assert(sizeof a==2*sizeof({name})); if(a[1]!=1) return 1; return 42; }}' for name in integers]
programs += [
    'int main(void) { int a[true]; a[0]=42; static_assert(sizeof a==4); return a[0]; }',
    "int main(void) { int a['A'-63]; a[1]=42; static_assert(sizeof a==8); return a[1]; }",
    'int main(void) { int a[(unsigned char)258]; a[1]=42; static_assert(sizeof a==8); return a[1]; }',
    'int main(void) { int a[4294967295U+3U]; a[1]=42; static_assert(sizeof a==8); return a[1]; }',
    'int main(void) { int a[1?2:1/0]; a[1]=42; static_assert(sizeof a==8); return a[1]; }',
    'int main(void) { int a[0?(1,2):2]; a[1]=42; static_assert(sizeof a==8); return a[1]; }',
    'int missing(void); int main(void) { int x; int a[sizeof(x=1)]; int b[sizeof missing()]; '
    'static_assert(sizeof a==16 && sizeof b==16); a[3]=42; return a[3]; }',
    'int main(void) { int a[sizeof(int)][alignof(short)]; a[3][1]=42; '
    'static_assert(sizeof a==32 && sizeof a[0]==8); return a[3][1]; }',
    'int main(void) { int a[1+1][2+1]; int (*p)[sizeof(int)-1]=a; p[1][2]=42; '
    'static_assert(sizeof *p==12); return a[1][2]; }',
    'int main(void) { int a[2]; int (*p)[1?2:3]=&a; int (*q)[]=(int (*)[sizeof(short)])p; '
    '(*q)[1]=42; static_assert(sizeof(int[sizeof "ab"])==12); return a[1]; }',
    'int f(int n,int a[sizeof n]) { static_assert(sizeof a==8); return a[3]; } '
    'int main(void) { int a[2+2]; a[3]=42; return f(0,a); }',
    'int f(int a[2],int b[sizeof a]) { static_assert(sizeof a==8 && sizeof b==8); return b[7]; } '
    'int main(void) { int a[8]; a[7]=42; return f(a,a); }',
    'int cb(char n,int a[sizeof n]) { return a[0]; } '
    'int apply(int n,int (*p)(char n,int a[sizeof n]),int a[sizeof n]) { return p(0,a); } '
    'int main(void) { int a[sizeof(int)]; a[0]=42; return apply(0,cb,a); }',
    'int main(void) { char n; int (*p)(int n,int a[sizeof n]); int b[sizeof n]; '
    'static_assert(sizeof b==4 && sizeof p==8); b[0]=42; return b[0]; }',
    'int main(void) { char a; int (*p)(int a[sizeof a]); static_assert(sizeof p==8); return 42; }',
    'int main(void) { char x; int (*(*p)(int x))[sizeof x]; '
    'static_assert(sizeof **p(0)==4); return 42; }',
    '#define N (1+1)\nint main(void) { int a[N],b[sizeof a/sizeof a[0]]; b[1]=42; '
    'static_assert(sizeof b==sizeof a); return b[1]; }',
    'int f(int a[][1+2]); int f(int a[2][sizeof(short)+1]) { return a[1][2]; } '
    'int main(void) { int a[2][3]; a[1][2]=42; return f(a); }',
    'int main(void) { int a[2]; { int a[sizeof a]; static_assert(sizeof a==32); a[7]=42; return a[7]; } }',
]
constraints = [
    ('int f(void) { int a[-1]; return 0; }', 'array bound must be positive'),
    ('int f(void) { int a[(signed char)-1]; return 0; }', 'array bound must be positive'),
    ('int f(void) { int a[(short)-1]; return 0; }', 'array bound must be positive'),
    ('int f(void) { int a[(int)-1]; return 0; }', 'array bound must be positive'),
    ('int f(void) { int a[(long)-1]; return 0; }', 'array bound must be positive'),
    ('int f(void) { int a[(long long)-1]; return 0; }', 'array bound must be positive'),
    ('int f(void) { int a[1-1]; return 0; }', 'array bound must be positive'),
    ('int f(void) { int a[false]; return 0; }', 'array bound must be positive'),
    ('int f(void) { int a[2147483647+1]; return 0; }', 'signed overflow'),
    ('int f(void) { int a[1/0]; return 0; }', 'division by zero'),
    ('int f(void) { int a[1ULL<<64]; return 0; }', 'invalid shift count'),
    ('int f(void) { int a[1ULL<<63]; return 0; }', 'storage limit'),
    ('int f(void) { int a[1?-1:0U]; return 0; }', 'storage limit'),
    ('int f(void) { int a[18446744073709551615ULL]; return 0; }', 'storage limit'),
    ('int f(int n) { int a[n]; return 0; }', 'variable-length arrays'),
    ('int f(void) { const int n=2; int a[n]; return 0; }', 'variable-length arrays'),
    ('int f(int n) { int a[1?n:2]; return 0; }', 'variable-length arrays'),
    ('int f(int n) { int a[1?2:n]; return 0; }', 'variable-length arrays'),
    ('int f(int n) { int a[(n=2)]; return 0; }', 'variable-length arrays'),
    ('int f(int n) { int a[(1,2)]; return 0; }', 'variable-length arrays'),
    ('int f(void); int g(void) { int a[1?2:f()]; return 0; }', 'variable-length arrays'),
    ('int f(int n,int a[n]);', 'variable-length arrays'),
    ('int f(int n,int (*p)[n]);', 'variable-length arrays'),
    ('int f(int a[sizeof a]);', 'undeclared identifier'),
    ('int f(void) { int a[sizeof a]; return 0; }', 'undeclared identifier'),
    ('int f(void) { int (*p)(int n,int a[sizeof n]); int b[sizeof n]; return 0; }', 'undeclared identifier'),
    ('int (*f(int n))[sizeof n];', 'undeclared identifier'),
    ('int f(void) { int a[&f]; return 0; }', 'integer constant expression'),
    ('int f(void) { int a[1,2]; return 0; }', "expected ']'"),
    ('int f(int a[static 2]);', 'static array bounds are not supported'),
    ('int f(int a[*]);', 'expected integer literal'),
    ('int f(void) { int a[1048576/4+1]; return 0; }', 'storage limit'),
    ('int f(void) { char a[1048576],b[1]; return 0; }', 'local object storage'),
    ('int f(void) { int a[2][1048576]; return 0; }', 'storage limit'),
]

with tempfile.TemporaryDirectory(prefix='kcc constant array bounds ') as directory:
    directory = Path(directory)
    source, native, il, assembly, obj, executable = [directory / name for name in ('k.c', 'h.c', 'k.ssa', 'k.s', 'h.o', 'p')]

    def compile_source(text, success=True, message=''):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=15)
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:600], result.stderr[-3000:])
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr, (text[:600], result.stderr[-3000:])
        return result.stdout

    def lower(text):
        il.write_text(text)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)

    def run(objects):
        subprocess.run([host, *map(str, objects), '-o', str(executable)], capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42

    for text in programs:
        output = compile_source(text)
        if qbe:
            lower(output)
            run([assembly])
        native.write_text(prefix + text + '\n')
        result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-fsigned-char', str(native), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (text, result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    for text, message in constraints:
        compile_source(text, False, message)
    for name in integers:
        helper = f'int read({name} a[sizeof(int)-2]) {{ return a[1]; }}'
        driver = f'int read({name} *); int main(void) {{ {name} a[1+1]; a[1]=1; return read(a)+41; }}'
        for kcc_text, host_text in [(helper, driver), (driver, helper)]:
            output = compile_source(kcc_text)
            if qbe:
                lower(output)
                native.write_text(prefix + host_text + '\n')
                subprocess.run([host, '-std=c2x', '-pedantic-errors', '-c', str(native), '-o', str(obj)],
                               capture_output=True, check=True, timeout=10)
                run([assembly, obj])

    for count, valid in [(127, True), (128, False)]:
        compile_source('int f(void) { int a[' + '+ ' * count + '1]; return 42; }', valid, 'depth')
    for count, valid in [(126, True), (127, False)]:
        compile_source('int f(void) { int a[' + '+ ' * count + 'true]; return 42; }', valid, 'typed expression exceeds depth')
    for count, valid in [(64, True), (65, False)]:
        bound = '1'
        for _ in range(count):
            bound = 'sizeof(char[' + bound + '])'
        compile_source('int f(void) { char a[' + bound + ']; return 42; }', valid, 'declarator exceeds nesting')
    for text in ['int f(void) { char a[1048576]; return 42; }',
                 'int f(void) { int a[1048576/4]; return 42; }']:
        compile_source(text)  # Compile-only resource boundaries, not executed.
    output = compile_source('int missing(void); int f(void) { int a[sizeof missing()]; return sizeof a; }')
    assert '$missing' not in output, output

print(f'Constant array bounds passed: {len(programs)} strict native/QBE programs, {len(constraints)} constraints, '
      f'exact parser/typed/cross-type recursion and storage boundaries; {host}; labelled legacy keyword oracles'
      + ('; 24 adjusted-array ABI arrangements passed' if qbe else ''))
