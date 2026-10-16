"""Typed function designators, once-only callbacks and complete fixed-call ABI."""
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
    programs.append(f'''{name} identity({name} x) {{ return x; }}
{name} apply({name} callback({name}),{name} x) {{ return callback(x); }}
int main(void) {{ {name} (*p)({name})=identity; {name} (*a[2])({name});
 a[0]=p; a[1]=&identity; if(p!=identity || &*p!=p || !p || p!=a[1]) return 1;
 if(apply(a[1],7)!=({name})7 || (*p)(7)!=({name})7 || (({name} (*)({name}))p)(7)!=({name})7) return 2;
 return 42; }}''')
programs += [
    'int id(int x) { return x; } int (*factory(void))(int) { return id; } '
    'int main(void) { return factory()(42); }',
    'int id(int x) { return x; } int (*pick(int *n))(int) { *n=*n+1; return id; } '
    'int main(void) { int n=0,x=pick(&n)(42); if(n!=1) return 1; return x; }',
    'int id(int x) { return x; } int next(int *n) { *n=*n+1; return 0; } '
    'int main(void) { int (*a[2])(int); a[0]=id; a[1]=id; int n=0,x=a[next(&n)](42); if(n!=1) return 1; return x; }',
    'int id(int x) { return x; } int main(void) { int (*p)(int)=id; int (**q)(int)=&p; return (**q)(42); }',
    'int g(int x) { return x; } int f(int x) { return x+1; } '
    'int main(void) { int (*f)(int)=g; return f(42); }',
    'int fact(int n) { if(n==0) return 1; return n*fact(n-1); } '
    'int main(void) { int (*p)(int)=fact; if(p(5)!=120) return 1; return 42; }',
    'int *id(int *p) { return p; } int main(void) { int x=42; int *(*p)(int *)=id; return *p(&x); }',
    'int id(int x) { return x; } int main(void) { int (*a[2])(int); a[0]=id; a[1]=id; '
    'int (**p)(int)=a; if(p+1!=&a[1] || p[1]!=id) return 1; return (*p)(42); }',
    'int id(int x) { return x; } int main(void) { if(!(_Bool)id || !id || !(id&&&id) || id!=&id) return 1; return 42; }',
    'int id(int x) { return x; } int ignore(int (int)) { return 42; } int main(void) { return ignore(id); }',
]

