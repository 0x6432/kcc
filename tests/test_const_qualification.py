"""Const syntax, immutable caches, safe qualification and target ABI regressions."""
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
    programs.append(f"int main(void) {{ const {name} x=7; {name} y=x; const {name} *p=&x; if(y!=({name})7 || *p!=y) return 1; return 42; }}")
qualified_integer_prototype = 'const int id(const int x); int id(int x) { return x; } int main(void) { return id(42); }'
qualified_integer_definition = 'int id(int); const int id(const int x) { return x; } int main(void) { int (*p)(int)=id; return p(42); }'
qualified_pointer_prototype = 'int *const id(int *const p); int *id(int *p) { return p; } int main(void) { int x=42; return *id(&x); }'
programs += [
    'int main(void) { unsigned const long const long x=4611686018427387904ULL; if(x!=4611686018427387904ULL) return 1; return 42; }',
    qualified_integer_prototype,
    qualified_integer_definition,
    qualified_pointer_prototype,
    'int main(void) { int x=41; const int *p=&x; *(int *)p=42; return x; }',
    'int main(void) { int x=42; const void *p=&x; const int *q=p; return *q; }',
    'int main(void) { const int x=42; const int *p=&x; const void *v=p; if(v!=p || p!=v) return 1; return *p; }',
    'int main(void) { int x=41,*p=&x; int *const *q=&p; **q=42; return x; }',
    'int main(void) { int x=42,*p=&x; const void *v=&p; int *const *q=v; return **q; }',
    'int main(void) { int a[3]; a[1]=42; int *p=a; const int *q=a+1; if(!(p<q) || !(q>p) || q-p!=1 || p-q!=-1) return 1; return *q; }',
    'int main(void) { int a[2][3]; a[1][2]=42; const int (*p)[3]=a; if(p+1-a!=1 || a!=p || p!=a) return 1; return p[1][2]; }',
    'int read(const int a[][3]) { return a[1][2]; } int main(void) { int a[2][3]; a[1][2]=42; return read(a); }',
    'int main(void) { const int a[2][3]; const int (*p)[2][3]=&a; const void *v=&a; if(p!=v) return 1; return 42; }',
    'int id(int x) { return x; } int main(void) { int (*const p)(int)=id; return p(42); }',
    'int apply(int (*const p)(const int),const int x) { return p(x); } int id(int x) { return x; } int main(void) { return apply(id,42); }',
    'const int (*id(const int (*p)[]))[]; const int (*id(const int (*p)[3]))[3] { return p; } int main(void) { int a[3]; a[2]=42; return (*id(&a))[2]; }',
    'int main(void) { int x=42; const int *p=&x; if((const int *const)p!=p) return 1; return (const int)x; }',
    'int main(void) { int n=0,x=42; const int *p=(n=1,&x); if(n!=1) return 1; return ((const void)(n=2),*p); }',
    'int main(void) { const char *p="*"; return *p; }',
    '#define READONLY const\n#define PTR(T) T *const\nint main(void) { READONLY int x=42; PTR(READONLY int) p=&x; return *p; }',
    'int main(void) { int x=41,*p=&x; int *const a[1]; const void *v=a; if(v!=&a) return 1; *p=42; return x; }',
    'int main(void) { int a[3]; a[1]=42; const int (*p)[]=&a; const int *q=*p; return q[1]; }',
    'const int *step(int **p) { int *r=*p; *p=*p+1; return r; } int main(void) { int a[2]; a[0]=42; int *p=a; if(step(&p)!=a || p!=a+1) return 1; return a[0]; }',
    'void *get(int *p,int *n) { *n=*n+1; return p; } int main(void) { int x=42,n=0; const int *p=&x; if(get(&x,&n)!=p || n!=1) return 1; return x; }',
    'const void done(void) { return; } int main(void) { done(); return 42; }',
    'int main(void) { for(const int x=42; x==42;) return x; return 1; }',
    'int main(void) { const int x=13,y=x+29; const int *p=&x,*q=&y; return *p+*q-13; }',
]
# C23 6.7.6.3p4 drops top-level return qualifiers. Clang 15 still treats
# these exact redeclarations as conflicting. Always execute the original kcc
# program; count a native diagnostic gap instead of fabricating host agreement.
return_qualifier_gap_cases = {qualified_integer_prototype, qualified_integer_definition, qualified_pointer_prototype}
legacy_host_gaps = 0
with tempfile.TemporaryDirectory(prefix='kcc const qualification ') as directory:
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
        if result.returncode != 0:
            assert text in return_qualifier_gap_cases and "conflicting types for 'id'" in result.stderr, (text, result.stderr)
            legacy_host_gaps += 1
            continue
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    abi_values = ['7', '-1', '-1', '255', '-32768', '65535', '-2147483647',
                  '4294967295U', '-4611686018427387904L', '9223372036854775808UL',
                  '-4611686018427387904LL', '18446744073709551615ULL']
    for name, value in zip(integers, abi_values):
        helper_text = f'{name} id(const {name} x) {{ return x; }}\n'
        relay = f'{name} id({name}); {name} relay(const {name} x) {{ return id(x); }}\n'
        driver = f'{name} id({name}); {name} relay({name}); int main(void) {{ if(relay({value})!=({name})({value})) return 1; return 42; }}'
        for kcc_text, host_text in [(helper_text, relay+driver), (relay, helper_text+driver)]:
            compile_source(kcc_text)
            if qbe:
                link_and_run(host_text)
        pointer_helper = f'const {name} *id(const {name} *const x) {{ return x; }}\n'
        pointer_relay = f'const {name} *id(const {name} *); const {name} *relay(const {name} *const p) {{ return id(p); }}\n'
        pointer_driver = f'const {name} *id(const {name} *); const {name} *relay(const {name} *); int main(void) {{ const {name} x=7; if(relay(&x)!=&x || *relay(&x)!=({name})7) return 1; return 42; }}'
        for kcc_text, host_text in [(pointer_helper, pointer_relay+pointer_driver), (pointer_relay, pointer_helper+pointer_driver)]:
            compile_source(kcc_text)
            if qbe:
                link_and_run(host_text)

    helper_text = ('long long id(const int *const a,const int *b,const int *c,const int *d,const int *e,const int *f,'
                   'const int *g,const long long tail) { return *a+*b+*c+*d+*e+*f+*g+tail; }')
    relay = ('long long id(const int *,const int *,const int *,const int *,const int *,const int *,const int *,long long);'
             'long long relay(const int *a,const int *b,const int *c,const int *d,const int *e,const int *f,const int *g,long long t)'
             ' { return id(a,b,c,d,e,f,g,t); }')
    driver = ('long long relay(const int *,const int *,const int *,const int *,const int *,const int *,const int *,long long);'
              'int main(void) { int a=1,b=2,c=3,d=4,e=5,f=6,g=7;'
              ' if(relay(&a,&b,&c,&d,&e,&f,&g,4611686018427387904LL)!=4611686018427387932LL) return 1; return 42; }')
    for kcc_text, host_text in [(helper_text, relay+driver), (relay, helper_text+driver)]:
        compile_source(kcc_text)
        if qbe:
            link_and_run(host_text)

    # Function parameter locals retain const while the signature ignores only
    # top-level qualification. Pointee const remains part of the callback type.
    callback = ('const int *call(const int *(*const fn)(const int *),const int *const p) { return fn(p); }')
    identity = 'const int *id(const int *p) { return p; }'
    driver = ('const int *call(const int *(*)(const int *),const int *); const int *id(const int *);'
              'int main(void) { const int x=42; if(call(id,&x)!=&x || *call(id,&x)!=42) return 1; return 42; }')
    for kcc_text, host_text in [(callback, identity+driver), (identity, callback+driver)]:
        compile_source(kcc_text)
        if qbe:
            link_and_run(host_text)

    # Nulls enter from a native C driver, not unsupported integer-null syntax.
    restore = 'const int *restore(const void *p) { return p; }'
    relay = 'const int *restore(const void *); const int *relay(const void *p) { return restore(p); }'
    driver = ('const int *relay(const void *); int main(void) { if(relay((const void *)0)!=(const int *)0) return 1; return 42; }')
    for kcc_text, host_text in [(restore, relay+driver), (relay, restore+driver)]:
        compile_source(kcc_text)
        if qbe:
            link_and_run(host_text)

    # Top-level const in an abstract cast is not an extra typed expression edge.
    for casts, valid in [(126, True), (127, False)]:
        source.write_text('int f(const int x) { return ' + '(const int)' * casts + 'x; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth limit (128)' in result.stderr, result.stderr
    # Qualifier conversion adds a real checked expression edge, unlike syntax wrappers.
    for casts, valid in [(124, True), (125, False)]:
        source.write_text('int f(int *p,const int *q) { return ' + '(int *)'*casts + 'p==q; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth limit (128)' in result.stderr, result.stderr
    for casts, valid in [(125, True), (126, False)]:
        source.write_text('const int *f(int *p) { return ' + '(int *)'*casts + 'p; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth limit (128)' in result.stderr, result.stderr
    for stars, valid in [(64, True), (65, False)]:
        source.write_text('int f(void) { int ' + '*const '*stars + 'p; return 42; }')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'pointer type exceeds depth limit (64)' in result.stderr, result.stderr
    compile_source('int f(void) { const ' + 'const '*1024 + 'int x=42; return x; }')
    invalid = [
        'int f(void) { const int x=1; x=2; return x; }',
        'int f(const int x) { x=2; return x; }',
        'void f(int *const p,int *q) { p=q; }',
        'void f(const int *p) { *p=1; }',
        'void f(const int a[2]) { a[0]=1; }',
        'void f(const int a[][3]) { a[0][0]=1; }',
        'void f(void) { int x=1; int *const a[2]; a[0]=&x; }',
        'int *f(const int *p) { return p; }',
        'void *f(const int *p) { return p; }',
        'int *f(const void *p) { return p; }',
        'void f(const int *p) { int *q=p; }',
        'void f(const int *p,int *q) { q=p; }',
        'void g(int *); void f(const int *p) { g(p); }',
        'const int **f(int **p) { return p; }',
        'int **f(int *const *p) { return p; }',
        'void f(int **p,const int **q) { p=q; }',
        'int f(int **p,const int **q) { return p==q; }',
        'int f(int **p,const int **q) { return p-q; }',
        'int f(const void *p,int *q) { return p<q; }',
        'long f(const void *p,void *q) { return p-q; }',
        'int f(const void);',
        'int f(void const);',
        'int f(const void x);',
        'int f(const int *); int f(int *);',
        'int f(int (*p)(const int *)); int f(int (*p)(int *));',
        'int f(void) { const x=1; return x; }',
        'int f(void) { const const x=1; return x; }',
        'int f(void) { void const int *p; return 0; }',
        'int f(void) { int const void *p; return 0; }',
        'int f(void) { const signed unsigned x=1; return x; }',
        'int f(void) { unsigned const _Bool x=1; return x; }',
        'int f(void) { const long long long x=1; return x; }',
        'int f(void) { const int int x=1; return x; }',
        'int f(void) { const void x; return 0; }',
        'int f(void) { const void x[2]; return 0; }',
        'int f(int a[const 3]);',
        'int f(int a[static 3]);',
        'int f(void) { volatile int x=1; return x; }',
        'int f(void) { int *restrict p; return 0; }',
        'int f(int (*p)(int)) { int (*const q)(int)=p; q=p; return 0; }',
    ]
    for text in invalid:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr, (text, result.stderr)
print(f'Const qualification passed ({len(programs)} full-value programs, 48 primitive/object ABI arrangements, '
      f'mixed stack/callback/null ABI, qualified arrays/functions/void, once-only effects, exact type/depth and {len(invalid)} constraints; '
      f'{len(programs)-legacy_host_gaps} native runtime agreements, {legacy_host_gaps} exact C23 return-qualifier gaps; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
