"""Declaration-only extern arrays backed by initialized native owners.

Run from the repository:
  [KCC=...] [HOST_CC=...] [QBE=...] python3 tests/test_extern_arrays.py
Only curated initialized owner pairs execute. Every invalid/subset/resource
source compiles only, and the native oracle always uses unchanged kcc source.
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
pairs = []


def pair(name, text, owner, features=(), owner_features=()):
    pairs.append((name, text, owner, features, owner_features))


# 48 primitive arrangements: 12 leaves x fixed/unknown outer x both directions.
# The native owner always defines exactly three explicitly initialized elements;
# incomplete kcc declarations never imply that arbitrary indices are safe.
for suffix, label in [('[3]', 'fixed'), ('[]', 'unknown')]:
    for typ, value in zip(integers, values):
        size_check = (f'if(sizeof items!=3*sizeof({typ})) return 3; '
                      if suffix == '[3]' else '')
        pair(typ+' '+label+' kcc driver',
             f'extern {typ} items{suffix}; extern int verify(void); '
             f'int main(void) {{ {size_check} '
             f'if(items[1]!=({typ}){value}) return 1; '
             f'{typ} *p=&items[1]; {typ} (*whole){suffix}=&items; '
             f'if(p!=items+1 || (*whole)[1]!=*p) return 2; '
             f'*p=0; if(items[1]!=0) return 4; items[1]=({typ}){value}; '
             'return verify(); }',
             f'{typ} items[3]={{0,{value},0}}; int verify(void) {{ '
             f'return items[0]==0 && items[1]==({typ}){value} && items[2]==0?42:1; }}')
        pair(typ+' '+label+' native driver',
             f'extern {typ} items{suffix}; {typ} get(void) {{ return items[1]; }} '
             f'void put({typ} x) {{ items[1]=x; }} '
             f'{typ} *elements(void) {{ return items; }} '
             f'{typ} (*whole(void)){suffix} {{ return &items; }}',
             f'{typ} items[3]={{0,0,0}}; {typ} get(void); void put({typ}); '
             f'{typ} *elements(void); {typ} (*whole(void)){suffix}; '
             f'int main(void) {{ if(elements()!=items || whole()!=&items || get()!=0) return 1; '
             f'put(({typ}){value}); if(get()!=({typ}){value} || items[1]!=({typ}){value}) return 2; '
             '*elements()=0; return items[0]==0 && items[2]==0?42:3; }')

pair('fixed rows preserve row and whole-array strides',
     'extern int rows[2][3]; int main(void) { int (*p)[3]=rows; '
     'int (*whole)[2][3]=&rows; if(sizeof rows!=24 || sizeof rows[0]!=12) return 1; '
     'if(p+1!=&rows[1] || p+2-p!=2 || whole+1-whole!=1) return 2; '
     'if((&rows)[0][1][2]!=40) return 3; rows[1][2]+=2; return p[1][2]; }',
     'int rows[2][3]={{1,2,3},{4,5,40}};')
pair('unknown outer rows through native driver',
     'extern int rows[][3]; int (*elements(void))[3] { return rows; } '
     'int get(void) { return rows[1][2]; } void put(int n) { rows[1][2]=n; }',
     'int rows[2][3]={{1,2,3},{4,5,0}}; int (*elements(void))[3]; '
     'int get(void); void put(int); int main(void) { '
     'if(elements()!=rows || elements()+1!=&rows[1] || get()!=0) return 1; '
     'put(42); return rows[1][2]==42 && get()==42 && rows[0][2]==3?42:2; }')
pair('three dimensional row-major shape',
     'extern int cube[2][2][2]; int main(void) { '
     'if(sizeof cube!=32 || sizeof cube[0]!=16 || sizeof cube[0][0]!=8) return 1; '
     'if(cube+1!=&cube[1] || cube[1]+1!=&cube[1][1]) return 2; '
     'cube[1][1][1]+=2; return cube[1][1][1]; }',
     'int cube[2][2][2]={{{0,1},{2,3}},{{4,5},{6,40}}};')
pair('pointer elements are writable through element address',
     'extern int *pointers[2]; int main(void) { int **slot=&pointers[0]; '
     'if(**slot!=40 || *pointers[1]!=2) return 1; *slot=pointers[1]; '
     '*pointers[0]+=40; return *pointers[1]; }',
     'int first=40,second=2; int *pointers[2]={&first,&second};')
pair('unknown pointer array native driver',
     'extern int *pointers[]; int **elements(void) { return pointers; } '
     'void replace(int *p) { pointers[1]=p; } int get(void) { return *pointers[1]; }',
     'int first=1,second=2,answer=42; int *pointers[2]={&first,&second}; '
     'int **elements(void); void replace(int *); int get(void); '
     'int main(void) { if(elements()!=pointers || get()!=2) return 1; '
     'replace(&answer); return pointers[1]==&answer && get()==42?42:2; }')
pair('callback array mutation through function-pointer element address',
     'extern int (*callbacks[2])(int); int main(void) { '
     'if(callbacks[0](40)!=41) return 1; int (**slot)(int)=&callbacks[0]; '
     '*slot=callbacks[1]; return callbacks[0](40); }',
     'int one(int x) { return x+1; } int two(int x) { return x+2; } '
     'int (*callbacks[2])(int)={one,two};')
pair('unknown callback array native driver',
     'extern int (*callbacks[])(int); int (**elements(void))(int) { return callbacks; } '
     'void replace(int (*f)(int)) { callbacks[1]=f; } '
     'int call(int x) { return callbacks[1](x); }',
     'int one(int x) { return x+1; } int two(int x) { return x+2; } '
     'int (*callbacks[2])(int)={one,one}; int (**elements(void))(int); '
     'void replace(int (*)(int)); int call(int); int main(void) { '
     'if(elements()!=callbacks || call(40)!=41) return 1; '
     'replace(two); return callbacks[1]==two && call(40)==42?42:2; }')
pair('void callback array',
     'extern void (*callbacks[1])(int *); int main(void) { '
     'int x=0; callbacks[0](&x); return x; }',
     'void set(int *p) { *p=42; } void (*callbacks[1])(int *)={set};')
pair('pointer-returning callback array',
     'extern int *(*callbacks[1])(int *); int main(void) { '
     'int x=40; int *p=callbacks[0](&x); if(p!=&x) return 1; *p+=2; return x; }',
     'int *identity(int *p) { return p; } int *(*callbacks[1])(int *)={identity};')
pair('const element reads and qualified decay',
     'extern const int items[]; int main(void) { const int *p=items; '
     'const int (*whole)[]=&items; return p[0]+(*whole)[1]; }',
     'const int items[2]={40,2};')
pair('const pointer elements leave pointees writable',
     'extern int *const pointers[2]; int main(void) { '
     '*pointers[0]+=*pointers[1]; return *pointers[0]; }',
     'int first=40,second=2; int *const pointers[2]={&first,&second};')
pair('mixed direct function scalar array callback list',
     'extern int cell,items[2],f(int),(*callbacks[1])(int); int main(void) { '
     'if(cell!=2 || callbacks[0]!=f) return 1; items[1]=callbacks[0](items[0]); '
     'return items[1]+cell; }',
     'int cell=2,items[2]={38,0}; int f(int x) { return x+2; } '
     'int (*callbacks[1])(int)={f};')
pair('unknown known unknown composite remains complete',
     'extern int items[]; extern int items[3]; extern int items[]; '
     'int main(void) { return sizeof items==12?items[2]:1; }',
     'int items[3]={0,0,42};')
pair('own redeclaration bound sees previous complete external array',
     'extern int items[3]; extern int items[sizeof items/sizeof items[0]]; '
     'int main(void) { return items[2]; }',
     'int items[3]={0,0,42};')
pair('same-list later bound sees preceding complete external array',
     'extern int items[3],other[sizeof items/sizeof items[0]]; '
     'int main(void) { if(sizeof other!=3*sizeof(int)) return 1; return other[2]; }',
     'int items[3]={0,0,0}; int other[3]={0,0,42};')
pair('own local array bound sees outer extern before publication',
     'extern int items[3]; int main(void) { long items[sizeof items]; '
     'if(sizeof items!=96) return 1; items[11]=42; return items[11]; }',
     'int items[3]={0,0,0};')
pair('scalar self-size initializer and restored array meaning',
     'extern int items[3]; int main(void) { int *saved=items; '
     '{ int items=sizeof items; if(items!=4) return 1; } '
     'return saved==items && sizeof items==12?items[2]:2; }',
     'int items[3]={0,0,42};')
pair('fixed row typedef root',
     'typedef int Row[3]; extern Row rows[2]; int main(void) { '
     'Row *p=rows; if(sizeof rows!=24) return 1; return p[1][2]; }',
     'int rows[2][3]={{0,0,0},{0,0,42}};')
pair('unknown array typedef with later completing declaration',
     'typedef int Incomplete[]; extern Incomplete items; extern int items[3]; '
     'int main(void) { return sizeof items==12?items[2]:1; }',
     'int items[3]={0,0,42};')
pair('earlier incomplete query preserves identity not later bound',
     'extern int items[]; typedef typeof(items) Saved; '
     'Saved *earlier(void) { return &items; } extern int items[3]; '
     'extern Saved other; int main(void) { Saved *p=earlier(); '
     'if(p!=&items || sizeof items!=12) return 1; '
     'return (*p)[2]+other[0]; }',
     'int items[3]={0,0,40}; int other[1]={2};', ('typeof',))
pair('whole-array typeof retains array rather than pointer type',
     'extern int source[3]; extern typeof(source) target; int main(void) { '
     'typeof(source) *p=&target; if(sizeof *p!=12) return 1; '
     'target[1]=source[1]+2; return (*p)[1]; }',
     'int source[3]={0,40,0}; int target[3]={0,0,0};', ('typeof',))
pair('one-dimensional typeof_unqual removes const element qualification',
     'extern const int source[3]; extern typeof_unqual(source) target; '
     'int main(void) { typeof_unqual(source[0]) value=source[1]; value+=2; '
     'target[1]=value; int *p=target; return p[1]; }',
     'const int source[3]={0,40,0}; int target[3]={0,0,0};', ('typeof_unqual',))
pair('alias base shared by scalar pointer array and function list',
     'typedef int I; extern I items[2],*p,f(I); int main(void) { '
     'if(p!=&items[0]) return 1; items[1]=f(*p); return items[1]; }',
     'int items[2]={40,0}; int *p=&items[0]; int f(int x) { return x+2; }')
pair('same-list query sees preceding array element',
     'extern int items[2],f(typeof(items[0])); int main(void) { return f(items[0]); }',
     'int items[2]={40,0}; int f(int x) { return x+2; }', ('typeof',))
pair('later parameter query sees adjusted parameter not outer array',
     'extern int items[3]; int f(int items[2],typeof(items) p) { '
     'if(sizeof p!=8 || p!=items) return 1; return p[1]; } '
     'int main(void) { return sizeof items==12?f(items,items):2; }',
     'int items[3]={0,42,0};', ('typeof',))
pair('current nullptr leaf array read write and element address',
     'extern typeof(nullptr) items[]; int main(void) { typeof(nullptr) *p=&items[1]; '
     'if(*p!=nullptr || items[0]!=nullptr) return 1; *p=nullptr; '
     'int *q=items[1]; return !q?42:2; }',
     'typeof(nullptr) items[2]={nullptr,nullptr};',
     ('typeof', 'nullptr'), ('typeof', 'nullptr'))

# These exact original sources must be diagnosed by native C23 as constraints.
# No source below (including unused/sizeof-only bodies) is ever executed.
constraints = [
    ('extern int a[2]; extern int a[3];', 'incompatible external object'),
    ('extern int a[][2]; extern int a[][3];', 'incompatible external object'),
    ('extern int a[2]; extern const int a[2];', 'incompatible external object'),
    ('extern int *a[2]; extern const int *a[2];', 'incompatible external object'),
    ('extern int a[2]; extern int *a;', 'incompatible external object'),
    ('extern int a[2]; int a(void);', 'function name conflicts with external object'),
    ('int a(void); extern int a[2];', 'external object conflicts with prior ordinary'),
    ('typedef int a; extern int a[2];', 'external object conflicts with prior ordinary'),
    ('extern int a[2]; typedef int a;', 'typedef name conflicts with prior ordinary'),
    ('extern int a[2],a[3];', 'incompatible external object'),
    ('extern int a[2][];', 'array element type must be complete'),
    ('extern int a[][];', 'array element type must be complete'),
    ('extern void a[2];', 'array element type must be complete'),
    ('extern int a[2](void);', 'error:'),
    ('extern int a[0];', 'array bound'),
    ('extern int a[-1];', 'array bound'),
    ('extern int n; extern int a[n];', 'integer constant expression'),
    ('extern int a[]; int f(void) { return sizeof a; }', 'complete object type'),
    ('extern int a[]; int f(void) { return sizeof a; } extern int a[3];', 'complete object type'),
    ('extern int a[]; int f(void) { return &a+1==&a; }', 'complete object referent'),
    ('extern int a[2],b[2]; int f(void) { a=b; return 0; }', 'modifiable lvalue'),
    ('extern int a[2][3]; int f(void) { a[0]=a[1]; return 0; }', 'modifiable lvalue'),
    ('extern int a[2]; int f(void) { ++a; return 0; }', 'modifiable'),
    ('extern const int a[2]; int f(void) { a[0]=1; return 0; }', 'modifiable lvalue'),
    ('extern const int a[2]; int f(void) { ++a[0]; return 0; }', 'modifiable'),
    ('extern int *const a[2]; int f(void) { a[0]=0; return 0; }', 'modifiable lvalue'),
    ('extern int a[2][3]; int f(void) { int **p=a; return 0; }', 'pointer conversion'),
    ('extern int a[2]; int f(void) { int *p=&a; return 0; }', 'pointer conversion'),
    ('extern int a[2]; int f(void) { return a(); }', 'called expression'),
    ('extern int a[2]; _Static_assert(a[0],"not ICE");', 'constant expression'),
]
c23_constraints = [
    ('extern int a[]; typedef typeof(a) Saved; extern int a[3]; '
     'extern Saved old; int f(void) { return sizeof old; }', 'complete object type'),
    ('extern int a[]; typeof(a) *earlier(void) { return &a; } extern int a[3]; '
     'int f(void) { return sizeof *earlier(); }', 'complete object type'),
    ('extern int a[2]; extern typeof(a) a[2];', 'incompatible external object'),
    ('extern int f(typeof(a[0])),a[2];', 'undeclared'),
]
# Deferred definitions/storage probes make no native-constraint claims.
subset_errors = [
    ('static int a[2]={40,2};', 'file-scope object initializers'),
    ('int a[2]={40,2};', 'file-scope object initializers'),
    ('extern int a[2]={40,2};', 'extern object definitions'),
    ('extern int a[]={40,2};', 'extern object definitions'),
    ('typedef int Row[2]; extern Row a={40,2};', "query-derived external declarations require ';'"),
    ('extern int a[2]; int f(void) { extern int a[2]; return 0; }', 'block-scope extern declarations'),
    ('int f(void) { extern int a[]; return 0; }', 'block-scope extern declarations'),
    ('extern thread_local int a[2];', 'error:'),
]
unavailable_initializers = [
    'extern int a[3]; int f(void) { auto a='+initializer+'; return 0; }'
    for initializer in ['a', 'sizeof a', '(typeof(a[0]))0', 'sizeof(typeof(a))', '&a', '0?a:a']
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


# N3096 6.7.2.5p5, 6.2.5p31 and the explicit array example in
# 6.7.2.5p7 require removing the array/element const here. The independently
# audited GCC14/Clang18 failures retain it. Keep this exact valid original;
# count neither failed native translation as an agreement or execute it.
array_unqual_gap_original = (
    'extern const int source[3]; extern typeof_unqual(source) target; '
    'int main(void) { typeof_unqual(source[0]) value=source[1]; value+=2; '
    'target[1]=value; int *p=target; return p[1]; }')


def native_array_unqual_gap(text, result):
    """One exact source, exit 1 and the entire saved diagnostic sequence only."""
    expected = [
        [('error', "assignment of read-only location 'target[1]'"),
         ('error', "initialization discards 'const' qualifier from pointer target type [-Wdiscarded-qualifiers]")],
        [('error', 'read-only variable is not assignable'),
         ('error', "initializing 'int *' with an expression of type 'typeof_unqual (source)' (aka 'const int[3]') discards qualifiers [-Werror,-Wincompatible-pointer-types-discards-qualifiers]")],
    ]
    return (text == array_unqual_gap_original and result.returncode == 1 and
            diagnostic_records(result.stderr) in expected)


def check_native_array_unqual_gap_controls(result):
    """Exercise negative controls using an actual recognized native result."""
    text = array_unqual_gap_original
    assert native_array_unqual_gap(text, result)
    for wrong_source in ['int unrelated;', text+' ', text.replace('target[1]=value;', 'target[0]=value;')]:
        assert not native_array_unqual_gap(wrong_source, result)
    for status in [0, 2, 127, -6, -9, -11]:
        assert not native_array_unqual_gap(text, subprocess.CompletedProcess([], status, '', result.stderr))
    for extra in ['error: extra', 'warning: extra', 'note: extra', 'fatal error: extra']:
        assert not native_array_unqual_gap(text, subprocess.CompletedProcess([], 1, '', result.stderr+'\n'+extra))
    records = diagnostic_records(result.stderr)
    for omitted in range(len(records)):
        missing = '\n'.join(f'{kind}: {message}' for i, (kind, message) in enumerate(records) if i != omitted)
        assert not native_array_unqual_gap(text, subprocess.CompletedProcess([], 1, '', missing))
    assert not native_array_unqual_gap(text, subprocess.CompletedProcess([], 1, '', result.stderr+result.stderr))


with tempfile.TemporaryDirectory(prefix='kcc extern arrays ') as directory:
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

    native_pairs = runtime_pairs = keyword_skips = owner_skips = native_array_unqual_gaps = 0
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
        # Owner compilation and any QBE runtime already happened independently.
        result = invoke([host, '-std=c2x', '-pedantic-errors', '-c', source, '-o', native_obj])
        if native_array_unqual_gap(text, result):
            check_native_array_unqual_gap_controls(result)
            native_array_unqual_gaps += 1
            continue  # Never link/run a rejected native original or count agreement.
        assert result.returncode == 0, (text, result.stderr)
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

    # Compile-only resource boundaries: arrays and scalars share one 256-object
    # pool. These declarations allocate no data and need no native definitions.
    for amount in [512, 513]:
        compile_source('extern int a[];'*amount, amount == 512,
                       '' if amount == 512 else 'declaration limit (512)')
        compile_source('extern int '+','.join(['a[]']*amount)+';', amount == 512,
                       '' if amount == 512 else 'declaration limit (512)')
    for amount in [256, 257]:
        compile_source('extern int '+','.join(f'a{i}[1]' for i in range(amount))+';', amount == 256,
                       '' if amount == 256 else 'external object limit (256)')
    shared = 'extern int '+','.join([f's{i}' for i in range(128)]+[f'a{i}[]' for i in range(128)])+';'
    assert not compile_source(shared).strip()
    for extra in ['extern int another;', 'extern int another[1];']:
        compile_source(shared+extra, False, 'external object limit (256)')
    mixed = shared+'extern int '+','.join(f'f{i}(void)' for i in range(256))+';'
    assert not compile_source(mixed).strip()
    compile_source(mixed+'extern int a0[];', False, 'declaration limit (512)')
    for text, success in [
        ('extern char a[1048576];', True),
        ('extern char a[1048577];', False),
        ('extern int a[262144];', True),
        ('extern int a[262145];', False),
        ('extern char a[1024][1024];', True),
        ('extern char a[1024][1025];', False),
        ('extern char a[][1048576];', True),
        ('extern char a[][1048576]; extern char a[2][1048576];', False),
        ('extern char a[1048576],b[1048576];', True),
        ('extern char a[]; extern char a[1048576];', True),
        ('extern char a[1048576]; int f(void) { char local[1048576]; return sizeof local; }', True),
    ]:
        compile_source(text, success, '' if success else 'storage limit')
    for dimensions in [64, 65]:
        compile_source('extern int a'+'[1]'*dimensions+';', dimensions == 64,
                       '' if dimensions == 64 else 'dimension limit (64)')
        compile_source('extern int a[]'+'[1]'*(dimensions-1)+';', dimensions == 64,
                       '' if dimensions == 64 else 'dimension limit (64)')

    # Declarations and non-VM queries do not load arrays, allocate storage, or
    # reference absent linker symbols. Earlier incomplete type caches stay so.
    for text in ['extern int absent[];', 'extern int absent[3];',
                 'extern int (*callbacks[2])(int);',
                 'typedef int Row[3]; extern Row rows[2];',
                 'extern int a[]; extern int a[3]; extern int a[];',
                 'extern int a[]; extern typeof(a) b;']:
        assert not compile_source(text).strip(), text
    query_only = ('extern int absent[3]; extern int (*callbacks[2])(int); '
                  'extern int unknown[]; typedef typeof(unknown) Saved; '
                  'static int private_fn(int); extern typeof(&private_fn) hidden_callbacks[2]; '
                  'int query(void) { return sizeof absent+sizeof callbacks+sizeof(Saved *)+sizeof hidden_callbacks; }')
    emitted = compile_source(query_only)
    assert all('$'+name not in emitted for name in
               ['absent', 'callbacks', 'unknown', 'private_fn', 'hidden_callbacks']), emitted
    assert 'alloc' not in emitted and 'data ' not in emitted, emitted
    simple = compile_source('extern int items[3]; int get(void) { return items[1]; }')
    assert '$items' in simple and 'alloc' not in simple and 'data ' not in simple, simple
    local = compile_source('int get(void) { int x=42; return x; }')
    with_extern = compile_source('extern int outside[3]; int get(void) { int x=42; return x; }')
    assert local == with_extern, (local, with_extern)
    if qbe:
        compile_source(query_only)
        result = invoke([host, '-c', assembly, '-o', kcc_obj])
        assert result.returncode == 0, result.stderr
        symbols = invoke(['nm', kcc_obj])
        assert symbols.returncode == 0 and not re.search(r'\b(absent|callbacks|unknown|private_fn|hidden_callbacks)$', symbols.stdout, re.M), symbols.stdout
        compile_source('extern int items[3]; extern int (*callbacks[1])(int); '
                       'static int hidden(void) { return items[1]; } '
                       'int get(void) { return callbacks[0](hidden()); }')
        result = invoke([host, '-c', assembly, '-o', kcc_obj])
        assert result.returncode == 0, result.stderr
        symbols = invoke(['nm', kcc_obj])
        assert symbols.returncode == 0, symbols.stderr
        for kind, name in [('U', 'items'), ('U', 'callbacks'), ('t', 'hidden'), ('T', 'get')]:
            assert re.search(r' '+kind+' '+name+'$', symbols.stdout, re.M), symbols.stdout

print(f'Extern arrays passed: {len(pairs)} initialized native-owner pairs '
      f'(48 fixed/unknown primitive both-direction arrangements), '
      f'{native_pairs} unchanged strict native agreements, {native_array_unqual_gaps} exact array-unqualification native gaps, '
      f'{keyword_skips} keyword-gated native pairs, '
      f'{native_constraints} native constraints, {len(constraints)+len(c23_constraints)} kcc constraints, '
      f'{len(subset_errors)} subset refusals, {len(unavailable_initializers)} kcc-only unavailable-name barriers; '
      f'512 declarations/256 shared scalar-array objects/256 functions/1 MiB per array/64 dimensions; '
      f'{host}; keywords available: {sorted(supported)}'
      + (f'; QBE {runtime_pairs} paired runtimes, {owner_skips} owner keyword gaps, IL/nm checks passed' if qbe else ''))
