"""Parameter point of declaration, nested prototypes and definition-body masks."""
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
        f'typedef long T; int f({name} T) {{ return T=={value}?42:1; }} '
        f'int main(void) {{ T x={value}; return f(x); }}',
        f'typedef long T; int f({name} T,int a[sizeof(T)]) {{ return a[sizeof(T)-1]; }} '
        f'int main(void) {{ int a[sizeof({name})]; a[sizeof({name})-1]=42; return f(0,a); }}',
    ]
programs += [
    'typedef long T; int f(T T) { T+=2; return T; } int main(void) { T x=40; return f(x); }',
    'typedef long T; int f(int T); int f(int x) { return x; } int main(void) { T x=42; return f(x); }',
    'typedef long T; int f(int x); int f(int T) { return T; } int main(void) { return f(42); }',
    'typedef char T; int f(int T[sizeof(T)]) { return sizeof(T)==8?T[0]:1; } '
    'int main(void) { int a[1]; a[0]=42; return f(a); }',
    'typedef long T; int f(int (*T)[sizeof(T)]) { return sizeof(*T)==32?(*T)[7]:1; } '
    'int main(void) { int a[8]; a[7]=42; return f(&a); }',
    'typedef long T; int cb(long x) { return x; } int f(int T(T)) { return T(42); } '
    'int main(void) { return f(cb); }',
    'typedef long T; int f(int T) { int *p=&T; { typedef char T; T x=2; *p+=x; } return T; } '
    'int main(void) { return f(40); }',
    'typedef long T; int f(int T) { { int T=2; if(T!=2) return 1; } return T; } '
    'int main(void) { return f(42); }',
    'typedef long T; int f(int T) { for(int T=0;T<2;T++) {} T+=2; return T; } '
    'int main(void) { return f(40); }',
    'typedef long T; int f(int T) { if(T) return f(T-1)+1; return 40; } '
    'int main(void) { T x=2; return f(x); }',
    'typedef long T; int f(int T) { goto T; T: return T; } int main(void) { return f(42); }',
    'typedef long T; int f(int (*cb)(char T,int a[sizeof(T)]),T x,int a[sizeof(T)]) { return x; } '
    'int main(void) { return f(0,42,0); }',
    'typedef long T; int f(int T,int (*cb)(int x,int a[sizeof(T)])) { return T; } '
    'int main(void) { return f(42,0); }',
    'typedef long T; int f(int (*a)(int T),int (*b)(T x),T x) { return x; } '
    'int main(void) { return f(0,0,42); }',
    'typedef long T; int main(void) { int (*p)(int T),(*q)(T x); T x=42; return x; }',
    'typedef long T; typedef int F(int T),G(T x); int main(void) { F *p=0; G *q=0; T x=42; return x; }',
    'typedef long T; int main(void) { return sizeof(int (*)(int T))+sizeof(T)+26; }',
    'typedef long T; int (*f(int T))[sizeof(T)] { if(sizeof(T)!=4) return 0; return 0; } '
    'int main(void) { return sizeof(*f(0))==32?42:1; }',
    'typedef long T; int pick(T x) { return x; } int (*f(int T))(T) { return T==2?pick:0; } '
    'int main(void) { return f(2)(42); }',
    'typedef long T; typedef char U; int pick(char x) { return x; } '
    'int (*f(int T))(char U) { U x=2; return sizeof(U)==1 && x==2 && T==40?pick:0; } '
    'int main(void) { return f(40)(42); }',
    'typedef long T; int f(int (T)) { T x=42; return x; } int main(void) { return f(0); }',
    'typedef long T; int f(int (*p)(int T)) { T x=42; return x; } int main(void) { return f(0); }',
    'typedef long T; int f(const int T) { return sizeof(T)==4?T:1; } int main(void) { return f(42); }',
    'typedef long T; int f(int *T,int a[sizeof(T)]) { return *T; } '
    'int main(void) { int x=42; return f(&x,0); }',
]
c23_programs = [
    'typedef long T; int f(int T,typeof(T) x) { return sizeof(x)==4?T+x:1; } '
    'int main(void) { return f(40,2); }',
    'typedef long T; int f(const int T,typeof_unqual(T) x) { x+=T; return x; } '
    'int main(void) { return f(40,2); }',
    'typedef long T; int f(int T) { typeof(T) x=T; x+=2; return sizeof(x)==4?x:1; } '
    'int main(void) { return f(40); }',
    'typedef long T; int f(int T[sizeof(T)],typeof(T) p) { return sizeof(*p)==4?*p:1; } '
    'int main(void) { int a[8]; a[0]=42; return f(a,a); }',
    'typedef long T; int f(int (*cb)(char T,typeof(T) x),typeof(T) x) { return sizeof(x)==8?x:1; } '
    'int main(void) { return f(0,42); }',
    'typedef long T; int f(int T) { for(typedef char T;0;) {} '
    'typeof(T) x=T; return sizeof(x)==4?x:1; } int main(void) { return f(42); }',
]
constraints = [
    ('typedef int T; int f(int T,T x);', 'expected integer type'),
    ('typedef int T; int f(int T,int T);', 'duplicate parameter name'),
    ('typedef int T; int f(int T) { typedef int T; return 0; }', 'typedef name conflicts'),
    ('typedef int T; int f(int T) { int T=1; return T; }', 'redeclaration of local'),
    ('typedef int T; int f(int T) { T x; return 0; }', 'error:'),
    ('typedef int T; int f(int T) { return (T)42; }', 'error:'),
    ('typedef int T; int f(int T) { return sizeof(T *); }', 'error:'),
    ('typedef int T; int f(const int T) { T=42; return T; }', 'modifiable'),
    ('typedef int T; int f(void T);', 'parameter cannot have void type'),
    ('typedef long T; int f(int T); long f(int x);', 'incompatible function declaration'),
]
# These are subset rejections, not native constraints (C permits prototype VLAs).
subset_errors = [
    ('typedef int T; int f(int T,int a[T]);', 'variable-length arrays'),
    ('typedef int T; int f(int T,int a[(T)2]);', 'error:'),
]
def native_named_void_warning(text, status, diagnostics):
    if text != 'typedef int T; int f(void T);' or status != 0:
        return False
    normalized = diagnostics.replace('‘', "'").replace('’', "'")
    return re.findall(r'(fatal error|error|warning): ([^\n]+)', normalized) == [
        ('warning', "parameter 1 ('T') has void type")]