with tempfile.TemporaryDirectory(prefix='kcc function pointers ') as directory:
    directory = Path(directory)
    source, other, il, assembly, obj, executable, dirty = [directory / name for name in
                                                          ('k.c', 'h.c', 'p.ssa', 'p.s', 'h.o', 'p', 'dirty.s')]

    def compile_source(text):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
        return result.stdout

    def link_and_run(host_text=None, assembly_text=None):
        objects = [str(assembly)]
        if host_text is not None:
            other.write_text(host_text)
            subprocess.run([host, '-std=c2x', '-fsigned-char', '-c', str(other), '-o', str(obj)],
                           capture_output=True, check=True, timeout=10)
            objects.append(str(obj))
        if assembly_text is not None:
            dirty.write_text(assembly_text)
            objects.append(str(dirty))
        subprocess.run([host, *objects, '-o', str(executable)], check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, host_text

    for index, text in enumerate(programs):
        result = compile_source(text)
        if index < len(integers):
            assert 'call %t' in result, result
        if qbe:
            link_and_run()
        result = subprocess.run([host, '-std=c2x', '-fsigned-char', str(source), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (text, result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    for name in integers:
        identity = f'{name} identity({name} x) {{ return x; }}\n'
        apply = f'{name} apply({name} callback({name}),{name} x) {{ return callback(x); }}\n'
        prototype = f'{name} identity({name}); {name} apply({name} (*)({name}),{name});\n'
        driver = prototype + f'int main(void) {{ if(apply(identity,7)!=({name})7) return 1; return 42; }}\n'
        factory = identity + f'{name} (*factory(void))({name}) {{ return identity; }}\n'
        factory_driver = (f'{name} (*factory(void))({name}); int main(void) '
                          f'{{ if(factory()(7)!=({name})7) return 1; return 42; }}\n')
        relay = f'{name} (*factory(void))({name}); int relay({name} x) {{ return factory()(x)==({name})7; }}\n'
        relay_driver = f'int relay({name}); int main(void) {{ if(!relay(7)) return 1; return 42; }}\n'
        for text, host_text in [(apply, identity + driver), (identity, apply + driver),
                                (factory, factory_driver), (relay, factory + relay_driver)]:
            compile_source(text)
            if qbe:
                link_and_run(host_text)

    signature = 'long long mixed(char a,short b,int c,long d,unsigned e,int *f,long long g,long long h)'
    body = ' { return a+b+c+d+e+*f+g+h; }\n'
    relay = ('long long relay(long long callback(char,short,int,long,unsigned,int *,long long,long long)) '
             '{ int x=13; return callback(1,2,3,4294967296L,5,&x,7,4611686018427387904LL); }\n')
    driver = (signature + '; long long relay(long long (*)(char,short,int,long,unsigned,int *,long long,long long)); '
              'int main(void) { if(relay(mixed)!=4611686022722355231LL) return 1; return 42; }\n')
    for text, host_text in [(relay, signature + body + driver), (signature + body, relay + driver)]:
        compile_source(text)
        if qbe:
            link_and_run(host_text)

    compile_source('int cancel(int (*p)(int)) { return &*p==p; }')
    if qbe:
        link_and_run('int cancel(int (*)(int)); int id(int x) { return x; } '
                     'int main(void) { if(!cancel(0) || !cancel(id)) return 1; return 42; }')

    # ABI-defined low return bits, deliberately unspecified upper bits.
    names = [('signed char', 'signed_byte', '0x123400ff', '-1'),
             ('unsigned char', 'unsigned_byte', '0x123400ff', '255'),
             ('short', 'signed_half', '0x1234ffff', '-1'),
             ('unsigned short', 'unsigned_half', '0x1234ffff', '65535'),
             ('_Bool', 'boolean_one', '0x12340001', '1'),
             ('_Bool', 'boolean_zero', '0x12340000', '0')]
    text = ''.join(f'{name} {symbol}(void);\n' for name, symbol, _, _ in names) + 'int main(void) {\n'
    asm = '.text\n'
    for index, (name, symbol, value, expected) in enumerate(names):
        text += f'{name} (*p{index})(void)={symbol}; if(p{index}()!={expected}) return 1;\n'
        asm += f'.globl {symbol}\n{symbol}:\n movl ${value}, %eax\n ret\n'
    text += 'return 42; }'
    asm += '.section .note.GNU-stack,"",@progbits\n'
    compile_source(text)
    if qbe:
        link_and_run(assembly_text=asm)

    for calls, valid in [(126, True), (127, False)]:
        source.write_text('int id(int x) { return x; } int main(void) { return ' + 'id(' * calls + '42' + ')' * calls + '; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'typed expression exceeds depth limit (128)' in result.stderr, result.stderr

    rejected = [
        ('int f(int); int main(void) { int (*p)(long)=f; return 0; }', 'pointer conversion'),
        ('int f(int); int main(void) { int *p=&f; return 0; }', 'pointer conversion'),
        ('int f(int); int main(void) { int (*p)(int)=0; return 0; }', 'pointer conversion'),
        ('int f(int); int main(void) { return f<f; }', 'relational comparison requires object pointers'),
        ('int f(int); int main(void) { return f+0==f; }', 'complete object referent'),
        ('int f(int); int main(void) { return f-f; }', 'complete object referents'),
        ('int f(int); int main(void) { return f[0](1); }', 'complete object referent'),
        ('int f(int); int main(void) { return f(); }', 'argument count'),
        ('int main(void) { int (*p)(int); return p(); }', 'argument count'),
        ('int f(int); int main(void) { return f; }', 'pointer conversion'),
        ('int f(int); int main(void) { f=3; return 0; }', 'modifiable lvalue'),
        ('int main(void) { int x=0; return x(); }', 'not a function pointer'),
        ('int main(void) { return absent(); }', 'call to undeclared function'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Function pointers passed ({len(programs)} full-value programs, concrete designator/decay and once-only targets, '
      f'both-direction callbacks/factories and mixed stack ABI, dirty narrow returns and typed-depth constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
