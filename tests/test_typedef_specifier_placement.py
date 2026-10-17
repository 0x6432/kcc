"""The typedef storage class participates in one shared specifier scan."""
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
programs = []
for name in integers:
    value = '1' if name == '_Bool' else '42'
    programs += [
        f'{name} typedef T; int main(void) {{ T x={value}; return x=={value}?42:1; }}',
        f'int main(void) {{ const typedef {name} T; T x={value}; return x=={value}?42:1; }}',
    ]
for index in range(5):
    specifiers = ['unsigned', 'long', 'long', 'const']
    specifiers.insert(index, 'typedef')
    declaration = ' '.join(specifiers)+' T;'
    programs += [declaration+' int main(void) { T x=42; return x; }',
                 'int main(void) { '+declaration+' T x=42; return x; }']
programs += [
    'long typedef T; T typedef U; int main(void) { U x=42; return x; }',
    'long typedef T; int main(void) { T typedef U,*P,F(U); U x=42; P p=&x; return *p; }',
    'long typedef T; int main(void) { T const typedef U; U x=42; return x; }',
    'int main(void) { long typedef T,T,*P,A[2],F(T); A a; a[1]=42; P p=&a[1]; return *p; }',
    'int main(void) { int x=42; { long typedef x; x y=2; if(y!=2) return 1; } return x; }',
    'int f(int T) { { long typedef T; T x=2; if(x!=2) return 1; } return T; } int main(void) { return f(42); }',
    'int f(void) { return 1; } int main(void) { long typedef f; f x=42; return x; }',
    'char typedef T; int main(void) { long typedef T[sizeof(T)]; T a; a[0]=42; return sizeof(a)==8?a[0]:1; }',
    'long typedef T; int main(void) { T typedef T,*P; { T T=42; P p=&T; return *p; } }',
    'int typedef T; T typedef U,*P,F(U); int pick(int x) { return x; } int main(void) { F *p=pick; return p(42); }',
    '#define DECL typedef\nunsigned DECL long T; int main(void) { T x=42; return x; }',
]
c23_programs = [
    'int typedef T; int main(void) { goto T; T: T typedef U; U x=42; return x; }',
    'typeof(int) typedef T; int main(void) { T x=42; return x; }',
    'int main(void) { typeof_unqual(const long) typedef T; T x=40; x+=2; return x; }',
    'int main(void) { int x=42; typeof(x) typedef T; T y=x; return y; }',
    'bool typedef T; int main(void) { T x=true; return x?42:1; }',
    'int main(void) { typeof(nullptr) typedef N; N x=0; return x==nullptr?42:1; }',
]
for_programs = [
    'int main(void) { int x=40; for(int typedef T;x<42;x+=(T)1) {} return x; }',
    'long typedef U; int main(void) { int x=40; for(U typedef T;x<42;x+=(T)1) {} U y=x; return y; }',
    'long typedef T; int main(void) { for(const typedef int T;0;) {} T x=42; return x; }',
    'int f(int T) { for(long typedef T;0;) {} return T; } int main(void) { return f(42); }',
]
constraints = [
    ('int typedef typedef T;', 'duplicate typedef storage-class'),
    ('typedef int const typedef T;', 'duplicate typedef storage-class'),
    ('int f(int typedef T);', 'typedef is not permitted'),
    ('int f(typedef int T);', 'typedef is not permitted'),
    ('int main(void) { return sizeof(int typedef); }', 'typedef is not permitted'),
    ('int main(void) { return (int typedef)42; }', 'typedef is not permitted'),
    ('int main(void) { int typedef T=42; return 0; }', 'cannot have initializers'),
    ('int main(void) { int T=1; long typedef T; return 0; }', 'typedef name conflicts'),
    ('int main(void) { int typedef T; int T=1; return 0; }', 'ordinary declaration conflicts'),
    ('int typedef T; long typedef T;', 'typedef redeclaration has different type'),
    ('int typedef T; T unsigned typedef U;', 'typedef name cannot combine'),
    ('int main(void) { const typedef int T; T x=0; x=1; return 0; }', 'modifiable'),
    ('int main(void) { int T typedef; return 0; }', 'error:'),
    ('int main(void) { return _Alignof(int typedef); }', 'typedef is not permitted'),
    ('int typedef f(void) { return 0; }', "expected ',' or ';' after typedef declarator"),
]
c23_constraints = [
    ('typeof(int typedef) x;', 'typedef is not permitted'),
    ('int main(void) { return alignof(int typedef); }', 'typedef is not permitted'),
]

subset_errors = [
    ('int f(int n) { int typedef T[n]; return 0; }', 'variable-length arrays'),
    ('int typedef F(void); F f { return 42; }', "query-derived external declarations require ';'"),
]


