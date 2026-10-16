"""Literal-bound array parameter spelling adjusts exactly one outer level."""
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
    programs += [f'''int move({name} a[3]) {{ {name} *original=a; a=a+1;
 {name} **address=&a; if(*address!=original+1 || a-original!=1) return 1;
 a[0]=7; if(original[1]!=({name})7) return 2; return 42; }}
int main(void) {{ {name} a[3]; a[0]=0; a[1]=0; a[2]=0;
 if(move(a)!=42 || a[1]!=({name})7 || a[0]!=0 || a[2]!=0) return 1; return 42; }}''',
                 f'''int matrix({name} [7][3]);
int matrix({name} a[2][3]) {{ if(&*a!=a || &a[1]-&a[0]!=1) return 1;
 a=a+1; a[0][2]=7; return 42; }}
int main(void) {{ {name} a[2][3];
 for(int i=0;i<2;i=i+1) for(int j=0;j<3;j=j+1) a[i][j]=0;
 if(matrix(a)!=42 || a[1][2]!=({name})7 || a[0][2]!=0) return 2; return 42; }}''']
programs += [
    'int f(int *a[3]) { int **p=a; a=a+1; int ***q=&a; '
    'if(*q!=p+1 || *a[0]!=42) return 1; return 42; } '
    'int main(void) { int x=42; int *p[3]; p[0]=&x; p[1]=&x; p[2]=&x; return f(p); }',
    'int f(int *); int f(int [9]); int f(int a[3]) { return a[0]; } '
    'int main(void) { int a[1]; a[0]=42; return f(a); }',
    'int sum(int a[5],int n) { if(n==0) return 0; return a[0]+sum(a+1,n-1); } '
    'int main(void) { int a[3]; a[0]=13; a[1]=14; a[2]=15; return sum(a,3); }',
]

with tempfile.TemporaryDirectory(prefix='kcc array parameters ') as directory:
    directory = Path(directory)
    source, other, il, assembly, obj, executable = [directory / name for name in
                                                   ('k.c', 'h.c', 'p.ssa', 'p.s', 'h.o', 'p')]

    def compile_source(text):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True,
                                text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)],
                           check=True, timeout=10)
        return result.stdout

    def link_and_run(host_text=None):
        objects = [str(assembly)]
        if host_text is not None:
            other.write_text(host_text)
            subprocess.run([host, '-std=c2x', '-fsigned-char', '-c', str(other),
                            '-o', str(obj)], capture_output=True, check=True, timeout=10)
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

    # Eight adjusted pointer arguments cover registers and stack arguments.
    signature = ('int mutate(_Bool b[2],char c[2],short s[2],int i[2],'
                 'long l[2],unsigned u[2],long long q[2],int *p[2])')
    body = (' { b[1]=1; c[1]=7; s[1]=8; i[1]=9; l[1]=10; u[1]=11; q[1]=12; p[1]=p[0]; '
            'if(c[0]!=1 || s[0]!=2 || i[0]!=3 || l[0]!=4 || u[0]!=5 || q[0]!=6) return 1; return 42; }\n')
    prototypes = ('int mutate(_Bool *,char *,short *,int *,long *,unsigned *,long long *,int **);\n')
    relay = ('int relay(_Bool b[3],char c[3],short s[3],int i[3],long l[3],unsigned u[3],long long q[3],int *p[3]) '
             '{ return mutate(b,c,s,i,l,u,q,p); }\n')
    driver = ('int relay(_Bool *,char *,short *,int *,long *,unsigned *,long long *,int **); '
              'int main(void) { int x=42; _Bool b[2]={0,0}; char c[2]={1,0}; short s[2]={2,0}; '
              'int i[2]={3,0}; long l[2]={4,0}; unsigned u[2]={5,0}; long long q[2]={6,0}; int *p[2]={&x,0}; '
              'if(relay(b,c,s,i,l,u,q,p)!=42) return 1; '
              'if(b[1]!=1 || c[1]!=7 || s[1]!=8 || i[1]!=9 || l[1]!=10 || u[1]!=11 || q[1]!=12 || p[1]!=&x) return 2; return 42; }\n')
    for text, host_text in [(signature + body, prototypes + relay + driver),
                            (prototypes + relay, signature + body + driver)]:
        compile_source(text)
        if qbe:
            link_and_run(host_text)

    matrix_helper = 'int matrix(int a[2][3]) { a[1][2]=42; return a[1][2]; }\n'
    matrix_relay = 'int matrix(int [7][3]); int relay(int a[9][3]) { return matrix(a); }\n'
    matrix_driver = ('int relay(int a[2][3]); int main(void) { int a[2][3]={{0}}; '
                     'int result=relay(a); if(a[1][2]!=42 || a[0][2]!=0) return 1; return result; }\n')
    for text, host_text in [(matrix_helper, matrix_relay + matrix_driver),
                            (matrix_relay, matrix_helper + matrix_driver)]:
        compile_source(text)
        if qbe:
            link_and_run(host_text)

    result = compile_source('int f(int a[3]) { return a[0]; }')
    assert 'alloc8 8\n' in result and 'alloc4 12\n' not in result, result
    for bytes_count, valid in [(1048568, True), (1048569, False)]:
        # Even a large declared bound adjusts to one eight-byte spill.
        source.write_text(f'int f(int a[262144]) {{ char local[{bytes_count}]; return a[0]; }}')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'storage limit' in result.stderr, result.stderr

    rejected = [
        ('int f(int [2][3]); int f(int [2][4]);', 'incompatible function'),
        ('int f(int **); int f(int [2][3]);', 'incompatible function'),
        ('int f(char [2]); int f(signed char [2]);', 'incompatible function'),
        ('int f(int a[2][]) { return 0; }', 'array element type must be complete'),
        ('int f(int a[0]) { return 0; }', 'array bound'),
        ('int f(int a[static 3]) { return 0; }', 'keyword is not supported'),
        ('int f(int a[2][3]) { return a[0][0]; } int main(void) { int b[2][4]; return f(b); }', 'pointer conversion'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Array parameters passed ({len(programs)} full-value programs, declared/effective shape, pointer rebinding/addressing, '
      f'both-direction eight-argument and row ABI, pointer-sized budgets and constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
