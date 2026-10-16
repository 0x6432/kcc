"""Unknown array referents have addresses and decay, never an invented stride."""
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
    programs.append(f'''int mutate({name} (*)[3]); int mutate({name} (*)[]);
int mutate({name} (*p)[]) {{ {name} (*q)[]=p; {name} (*known)[3]=q;
 (*q)[2]=7; if(&*q!=p || known!=p || !q) return 1; return 42; }}
int main(void) {{ {name} a[3]; a[0]=0; a[1]=0; a[2]=0;
 {name} (*p)[]=&a; if(mutate(p)!=42 || (*p)[2]!=({name})7 || a[1]!=0) return 2; return 42; }}''')
programs += [
    '''int main(void) { int x=42; int *a[3]; a[0]=&x; a[1]=&x; a[2]=&x;
 int *(*p)[]=&a; return *(*p)[2]; }''',
    '''int main(void) { int a[2][3]; a[1][2]=42; int (*p)[][3]=&a;
 int (*q)[3]=*p; if(q+1!=&a[1]) return 1; return (*p)[1][2]; }''',
    '''int main(void) { int a[3]; int b[4]; a[2]=7; b[3]=42;
 int (*p[2])[]; p[0]=&a; p[1]=&b; return (*p[1])[3]; }''',
    '''int main(void) { int a[3]; a[2]=42; int (*p)[]=&a;
 int (**q)[]=&p; return (**q)[2]; }''',
    '''int main(void) { int a[3]; a[2]=42; int (*p)[]=&a;
 int (*q)[3]=(int (*)[3])p; if(q+1!=&a+1) return 1; return (*q)[2]; }''',
    '''int main(void) { int a[2][3]; int (*p)[]=&a[0]; int (*q)[]=&a[1];
 if(!(p<q) || !(p<=q) || !(q>p) || !(q>=p) || p==q || !(p!=q)) return 1; return 42; }''',
    '''int get(int (*p)[]) { return (*p)[2]; }
 int main(void) { int a[3]; a[2]=42; return get((int (*)[])&a); }''',
]

with tempfile.TemporaryDirectory(prefix='kcc incomplete object pointers ') as directory:
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
        helper = f'int mutate({name} (*p)[]) {{ (*p)[2]=7; return 42; }}\n'
        relay = f'int mutate({name} (*)[]); int relay({name} (*p)[3]) {{ return mutate(p); }}\n'
        driver = (f'int relay({name} (*)[3]); int main(void) {{ {name} a[3]={{0}}; '
                  f'if(relay(&a)!=42 || a[2]!=({name})7 || a[1]!=0) return 1; return 42; }}\n')
        for text, host_text in [(helper, relay + driver), (relay, helper + driver)]:
            compile_source(text)
            if qbe:
                link_and_run(host_text)

    signature = ('int mutate(_Bool (*a)[],char (*b)[],short (*c)[],int (*d)[],'
                 'long (*e)[],unsigned (*f)[],long long (*g)[],int *(*h)[])')
    body = ' { (*a)[1]=1; (*b)[1]=2; (*c)[1]=3; (*d)[1]=4; (*e)[1]=5; (*f)[1]=6; (*g)[1]=7; (*h)[1]=(*h)[0]; return 42; }\n'
    relay = signature + ';\n' + signature.replace('mutate(', 'relay(') + ' { return mutate(a,b,c,d,e,f,g,h); }\n'
    driver = (signature.replace('mutate(', 'relay(') + ';\n'
              'int main(void) { int x=42; _Bool a[2]={0}; char b[2]={0}; short c[2]={0}; int d[2]={0}; '
              'long e[2]={0}; unsigned f[2]={0}; long long g[2]={0}; int *h[2]={&x,0}; '
              'if(relay(&a,&b,&c,&d,&e,&f,&g,&h)!=42) return 1; '
              'if(a[1]!=1 || b[1]!=2 || c[1]!=3 || d[1]!=4 || e[1]!=5 || f[1]!=6 || g[1]!=7 || h[1]!=&x) return 2; return 42; }\n')
    for text, host_text in [(signature + body, relay + driver), (relay, signature + body + driver)]:
        compile_source(text)
        if qbe:
            link_and_run(host_text)

    compile_source('int cancel(int (*p)[]) { return &*p==p; }')
    if qbe:
        link_and_run('int cancel(int (*)[]); int main(void) { int a[3]; if(!cancel(0) || !cancel(&a)) return 1; return 42; }')

    # Known bounds survive later unknown redeclarations; earlier call nodes remain valid.
    compile_source('int f(int (*)[]); int g(void) { int a[4]; a[0]=0; return f(&a); } int f(int (*)[3]);')
    compile_source('int f(int (*)[3]); int f(int (*)[]); int f(int (*p)[]) { return (*p)[2]; }')
    rejected = [
        ('int f(int (*p)[]) { return p+0==p; }', 'pointer arithmetic requires a complete object referent'),
        ('int f(int (*p)[]) { return 0+p==p; }', 'pointer arithmetic requires a complete object referent'),
        ('int f(int (*p)[]) { return p-0==p; }', 'pointer arithmetic requires a complete object referent'),
        ('int f(int (*p)[]) { return p-p; }', 'pointer subtraction requires complete object referents'),
        ('int f(int (*p)[],int (*q)[3]) { return q-p; }', 'pointer subtraction requires complete object referents'),
        ('int f(int (*p)[],int (*q)[3]) { return p-q; }', 'pointer subtraction requires complete object referents'),
        ('int f(int (*p)[]) { return p[0][0]; }', 'pointer arithmetic requires a complete object referent'),
        ('int f(int (*p)[]) { return 0[p][0]; }', 'pointer arithmetic requires a complete object referent'),
        ('int f(void) { int a[]; return 0; }', 'local object type must be complete'),
        ('int f(void) { int a[2][]; return 0; }', 'array element type must be complete'),
        ('int f(void) { int (*p)[][]; return 0; }', 'array element type must be complete'),
        ('int f(void) { int (*p)[0]; return 0; }', 'array bound'),
        ('int f(int (*)[]); int f(int (*)[3]); int f(int (*)[4]);', 'incompatible function'),
        ('int f(int (*)[3]); int f(int (*)[]); int f(int (*)[4]);', 'incompatible function'),
        ('int f(int (*)[]); int f(int (*)[3]); int f(int (*)[]); int f(int (*)[4]);', 'incompatible function'),
        ('int f(int (**a)[]); int f(int (**a)[3]); int f(int (**a)[4]);', 'incompatible function'),
        ('int f(int (*a[2])[]); int f(int (*a[2])[3]); int f(int (*a[2])[4]);', 'incompatible function'),
        ('int f(int (*)[3]); int f(int (*)[]); int f(int (*p)[]) { return p+1==p; }', 'complete object referent'),
        ('int f(int (*)[]); int f(int (*)[3]); int f(int (*)[]); '
         'int main(void) { int a[4]; return f(&a); }', 'pointer conversion'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Incomplete object pointers passed ({len(programs)} full-value programs, all primitive/pointer leaves, '
      f'both-direction row/eight-argument ABI, null address cancellation, composite redeclarations and completeness constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