def native_for_gap(text, status, diagnostics):
    if text not in for_programs or status != 1:
        return False
    normalized = diagnostics.replace('‘', "'").replace('’', "'")
    return re.findall(r'(fatal error|error|warning|note): ([^\n]+)', normalized) in [
        [('error', "non-variable declaration in 'for' loop")],
        [('error', "declaration of non-variable 'T' in 'for' loop initial declaration")],
    ]


for message in ["non-variable declaration in 'for' loop",
                "declaration of non-variable 'T' in 'for' loop initial declaration"]:
    diagnostic = 'test.c:1:1: error: '+message+'\n'
    assert native_for_gap(for_programs[0], 1, diagnostic)
    for status in [0, -11, 127]:
        assert not native_for_gap(for_programs[0], status, diagnostic)
    assert not native_for_gap(programs[0], 1, diagnostic)
    assert not native_for_gap(for_programs[0], 1, diagnostic+diagnostic)
    assert not native_for_gap(for_programs[0], 1, diagnostic+'test.c:1:1: note: unrelated\n')

with tempfile.TemporaryDirectory(prefix='kcc typedef placement ') as directory:
    directory = Path(directory)
    source, native, il, assembly, obj, executable = [directory/n for n in ('k.c','h.c','p.ssa','p.s','h.o','p')]

    def compile_source(text, success=True, message=''):
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=15)
        if success:
            assert result.returncode == 0 and not result.stderr,(text[:1800],result.stderr)
            if qbe:
                il.write_text(result.stdout)
                subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=15)
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr,(text[:1800],result.stderr)
        return result.stdout

    def link_run(objects):
        result = subprocess.run([host,*map(str,objects),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        assert result.returncode == 0,result.stderr
        assert subprocess.run([str(executable)],timeout=5).returncode == 42

    native.write_text('typeof(int) value;\n')
    probe = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
    native_c23 = probe.returncode == 0
    if not native_c23:
        errors = re.findall(r'error: ([^\n]+)',probe.stderr.replace('‘', "'").replace('’', "'"))
        assert errors in [["return type defaults to 'int' [-Wimplicit-int]", "expected declaration specifiers before 'value'", "expected '{' at end of input"], ['expected function body after function declarator']],probe.stderr
    native_programs = native_gaps = native_constraints = 0
    for text in programs+c23_programs+for_programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if text in c23_programs and not native_c23:
            continue
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        if native_for_gap(text,result.returncode,result.stderr):
            native_gaps += 1
            continue
        assert result.returncode == 0,(text,result.stderr)
        assert subprocess.run([str(executable)],timeout=5).returncode == 42,text
        native_programs += 1
    for text,message in constraints+c23_constraints:
        compile_source(text,False,message)
        if (text,message) in c23_constraints and not native_c23:
            continue
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
        assert result.returncode != 0,(text,result.stderr)
        native_constraints += 1
    for text,message in subset_errors:
        compile_source(text,False,message)
    only_aliases = compile_source('int f(void) { long typedef T,*P,A[2],F(T); return 42; }')
    assert 'alloc' not in only_aliases and 'data ' not in only_aliases
    for amount in [511,512]:
        compile_source('int typedef '+','.join(f'T{i}' for i in range(amount))+'; int main(void) { return 42; }',amount==511,
                       '' if amount==511 else 'translation unit exceeds declaration limit (512)')
    for amount in [4095,4096]:
        compile_source('int main(void) { int typedef '+','.join(f'T{i}' for i in range(amount))+'; return 42; }',amount==4095,
                       '' if amount==4095 else 'function body exceeds item limit (4096)')
    for depth in [63,64]:
        compile_source('int typedef '+'*'*64+' A; A typedef '+'*'*depth+' B;',depth==63,
                       '' if depth==63 else 'typedef type exceeds expanded depth limit (128)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = 'int a,int b,int c,int d,int e,int f,int g,int h'
        checks = 'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0;'
        helper = f'{name} pick({params}) {{ {checks} return {expected}; }}'
        definition = f'{name} typedef R; R pick({params}) {{ {name} typedef T; T x={expected}; {checks} return x; }}'
        driver = f'{name} pick({params}); int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        typed_driver = f'{name} pick({params}); {name} typedef R; int main(void) {{ R x=pick(1,2,3,4,5,6,7,8); return x=={expected}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(typed_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Typedef placement passed: {len(programs)} standard + {len(c23_programs)} C23-specific + {len(for_programs)} C23 for originals; '
      f'{native_programs} strict native agreements, {native_gaps} exact for-typedef grammar gaps, {native_constraints} strict native constraints; '
      f'512 externals/4096 items/128 expanded-depth boundaries and no alias storage; {host}'
      + ('; original C23 keywords' if native_c23 else '; exact legacy keyword absence (not agreements)')
      + ('; QBE/runtime and 24 both-direction mixed-stack ABI arrangements passed' if qbe else ''))
