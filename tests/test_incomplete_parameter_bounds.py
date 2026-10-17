"""Unknown outer parameter bounds remain metadata, never zero-sized objects."""
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
    programs += [f'''int move({name} []); int move({name} [9]);
int move({name} a[]) {{ {name} *original=a; a=a+1; {name} **q=&a;
 if(*q!=original+1) return 1; a[0]=7; return 42; }}
int main(void) {{ {name} a[3]; a[0]=0; a[1]=0; a[2]=0;
 if(move(a)!=42 || a[1]!=({name})7 || a[0]!=0 || a[2]!=0) return 2; return 42; }}''',
                 f'''int matrix({name} [][3]); int matrix({name} [7][3]);
int matrix({name} a[][3]) {{ a=a+1; a[0][2]=7; return 42; }}
int main(void) {{ {name} a[2][3];
 for(int i=0;i<2;i=i+1) for(int j=0;j<3;j=j+1) a[i][j]=0;
 if(matrix(a)!=42 || a[1][2]!=({name})7 || a[0][2]!=0) return 1; return 42; }}''']
programs += [
    'int f(int *a[]) { a[1]=a[0]; return *a[1]; } int main(void) { int x=42; int *p[2]; p[0]=&x; p[1]=&x; return f(p); }',
    'int length(char a[]) { int n=0; while(a[n]) n=n+1; return n; } int main(void) { return length("a" "bc")+39; }',
    'int sum(int a[],int n) { if(n==0) return 0; return a[0]+sum(a+1,n-1); } '
    'int main(void) { int a[3]; a[0]=13; a[1]=14; a[2]=15; return sum(a,3); }',
]

with tempfile.TemporaryDirectory(prefix='kcc incomplete parameter bounds ') as directory:
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

    signature = ('int mutate(_Bool b[],char c[],short s[],int i[],'
                 'long l[],unsigned u[],long long q[],int *p[])')
    body = (' { b[1]=1; c[1]=7; s[1]=8; i[1]=9; l[1]=10; u[1]=11; q[1]=12; p[1]=p[0]; '
            'if(c[0]!=1 || s[0]!=2 || i[0]!=3 || l[0]!=4 || u[0]!=5 || q[0]!=6) return 1; return 42; }\n')
    prototypes = 'int mutate(_Bool *,char *,short *,int *,long *,unsigned *,long long *,int **);\n'
    relay = ('int relay(_Bool b[],char c[],short s[],int i[],long l[],unsigned u[],long long q[],int *p[]) '
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

    helper = 'int matrix(int a[][3]) { a[1][2]=42; return a[1][2]; }\n'
    relay = 'int matrix(int [][3]); int relay(int a[][3]) { return matrix(a); }\n'
    driver = ('int relay(int a[][3]); int main(void) { int a[2][3]={{0}}; '
              'int result=relay(a); if(a[1][2]!=42 || a[0][2]!=0) return 1; return result; }\n')
    for text, host_text in [(helper, relay + driver), (relay, helper + driver)]:
        compile_source(text)
        if qbe:
            link_and_run(host_text)

    result = compile_source('int f(int a[]) { return a[0]; }')
    assert 'alloc8 8\n' in result and 'alloc4 0\n' not in result, result
    for bytes_count, valid in [(1048568, True), (1048569, False)]:
        source.write_text(f'int f(int a[]) {{ char local[{bytes_count}]; return 0; }}')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'storage limit' in result.stderr, result.stderr
    for dimensions, valid in [(64, True), (65, False)]:
        source.write_text('int f(int a[]' + '[1]' * (dimensions - 1) + ') { return 0; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'dimension limit' in result.stderr, result.stderr

    rejected = [
        ('int f(int a[][]) { return 0; }', 'array element type must be complete'),
        ('int f(int a[2][]) { return 0; }', 'array element type must be complete'),
        ('int main(void) { int a[]; return 0; }', 'local object type must be complete'),
        ('int f(int a[0]) { return 0; }', 'array bound'),
        ('int f(int a[][0]) { return 0; }', 'array bound'),
        ('int f(int a[static 2]) { return 0; }', 'static array bounds are not supported'),
        ('int f(int [][3]); int f(int [][4]);', 'incompatible function'),
        ('int f(int **); int f(int [][3]);', 'incompatible function'),
        ('int f(char []); int f(signed char []);', 'incompatible function'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Omitted parameter bounds passed ({len(programs)} full-value programs, incomplete versus effective type, all primitive/pointer leaves, '
      f'both-direction stack/row ABI, string decay, storage/dimension constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
