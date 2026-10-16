"""Postfix pointer subscripts share arithmetic and object-lvalue semantics."""
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
    value = 1 if name == '_Bool' else 7
    programs.append(f'''int main(void) {{ {name} x=0; {name} *p=&x;
 if((p[0]={value})!={value} || 0[p]!={value} || x!={value}) return 1;
 if(&p[0]!=p || &0[p]!=p || &p[1]!=p+1 || &1[p]!=1+p) return 2;
 if((&x)[0]!={value} || (p+1)[-1]!={value}) return 3;
 p<:0:>=1; if(p[0]!=1) return 4; return 42; }}''')
programs += [
    'int main(void) { int x=42; int *p=&x; int **q=&p; '
    'if(q[0][0]!=42 || 0[0[q]]!=42 || &q[0][0]!=&x) return 1; return 42; }',
    'int *get(int *p,int *n) { *n=*n+1; return p; } '
    'int index(int *n) { *n=*n+1; return 0; } '
    'int main(void) { int x=0; int a=0; int b=0; '
    'get(&x,&a)[index(&b)]=7; if(a!=1 || b!=1 || x!=7) return 1; '
    'if(&get(&x,&a)[index(&b)+1]!=&x+1 || a!=2 || b!=2) return 2; '
    '0 && get(&x,&a)[index(&b)]; 1 || get(&x,&a)[index(&b)]; '
    'if(a!=2 || b!=2) return 3; return 42; }',
    '#define AT(p,i) p<:i:>\nint main(void) { int x=42; return AT((&x),0); }',
]

with tempfile.TemporaryDirectory(prefix='kcc pointer subscripts ') as directory:
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

    for name in referents:
        signatures, definitions, checks = [], [], []
        for i, index_type in enumerate(integers):
            signature = f'{name} read_{i}({name} *p,{index_type} n)'
            signatures.append(signature + ';\n')
            definitions.append(signature + ' { return n[p]; }\n')
            signature = f'{name} write_{i}({name} *p,{index_type} n,{name} value)'
            signatures.append(signature + ';\n')
            definitions.append(signature + ' { return p[n]=value; }\n')
            index = 1 if index_type == '_Bool' else 3
            checks += [f'if(read_{i}(p,{index})!=p[{index}]) return 1;',
                       f'if(write_{i}(p,{index},value)!=value || p[{index}]!=value) return 2;']
            if index_type != '_Bool' and not index_type.startswith('unsigned'):
                checks += [f'if(read_{i}(p+4,-3)!=p[1]) return 3;',
                           f'if(write_{i}(p+4,-3,value)!=value || p[1]!=value) return 4;']
        prototypes = ''.join(signatures)
        helpers = ''.join(definitions)
        relay = f'int relay({name} *p,{name} value) {{ ' + '\n'.join(checks) + ' return 42; }\n'
        initialization = (f'{name} a[9]={{1,1,1,1,1,1,1,1,1}}; {name} value=1;'
                          if name != 'int *' else
                          'int x=1; int *a[9]={&x,&x,&x,&x,&x,&x,&x,&x,&x}; int *value=&x;')
        driver = f'int relay({name} *,{name}); int main(void) {{ {initialization} return relay(a,value); }}\n'
        for text, host_text in [(helpers, prototypes + relay + driver),
                                (prototypes + relay, helpers + driver)]:
            compile_source(text)
            if qbe:
                link_and_run(host_text)
        other.write_text(helpers + relay + driver)
        subprocess.run([host, '-std=c2x', '-fsigned-char', str(other), '-o', str(executable)],
                       capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, name

    helper = 'int chain(int **r) { r[1][2]=40; return r[1][2]+r[0][0]; }\n'
    relay = 'int chain(int **); int relay(int **r) { return chain(r); }\n'
    driver = ('int relay(int **); int chain(int **); int main(void) { '
              'int a[3]={2,3,4}; int b[3]={5,6,7}; int *r[2]={a,b}; '
              'int value=relay(r); if(b[2]!=40) return 1; return value; }\n')
    for text, host_text in [(helper, relay + driver), (relay, helper + driver)]:
        compile_source(text)
        if qbe:
            link_and_run(host_text)

    for depth, valid in [(42, True), (43, False)]:
        text = 'int f(int ' + '*' * depth + 'p) { return p' + '[0]' * depth + '; }'
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr
        elif qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
    # These nested indices exercise the parser's recursive nesting budget too;
    # invalid/depth-limited sources are compiled only, never executed.
    source.write_text('int f(int *p) { return ' + 'p[' * 130 + '0' + ']' * 130 + '; }')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and not result.stdout and 'nesting' in result.stderr, result.stderr

    rejected = [
        ('int f(int *p) { return p[p]; }', 'one pointer and one integer'),
        ('int f(void) { return 1[2]; }', 'one pointer and one integer'),
        ('int f(int *p) { return p[0; }', "expected ']'"),
        ('int f(int *p) { return p[0,]; }', 'expected integer literal'),
        ('int f(int *p) { return p[]; }', 'expected integer literal'),
        ('int f(int *p) { return p[0](); }', 'not a function pointer'),
        ('int f(int *p) { return p[1.0]; }', ''),
        ('int main(void) { int a[]; return 0; }', ''),
        ('int main(void) { int x=0; (&x)[0][0]=1; return 0; }', 'one pointer and one integer'),
    ]
    for text, message in rejected:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)
print(f'Pointer subscripts passed ({len(programs)} full-value programs, {len(referents)} referents x all integer indices, '
      f'both-direction read/write/chained ABI, postfix/digraph/once-only/depth checks; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
