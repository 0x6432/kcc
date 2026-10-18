"""Externally linked scalar tentative definitions own one zero-initialized object.

Run: [KCC=...] [HOST_CC=...] [QBE=...] python3 tests/test_tentative_scalars.py
Only defined curated originals execute. Native constraint oracles compile real
objects so translation-unit tentative finalization is not skipped by syntax-only
mode. No original is rewritten and no native diagnostic failure is waived.

The UNCHANGED kcc TU is the sole storage owner, including in the native oracle.
Its companion only extern-declares those objects; it never defines them, even
with an initializer. All storage reads are defined static-duration zero reads or
follow a write. Callbacks are assigned before calls; null pointers are not
subscripted, dereferenced, updated or used in pointer arithmetic. Invalid and
resource-generated programs compile only. Native objects use -fno-common so a
mistaken second definition cannot hide behind legacy common-symbol merging.
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
# name, unchanged sole-owner TU, declaration-only companion, owned object names,
# owner keyword requirements, companion keyword requirements
pairs = []


def pair(name, text, companion, owned=('cell',), features=(), companion_features=()):
    pairs.append((name, text, companion, owned, features, companion_features))


# 24 simple primitive arrangements; extern/tentative interleavings remain one
# definition in the owner TU. Companion writes are observed back in the owner.
for typ, value in zip(integers, values):
    pair(typ+' owner driver',
         f'{typ} cell; extern {typ} cell; {typ} cell; extern int verify({typ} *,{typ}); '
         f'int main(void) {{ if(cell!=0) return 1; cell=({typ}){value}; '
         'int result=verify(&cell,cell); return result==42 && cell==0?42:2; }',
         f'extern {typ} cell; int verify({typ} *p,{typ} value) {{ '
         f'if(p!=&cell || cell!=({typ}){value} || value!=cell) return 1; *p=0; return 42; }}')
    pair(typ+' companion driver',
         f'extern {typ} cell; {typ} cell; extern {typ} cell; {typ} cell; '
         f'{typ} get(void) {{ return cell; }} void put({typ} x) {{ cell=x; }} '
         f'{typ} *slot(void) {{ return &cell; }}',
         f'extern {typ} cell; {typ} get(void); void put({typ}); {typ} *slot(void); '
         f'int main(void) {{ if(cell!=0 || get()!=0 || slot()!=&cell) return 1; '
         f'put(({typ}){value}); if(cell!=({typ}){value} || get()!=cell) return 2; '
         '*slot()=0; return get()==0?42:3; }')

# Another 24 arrangements, not relabeled simple object tests: six register and
# two stack integer-class parameters, checked at full width in both directions.
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
    pair(typ+' mixed-stack owner callee', f'{typ} cell; '+definition,
         f'extern {typ} cell; {typ} pick({params}); '+driver)
    pair(typ+' mixed-stack owner caller', f'{typ} cell; extern {typ} pick({params}); '+driver,
         f'extern {typ} cell; '+definition)

pair('zero-origin integer update lvalue',
     'int cell; int main(void) { if(cell++!=0 || ++cell!=2) return 1; '
     'cell+=40; return cell; }',
     'extern int cell;')
pair('zero-origin boolean updates use truth conversion',
     '_Bool cell; int main(void) { if(cell || cell++!=0 || !cell) return 1; '
     'if(++cell!=1) return 2; return cell?42:3; }',
     'extern _Bool cell;')
pair('const integer tentative zero and address identity',
     'const int cell; extern const int cell; const int cell; '
     'const int *slot(void) { return &cell; }',
     'extern const int cell; const int *slot(void); int main(void) { '
     'return cell==0 && slot()==&cell && *slot()==0?42:1; }')
pair('const pointer tentative zero value',
     'int *const cell; int *const *slot(void) { return &cell; }',
     'extern int *const cell; int *const *slot(void); '
     'int main(void) { return cell==0 && slot()==&cell && *slot()==0?42:1; }')
pair('object and void pointer zero then live local storage',
     'int *p; void *vp; extern int inspect(void); int main(void) { '
     'if(p || vp) return 1; int value=42; p=&value; vp=p; '
     'int result=inspect(); p=0; vp=0; return result; }',
     'extern int *p; extern void *vp; int inspect(void) { '
     'if(!p || p!=vp) return 1; return *p; }', ('p', 'vp'))
pair('pointer slot exposed to companion with live local pointee',
     'int *cell; int **slot(void) { return &cell; } int get(void) { return *cell; }',
     'extern int *cell; int **slot(void); int get(void); int main(void) { '
     'if(cell || slot()!=&cell) return 1; int local=42; *slot()=&local; '
     'int result=get(); cell=0; return result; }')
pair('private function callback assignment and persistent function address',
     'int (*cell)(int); static int plus(int x) { return x+2; } '
     'void arm(void) { cell=plus; } int (**slot(void))(int) { return &cell; }',
     'extern int (*cell)(int); void arm(void); int (**slot(void))(int); '
     'int main(void) { if(cell || slot()!=&cell) return 1; arm(); '
     'if(!cell) return 2; return cell(40); }')
pair('public companion callback assigned only after zero check',
     'int (*cell)(int); extern int plus(int); int main(void) { '
     'if(cell) return 1; cell=plus; int result=cell(40); cell=0; return result; }',
     'extern int (*cell)(int); int plus(int x) { return x+2; }')
pair('void callback zero then nonnull call',
     'void (*cell)(int *); extern void set(int *); int main(void) { '
     'if(cell) return 1; int value=0; cell=set; cell(&value); cell=0; return value; }',
     'extern void (*cell)(int *); void set(int *p) { *p=42; }')
pair('pointer-returning callback zero then live pointee',
     'int *(*cell)(int *); extern int *identity(int *); int main(void) { '
     'if(cell) return 1; int value=40; cell=identity; int *p=cell(&value); '
     'if(p!=&value) return 2; *p+=2; cell=0; return value; }',
     'extern int *(*cell)(int *); int *identity(int *p) { return p; }')
pair('parameter local typedef and for shadows restore tentative object',
     'int cell; int parameter(int cell) { return cell; } int main(void) { '
     'if(cell) return 1; cell=42; int *saved=&cell; { int cell=2; if(cell!=2) return 2; } '
     '{ typedef long cell; cell local=2; if(sizeof local!=8) return 3; } '
     'for(int cell=0;cell<2;cell++) { if(cell>1) return 4; } '
     'return saved==&cell?parameter(cell):5; }',
     'extern int cell;')
pair('completed local list initializer captures outer tentative object',
     'int cell; int main(void) { if(cell) return 1; cell=42; '
     '{ int copy=cell,cell=2; if(copy!=42 || cell!=2) return 2; } return cell; }',
     'extern int cell;')
pair('tentative storage declaration after a function definition',
     'extern int verify(void); int main(void) { return verify(); } int cell;',
     'extern int cell; int verify(void) { return cell==0?42:1; }')
pair('alias-root tentative object and repeated declarations',
     'typedef long T; T cell; extern T cell; T cell; int main(void) { '
     'if(cell) return 1; cell=4294967296L; return cell==4294967296L?42:2; }',
     'extern long cell;')
pair('mixed unadorned direct function scalar and callback list',
     'int cell,f(int),*p,(*fp)(int); int main(void) { '
     'if(cell || p || fp) return 1; cell=40; p=&cell; fp=f; '
     'int result=fp(*p); p=0; fp=0; return result; }',
     'extern int cell; extern int *p; extern int (*fp)(int); '
     'int f(int x) { return x+2; }', ('cell', 'p', 'fp'))
pair('function typedef root distinguishes prototype and pointer object',
     'typedef int F(int); F f,*cell; int main(void) { '
     'if(cell) return 1; cell=f; int result=cell(40); cell=0; return result; }',
     'extern int (*cell)(int); int f(int x) { return x+2; }')
pair('typeof scalar query root owns separate zero object',
     'long first; typeof(first) cell; extern typeof(cell) cell; '
     'int main(void) { if(first || cell) return 1; first=40; cell=first+2; return cell; }',
     'extern long first; extern long cell;', ('first', 'cell'), ('typeof',))
pair('typeof function and pointer query roots classify separately',
     'int f(int); typeof(&f) cell; typeof(f) g; int main(void) { '
     'if(cell) return 1; cell=g; int result=cell(40); cell=0; return result; }',
     'extern int (*cell)(int); int g(int x) { return x+2; }', features=('typeof',))
pair('query-only undefined private function owns null callback object',
     'static int private_fn(int); typeof(&private_fn) cell; extern int inspect(void); '
     'int main(void) { if(cell) return 1; return inspect(); }',
     'extern int (*cell)(int); int inspect(void) { return cell==0?42:1; }', features=('typeof',))
pair('typeof_unqual scalar query does not qualify new tentative storage',
     'const long readonly; typeof_unqual(readonly) cell; int main(void) { '
     'if(readonly || cell) return 1; cell=42; return cell; }',
     'extern const long readonly; extern long cell;', ('readonly', 'cell'), ('typeof_unqual',))
pair('row-pointer canonical completion preserves earlier query snapshot',
     'int (*cell)[]; typedef typeof(cell) Saved; Saved earlier(void) { return cell; } '
     'extern int (*cell)[3]; extern int inspect(void); int main(void) { '
     'if(cell || earlier()) return 1; int row[3]; row[0]=0; row[1]=0; row[2]=42; '
     'cell=&row; if(earlier()!=cell || sizeof *cell!=12) return 2; '
     'int result=inspect(); cell=0; return result; }',
     'extern int (*cell)[3]; int inspect(void) { if(!cell) return 1; return (*cell)[2]; }',
     features=('typeof',))
pair('later parameter query hides outer tentative scalar',
     'long cell; int f(int cell,typeof(cell) second) { '
     'return sizeof second==4?cell+second:1; } int main(void) { '
     'return cell==0 && sizeof cell==8?f(40,2):2; }',
     'extern long cell;', features=('typeof',))
pair('nullptr tentative owner zero storage and conversions',
     'typeof(nullptr) cell; extern typeof(nullptr) cell; extern int inspect(void); '
     'int main(void) { typeof(nullptr) *slot=&cell; if(cell!=nullptr || *slot!=nullptr) return 1; '
     'int *p=cell; int (*f)(int)=cell; if(p || f) return 2; *slot=nullptr; return inspect(); }',
     'extern typeof(nullptr) cell; int inspect(void) { return cell==nullptr?42:1; }',
     features=('typeof', 'nullptr'), companion_features=('typeof', 'nullptr'))
pair('nullptr tentative owner through companion slot',
     'typeof(nullptr) cell; typeof(nullptr) get(void) { return cell; } '
     'typeof(nullptr) *slot(void) { return &cell; }',
     'extern typeof(nullptr) cell; typeof(nullptr) get(void); typeof(nullptr) *slot(void); '
     'int main(void) { if(slot()!=&cell || get()!=nullptr || cell!=nullptr) return 1; '
     '*slot()=nullptr; return get()==nullptr?42:2; }',
     features=('typeof', 'nullptr'), companion_features=('typeof', 'nullptr'))

# These original-source native constraints compile only; compatible repeated
# tentative declarations are intentionally NOT labeled redefinitions.
constraints = [
    ('int cell; long cell;', 'incompatible external object'),
    ('int cell; extern long cell;', 'incompatible external object'),
    ('extern long cell; int cell;', 'incompatible external object'),
    ('const int cell; int cell;', 'incompatible external object'),
    ('int cell; extern const int cell;', 'incompatible external object'),
    ('int *cell; const int *cell;', 'incompatible external object'),
    ('int *cell; int *const cell;', 'incompatible external object'),
    ('int (*cell)(int); int (*cell)(long);', 'incompatible external object'),
    ('int cell; int cell(void);', 'function name conflicts'),
    ('int cell(void); int cell;', 'conflicts with prior ordinary'),
    ('typedef int cell; int cell;', 'conflicts with prior ordinary'),
    ('int cell; typedef int cell;', 'conflicts with prior ordinary'),
    ('int cell,cell(void);', 'function name conflicts'),
    ('void cell;', 'only scalar or array file-scope objects'),
    ('const int cell; int f(void) { cell=42; return 0; }', 'modifiable lvalue'),
    ('const int cell; int f(void) { ++cell; return 0; }', 'modifiable'),
    ('int *const cell; int f(void) { cell=0; return 0; }', 'modifiable lvalue'),
    ('int cell; int f(void) { return cell(); }', 'called expression'),
    ('int f(void) { return cell; } int cell;', 'undeclared'),
    ('const int cell; _Static_assert(cell==0,"not ICE");', 'constant expression'),
    ('int cell; int f(void) { int *p=cell; return 0; }', 'pointer conversion'),
]
c23_constraints = [
    ('int (*cell)[]; typedef typeof(cell) Saved; extern int (*cell)[3]; '
     'Saved old; int f(void) { return sizeof *old; }', 'complete object type'),
    ('int (*cell)[]; typeof(cell) earlier(void) { return cell; } '
     'extern int (*cell)[3]; int f(void) { return sizeof *earlier(); }', 'complete object type'),
    ('int f(typeof(cell)),cell;', 'undeclared'),
]
# No native-rejection claim for these legal/deferred forms. All compile only.
subset_errors = [
    ('const int *cell=0;', 'file-scope object initializers'),
    ('int *cell=0;', 'file-scope object initializers'),
    ('int (*cell)(int)=0;', 'file-scope object initializers'),
    ('extern int *cell=0;', 'extern object definitions'),
    ('typedef int *T; T cell=0;', "query-derived external declarations require ';'"),
    ('typeof(int *) cell=0;', "query-derived external declarations require ';'"),
    ('extern int cell; int f(void) { extern int cell; return 0; }', 'block-scope extern declarations'),
    ('thread_local int cell;', 'expected integer type specifier'),
]
unavailable_initializers = [
    'int cell; int f(void) { auto cell='+initializer+'; return 0; }'
    for initializer in ['cell', 'sizeof cell', '(typeof(cell))0', 'sizeof(typeof(cell))', '&cell', '0?cell:42']
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


with tempfile.TemporaryDirectory(prefix='kcc tentative scalars ') as directory:
    directory = Path(directory)
    source, companion, il, assembly, native_obj, companion_obj, kcc_obj, executable = [directory/n for n in
        ('owner.c', 'companion.c', 'p.ssa', 'p.s', 'native-owner.o', 'companion.o', 'kcc-owner.o', 'program')]

    def invoke(args):
        return subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=15)

    def compile_source(text, success=True, message=None):
        source.write_text(text+'\n')
        result = invoke([compiler, source])
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:1800], result.stderr)
            if qbe:
                il.write_text(result.stdout)
                translated = invoke([qbe, '-t', 'amd64_sysv', '-o', assembly, il])
                assert translated.returncode == 0, translated.stderr
                # Owned storage is a real definition, never a common symbol.
                assert not re.search(r'^\s*\.(?:comm|lcomm)\b', assembly.read_text(), re.M), assembly.read_text()
        else:
            assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr, (text[:1800], result.stderr)
            assert str(source)+':' in result.stderr, result.stderr
            if message is not None:
                assert message in result.stderr, (text[:1800], message, result.stderr)
        return result.stdout

    def native_compile(path, output):
        result = invoke([host, '-std=c2x', '-pedantic-errors', '-fno-common', '-c', path, '-o', output])
        assert result.returncode == 0, (path.read_text(), result.stderr)

    def symbols(path):
        result = invoke(['nm', path])
        assert result.returncode == 0, result.stderr
        # Includes undefined lines (two fields) and defined lines (three fields).
        return [(parts[-2], parts[-1]) for line in result.stdout.splitlines()
                if len(parts := line.split()) >= 2]

    def owned_once(path, owned):
        records = symbols(path)
        for name in owned:
            found = [kind for kind, symbol in records if symbol == name]
            # Const native storage can legitimately live in R; mutable ownership
            # is B/D, not common C or undefined U. One symbol in each owner object.
            assert len(found) == 1 and found[0] in ['B', 'D', 'R'], (name, records)
        return records

    def companion_declares_only(path, owned):
        records = symbols(path)
        for kind, name in records:
            if name in owned:
                assert kind == 'U', (name, records)

    def link_run(objects):
        result = invoke([host, *objects, '-o', executable])
        assert result.returncode == 0, result.stderr
        result = subprocess.run([str(executable)], timeout=5)
        assert result.returncode == 42, (source.read_text(), companion.read_text(), result.returncode)

    supported = set()
    for feature, text in [('typeof', 'typeof(int) value;'),
                          ('typeof_unqual', 'typeof_unqual(int) value;'),
                          ('nullptr', 'int *p=nullptr;')]:
        companion.write_text(text+'\n')
        probe = invoke([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', companion])
        if probe.returncode == 0:
            supported.add(feature)
        else:
            assert legacy_feature_gap(feature, text, probe), probe.stderr
            assert not legacy_feature_gap(feature, 'int unrelated;', probe)
            for status in [0, -6, -9, -11, 2, 127]:
                assert not legacy_feature_gap(feature, text, subprocess.CompletedProcess([], status, '', probe.stderr))
            for extra in ['warning: extra', 'note: extra', 'error: extra', 'fatal error: extra']:
                assert not legacy_feature_gap(feature, text, subprocess.CompletedProcess([], 1, '', probe.stderr+'\n'+extra))

    # Exact target LP64 layout, independently of value/ABI runtime agreement.
    # Repeated declarations/interleaved extern must still emit just one normal
    # zero-data definition, with byte count and alignment matching each leaf.
    primitive_sizes = [1, 1, 1, 1, 2, 2, 4, 4, 8, 8, 8, 8]
    for typ, size in zip(integers, primitive_sizes):
        emitted = compile_source(f'{typ} cell; extern {typ} cell; {typ} cell;')
        expected = f'export data $cell = align {size} {{ z {size} }}\n'
        assert emitted == expected, (typ, expected, emitted)
    for declaration, size in [('const int cell;', 4), ('int *cell;', 8),
                              ('int (*cell)(int);', 8), ('typeof(nullptr) cell;', 8)]:
        emitted = compile_source(declaration)
        assert emitted == f'export data $cell = align {size} {{ z {size} }}\n', (declaration, emitted)

    # A declaration-only owned-data TU still must report write/flush failure;
    # this compiles valid C only, with no linking or C execution.
    source.write_text('int cell;\n')
    with open('/dev/full', 'w') as full:
        failed_output = subprocess.run([str(compiler), str(source)], stdout=full,
                                       stderr=subprocess.PIPE, text=True, timeout=15)
    assert failed_output.returncode == 1 and failed_output.stderr == 'kcc: error: cannot write QBE output\n', failed_output.stderr

    native_pairs = runtime_pairs = keyword_skips = companion_skips = 0
    for name, text, companion_text, owned, features, companion_features in pairs:
        emitted = compile_source(text)
        for symbol in owned:
            assert len(re.findall(r'\bdata \$'+re.escape(symbol)+r'\b', emitted)) == 1, (name, emitted)
        companion.write_text(companion_text+'\n')
        if not set(companion_features) <= supported:
            companion_skips += 1
        else:
            native_compile(companion, companion_obj)
            companion_declares_only(companion_obj, owned)
            if qbe:
                result = invoke([host, '-c', assembly, '-o', kcc_obj])
                assert result.returncode == 0, result.stderr
                owned_once(kcc_obj, owned)
                link_run([kcc_obj, companion_obj])
                runtime_pairs += 1
        if not set(features+companion_features) <= supported:
            keyword_skips += 1
            continue
        # The owner source is unchanged. -fno-common makes ownership explicit.
        native_compile(source, native_obj)
        owned_once(native_obj, owned)
        link_run([native_obj, companion_obj])
        native_pairs += 1

    native_constraints = 0
    for cases, features in [(constraints, ()), (c23_constraints, ('typeof',))]:
        for text, message in cases:
            compile_source(text, False, message)
            if not set(features) <= supported:
                continue
            # GCC14 syntax-only mode skips tentative finalization for void cell;
            # actual object compilation diagnoses it. Every invalid original
            # remains compile-only, with no linking or execution.
            result = invoke([host, '-std=c2x', '-pedantic-errors', '-fno-common', '-c', source, '-o', native_obj])
            assert result.returncode == 1, (text, result.stderr)
            native_constraints += 1
    for text, message in subset_errors:
        compile_source(text, False, message)
    for text in unavailable_initializers:
        compile_source(text, False, 'inferred name is unavailable in its initializer')

    # Generated boundaries compile only. Limits are the existing object,
    # declaration/type/local budgets, not an invented cumulative global-byte cap.
    for amount in [512, 513]:
        emitted = compile_source('int cell;'*amount, amount == 512,
                                 None if amount == 512 else 'declaration limit (512)')
        if amount == 512:
            assert len(re.findall(r'\bdata \$cell\b', emitted)) == 1, emitted
        compile_source('int '+','.join(['cell']*amount)+';', amount == 512,
                       None if amount == 512 else 'declaration limit (512)')
    for amount in [256, 257]:
        compile_source('long long '+','.join(f'g{i}' for i in range(amount))+';', amount == 256,
                       None if amount == 256 else 'external object limit (256)')
    # Pure extern arrays still consume the shared object pool but never storage.
    shared = ('int '+','.join(f'g{i}' for i in range(128))+'; extern int '+
              ','.join(f'a{i}[3]' for i in range(128))+';')
    emitted = compile_source(shared)
    assert len(re.findall(r'\bdata \$', emitted)) == 128, emitted
    assert not re.search(r'\bdata \$a\d+\b', emitted), emitted
    compile_source(shared+'int extra;', False, 'external object limit (256)')
    mixed = shared+'int '+','.join(f'f{i}(void)' for i in range(256))+';'
    compile_source(mixed)
    compile_source(mixed+'extern int g0;', False, 'declaration limit (512)')
    globals_text = 'int '+','.join(f'g{i}' for i in range(256))+';'
    for amount in [256, 257]:
        compile_source(globals_text+'int f(void) { int '+','.join(f'v{i}' for i in range(amount))+'; return g0; }',
                       amount == 256, None if amount == 256 else 'local limit (256)')
    for count in [262144, 262145]:
        compile_source(f'int (*cell)[{count}];', count == 262144,
                       None if count == 262144 else 'storage limit')
    # Complete referent arrays and extern arrays keep existing array budgets,
    # even though array definitions themselves remain an excluded next slice.
    compile_source('extern char absent[1048576];')
    compile_source('extern char absent[1048577];', False, 'storage limit')

    for declaration in ['int cell;', 'int cell; extern int cell; int cell;',
                        'extern int cell; int cell; extern int cell;',
                        'typedef int T; T cell; extern T cell;',
                        'typeof(int) cell; extern typeof(cell) cell;']:
        emitted = compile_source(declaration)
        assert len(re.findall(r'\bdata \$cell\b', emitted)) == 1, emitted
        assert 'alloc' not in emitted, emitted
    for pure_extern in ['extern int absent;', 'extern int absent[];',
                        'extern int absent[3];', 'extern int (*callback)(int);']:
        assert not compile_source(pure_extern).strip(), pure_extern
    comparison = compile_source('int get(void) { int local=42; return local; }')
    with_storage = compile_source('int cell; int get(void) { int local=42; return local; }')
    # Do not assume data placement/order: function-local allocations stay equal.
    assert comparison.count('alloc') == with_storage.count('alloc') == 1, (comparison, with_storage)

    # Query-only use of an undefined private function must not become a linker
    # requirement just because a separately owned callback has zero storage.
    query_only = ('static int private_fn(int); typeof(&private_fn) cell; '
                  'extern int absent[3]; int query(void) { return sizeof cell+sizeof absent; }')
    emitted = compile_source(query_only)
    assert '$private_fn' not in emitted and '$absent' not in emitted, emitted
    assert len(re.findall(r'\bdata \$cell\b', emitted)) == 1 and 'alloc' not in emitted, emitted
    if qbe:
        result = invoke([host, '-c', assembly, '-o', kcc_obj])
        assert result.returncode == 0, result.stderr
        records = owned_once(kcc_obj, ['cell'])
        assert not any(name in ['private_fn', 'absent'] for kind, name in records), records
        # Mutable storage specifically must be one B/D definition, never U/C.
        emitted = compile_source('int cell; extern int cell; int cell; '
                                 'extern int array[3]; int get(void) { return cell+array[0]; }')
        assert len(re.findall(r'\bdata \$cell\b', emitted)) == 1 and 'data $array' not in emitted, emitted
        result = invoke([host, '-c', assembly, '-o', kcc_obj])
        assert result.returncode == 0, result.stderr
        records = owned_once(kcc_obj, ['cell'])
        assert [kind for kind, name in records if name == 'cell'][0] in ['B', 'D'], records
        assert ('U', 'array') in records, records

print(f'Tentative scalars passed: {len(pairs)} sole-owner zero-storage pairs '
      f'(24 simple primitive + 24 mixed-stack primitive both-direction arrangements), '
      f'{native_pairs} unchanged strict native agreements, {keyword_skips} keyword-gated native pairs, '
      f'{native_constraints} native constraints, {len(constraints)+len(c23_constraints)} kcc constraints, '
      f'{len(subset_errors)} subset refusals, {len(unavailable_initializers)} kcc-only unavailable-name barriers; '
      f'512 declarations/256 shared objects/256 functions/256 locals/retained array-type size budgets; '
      f'{host}; keywords available: {sorted(supported)}; 12 primitive + 4 pointer/const/nullptr exact layouts and data-only output-error regression passed'
      + (f'; QBE {runtime_pairs} paired runtimes, {companion_skips} companion keyword gaps, single-definition/nm checks passed' if qbe else ''))
