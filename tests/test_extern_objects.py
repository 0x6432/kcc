"""Declaration-only extern scalars backed by initialized native-owned storage.

Run: [KCC=...] [HOST_CC=...] [QBE=...] python3 tests/test_extern_objects.py
The native oracle compiles the unchanged kcc translation unit separately from
its owner. Only defined curated pairs execute; constraints, subset refusals and
generated resource boundaries compile only. No build outputs are modified.
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root/'build'/'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short', 'unsigned short',
            'int', 'unsigned', 'long', 'unsigned long', 'long long', 'unsigned long long']
values = ['1', '-7', '-7', '255', '-1234', '65535', '-1234567', '4294967295U',
          '4294967296L', '18446744073709551615UL', '4611686018427387904LL',
          '18446744073709551615ULL']
# name, unchanged kcc TU, native storage owner, keywords needed by each TU
pairs = []


def pair(name, text, owner, features=(), owner_features=()):
    pairs.append((name, text, owner, features, owner_features))


# Twenty-four genuine both-direction full-width object-reference arrangements.
# The native driver checks both values and the exact address of its own object.
for typ, value in zip(integers, values):
    pair(typ+' kcc driver',
         f'extern {typ} cell; extern int verify(void); int main(void) {{ '
         f'if(cell!=({typ}){value}) return 1; {typ} *p=&cell; *p=({typ})0; '
         f'if(cell!=0) return 2; cell=({typ}){value}; return verify(); }}',
         f'{typ} cell={value}; int verify(void) {{ return cell==({typ}){value}?42:1; }}')
    pair(typ+' native driver',
         f'extern {typ} cell; {typ} get(void) {{ return cell; }} '
         f'void put({typ} x) {{ cell=x; }} {typ} *slot(void) {{ return &cell; }}',
         f'{typ} cell=0; {typ} get(void); void put({typ}); {typ} *slot(void); '
         f'int main(void) {{ if(slot()!=&cell || get()!=0) return 1; '
         f'put(({typ}){value}); if(cell!=({typ}){value} || get()!=cell) return 2; '
         f'*slot()=0; return get()==0?42:3; }}')

pair('integer lvalue updates',
     'extern int x; int main(void) { if(x++!=38 || ++x!=40) return 1; '
     'if(x--!=40 || --x!=38) return 2; x+=6; x-=2; x*=2; x/=2; '
     'x%=43; x^=3; x^=3; x|=0; x&=63; x<<=1; x>>=1; return x; }',
     'int x=38;')
pair('boolean update truth conversion',
     'extern _Bool flag; int main(void) { if(flag++!=1 || !flag) return 1; '
     'flag=0; if(++flag!=1) return 2; return flag?42:3; }', '_Bool flag=1;')
pair('object pointer updates within one array',
     'extern int *p; int main(void) { if(*p++!=10 || *p!=20) return 1; '
     'if(*++p!=42 || *p--!=42 || *--p!=10) return 2; p+=2; p-=1; '
     '*p=42; return *p; }', 'int items[3]={10,20,42}; int *p=&items[0];')
pair('pointer slot native driver',
     'extern int *p; int **slot(void) { return &p; } '
     'void set(int *x) { p=x; } int get(void) { return *p; }',
     'int first=7,second=42; int *p=&first; int **slot(void); void set(int *); '
     'int get(void); int main(void) { if(slot()!=&p || get()!=7) return 1; '
     'set(&second); return p==&second && get()==42?42:2; }')
pair('void pointer and qualified pointee',
     'extern void *vp; extern const int *cp; int main(void) { '
     'const int *p=vp; if(p!=cp || *cp!=42) return 1; vp=0; return !vp?42:2; }',
     'const int answer=42; void *vp=(void *)&answer; const int *cp=&answer;')
pair('const object and const pointer reads',
     'extern const int x; extern int *const p; int main(void) { '
     'const int *q=&x; *p=40; return *q+*p; }',
     'const int x=2; int value=0; int *const p=&value;')
pair('callback object is an indirect callee',
     'extern int (*fp)(int); extern int second(int); int main(void) { '
     'if(fp(40)!=41 || (*fp)(40)!=41 || (&*fp)(40)!=41) return 1; '
     'int (**slot)(int)=&fp; *slot=second; return fp(40); }',
     'int first(int x) { return x+1; } int second(int x) { return x+2; } '
     'int (*fp)(int)=first;')
pair('callback slot native driver',
     'extern int (*fp)(int); int call(int x) { return fp(x); } '
     'int (**slot(void))(int) { return &fp; }',
     'int first(int x) { return x+1; } int second(int x) { return x+2; } '
     'int (*fp)(int)=first; int call(int); int (**slot(void))(int); '
     'int main(void) { if(slot()!=&fp || call(40)!=41) return 1; '
     '*slot()=second; return call(40); }')
pair('row pointer composite',
     'extern int (*row)[]; extern int (*row)[3]; extern int (*row)[]; '
     'int main(void) { if(sizeof *row!=12) return 1; (*row)[1]+=2; return (*row)[1]; }',
     'int items[3]={1,40,3}; int (*row)[3]=&items;')
pair('local parameter typedef and for shadows restore',
     'extern int x; int param(int x) { return x; } int main(void) { '
     'int *saved=&x; { int x=2; { int x=3; if(x!=3) return 1; } '
     'if(x!=2) return 2; } { typedef long x; x v=2; if(sizeof v!=8) return 3; } '
     'for(int x=0;x<2;x++) { if(x>1) return 4; } '
     'return saved==&x?param(x):5; }', 'int x=42;')
pair('inner initializer captures still-visible outer object',
     'extern int x; int main(void) { { int y=x,x=2; if(y!=42 || x!=2) return 1; } '
     'return x; }', 'int x=42;')
pair('prototype scopes do not hide outer object',
     'extern int x; extern int f(int x); extern int g(int (*cb)(int x)); '
     'int main(void) { return x; }', 'int x=42;')
pair('mixed direct function object and pointer list',
     'extern int x,f(int),*p,(*fp)(int); int main(void) { '
     'if(p!=&x || fp!=f) return 1; x=f(40); return fp(*p-2); }',
     'int x=0; int f(int x) { return x+2; } int *p=&x; int (*fp)(int)=f;')
pair('mixed alias function and pointer object list',
     'typedef int F(int); extern F f,*fp; int main(void) { return fp(f(38)); }',
     'int f(int x) { return x+2; } int (*fp)(int)=f;')
pair('one specifier base const list',
     'extern const int x,*p,y; int main(void) { '
     'if(x!=2 || y!=40) return 1; p=&y; return x+*p; }',
     'const int x=2,y=40; const int *p=&x;')
for position in range(5):
    specs = ['unsigned', 'long', 'long', 'const']
    specs.insert(position, 'extern')
    pair('extern specifier position '+str(position),
         ' '.join(specs)+' value; int main(void) { '
         'return value==18446744073709551615ULL?42:1; }',
         'const unsigned long long value=18446744073709551615ULL;')
pair('query selects object versus function',
     'int f(int); extern typeof(&f) fp; extern typeof(f) g; '
     'int main(void) { return fp(g(38)); }',
     'int f(int x) { return x+2; } int g(int x) { return x+2; } '
     'int (*fp)(int)=f;', ('typeof',))
pair('query-only private function does not gain runtime use',
     'static int private_fn(int); extern typeof(&private_fn) fp; '
     'int main(void) { return fp(40); }',
     'int real(int x) { return x+2; } int (*fp)(int)=real;', ('typeof',))
pair('earlier query and expression snapshots retain object identity',
     'extern int (*row)[]; typedef typeof(row) Saved; '
     'typeof(row) original(void) { return row; } '
     'extern int (*row)[3]; extern Saved other; '
     'int main(void) { Saved p=original(); if(p!=row || p!=other) return 1; '
     'if(sizeof *row!=12) return 2; return (*p)[2]; }',
     'int items[3]={0,0,42}; int (*row)[3]=&items; int (*other)[3]=&items;', ('typeof',))
pair('same-list query sees preceding member',
     'extern int x,f(typeof(x)); int main(void) { return f(x); }',
     'int x=40; int f(int x) { return x+2; }', ('typeof',))
pair('typeof local shadow restores extern meaning',
     'extern int x; int main(void) { { typeof(x) x=2; if(x!=2) return 1; } return x; }',
     'int x=42;', ('typeof',))
pair('nullptr object read write address conversion',
     'extern typeof(nullptr) n; int main(void) { typeof(nullptr) *p=&n; '
     'if(n!=nullptr || *p!=nullptr) return 1; n=nullptr; *p=nullptr; '
     'int *q=n; int (*f)(int)=n; return !q && !f && !n?42:2; }',
     'typeof(nullptr) n=nullptr;', ('typeof', 'nullptr'), ('typeof', 'nullptr'))
pair('nullptr native driver',
     'extern typeof(nullptr) n; typeof(nullptr) get(void) { return n; } '
     'typeof(nullptr) *slot(void) { return &n; } '
     'void set(typeof(nullptr) x) { n=x; }',
     'typeof(nullptr) n=nullptr; typeof(nullptr) get(void); '
     'typeof(nullptr) *slot(void); void set(typeof(nullptr)); '
     'int main(void) { if(slot()!=&n || get()!=nullptr) return 1; '
     'set(nullptr); return n==nullptr?42:2; }',
     ('typeof', 'nullptr'), ('typeof', 'nullptr'))

pair('void callback object',
     'extern void (*notify)(int *); int main(void) { int x=0; '
     'notify(&x); return x; }',
     'void set(int *p) { *p=42; } void (*notify)(int *)=set;')
pair('pointer-returning callback object',
     'extern int *(*choose)(int *,int *); int main(void) { int a=40,b=2; '
     'int *p=choose(&a,&b); if(p!=&a) return 1; *p+=b; return a; }',
     'int *first(int *a,int *b) { (void)b; return a; } '
     'int *(*choose)(int *,int *)=first;')
pair('later parameter query sees parameter rather than extern',
     'extern long x; int f(int x,typeof(x) y); '
     'int f(int x,typeof(x) y) { return sizeof y==4?x+y:1; } '
     'int main(void) { if(sizeof x!=8 || x!=42) return 1; return f(40,2); }',
     'long x=42;', ('typeof',))
pair('typeof_unqual removes const from external object query',
     'extern const long x; extern typeof_unqual(x) y; int main(void) { '
     'typeof_unqual(x) copy=x; long *p=&copy; *p+=2; y=copy; return y; }',
     'const long x=40; long y=0;', ('typeof_unqual',))

# Separate from the 24 simple object arrangements: eight independently checked
# integer-class parameters force six register arguments and two stack arguments
# under amd64 SysV. Both directions return every full-width primitive while
# observing and mutating initialized host-owned storage, without ABI adapters.
mixed_types = ['char', 'short', 'int', 'long', 'unsigned', 'long long', 'unsigned long long', 'int']
mixed_values = ['-7', '-1234', '-1234567', '4294967296L', '4294967295U',
                '4611686018427387904LL', '18446744073709551615ULL', '8']
names = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
params = ','.join(f'{typ} {name}' for typ, name in zip(mixed_types, names))
args = ','.join(mixed_values)
checks = 'if('+' || '.join(f'{name}!={value}' for name, value in zip(names, mixed_values))+') return 0;'
for typ, value in zip(integers, values):
    definition = (f'{typ} pick({params}) {{ {checks} if(cell!=0) return 0; '
                  f'cell=({typ}){value}; return cell; }}')
    driver = (f'int main(void) {{ if(cell!=0) return 1; '
              f'if(pick({args})!=({typ}){value}) return 2; '
              f'return cell==({typ}){value}?42:3; }}')
    pair(typ+' mixed-stack kcc callee',
         f'extern {typ} cell; '+definition,
         f'{typ} cell=0; {typ} pick({params}); '+driver)
    pair(typ+' mixed-stack kcc caller',
         f'extern {typ} cell; extern {typ} pick({params}); '+driver,
         f'{typ} cell=0; '+definition)

# Inferred declarations reserve their name before initialization. These are kcc
# compile-only visibility barriers, not required native constraint rejections;
# never execute the self-initialization or turn an outer object into a fallback.
unavailable_initializers = [
    'extern long x; int f(void) { auto x='+initializer+'; return 0; }'
    for initializer in ['x', 'sizeof x', '(typeof(x))0', 'sizeof(typeof(x))', '&x', '0?x:42']
]

# Native constraint oracle is compile-only. Legal-but-deferred forms are below,
# never mislabeled as native constraints (extern initializers define storage).
constraints = [
    ('extern int x; extern long x;', 'incompatible external object'),
    ('extern int x; extern const int x;', 'incompatible external object'),
    ('extern int *p; extern const int *p;', 'incompatible external object'),
    ('extern int *p; extern int *const p;', 'incompatible external object'),
    ('extern int (*p)[2]; extern int (*p)[3];', 'incompatible external object'),
    ('extern int (*fp)(int); extern int (*fp)(long);', 'incompatible external object'),
    ('extern int x; int x(void);', 'function name conflicts with external object'),
    ('int x(void); extern int x;', 'external object conflicts with prior ordinary'),
    ('typedef int x; extern int x;', 'external object conflicts with prior ordinary'),
    ('extern int x; typedef int x;', 'typedef name conflicts with prior ordinary'),
    ('extern int x,x(void);', 'function name conflicts with external object'),
    ('extern int x(void),x;', 'external object conflicts with prior ordinary'),
    ('extern const int x; int f(void) { x=42; return 0; }', 'modifiable lvalue'),
    ('extern const int x; int f(void) { ++x; return 0; }', 'modifiable'),
    ('extern const int x; int f(void) { x+=1; return 0; }', 'modifiable'),
    ('extern int *const p; int f(void) { p=0; return 0; }', 'modifiable lvalue'),
    ('extern const int *p; int f(void) { *p=42; return 0; }', 'modifiable lvalue'),
    ('extern int x; int f(void) { return x(); }', 'called expression'),
    ('int f(void) { return x; } extern int x;', 'undeclared'),
    ('extern const int x; _Static_assert(x,"not ICE");', 'constant expression'),
    ('extern int (*row)[]; int f(void) { return sizeof *row; } extern int (*row)[3];', 'complete object type'),
    ('extern int x; int f(void) { typedef int x; return x; }', 'typedef'),
    ('extern extern int x;', 'duplicate extern'),
    ('extern register int x;', 'multiple storage-class'),
    ('extern typedef int x;', 'multiple storage-class'),
]
c23_constraints = [
    ('extern int (*row)[]; typedef typeof(row) Saved; extern int (*row)[3]; '
     'extern Saved old; int f(void) { return sizeof *old; }', 'complete object type'),
    ('extern int (*row)[]; typeof(row) earlier(void) { return row; } '
     'extern int (*row)[3]; int f(void) { return sizeof *earlier(); }', 'complete object type'),
    ('extern int f(typeof(x)),x;', 'undeclared'),
    ('extern int x; extern typeof(x) x(void);', 'function name conflicts with external object'),
    ('extern int f(void); extern typeof(&f) f;', 'external object conflicts with prior ordinary'),
]
subset_errors = [
    ('int x;', 'file-scope object declarations'),
    ('int x=42;', 'file-scope object declarations'),
    ('static int x;', 'file-scope object declarations'),
    ('extern int x=42;', 'extern object definitions'),
    ('extern int (*fp)(int)=0;', 'extern object definitions'),
    ('typedef int T; extern T x=42;', "query-derived external declarations require ';'"),
    ('extern void x;', 'only scalar or array extern objects'),
    ('int f(void) { extern int x; return 0; }', 'block-scope extern declarations'),
    ('extern int x; int f(void) { extern int x; return 0; }', 'block-scope extern declarations'),
    ('extern auto x=42;', 'file-scope auto declarations'),
    ('extern inline int x;', 'error:'),
    ('extern thread_local int x;', 'error:'),
]


def diagnostic_records(text):
    return re.findall(r'(fatal error|error|warning|note): ([^\n]+)',
                      text.replace('‘', "'").replace('’', "'"))


def legacy_feature_gap(feature, text, result):
    """Exact independent keyword probes, not a catch-all native failure waiver."""
    probes = {'typeof': 'typeof(int) value;', 'typeof_unqual': 'typeof_unqual(int) value;',
              'nullptr': 'int *p=nullptr;'}
    expected = {
        'typeof': [
            [('error', "return type defaults to 'int' [-Wimplicit-int]"),
             ('error', "expected declaration specifiers before 'value'"),
             ('error', "expected '{' at end of input")],
            [('error', 'expected function body after function declarator')],
        ],
        'nullptr': [
            [('error', "'nullptr' undeclared here (not in a function)")],
            [('error', "use of undeclared identifier 'nullptr'")],
        ],
    }
    expected['typeof_unqual'] = expected['typeof']
    return (text == probes[feature] and result.returncode == 1 and
            diagnostic_records(result.stderr) in expected[feature])


with tempfile.TemporaryDirectory(prefix='kcc extern objects ') as directory:
    directory = Path(directory)
    source, owner, il, assembly, native_obj, owner_obj, kcc_obj, executable = [directory/n for n in
        ('k.c', 'owner.c', 'p.ssa', 'p.s', 'native.o', 'owner.o', 'kcc.o', 'program')]

    def invoke(args):
        return subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=15)

    def compile_source(text, success=True, message=''):
        source.write_text(text+'\n')
        result = invoke([compiler, source])
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:1800], result.stderr)
            if qbe:
                il.write_text(result.stdout)
                result_qbe = invoke([qbe, '-t', 'amd64_sysv', '-o', assembly, il])
                assert result_qbe.returncode == 0, result_qbe.stderr
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr, (text[:1800], message, result.stderr)
            assert str(source)+':' in result.stderr, result.stderr
        return result.stdout

    def native_compile(path, output):
        result = invoke([host, '-std=c2x', '-pedantic-errors', '-c', path, '-o', output])
        assert result.returncode == 0, (path.read_text(), result.stderr)

    def link_run(objects):
        result = invoke([host, *objects, '-o', executable])
        assert result.returncode == 0, result.stderr
        result = subprocess.run([str(executable)], timeout=5)
        assert result.returncode == 42, (source.read_text(), owner.read_text(), result.returncode)

    supported = set()
    for feature, text in [('typeof', 'typeof(int) value;'),
                          ('typeof_unqual', 'typeof_unqual(int) value;'),
                          ('nullptr', 'int *p=nullptr;')]:
        owner.write_text(text+'\n')
        probe = invoke([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', owner])
        if probe.returncode == 0:
            supported.add(feature)
        else:
            assert legacy_feature_gap(feature, text, probe), probe.stderr
            assert not legacy_feature_gap(feature, 'int unrelated;', probe)
            for status in [0, -11, 2, 127]:
                assert not legacy_feature_gap(feature, text, subprocess.CompletedProcess([], status, '', probe.stderr))
            for extra in ['error: extra', 'warning: extra', 'note: extra', 'fatal error: extra']:
                assert not legacy_feature_gap(feature, text, subprocess.CompletedProcess([], 1, '', probe.stderr+'\n'+extra))

    native_pairs = runtime_pairs = keyword_skips = owner_skips = 0
    for name, text, owner_text, features, owner_features in pairs:
        emitted = compile_source(text)
        assert 'data ' not in emitted, (name, emitted)
        owner.write_text(owner_text+'\n')
        if not set(owner_features) <= supported:
            owner_skips += 1
        else:
            native_compile(owner, owner_obj)
            if qbe:
                link_run([assembly, owner_obj])
                runtime_pairs += 1
        if not set(features+owner_features) <= supported:
            keyword_skips += 1
            continue
        # The exact source written by compile_source is the oracle input.
        native_compile(source, native_obj)
        link_run([native_obj, owner_obj])
        native_pairs += 1

    native_constraints = 0
    for cases, features in [(constraints, ()), (c23_constraints, ('typeof',))]:
        for text, message in cases:
            compile_source(text, False, message)
            if not set(features) <= supported:
                continue
            result = invoke([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', source])
            assert result.returncode == 1, (text, result.stderr)
            native_constraints += 1
    for text, message in subset_errors:
        compile_source(text, False, message)
    for text in unavailable_initializers:
        compile_source(text, False, 'inferred name is unavailable in its initializer')

    # Repeated names consume declarations, not new canonical object slots.
    for amount in [512, 513]:
        compile_source('extern int x;'*amount, amount == 512,
                       '' if amount == 512 else 'declaration limit (512)')
        compile_source('extern int '+','.join(['x']*amount)+';', amount == 512,
                       '' if amount == 512 else 'declaration limit (512)')
    for amount in [256, 257]:
        compile_source('extern int '+','.join(f'x{i}' for i in range(amount))+';', amount == 256,
                       '' if amount == 256 else 'external object limit (256)')
        compile_source('extern int '+','.join(f'f{i}(void)' for i in range(amount))+';', amount == 256,
                       '' if amount == 256 else 'function limit (256)')
    mixed = 'extern int '+','.join([f'x{i}' for i in range(256)]+[f'f{i}(void)' for i in range(256)])+';'
    assert not compile_source(mixed).strip()  # Independent pools reach 512 together.
    compile_source(mixed+'extern int x0;', False, 'declaration limit (512)')
    for amount in [128, 129]:
        compile_source('extern int x,f('+','.join(['int']*amount)+');', amount == 128,
                       '' if amount == 128 else 'parameter limit (128)')
    params = ','.join(f'register long p{i}' for i in range(128))
    for amount in [128, 129]:
        compile_source(f'extern int x; int f({params}) {{ char '+','.join(f'v{i}' for i in range(amount))+'; return x; }',
                       amount == 128, '' if amount == 128 else 'local limit (256)')
    for amount in [1047552, 1047553]:
        compile_source(f'extern int x; int f({params}) {{ char a[{amount}]; return x; }}',
                       amount == 1047552, '' if amount == 1047552 else 'storage limit')
    for amount in [4095, 4096]:
        compile_source('extern int x; int f(void) { '+'0;'*amount+' return x; }',
                       amount == 4095, '' if amount == 4095 else 'item limit (4096)')
    for depth in [63, 64]:
        compile_source('extern int x,f('+'int g('*depth+'int'+')'*depth+');', depth == 63,
                       '' if depth == 63 else 'nesting limit (64)')
    for depth in [62, 63]:
        compile_source('typedef int '+'*'*64+' A; typedef A '+'*'*depth+' B[1]; extern int x,f(register B a);', depth == 62,
                       '' if depth == 62 else 'depth limit (128)')

    # No allocation or linker requirement for unused/unevaluated names. Missing
    # used external storage is a linker responsibility, not a sema definition rule.
    for text in ['extern int unused;', 'extern int (*unused)(int);',
                 'typedef int T; extern T x,x;', 'extern typeof(nullptr) unused;',
                 'extern int (*row)[]; extern int (*row)[3];']:
        assert not compile_source(text).strip(), text
    query_only = ('extern int absent; extern int (*callback)(int); '
                  'static int private_fn(int); extern typeof(&private_fn) fp; '
                  'int query(void) { return sizeof absent+sizeof callback+sizeof fp; }')
    emitted = compile_source(query_only)
    assert all('$'+name not in emitted for name in ['absent', 'callback', 'fp', 'private_fn']), emitted
    simple = compile_source('extern int x; int get(void) { return x; }')
    assert '$x' in simple and 'alloc' not in simple and 'data ' not in simple, simple
    local = compile_source('int get(void) { int x=42; return x; }')
    with_extern = compile_source('extern int outside; int get(void) { int x=42; return x; }')
    assert local == with_extern, (local, with_extern)
    if qbe:
        compile_source(query_only)
        result = invoke([host, '-c', assembly, '-o', kcc_obj])
        assert result.returncode == 0, result.stderr
        symbols = invoke(['nm', kcc_obj])
        assert symbols.returncode == 0 and not re.search(r'\b(absent|callback|fp|private_fn)$', symbols.stdout, re.M), symbols.stdout
        compile_source('extern int x; extern int (*fp)(int); static int hidden(void) { return x; } '
                       'int get(void) { return fp(hidden()); }')
        result = invoke([host, '-c', assembly, '-o', kcc_obj])
        assert result.returncode == 0, result.stderr
        symbols = invoke(['nm', kcc_obj])
        assert symbols.returncode == 0, symbols.stderr
        for kind, name in [('U', 'x'), ('U', 'fp'), ('t', 'hidden'), ('T', 'get')]:
            assert re.search(r' '+kind+' '+name+'$', symbols.stdout, re.M), symbols.stdout

print(f'Extern objects passed: {len(pairs)} initialized native-owner pairs '
      f'(24 simple primitive + 24 mixed-stack primitive both-direction arrangements), '
      f'{native_pairs} unchanged strict native agreements, {keyword_skips} keyword-gated native pairs, '
      f'{native_constraints} native constraints, {len(constraints)+len(c23_constraints)} kcc constraints, '
      f'{len(subset_errors)} subset refusals, {len(unavailable_initializers)} kcc-only unavailable-name barriers; '
      f'512 declarations/256 objects/256 functions/independent mixed pools, '
      f'128 parameters/256 locals incl spills/4096 items/1 MiB storage/64 nesting/128 expanded-depth boundaries; '
      f'{host}; keywords available: {sorted(supported)}'
      + (f'; QBE {runtime_pairs} paired runtimes, {owner_skips} owner keyword gaps, IL/nm checks passed' if qbe else ''))
