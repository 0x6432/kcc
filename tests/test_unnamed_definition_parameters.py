"""C23 omitted names do not remove ABI arguments or caller evaluation."""
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
    programs.append(f'''int select({name}, {name} x, {name} [], {name} (*)[3])
{{ return x==({name})7; }}
int main(void) {{ {name} a[3]; a[0]=0; a[1]=0; a[2]=0;
 if(!select(0,({name})7,a,&a)) return 1; return 42; }}''')
programs += [
    'int ignore(int,int *,int [4],int (*)[3]) { return 42; } '
    'int main(void) { int a[3]; a[0]=0; a[1]=0; a[2]=0; return ignore(7,a,a,&a); }',
    'int next(int *p) { *p=*p+1; return 7; } int ignore(int,int x) { return x; } '
    'int main(void) { int n=0,x=ignore(next(&n),42); if(n!=1) return 1; return x; }',
    'int f(int,int x) { if(x==0) return 42; return f(x,x-1); } int main(void) { return f(99,3); }',
    'int f(int); int f(int) { int x=42; return x; } int main(void) { return f(7); }',
    'int f(int (*p)[],int (*)[3]) { return (*p)[2]; } '
    'int main(void) { int a[3]; a[2]=42; return f(&a,&a); }',
]

with tempfile.TemporaryDirectory(prefix='kcc unnamed definition parameters ') as directory:
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
        helper = (f'{name} select({name},{name} x,{name},{name},{name},{name},{name},{name} y) '
                  f'{{ if(x!=({name})3) return 0; return y; }}\n')
        prototype = f'{name} select({name},{name},{name},{name},{name},{name},{name},{name});\n'
        relay = (prototype + f'{name} relay({name} a,{name} b,{name} c,{name} d,{name} e,{name} f,{name} g,{name} h) '
                 '{ return select(a,b,c,d,e,f,g,h); }\n')
        driver = (prototype.replace('select(', 'relay(') +
                  f'int main(void) {{ if(relay(1,3,1,1,1,1,1,7)!=({name})7) return 1; return 42; }}\n')
        for text, host_text in [(helper, relay + driver), (relay, helper + driver)]:
            compile_source(text)
            if qbe:
                link_and_run(host_text)

    signature = 'long long wide(char,int a,short,long b,int *,unsigned c,long long,long long d)'
    body = ' { return a+b+c+d; }\n'
    relay = signature + ';\n' + ('long long relay(char q,int a,short s,long b,int *p,unsigned c,long long r,long long d) '
                                               '{ return wide(q,a,s,b,p,c,r,d); }\n')
    driver = ('long long relay(char,int,short,long,int *,unsigned,long long,long long); '
              'int main(void) { int x=0; '
              'long long value=relay(-7,3,-8,4294967296L,&x,7,9,4611686018427387904LL); '
              'if(value!=4611686022722355210LL) return 1; return 42; }\n')
    for text, host_text in [(signature + body, relay + driver), (relay, signature + body + driver)]:
        compile_source(text)
        if qbe:
            link_and_run(host_text)

    result = compile_source('int f(int,char,int *,int [],int (*)[3],long,long long,short) { return 42; }')
    assert 'alloc' not in result and '\tstore' not in result and '%p7' in result, result
    result = compile_source('int f(int,int x,int,int,int,int,int,int y) { return x+y; }')
    assert 'storew %p1, %v0' in result and 'storew %p7, %v1' in result, result
    assert 'storew %p0' not in result and 'storew %p6' not in result, result

    parameters = ','.join(['int'] * 127 + ['int x'])
    arguments = ','.join(['0'] * 127 + ['42'])
    compile_source(f'int f({parameters}) {{ return x; }} int main(void) {{ return f({arguments}); }}')
    if qbe:
        link_and_run()
    source.write_text('int f(' + ','.join(['int'] * 129) + ') { return 42; }')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and not result.stdout and 'parameter limit (128)' in result.stderr, result.stderr

    # Actual storage, not unnamed ABI positions, counts toward local budgets.
    for parameters, locals_count, valid in [(','.join(['int'] * 128), 256, True),
                                             (','.join(f'int p{i}' for i in range(128)), 129, False)]:
        source.write_text('int f(' + parameters + ') { int ' + ','.join(f'x{i}' for i in range(locals_count)) + '; return 42; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'local limit (256)' in result.stderr, result.stderr
    for named, valid in [(False, True), (True, False)]:
        source.write_text('int f(int' + (' p' if named else '') + ') { char a[1048576]; return 42; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'storage limit' in result.stderr, result.stderr

    rejected = [
        ('int f(int,int x,int x) { return 0; }', 'duplicate parameter name'),
        ('int f(int) { return missing; }', 'undeclared identifier'),
        ('int f(int) { return 42; } int main(void) { return f(); }', 'argument count'),
        ('int f(int *) { return 42; } int main(void) { return f(1); }', 'pointer conversion'),
        ('int f(int) { return 42; } int main(void) { return f(missing); }', 'undeclared identifier'),
        ('int f(int [2][]) { return 42; }', 'array element type must be complete'),
        ('int f(int [0]) { return 42; }', 'array bound'),
        ('int f(int); int f(long) { return 42; }', 'incompatible function'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Unnamed definition parameters passed ({len(programs)} full-value programs, all primitive/adjusted array types, '
      f'both-direction register/stack/full-width ABI, caller side effects and exact parameter/spill budgets; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
