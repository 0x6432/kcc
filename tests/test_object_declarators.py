"""Single-pass object declarator precedence, shape and host ABI checks."""
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
    programs.append(f'''int row({name} (*)[3]); int row({name} a[][3]);
int row({name} (*a)[3]) {{ {name} (*p)[3]=a+1; (*p)[2]=7;
 if(p-a!=1 || a+2-p!=1) return 1; return 42; }}
int main(void) {{ {name} a[2][3];
 for(int i=0;i<2;i=i+1) for(int j=0;j<3;j=j+1) a[i][j]=0;
 {name} (*p)[3]=(a); {name} (*q[2])[3]; q[0]=p; q[1]=p+1;
 if(row(p)!=42 || q[1][0][2]!=({name})7 || q[0][0][2]!=0) return 2;
 {name} (**r)[3]=&p; (*r)=(*r)+1;
 if(p!=q[1] || (*p)[2]!=({name})7) return 3; return 42; }}''')
programs += [
    '''int main(void) { int (x)=42; int (((*p)))=&x; int (*a[2])[3]; int row[3];
 row[0]=1; row[1]=2; row[2]=3; a[0]=&row; a[1]=a[0];
 if(a[0][0][1]!=2 || **&p!=42) return 1; return x; }''',
    '''int main(void) { int x=42; int *row[3]; row[0]=&x; row[1]=&x; row[2]=&x;
 int *(*a[2])[3]; a[0]=&row; a[1]=a[0]; return *a[1][0][2]; }''',
    '''int main(void) { int a[2][3]; a[1][2]=42;
 int (*p)[2][3]=&a; int (*q)[3]=(int (*)[3])(*p);
 return q[1][2]; }''',
    '''int f(int (*a[2])[3]); int f(int (**a)[3]) { return a[1][0][2]; }
 int main(void) { int a[3]; int b[3]; a[2]=7; b[2]=42;
 int (*p[2])[3]; p[0]=&a; p[1]=&b; return f(p); }''',
    '''int next(int *n) { *n=*n+1; return 1; }
 int main(void) { int a[2][3]; a[1][2]=42; int (*p)[3]=a;
 int n=0; int x=p[next(&n)][2]; if(n!=1) return 1; return x; }''',
    '''int f(int (a)[][3]) { return a[1][2]; }
 int main(void) { int a[2][3]; a[1][2]=42; return f(a); }''',
    '''int sum(int (*a)[3],int n) { if(!n) return 0; return a[0][2]+sum(a+1,n-1); }
 int main(void) { int a[3][3]; a[0][2]=13; a[1][2]=14; a[2][2]=15; return sum(a,3); }''',
    '''int main(void) { int *a[2]; int x=42; a[0]=&x; a[1]=a[0];
 int *(*p)[2]=&a; return *(*p)[1]; }''',
]

with tempfile.TemporaryDirectory(prefix='kcc object declarators ') as directory:
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
        signature = f'int mutate({name} (*a)[3])'
        body = ' { a[1][2]=7; return 42; }\n'
        relay = f'int mutate({name} [][3]); int relay({name} (*a)[3]) {{ return mutate(a); }}\n'
        driver = (f'int relay({name} (*)[3]); int main(void) {{ {name} a[2][3]={{{{0}}}}; '
                  f'if(relay(a)!=42 || a[1][2]!=({name})7 || a[0][2]!=0) return 1; return 42; }}\n')
        for text, host_text in [(signature + body, relay + driver), (relay, signature + body + driver)]:
            compile_source(text)
            if qbe:
                link_and_run(host_text)

    signature = ('int mutate(int (*a)[3],int (**b)[3],int *c,int (*d)[2][3],'
                 'int *(*e)[2],int (*f)[3],int (**g)[3],int (*h)[3])')
    body = (' { a[1][2]=5; (*b)=f+1; *c=6; (*d)[1][2]=7; *(*e)[1]=8; '
            'if(h-f!=1 || *g!=f+1) return 1; return 42; }\n')
    prototype = signature + ';\n'
    relay = signature.replace('mutate(', 'relay(') + ' { return mutate(a,b,c,d,e,f,g,h); }\n'
    driver = (signature.replace('mutate(', 'relay(') + ';\n'
              'int main(void) { int a[2][3]={{0}}; int (*b)[3]=a; int c=0; int d[2][3]={{0}}; '
              'int x=0; int *e[2]={&x,&x}; '
              'if(relay(a,&b,&c,&d,&e,a,&b,a+1)!=42) return 1; '
              'if(a[1][2]!=5 || b!=a+1 || c!=6 || d[1][2]!=7 || x!=8) return 2; return 42; }\n')
    for text, host_text in [(signature + body, prototype + relay + driver),
                            (prototype + relay, signature + body + driver)]:
        compile_source(text)
        if qbe:
            link_and_run(host_text)

    # These resource fixtures only compile; they do not read uninitialized objects.
    for nesting, valid in [(64, True), (65, False)]:
        text = 'int main(void) { int ' + '(' * nesting + 'x' + ')' * nesting + '=42; return x; }'
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'declarator exceeds nesting limit (64)' in result.stderr, result.stderr
    for count, valid in [(64, True), (65, False)]:
        # Split stars across a grouping boundary: a per-prefix limit is insufficient.
        text = 'int f(void) { int ' + '*' * 32 + '(*' + '*' * (count - 33) + 'p); return 0; }'
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'pointer type exceeds depth limit (64)' in result.stderr, result.stderr
    for count, valid in [(64, True), (65, False)]:
        text = 'int f(void) { int (*p' + '[1]' * 32 + ')' + '[1]' * (count - 32) + '; return 0; }'
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'array declarator exceeds dimension limit (64)' in result.stderr, result.stderr

    rejected = [
        ('int f(void) { int (*p)[3]; int a[2][4]; p=a; return 0; }', 'pointer conversion'),
        ('int f(int (*)[3]); int f(int **);', 'incompatible function'),
        ('int f(int (*a)[3]); int f(int (*a)[4]);', 'incompatible function'),
        ('int f(void) { int (*p)[][]; return 0; }', 'array element type must be complete'),
        ('int f(int (*a)[][]);', 'array element type must be complete'),
        ('int f(void) { int (); return 0; }', 'expected local name'),
        ('int f(int ()[3]);', 'function return type'),
        ('int f(void) { int x=0; return (int (name))x; }', 'expected object declarator'),
        ('int f(void) { int (*p[2])[0]; return 0; }', 'array bound'),
        ('int f(void) { int (*p)[3; return 0; }', "expected ']'"),
        ('int f(void) { int (*p[2]; return 0; }', "expected ')'"),
        ('int f(void) { int (*p)(int)=1; return 0; }', 'pointer conversion'),
        ('int f(void) { int a[3]; return (int [3])a; }', 'cast target must be a scalar type'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Object declarators passed ({len(programs)} full-value programs, all primitive leaves, alternating pointer/array shapes, '
      f'both-direction row and eight-argument ABI, abstract casts and exact resource constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
