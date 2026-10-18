"""File-scope static tentative SCALARS: object linkage is NOT function linkage.

N3096 6.2.2p3-5,7; 6.9.2p2-4; 6.7.10p11. Only defined originals
execute. Mixed-linkage UB refusals and unsupported forms compile only; no claim
that native compilers must diagnose UB. No test rewrites an oracle original.
Run: [KCC=...] [HOST_CC=...] [QBE=...] python3 tests/test_static_objects.py
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
sizes = [1, 1, 1, 1, 2, 2, 4, 4, 8, 8, 8, 8]
# text, expected local storage names, required modern keywords
programs = []
for typ, value in zip(integers, values):
    programs.append((f'static {typ} cell; extern {typ} cell; static {typ} cell; '
                     f'int main(void) {{ if(cell!=0) return 1; cell=({typ}){value}; '
                     f'{typ} *p=&cell; return *p==({typ}){value}?42:2; }}', ('cell',), ()))
    programs.append((f'typedef {typ} T; T static cell; extern T cell; static T cell; '
                     f'int main(void) {{ if(cell!=0) return 1; cell=({typ}){value}; '
                     f'return cell==({typ}){value}?42:2; }}', ('cell',), ()))
for index in range(5):
    specs = ['unsigned', 'long', 'long', 'const']
    specs.insert(index, 'static')
    programs.append((' '.join(specs)+' cell; int main(void) { return cell==0?42:1; }', ('cell',), ()))
programs += [
    ('static int cell,cell; extern int cell,cell; static int cell; '
     'int main(void) { return cell==0?42:1; }', ('cell',), ()),
    ('static int cell; int main(void) { if(cell++!=0 || ++cell!=2) return 1; '
     'cell+=40; return cell; }', ('cell',), ()),
    ('static _Bool cell; int main(void) { if(cell || cell++!=0 || ++cell!=1) return 1; '
     'return cell?42:2; }', ('cell',), ()),
    ('static const int cell; extern const int cell; static const int cell; '
     'int main(void) { const int *p=&cell; return *p==0 && p==&cell?42:1; }', ('cell',), ()),
    ('static int *const cell; extern int *const cell; '
     'int main(void) { return cell==0 && *(&cell)==0?42:1; }', ('cell',), ()),
    ('static int *p; static void *vp; int main(void) { if(p || vp) return 1; '
     'int x=42; p=&x; vp=p; int result=p==vp?*p:1; p=0; vp=0; return result; }', ('p', 'vp'), ()),
    ('static int (*cell)[]; extern int (*cell)[3]; static int (*cell)[]; '
     'int main(void) { if(cell) return 1; int row[3]; row[2]=42; cell=&row; '
     'int result=(*cell)[2]; cell=0; return result; }', ('cell',), ()),
    ('static int cell,f(int),*p,(*fp)(int); extern int cell,f(int),*p,(*fp)(int); '
     'int f(int x) { return x+2; } int main(void) { if(cell || p || fp) return 1; '
     'cell=40; p=&cell; fp=f; int result=fp(*p); p=0; fp=0; return result; }', ('cell', 'p', 'fp'), ()),
    ('typedef int F(int); static F f,*cell; extern F f,*cell; '
     'int f(int x) { return x+2; } int main(void) { if(cell) return 1; cell=f; '
     'return cell(40); }', ('cell',), ()),
    ('static int (*cell)(int); static int plus(int x) { return x+2; } '
     'int main(void) { if(cell) return 1; cell=plus; int result=cell(40); cell=0; return result; }', ('cell',), ()),
    ('static void (*cell)(int *); static void set(int *p) { *p=42; } '
     'int main(void) { if(cell) return 1; int x=0; cell=set; cell(&x); cell=0; return x; }', ('cell',), ()),
    ('static int *(*cell)(int *); int *identity(int *p) { return p; } '
     'int main(void) { if(cell) return 1; int x=42; cell=identity; '
     'int *p=cell(&x); cell=0; return p==&x?*p:1; }', ('cell',), ()),
    ('static int cell; int parameter(int cell) { return cell; } int main(void) { '
     'if(cell) return 1; cell=42; int *saved=&cell; { int cell=2; if(cell!=2) return 2; } '
     '{ typedef long cell; cell x=2; if(sizeof x!=8) return 3; } '
     'for(int cell=0;cell<2;cell++) {} return saved==&cell?parameter(cell):4; }', ('cell',), ()),
    ('static int cell; int main(void) { cell=42; { int copy=cell,cell=2; '
     'if(copy!=42 || cell!=2) return 1; } return cell; }', ('cell',), ()),
    ('int main(void) { return 42; } static long cell;', ('cell',), ()),
    ('static int cell; static typeof(cell) cell; extern typeof(cell) cell; '
     'int main(void) { cell=42; return cell; }', ('cell',), ('typeof',)),
    ('static const long frozen; static typeof_unqual(frozen) cell; '
     'int main(void) { if(frozen || cell) return 1; cell=42; return cell; }', ('frozen', 'cell'), ('typeof_unqual',)),
    ('static bool cell; int main(void) { if(cell) return 1; cell=true; return cell?42:2; }', ('cell',), ('bool',)),
    ('static typeof(nullptr) cell; extern typeof(nullptr) cell; '
     'int main(void) { typeof(nullptr) *p=&cell; if(cell!=nullptr || *p!=nullptr) return 1; '
     'int *object=cell; int (*function)(int)=cell; *p=nullptr; return !object && !function?42:2; }', ('cell',), ('typeof', 'nullptr')),
    ('static int seed(int); static typeof(&seed) cell; '
     'int main(void) { return cell==0 && sizeof(&seed)==sizeof(cell)?42:1; }', ('cell',), ('typeof',)),
    ('static int f(int); static typeof(f) f; static typeof(&f) cell; '
     'int f(int x) { return x+2; } int main(void) { if(cell) return 1; cell=f; return cell(40); }', ('cell',), ('typeof',)),
    ('static int (*cell)[]; typedef typeof(cell) Saved; Saved early(void) { return cell; } '
     'extern int (*cell)[3]; int main(void) { if(cell || early()) return 1; '
     'int row[3]; row[2]=42; cell=&row; int result=sizeof *cell==12 && early()==cell?(*cell)[2]:2; '
     'cell=0; return result; }', ('cell',), ('typeof',)),
]
constraints = [
    'static static int cell;', 'static extern int cell;', 'extern static int cell;',
    'static register int cell;', 'register static int cell;', 'typedef static int cell;',
    'static typedef int cell;', 'static auto int cell;', 'auto static int cell;',
    'int f(static int cell);', 'int f(int (*g)(static int));',
    'int main(void) { return sizeof(static int); }',
    'static int cell; static long cell;', 'static int cell; extern long cell;',
    'static const int cell; static int cell;', 'static int cell; extern const int cell;',
    'static int *cell; static const int *cell;', 'static int *cell; static int *const cell;',
    'static int (*cell)(int); extern int (*cell)(long);',
    'static int cell; int cell(void);', 'static int cell(void); static int cell;',
    'typedef int cell; static int cell;', 'static int cell; typedef int cell;',
    'static int cell,cell(void);', 'static int cell(void),cell;',
    'static int cell; static int cell(void) { return 42; }',
    'int cell(void) { return 42; } static int cell;',
    'static void cell;', 'static const int cell; int f(void) { cell=42; return 0; }',
    'static int *const cell; int f(void) { cell=0; return 0; }',
    'static int cell; int f(void) { return cell(); }',
    'int f(void) { return cell; } static int cell;',
    'static const int cell; _Static_assert(cell==0,"not ICE");',
    'static int cell; int f(void) { int *p=cell; return 0; }',
]
c23_constraints = [
    'static int cell; static typeof(cell) cell(void);',
    'static int seed(void); static typeof(&seed) seed;',
    'static int (*cell)[]; typedef typeof(cell) Saved; extern int (*cell)[3]; '
    'static Saved old; int f(void) { return sizeof *old; }',
    'static int f(typeof(cell)),cell;',
]
# UB under 6.2.2p7, not mandatory native constraints. In particular, objects
# without a storage class do NOT inherit static function linkage rules.
ub_refusals = [
    'int cell; static int cell;', 'extern int cell; static int cell;',
    'static int cell; int cell;', 'static int cell; extern int cell; int cell;',
    'static const int cell; const int cell;', 'static int *cell; int *cell;',
    'typedef int T; static T cell; T cell;',
    'static int cell; typeof(cell) cell;',
    'extern int cell; static int other,cell;',
    'static int cell; int other,cell;',
    'static int f(void),cell; int f(void),cell;',
    'static int (*cell)(int); int (*cell)(int);',
]
# Unsupported/legal forms are subset-only checks. Keep all array and block
# storage refusals through this scalar checkpoint, including typedef/query roots.
subset_errors = [
    'static int cell=0;', 'static int cell=42;', 'static int cell={};',
    'static const int cell=0;', 'static int *cell=0;', 'static int (*cell)(int)=0;',
    'typedef int T; static T cell=0;', 'static typeof(int) cell=0;',
    'static int cell[3];', 'static int cell[];', 'static int cell[2][3];',
    'typedef int A[3]; static A cell;', 'static typeof(int[3]) cell;',
    'extern int cell[3]; static int cell[3];',
    'static int cell,items[3];', 'static int items[3],cell;',
    'int main(void) { static int cell; return 0; }',
    'int main(void) { static int cell=0; return 0; }',
    'int main(void) { static int cell[3]; return 0; }',
    'typedef int T; int main(void) { T static cell; return 0; }',
    'static auto cell=42;', 'auto static cell=42;', 'static thread_local int cell;',
    'int f(int cell[static 3]);',
]


def records(text):
    return re.findall(r'(fatal error|error|warning|note): ([^\n]+)',
                      text.replace('‘', "'").replace('’', "'"))


# Only exact independent keyword probes may gate native originals. Do not turn
# arbitrary native failure into a claimed feature gap or native agreement.
probes = {'typeof': 'typeof(int) value;', 'typeof_unqual': 'typeof_unqual(int) value;',
          'nullptr': 'int *p=nullptr;', 'bool': 'bool value;'}

def legacy_gap(feature, text, result):
    expected = {
        'typeof': [[('error', "return type defaults to 'int' [-Wimplicit-int]"),
                    ('error', "expected declaration specifiers before 'value'"),
                    ('error', "expected '{' at end of input")],
                   [('error', 'expected function body after function declarator')]],
        'nullptr': [[('error', "'nullptr' undeclared here (not in a function)")],
                    [('error', "use of undeclared identifier 'nullptr'")]],
        'bool': [[('error', "unknown type name 'bool'")],
                 [('error', "unknown type name 'bool'"),
                  ('note', "'bool' is defined in header '<stdbool.h>'; did you forget to '#include <stdbool.h>'?")]],
    }
    expected['typeof_unqual'] = expected['typeof']
    return text == probes[feature] and result.returncode == 1 and records(result.stderr) in expected[feature]


with tempfile.TemporaryDirectory(prefix='kcc static scalar objects ') as directory:
    directory = Path(directory)
    source, native, il, assembly, obj, native_obj, peer, peer_obj, exe = [directory/name for name in
        ['k.c', 'native.c', 'p.ssa', 'p.s', 'p.o', 'native.o', 'peer.c', 'peer.o', 'p']]

    def invoke(args):
        return subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=20)

    def compile_source(text, success=True, message='error:'):
        source.write_text(text+'\n')
        result = invoke([compiler, source])
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:1600], result.stderr)
            if qbe:
                il.write_text(result.stdout)
                lowered = invoke([qbe, '-t', 'amd64_sysv', '-o', assembly, il])
                assert lowered.returncode == 0, (text[:1600], lowered.stderr)
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr, (text[:1600], result)
        return result.stdout

    def native_compile(path, output):
        result = invoke([host, '-std=c2x', '-pedantic-errors', '-fno-common', '-O0', '-c', path, '-o', output])
        assert result.returncode == 0, (path.read_text(), result.stderr)

    def symbols(path, global_only=False):
        result = invoke(['nm', *(['-g'] if global_only else []), path])
        assert result.returncode == 0, result.stderr
        return [(parts[-2], parts[-1]) for line in result.stdout.splitlines()
                if len(parts := line.split()) >= 2]

    def private_storage(path, names):
        syms = symbols(path)
        exported = symbols(path, True)
        for name in names:
            kinds = [kind for kind, symbol in syms if symbol == name]
            assert len(kinds) == 1 and kinds[0] in ['b', 'd', 'r'], (name, syms)
            assert not any(symbol == name for _, symbol in exported), (name, exported)
        return syms

    def link_run(objects):
        result = invoke([host, *objects, '-o', exe])
        assert result.returncode == 0, result.stderr
        assert subprocess.run([str(exe)], timeout=5).returncode == 42

    supported = set()
    for feature, text in probes.items():
        native.write_text(text+'\n')
        result = invoke([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', native])
        if result.returncode == 0:
            supported.add(feature)
        else:
            assert legacy_gap(feature, text, result), (feature, result.stderr)
            assert not legacy_gap(feature, 'int unrelated;', result)
            for status in [0, -6, -9, -11, 2, 127]:
                assert not legacy_gap(feature, text, subprocess.CompletedProcess([], status, '', result.stderr))
            for extra in ['warning: extra', 'note: extra', 'error: extra', 'fatal error: extra']:
                assert not legacy_gap(feature, text, subprocess.CompletedProcess([], 1, '', result.stderr+'\n'+extra))

    # Exact LP64 zero layout, no exports, no duplicate data, even unused objects.
    layouts = [(f'static {typ} cell; extern {typ} cell; static {typ} cell;', size)
               for typ, size in zip(integers, sizes)]
    layouts += [(f'static {typ} cell;', size) for typ, size in
                [('const int', 4), ('typeof(nullptr)', 8)]]
    layouts += [('static int *cell;', 8), ('static int (*cell)(int);', 8),
                ('static int (*cell)[];', 8)]
    for text, size in layouts:
        emitted = compile_source(text)
        assert emitted == f'data $cell = align {size} {{ z {size} }}\n', (text, emitted)
        if qbe:
            result = invoke([host, '-c', assembly, '-o', obj])
            assert result.returncode == 0, result.stderr
            private_storage(obj, ['cell'])

    native_programs = runtime_programs = gaps = 0
    for text, names, features in programs:
        emitted = compile_source(text)
        for name in names:
            assert len(re.findall(r'(?m)^data \$'+re.escape(name)+r'\b', emitted)) == 1, (text, emitted)
            assert not re.search(r'export data \$'+re.escape(name)+r'\b', emitted), emitted
        if qbe:
            result = invoke([host, '-c', assembly, '-o', obj])
            assert result.returncode == 0, result.stderr
            private_storage(obj, names)
            link_run([obj])
            runtime_programs += 1
        if not set(features) <= supported:
            gaps += 1
            continue
        native.write_text(text+'\n')
        native_compile(native, native_obj)
        private_storage(native_obj, names)
        link_run([native_obj])
        native_programs += 1

    native_constraints = 0
    for cases, features in [(constraints, ()), (c23_constraints, ('typeof',))]:
        for text in cases:
            compile_source(text, False)
            if not set(features) <= supported:
                continue
            native.write_text(text+'\n')
            result = invoke([host, '-std=c2x', '-pedantic-errors', '-fno-common', '-c', native, '-o', native_obj])
            assert result.returncode == 1, (text, result.stderr)
            native_constraints += 1
    for text in ub_refusals+subset_errors:
        compile_source(text, False)

    # Same-named private datum in TWO TUs, plus a public datum with that same
    # spelling: neither collision nor accidental interposition is permissible.
    owner = ('static long cell; long *slot(void) { return &cell; } '
             'long get(void) { return cell; } void put(long x) { cell=x; }')
    companion = ('long cell; long *slot(void); long get(void); void put(long); '
                 'int main(void) { if(cell || get() || slot()==&cell || *slot()) return 1; '
                 'cell=7; put(4294967296L); if(cell!=7 || get()!=4294967296L) return 2; '
                 '*slot()=42; return get()==42 && cell==7?42:3; }')
    second_private = ('static long cell; long *slot(void); long get(void); void put(long); '
                      'int main(void) { if(cell || get() || slot()==&cell) return 1; '
                      'cell=7; put(4294967296L); return cell==7 && get()==4294967296L?42:2; }')
    paired_runs = 0
    for companion in [companion, second_private]:
        compile_source(owner)
        peer.write_text(companion+'\n')
        native_compile(peer, peer_obj)
        if qbe:
            result = invoke([host, '-c', assembly, '-o', obj])
            assert result.returncode == 0, result.stderr
            private_storage(obj, ['cell'])
            link_run([obj, peer_obj])
            paired_runs += 1
        native.write_text(owner+'\n')
        native_compile(native, native_obj)
        private_storage(native_obj, ['cell'])
        link_run([native_obj, peer_obj])
        # Also compile BOTH TUs with kcc; native-only peer is not a substitute.
        if qbe:
            compile_source(companion)
            result = invoke([host, '-c', assembly, '-o', peer_obj])
            assert result.returncode == 0, result.stderr
            link_run([obj, peer_obj])
            paired_runs += 1

    # Native ABI, six register + two stack integer-class args, private storage
    # exposed only through wrapper address/value interfaces. Full-width values.
    mixed_types = ['char', 'short', 'int', 'long', 'unsigned', 'long long', 'unsigned long long', 'int']
    mixed_values = ['-7', '-1234', '-1234567', '4294967296L', '4294967295U',
                    '4611686018427387904LL', '18446744073709551615ULL', '8']
    names = list('abcdefgh')
    params = ','.join(f'{typ} {name}' for typ, name in zip(mixed_types, names))
    checks = 'if('+' || '.join(f'{name}!={value}' for name, value in zip(names, mixed_values))+') return 0;'
    abi_runs = 0
    for typ, value in zip(integers, values):
        callee = (f'static {typ} cell; {typ} pick({params}) {{ {checks} '
                  f'if(cell) return 0; cell=({typ}){value}; return cell; }} '
                  f'{typ} *slot(void) {{ return &cell; }}')
        caller = (f'{typ} pick({params}); {typ} *slot(void); int main(void) {{ '
                  f'if(*slot()!=0) return 1; if(pick({",".join(mixed_values)})!=({typ}){value}) return 2; '
                  f'return *slot()==({typ}){value}?42:3; }}')
        for kcc_text, peer_text, owned in [(callee, caller, ('cell',)), (caller, callee, ())]:
            compile_source(kcc_text)
            peer.write_text(peer_text+'\n')
            native_compile(peer, peer_obj)
            native.write_text(kcc_text+'\n')
            native_compile(native, native_obj)
            if owned:
                private_storage(native_obj, owned)
            link_run([native_obj, peer_obj])
            if qbe:
                result = invoke([host, '-c', assembly, '-o', obj])
                assert result.returncode == 0, result.stderr
                if owned:
                    private_storage(obj, owned)
                link_run([obj, peer_obj])
                abi_runs += 1

    # Query-only internal function must never become a missing definition/use.
    emitted = compile_source('static int seed(int); static typeof(&seed) cell; '
                             'extern int absent[3]; int query(void) { return sizeof cell+sizeof absent; }')
    assert '$seed' not in emitted and '$absent' not in emitted and 'alloc' not in emitted, emitted
    if qbe:
        result = invoke([host, '-c', assembly, '-o', obj])
        assert result.returncode == 0, result.stderr
        assert not any(name in ['seed', 'absent'] for _, name in symbols(obj))
    comparison = compile_source('int get(void) { int local=42; return local; }')
    owned = compile_source('static int cell; int get(void) { int local=42; return local+cell; }')
    assert comparison.count('alloc') == owned.count('alloc') == 1, (comparison, owned)
    pure = compile_source('static int cell; extern int cell; static int cell;')
    assert 'alloc' not in pure and pure.count('data ') == 1, pure
    mixed = compile_source('static int cell; int public; extern int absent; '
                           'int get(void) { return cell+public+absent; }')
    assert 'export data $public' in mixed and 'export data $cell' not in mixed and 'data $absent' not in mixed

    # Existing budgets, shared with external objects. Generated programs are
    # compile-only; globals do not consume local slots or a cumulative byte cap.
    for amount in [512, 513]:
        for text in ['static int cell;'*amount, 'static int '+','.join(['cell']*amount)+';']:
            emitted = compile_source(text, amount == 512, 'declaration limit (512)')
            if amount == 512:
                assert emitted.count('data $cell ') == 1, emitted
    for amount in [256, 257]:
        text = 'static long '+','.join(f'g{i}' for i in range(amount))+';'
        compile_source(text, amount == 256, 'object limit (256)')
    globals_text = 'static int '+','.join(f'g{i}' for i in range(128))+';'
    shared = globals_text+'extern int '+','.join(f'a{i}[3]' for i in range(128))+';'
    emitted = compile_source(shared)
    assert len(re.findall(r'(?m)^data \$', emitted)) == 128, emitted
    compile_source(shared+'static int extra;', False, 'object limit (256)')
    both = shared+'static int '+','.join(f'f{i}(void)' for i in range(256))+';'
    compile_source(both)
    compile_source(both+'extern int g0;', False, 'declaration limit (512)')
    for amount in [256, 257]:
        compile_source(globals_text+'int f(void) { int '+','.join(f'v{i}' for i in range(amount))+'; return g0; }',
                       amount == 256, 'local limit (256)')
    for count in [262144, 262145]:
        compile_source(f'static int (*cell)[{count}];', count == 262144, 'storage limit')
    for amount in [1048576, 1048577]:
        compile_source(f'static int cell; int f(void) {{ char a[{amount}]; return cell; }}',
                       amount == 1048576, 'storage limit')
    for depth in [64, 65]:
        compile_source('static int '+'*'*depth+'cell;', depth == 64, 'nesting limit (64)')
    source.write_text('static int cell;\n')
    with open('/dev/full', 'w') as full:
        result = subprocess.run([str(compiler), str(source)], stdout=full,
                                stderr=subprocess.PIPE, text=True, timeout=15)
    assert result.returncode == 1 and result.stderr == 'kcc: error: cannot write QBE output\n', result.stderr

print(f'Static scalar objects passed: {len(programs)} defined originals, {native_programs} unchanged native agreements, '
      f'{gaps} exact keyword-gated originals, {len(layouts)} exact zero layouts, '
      f'{len(constraints)+len(c23_constraints)} constraints ({native_constraints} native), '
      f'{len(ub_refusals)} compile-only UB refusals, {len(subset_errors)} subset refusals; '
      f'2 native multi-TU and 24 native mixed-stack ABI pairs; budgets/no-extra-slots/output failure; '
      f'{host}; keywords {sorted(supported)}'
      + (f'; QBE {runtime_programs} originals/{paired_runs} multi-TU/{abi_runs} mixed-stack ABI runs and nm local binding' if qbe else '; QBE not requested'))