def native_for_typedef_gap(text, status, diagnostics):
    if text != c23_programs[-1] or status != 1:
        return False
    normalized = diagnostics.replace('‘', "'").replace('’', "'")
    messages = re.findall(r'(fatal error|error|warning): ([^\n]+)', normalized)
    return messages in [
        [('error', "non-variable declaration in 'for' loop")],
        [('error', "declaration of non-variable 'T' in 'for' loop initial declaration")],
    ]


void_warning = "test.c:1:1: warning: parameter 1 ('T') has void type\n"
assert native_named_void_warning('typedef int T; int f(void T);', 0, void_warning)
assert not native_named_void_warning('int other(void);', 0, void_warning)
assert not native_named_void_warning('typedef int T; int f(void T);', 1, void_warning)
assert not native_named_void_warning('typedef int T; int f(void T);', 0, '')
assert not native_named_void_warning('typedef int T; int f(void T);', 0, void_warning+void_warning)
for_error = "test.c:1:1: error: non-variable declaration in 'for' loop\n"
gcc_for_error = "test.c:1:1: error: declaration of non-variable ‘T’ in ‘for’ loop initial declaration\n"
for diagnostic in [for_error, gcc_for_error]:
    assert native_for_typedef_gap(c23_programs[-1], 1, diagnostic)
    assert not native_for_typedef_gap(programs[0], 1, diagnostic)
    assert not native_for_typedef_gap(c23_programs[-1], 0, diagnostic)
    assert not native_for_typedef_gap(c23_programs[-1], -11, diagnostic)
    assert not native_for_typedef_gap(c23_programs[-1], 127, diagnostic)
    assert not native_for_typedef_gap(c23_programs[-1], 1, '')
    assert not native_for_typedef_gap(c23_programs[-1], 1, diagnostic+diagnostic)
    assert not native_for_typedef_gap(c23_programs[-1], 1, diagnostic+'test.c:1:1: warning: unrelated\n')
