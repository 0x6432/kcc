"""Nested array shape, one-level decay, row strides and borrowed-row ABI."""
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
    programs.append(f'''int main(void) {{ {name} a[2][3];
 for(int i=0;i<2;i=i+1) for(int j=0;j<3;j=j+1) a[i][j]=i*3+j+1;
 if(a[1][2]!=({name})6 || a[0][1]!=({name})2) return 1;
 if(a+2-a!=2L || &a[1]-&a[0]!=1L || (&a+1)-&a!=1L) return 2;
 if((a+2)[-1][2]!=({name})6 || (&a)[0][1][1]!=({name})5) return 3;
 {name} *p=a[1]; if(p!=&a[1][0] || p[2]!=({name})6) return 4;
 if(&a[0][3]!=a[0]+3 || &a[2]!=a+2) return 5;
 return 42; }}''')
programs += [
    'int main(void) { int a[2][3][4]; '
    'for(int i=0;i<2;i=i+1) for(int j=0;j<3;j=j+1) '
    'for(int k=0;k<4;k=k+1) a[i][j][k]=i*12+j*4+k; '
    'if(a[1][2][3]!=23 || a+2-a!=2 || a[0]+3-a[0]!=3) return 1; '
    'if((&a[1]+1)-&a[1]!=1 || (&a)[0][1][2][3]!=23) return 2; return 42; }',
    'int main(void) { int x=42; int *p[2][3]; '
    'for(int i=0;i<2;i=i+1) for(int j=0;j<3;j=j+1) p[i][j]=&x; '
    'if(*p[1][2]!=42 || p+2-p!=2 || (&p+1)-&p!=1) return 1; '
    'int **row=p[1]; if(row[2]!=&x || (&p)[0][0][0]!=&x) return 2; return 42; }',
    '#define ROWS 2U\n#define COLS 03L\nint main(void) { int a[ROWS][COLS]; '
    'a[1][2]=42; return a[1][2]; }',
]

with tempfile.TemporaryDirectory(prefix='kcc multidimensional arrays ') as directory:
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

    for name in integers:
        helper = f'{name} update({name} *p) {{ p[2]=7; return p[0]+p[1]+p[2]; }}\n'
        relay = f'''{name} update({name} *);
int local(void) {{ {name} a[2][3];
 for(int i=0;i<2;i=i+1) for(int j=0;j<3;j=j+1) a[i][j]=j+1;
 if(update(a[1])!=({name})((({name})1)+(({name})2)+(({name})7))) return 1;
 if(a[1][2]!=({name})7 || a[0][2]!=({name})3) return 2; return 42; }}\n'''
        host_driver = f'''int local(void); {name} update({name} *);
int main(void) {{ {name} a[2][3];
 for(int i=0;i<2;i++) for(int j=0;j<3;j++) a[i][j]=j+1;
 if(update(a[0])!=({name})((({name})1)+(({name})2)+(({name})7))) return 3;
 if(a[0][2]!=({name})7 || a[1][2]!=({name})3) return 4; return local(); }}\n'''
        for text, host_text in [(helper + relay, host_driver), (relay, helper + host_driver)]:
            compile_source(text)
            if qbe:
                link_and_run(host_text)
        other.write_text(helper + relay + host_driver)
        subprocess.run([host, '-std=c2x', '-fsigned-char', str(other), '-o', str(executable)],
                       capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, name

    result = compile_source('int f(void) { int a[2][3]; return (a+1)-a; }')
    assert 'alloc4 24\n' in result and ', 12\n' in result, result
    result = compile_source('int f(void) { int a[2][3]; return (&a+1)-&a; }')
    assert 'alloc4 24\n' in result and ', 24\n' in result, result
    assert 'load' not in result, result

    for dimensions, valid in [(64, True), (65, False)]:
        text = 'int f(void) { int a' + '[1]' * dimensions + '; return 0; }'
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'dimension limit' in result.stderr, result.stderr
    for dimensions, valid in [(42, True), (43, False)]:
        text = 'int f(void) { int a' + '[1]' * dimensions + '; return a' + '[0]' * dimensions + '; }'
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr
        elif qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
    for text, valid in [('int f(void) { char a[1024][1024]; return 0; }', True),
                        ('int f(void) { char a[1024][1025]; return 0; }', False)]:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'storage limit' in result.stderr, result.stderr

    rejected = [
        ('int main(void) { int a[2][0]; return 0; }', 'array bound'),
        ('int main(void) { int a[2][]; return 0; }', 'array element type must be complete'),
        ('int main(void) { int a[2][1,2]; return 0; }', "expected ']'"),
        ('int main(void) { int a[2][3]; int b[3][2]; return &a==&b; }', 'compatible pointer'),
        ('int main(void) { int a[2][3]; int b[3][2]; return a-b; }', 'compatible pointer'),
        ('int main(void) { int a[2][3]; int **p=a; return 0; }', 'pointer conversion'),
        ('int main(void) { int a[2][3]; int *p=&a[0]; return 0; }', 'pointer conversion'),
        ('int main(void) { int a[2][3]; a[0]=a[1]; return 0; }', 'modifiable lvalue'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Multidimensional arrays passed ({len(programs)} full-value programs, all primitive/pointer leaves, both-direction '
      f'borrowed-row ABI, shape/stride/decay, dimensions/product/depth constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
