"""Explicit pointer casts preserve addresses, representation and original function ABI."""
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
    expected_byte = 1 if name == '_Bool' else 7
    programs.append(f'''int main(void) {{ {name} x=7; {name} *p=&x; unsigned char *b=(unsigned char *)p;
 {name} *q=({name} *)b; if(q!=p || *q!=({name})7 || b[0]!={expected_byte}) return 1;
 return 42; }}''')
for name in integers:
    programs.append(f'''{name} id({name} x) {{ return x; }}
int main(void) {{ {name} (*p)({name})=id; void (*other)(void)=(void (*)(void))p;
 {name} (*q)({name})=({name} (*)({name}))other; if(q!=p || q(7)!=({name})7) return 1;
 return 42; }}''')
programs += [
 'int main(void) { unsigned x=0; unsigned char *p=(unsigned char *)&x; p[0]=42; '
 'if(x!=42 || p[1]!=0 || p[2]!=0 || p[3]!=0) return 1; return 42; }',
 'int main(void) { int a[2][3]; a[1][2]=42; unsigned char *p=(unsigned char *)&a; '
 'int (*q)[2][3]=(int (*)[2][3])p; return (*q)[1][2]; }',
 'int main(void) { int a[3]; a[2]=42; int (*p)[]= &a; unsigned char *b=(unsigned char *)p; '
 'int (*q)[]=(int (*)[])b; return (*q)[2]; }',
 'int main(void) { int x=42,*p=&x; void **v=(void **)&p; int **q=(int **)v; return **q; }',
 'int id(int x) { return x; } int main(void) { int (*p)(int)=id; int **v=(int **)&p; '
 'int (**q)(int)=(int (**)(int))v; return (*q)(42); }',
 'int *get(int *p,int *n) { *n=*n+1; return p; } int main(void) { int x=42,n=0; '
 'unsigned char *b=(unsigned char *)get(&x,&n); int *q=(int *)b; if(n!=1) return 1; return *q; }',
 'void set(int *p) { *p=42; } int main(void) { void (*p)(int *)=set; '
 'int (*v)(long,long)=(int (*)(long,long))p; void (*q)(int *)=(void (*)(int *))v; int x=0; q(&x); return x; }',
]
with tempfile.TemporaryDirectory(prefix='kcc explicit pointer casts ') as directory:
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


    for text in programs:
        compile_source(text)
        if qbe:
            link_and_run()
        result = subprocess.run([host, '-std=c2x', '-fsigned-char', str(source), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (text, result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    for name in integers:
        bytes_function = f'unsigned char *bytes({name} *p) {{ return (unsigned char *)p; }}\n'
        restore = f'{name} *restore(unsigned char *p) {{ return ({name} *)p; }}\n'
        prototypes = f'unsigned char *bytes({name} *); {name} *restore(unsigned char *);\n'
        driver = prototypes + f'int main(void) {{ {name} x=7; {name} *p=restore(bytes(&x)); if(p!=&x || *p!=({name})7) return 1; return 42; }}'
        identity = f'{name} id({name} x) {{ return x; }}\n'
        relay = f'{name} relay(void (*p)(void),{name} x) {{ return (({name} (*)({name}))p)(x); }}\n'
        relay_driver = f'{name} id({name}); {name} relay(void (*)(void),{name}); int main(void) {{ if(relay((void (*)(void))id,7)!=({name})7) return 1; return 42; }}'
        for kcc_text, host_text in [(bytes_function+restore, driver),
                                    (prototypes + f'int relay({name} *p) {{ return restore(bytes(p))==p; }}',
                                     bytes_function+restore+f'int relay({name} *); int main(void) {{ {name} x=0; if(!relay(&x)) return 1; return 42; }}'),
                                    (relay, identity+relay_driver), (identity, relay+relay_driver)]:
            compile_source(kcc_text)
            if qbe:
                link_and_run(host_text)

    compile_source('int object_cancel(int *p) { return (int *)(unsigned char *)p==p; } '
                   'int function_cancel(int (*p)(int)) { return (int (*)(int))(void (*)(void))p==p; }')
    if qbe:
        link_and_run('int object_cancel(int *); int function_cancel(int (*)(int)); int id(int x) { return x; } '
                     'int main(void) { int x=42; if(!object_cancel(0)||!object_cancel(&x)||!function_cancel(0)||!function_cancel(id)) return 1; return 42; }')

    signature = 'long long mixed(char a,short b,int c,long d,unsigned e,int *f,long long g,long long h)'
    helper = signature + ' { return a+b+c+d+e+*f+g+h; }'
    relay = ('long long relay(void (*p)(void)) { int x=13; return '
             '((long long (*)(char,short,int,long,unsigned,int *,long long,long long))p)'
             '(1,2,3,4294967296L,5,&x,7,4611686018427387904LL); }')
    driver = (signature + '; long long relay(void (*)(void)); int main(void) {'
              ' if(relay((void (*)(void))mixed)!=4611686022722355231LL) return 1; return 42; }')
    for kcc_text, host_text in [(relay, helper+driver), (helper, relay+driver)]:
        compile_source(kcc_text)
        if qbe:
            link_and_run(host_text)

    for casts, valid in [(126, True), (127, False)]:
        source.write_text('int *f(int *p) { return ' + '(int *)' * casts + 'p; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth limit (128)' in result.stderr, result.stderr

    invalid = [
      'unsigned char *f(int *p) { return p; }', 'int *f(unsigned char *p) { return p; }',
      'int **f(void **p) { return p; }', 'void **f(int **p) { return p; }',
      'void f(int *p) { unsigned char *q=p; }', 'void f(int *p,unsigned char *q) { p=q; }',
      'void f(unsigned char *); void g(int *p) { f(p); }',
      'int f(int *p,unsigned char *q) { return p==q; }',
      'void *f(int (*p)(void)) { return (void *)p; }', 'int (*f(void *p))(void) { return (int (*)(void))p; }',
      'int *f(int (*p)(void)) { return (int *)p; }', 'int (*f(int *p))(void) { return (int (*)(void))p; }',
      'int (*f(void (*p)(void)))(int) { return p; }',
      'void f(int (*p)(int)) { void (*q)(void)=p; }',
      'int f(int *); int f(unsigned char *);', 'int f(void); long f(void);',
      'int *f(void) { return (int *)0; }', 'int f(int *p) { return (int)p; }',
      'int f(void *p) { return *(int [3])p; }', 'int f(void *p) { return (int (int))p; }',
      'int f(void *p) { return *(void *)p; }',
    ]
    for text in invalid:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr, (text, result.stderr)
print(f'Explicit pointer casts passed ({len(programs)} full-value programs, byte representation and original-signature round trips, '
      f'both host ABI directions, mixed callbacks, null/effect and exact depth checks, {len(invalid)} constraints; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