assert not native_for_typedef_gap(c23_programs[-1], 1, gcc_for_error.replace('‘T’', '‘U’'))


with tempfile.TemporaryDirectory(prefix='kcc parameter typedef ') as directory:
    directory = Path(directory)
    source, native, il, assembly, obj, executable = [directory/n for n in ('k.c','h.c','p.ssa','p.s','h.o','p')]

    def compile_source(text, success=True, message=''):
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler),str(source)], capture_output=True, text=True, timeout=15)
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:1800],result.stderr)
            if qbe:
                il.write_text(result.stdout)
                subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)], check=True, timeout=15)
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr, (text[:1800],result.stderr)
        return result.stdout

    def link_run(objects):
        result = subprocess.run([host,*map(str,objects),'-o',str(executable)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert subprocess.run([str(executable)],timeout=5).returncode == 42

    native.write_text('typeof(int) value;\n')
    probe = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
    native_c23 = probe.returncode == 0
    if not native_c23:
        errors = re.findall(r'error: ([^\n]+)',probe.stderr.replace('‘', "'").replace('’', "'"))
        assert errors in [["return type defaults to 'int' [-Wimplicit-int]", "expected declaration specifiers before 'value'", "expected '{' at end of input"], ['expected function body after function declarator']],probe.stderr
    native_programs = 0
    native_constraints = 0
    native_void_warnings = 0
    native_for_gaps = 0
    for text in programs+c23_programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if text in programs or native_c23:
            native.write_text(text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],capture_output=True,text=True,timeout=10)
            if native_for_typedef_gap(text, result.returncode, result.stderr):
                native_for_gaps += 1
                continue
            assert result.returncode == 0,(text,result.stderr)
            assert subprocess.run([str(executable)],timeout=5).returncode == 42,text
            native_programs += 1
    for text,message in constraints:
        compile_source(text,False,message)
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
        if native_named_void_warning(text, result.returncode, result.stderr):
            native_void_warnings += 1
        else:
            assert result.returncode != 0,(text,result.stderr)
            native_constraints += 1
    for text,message in subset_errors:
        compile_source(text,False,message)
    prototype_il = compile_source('typedef long T; typedef int F(int T); int f(int T,int (*cb)(char T));')
    assert 'alloc' not in prototype_il and 'data ' not in prototype_il and 'function ' not in prototype_il
    for amount in [128,129]:
        names = [f'T{i}' for i in range(amount)]
        aliases = 'typedef long '+','.join(names)+';'
        params = ','.join('int '+name for name in names)
        compile_source(aliases+f'int f({params});',amount==128,
                       '' if amount==128 else 'function exceeds parameter limit (128)')
        compile_source(aliases+f'int f({params}) {{ return T0; }}',amount==128,
                       '' if amount==128 else 'function exceeds parameter limit (128)')
    for amount in [128,129]:
        params = ','.join(f'int T{i}' for i in range(128))
        locals_text = ''.join(f'int x{i}=0;' for i in range(amount))
        compile_source('typedef long T0;'+f'int f({params}) {{ {locals_text} return T0; }}',amount==128,
                       '' if amount==128 else 'function exceeds local limit (256)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = f'int a,int b,int c,int d,int e,int f,{name} T,int h'
        checks = f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || T!={expected} || h!=8) return 0;'
        helper = f'{name} pick({params}) {{ {checks} return T; }}'
        definition = f'typedef long T; {helper}'
        driver = f'{name} pick({params}); int main(void) {{ return pick(1,2,3,4,5,6,{expected},8)=={expected}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(f'typedef long T; {driver}',helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Parameter/typedef shadowing passed: {len(programs)} standard + {len(c23_programs)} C23 originals, '
      f'{native_programs} strict native agreements, {native_constraints} strict native constraints / '
      f'{native_void_warnings} exact named-void warnings / {native_for_gaps} exact for-typedef grammar gaps; nested callbacks, '
      f'own/later declarators, trailing returns and body restoration; 128/129 parameters, 256/257 locals, '
      f'no prototype storage; {host}'
      + ('; original C23 support' if native_c23 else '; exact legacy keyword absence (no source rewriting)')
      + ('; QBE/runtime and 24 both-direction mixed-stack ABI arrangements passed' if qbe else ''))
