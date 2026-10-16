"""Pointer scaling/ordering on live scalar objects and host-created arrays.

No unrelated subtraction/order, out-of-bounds arithmetic or one-past load is
executed. Large word extension is checked in IL, not by fabricating huge arrays.
"""
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
referents = integers + ['int *']
programs = []
for name in integers:
    programs.append(f'''int main(void) {{ {name} x=1; {name} *p=&x;
 {name} *q=1+p; if(q-p!=1L || p-q!=-1L) return 1;
 if(!(p<q) || !(p<=q) || !(q>p) || !(q>=p) || p>=q || q<=p) return 2;
 if(p+0!=p || 0+p!=p || q-1!=p || p-(-1)!=q) return 3;
 *(q-1)=1; if(*p!=1 || !(p<=p) || !(p>=p)) return 4;
 return 42; }}''')
programs += [
    'int main(void) { int x=1; int *p=&x; int **q=&p; int **r=q+1; '
    'if(r-q!=1 || q-r!=-1 || *(r-1)!=&x) return 1; return 42; }',
    'int *get(int *p,int *n) { *n=*n+1; return p; } '
    'int index(int *n) { *n=*n+1; return 1; } '
    'int main(void) { int x=42; int a=0; int b=0; int *p=get(&x,&a)+index(&b); '
    'if(a!=1 || b!=1 || p-&x!=1) return 1; '
    'p=index(&b)+get(&x,&a); if(a!=2 || b!=2 || p-&x!=1) return 2; '
    'if(get(&x,&a)-p!=-1 || a!=3) return 3; '
    '0 && get(&x,&a)+index(&b); 1 || get(&x,&a)-p; '
    'if(a!=3 || b!=2) return 4; return 42; }',
]

with tempfile.TemporaryDirectory(prefix='kcc pointer arithmetic ') as directory:
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
        subprocess.run([host, '-std=c2x', '-fsigned-char', str(source), '-o', str(executable)],
                       capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    # Each referent gets all twelve integer index types, both arithmetic orders,
    # subtraction, negative signed indices and signed same-array differences.
    # Separate objects exercise both kcc->host and host->kcc call boundaries.
    for name in referents:
        signatures, definitions, checks = [], [], []
        for i, index_type in enumerate(integers):
            for operation, body in [('add', 'p+n'), ('reverse', 'n+p'), ('sub', 'p-n')]:
                signature = f'{name} *{operation}_{i}({name} *p,{index_type} n)'
                signatures.append(signature + ';\n')
                definitions.append(signature + ' { return ' + body + '; }\n')
                value = 1 if index_type == '_Bool' else 3
                if operation == 'sub':
                    checks.append(f'if({operation}_{i}(p+4,{value})!=p+{4-value}) return 1;')
                else:
                    checks.append(f'if({operation}_{i}(p+1,{value})!=p+{1+value}) return 2;')
                if index_type != '_Bool' and not index_type.startswith('unsigned'):
                    expected = 7 if operation == 'sub' else 1
                    checks.append(f'if({operation}_{i}(p+4,-3)!=p+{expected}) return 3;')
        signatures += [f'long distance({name} *p,{name} *q);\n',
                       f'int order({name} *p,{name} *q);\n']
        definitions += [f'long distance({name} *p,{name} *q) {{ return p-q; }}\n',
                        f'int order({name} *p,{name} *q) {{ return (p<q)+2*(p<=q)+4*(p>q)+8*(p>=q)+16*(p==q)+32*(p!=q); }}\n']
        checks += ['if(distance(p,end)!=-9L || distance(end,p)!=9L) return 4;',
                   'if(distance(p,p)!=0L || order(p,end)!=35 || order(end,p)!=44 || order(p,p)!=26) return 5;',
                   'if(end-9!=p || p+9!=end || end-0!=end) return 6;']
        prototypes = ''.join(signatures)
        helpers = ''.join(definitions)
        relay = f'int relay({name} *p,{name} *end) {{ ' + '\n'.join(checks) + ' return 42; }\n'
        driver = f'int relay({name} *,{name} *); int main(void) {{ {name} a[9]={{0}}; return relay(a,a+9); }}\n'
        for text, host_text in [(helpers, prototypes + relay + driver),
                                (prototypes + relay, helpers + driver)]:
            compile_source(text)
            if qbe:
                link_and_run(host_text)
        # Independent host reference runs the exact same helper/relay checks.
        other.write_text(helpers + relay + driver)
        subprocess.run([host, '-std=c2x', '-fsigned-char', str(other), '-o', str(executable)],
                       capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, name

    for index_type, instruction in [('int', 'extsw'), ('unsigned', 'extuw'),
                                    ('short', 'extsw'), ('unsigned short', 'extsw')]:
        result = compile_source(f'int *f(int *p,{index_type} n) {{ return p+n; }}')
        assert f'=l {instruction} ' in result, (index_type, result)
        assert ('=l extuw ' in result) == (index_type == 'unsigned'), result
    for index_type in ['long', 'unsigned long', 'long long', 'unsigned long long']:
        result = compile_source(f'int *f(int *p,{index_type} n) {{ return p+n; }}')
        assert '=l extsw ' not in result and '=l extuw ' not in result, result

    # Every lowering/promotion counts against typed depth. Parsing alone permits
    # these expressions; the boundary depends on the explicit index promotion.
    for count, valid in [(124, True), (125, False)]:
        text = 'int *f(int *p,unsigned short n) { return p+(' + '+ ' * count + 'n); }'
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr

    rejected = [
        ('int *f(int *p,int *q) { return p+q; }', 'pointer offset'),
        ('int *f(int *p) { return 1-p; }', 'pointer offset'),
        ('long f(int *p,unsigned *q) { return p-q; }', 'compatible pointer'),
        ('int f(char *p,signed char *q) { return p<q; }', 'compatible pointer'),
        ('int f(int *p,int **q) { return p>=q; }', 'compatible pointer'),
        ('int f(int *p) { return p<0; }', 'compatible pointers'),
        ('int *f(int *p) { return p+1.0; }', ''),
        ('int main(void) { int x=0; (&x+1)=&x; return 0; }', 'modifiable lvalue'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Pointer arithmetic passed ({len(programs)} full-value programs, {len(referents)} referents x all integer indices, '
      f'both-direction array ABI, signed differences/ordering, once-only and depth checks; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
