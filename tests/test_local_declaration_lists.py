"""Each declarator owns its shape and enters scope in source order."""
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
    programs.append(f'''int main(void) {{ {name} x=1, *p=&x, a[2], y=*p, (*q)[2]=&a;
 a[0]=0; a[1]=0; (*q)[1]=7;
 if(y!=1 || p!=&x || a[1]!=({name})7 || a[0]!=0) return 1; return 42; }}''')
programs += [
    'int main(void) { int x=13,y=x+1,z=y+1; return x+y+z; }',
    'int main(void) { int y=42; { int x=y,y=7; if(x!=42 || y!=7) return 1; } return y; }',
    'int next(int *p) { *p=*p+1; return *p; } int main(void) { int n=0,x=next(&n),y=next(&n),z=next(&n); '
    'if(n!=3 || x!=1 || y!=2 || z!=3) return 1; return 42; }',
    'int add(int a,int b) { return a+b; } int main(void) { int x=add(1,2),y=add(x,4),z=add(y,35); return z; }',
    'int main(void) { int a=13,b=14,c=15,n=0; for(int i=0,end=3,x=end;i<end;i=i+1) n=n+x; '
    'if(n!=9) return 1; return a+b+c; }',
    'int main(void) { int n=0; for(int i=0,end=3;i<end;i=i+1) { '
    'for(int j=0,stop=3;j<stop;j=j+1) { if(j==1) continue; n=n+1; } if(i==1) break; } '
    'if(n!=4) return 1; return 42; }',
    'int main(void) { int a[3], *p=a, (*q)[3]=&a, x=42; a[2]=x; if(p+2!=&(*q)[2]) return 1; return p[2]; }',
    'int main(void) { int a[3], (*p)[]=&a, (*q)[3]=p; a[2]=42; return (*q)[2]; }',
    'int main(void) { int x=0,y=0&&(x=1),z=1||(x=2); if(x!=0 || y!=0 || z!=1) return 1; return 42; }',
    'int next(int *p) { *p=*p+1; return *p; } int main(void) { int calls=0,total=0; '
    'for(int i=next(&calls),end=next(&calls)+2;i<end;i=i+1) total=total+i; '
    'if(calls!=2 || total!=6) return 1; return 42; }',
    'int main(void) { int i=42; for(int i=0,j=i+3;i<j;i=i+1) { int x=i,y=x; if(y!=i) return 1; } return i; }',
]

with tempfile.TemporaryDirectory(prefix='kcc local declaration lists ') as directory:
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
        helper = f'int mutate({name} *p) {{ {name} x=7,*q=p,old=q[0]; q[1]=x; return 42+old; }}\n'
        relay = f'int mutate({name} *); int relay({name} *p) {{ {name} *q=p,x=0; return mutate(q)+x; }}\n'
        driver = (f'int relay({name} *); int main(void) {{ {name} a[2]={{0}}; '
                  f'if(relay(a)!=42 || a[1]!=({name})7 || a[0]!=0) return 1; return 42; }}\n')
        for text, host_text in [(helper, relay + driver), (relay, helper + driver)]:
            compile_source(text)
            if qbe:
                link_and_run(host_text)

    # Compile-only boundaries: each declaration consumes an item and a local slot.
    for count, valid in [(256, True), (257, False)]:
        source.write_text('int main(void) { int ' + ','.join(f'x{i}' for i in range(count)) + '; return 42; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'local limit (256)' in result.stderr, result.stderr
    for count, message in [(4096, 'local limit (256)'), (4097, 'item limit (4096)')]:
        source.write_text('int main(void) { int ' + ','.join(f'x{i}' for i in range(count)) + '; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    for padding, valid in [(4092, True), (4093, False)]:
        # Padding + for block item + two header declarations + return item.
        source.write_text('int main(void) {' + ';' * padding + 'for(int i=0,j=0;i<0;i=i+1); return 42;}')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'item limit (4096)' in result.stderr, result.stderr
    for extra, valid in [(0, True), (1, False)]:
        source.write_text(f'int main(void) {{ char a[524288],b[{524288+extra}]; return 42; }}')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'storage limit' in result.stderr, result.stderr

    rejected = [
        ('int main(void) { int x=1,x=2; return 0; }', 'redeclaration'),
        ('int main(void) { int x=y,y=42; return x; }', 'undeclared identifier'),
        ('int main(void) { int x=1,; return 0; }', 'expected local name'),
        ('int main(void) { int x=1,int y=2; return 0; }', 'expected local name'),
        ('int main(void) { int x=1,*; return 0; }', 'expected local name'),
        ('int main(void) { int x=1,y=(x=2,(void)3); return 0; }', 'conversion requires a scalar'),
        ('int main(void) { int x=1,a[2]=x; return 0; }', 'aggregate initializer requires braces or a compatible record value'),
        ('int main(void) { int x=1,a[]; return 0; }', 'local object type must be complete'),
        ('int main(void) { for(int i=0,j=3;i<j;i=i+1); return j; }', 'undeclared identifier'),
        ('int main(void) { for(int i=0,i=3;i<0;i=i+1); return 0; }', 'redeclaration'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Local declaration lists passed ({len(programs)} full-value programs, per-declarator shape and scope, '
      f'both-direction all-primitive ABI, for-list sequencing and exact item/local/storage budgets; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
