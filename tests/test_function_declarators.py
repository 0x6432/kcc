"""Fixed function declarators share the general chain and resolved signature."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short',
            'unsigned short', 'int', 'unsigned', 'long', 'unsigned long',
            'long long', 'unsigned long long']
programs = []
for name in integers:
    programs.append(f'''{name} (*row({name} [][3],int))[3];
{name} (*(row)({name} (*a)[3],int n))[3] {{ return a+n; }}
int main(void) {{ {name} a[2][3];
 for(int i=0;i<2;i=i+1) for(int j=0;j<3;j=j+1) a[i][j]=0;
 {name} (*p)[3]=row(a,1); (*p)[2]=7;
 if(a[1][2]!=({name})7 || a[0][2]!=0 || p-a!=1) return 1; return 42; }}''')
programs += [
    'int ((sum))(int,int); int ((sum))(int x,int y) { return x+y; } int main(void) { return sum(13,29); }',
    'int *(identity)(int *p) { return p; } int main(void) { int x=42; return *identity(&x); }',
    'int (ignore)(int) { return 42; } int main(void) { return ignore(7); }',
    'int (*matrix(int (*p)[2][3]))[2][3] { return p; } '
    'int main(void) { int a[2][3]; a[1][2]=42; return (*matrix(&a))[1][2]; }',
    'int (*unknown(int (*p)[3]))[] { return p; } '
    'int main(void) { int a[3]; a[2]=42; return (*unknown(&a))[2]; }',
    'char (*literal(void))[3] { return &"hi"; } '
    'int main(void) { if((*literal())[0]!=\'h\' || (*literal())[2]!=0) return 1; return 42; }',
    'int *(*row(int *(*p)[3]))[3] { return p; } '
    'int main(void) { int x=42; int *a[3]; a[0]=&x; a[1]=&x; a[2]=&x; return *(*row(&a))[2]; }',
    'int (*pick(int (*p)[3],int n))[3] { if(!n) return p; return pick(p+1,n-1); } '
    'int main(void) { int a[2][3]; a[1][2]=42; return (*pick(a,1))[2]; }',
    'int (*row(int (*)[]))[]; int (*row(int (*)[]))[3]; '
    'int (*row(int (*p)[]))[] { return p; } '
    'int main(void) { int a[3]; a[2]=42; if(row(&a)+1!=&a+1) return 1; return (*row(&a))[2]; }',
]

with tempfile.TemporaryDirectory(prefix='kcc function declarators ') as directory:
    directory = Path(directory)
    source, other, il, assembly, obj, executable = [directory / name for name in
                                                   ('k.c', 'h.c', 'p.ssa', 'p.s', 'h.o', 'p')]

    def compile_source(text):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
        return result.stdout

    def link_and_run(host_text=None):
        objects = [str(assembly)]
        if host_text is not None:
            other.write_text(host_text)
            subprocess.run([host, '-std=c2x', '-fsigned-char', '-c', str(other), '-o', str(obj)],
                           capture_output=True, check=True, timeout=10)
            objects.append(str(obj))
        subprocess.run([host, *objects, '-o', str(executable)], check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, host_text

    for text in programs:
        compile_source(text)
        if qbe:
            link_and_run()
        result = subprocess.run([host, '-std=c2x', '-fsigned-char', str(source), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (text, result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    for name in integers:
        helper = f'{name} (*row({name} (*p)[3],int n))[3] {{ return p+n; }}\n'
        relay = f'{name} (*row({name} (*)[3],int))[3]; int relay({name} (*p)[3]) {{ (*row(p,1))[2]=7; return 42; }}\n'
        driver = (f'int relay({name} (*)[3]); int main(void) {{ {name} a[2][3]={{{{0}}}}; '
                  f'if(relay(a)!=42 || a[1][2]!=({name})7 || a[0][2]!=0) return 1; return 42; }}\n')
        for text, host_text in [(helper, relay + driver), (relay, helper + driver)]:
            compile_source(text)
            if qbe:
                link_and_run(host_text)

    for layers, message in [(64, 'function return type'), (65, 'function declarator exceeds layer limit (64)')]:
        source.write_text('int f' + '()' * layers + ';')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    for layers, valid in [(63, True), (64, False)]:
        source.write_text('int f(' + 'int g(' * layers + 'int' + ')' * layers + ');')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and not result.stdout, result.stderr
        if not valid:
            assert 'declarator exceeds nesting limit (64)' in result.stderr, result.stderr

    rejected = [
        ('int f(void)[3];', 'function return type'),
        ('int f(void)(int);', 'function return type'),
        ('int f(void) { int a[2](void); return 0; }', 'array element type must be complete'),
        ('int f(void) { int (*p)(int)=1; return 0; }', 'pointer conversion'),
        ('int f(int (int)[3]);', 'function return type'),
        ('int f(void) { int g(int); return 0; }', 'block-scope function declarations'),
        ('int f(void) { return (int ())0; }', 'cast target must be a scalar type'),
        ('int (*row(int (*)[3]))[3]; int (*row(int (*)[3]))[4];', 'incompatible function'),
        ('int (*row(int (*)[]))[]; int (*row(int (*)[]))[3]; int (*row(int (*)[]))[4];', 'incompatible function'),
        ('int (f)(int x,int x);', 'duplicate parameter name'),
        ('int (f)(int x) { int x; return 0; }', 'redeclaration'),
        ('int f(int (*)(int)); int f(int (*)(long));', 'incompatible function'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Function declarators passed ({len(programs)} full-value programs, parenthesized names and array-pointer returns, '
      f'both-direction all-primitive return ABI, composite signatures and exact function/nested-type limits; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
