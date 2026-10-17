"""Scalar register objects retain storage identity without becoming type qualifiers."""
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
    programs += [f'int main(void) {{ register {name} x={value}; return x=={value}?42:1; }}',
                 f'typedef {name} T; int main(void) {{ T register x={value},y=x; return y=={value}?42:1; }}']
for index in range(5):
    specifiers = ['unsigned','long','long','const']
    specifiers.insert(index,'register')
    programs += ['int main(void) { '+' '.join(specifiers)+' x=42; return x; }']
programs += [
    'int main(void) { register int x=40; x+=2; ++x; x--; return x; }',
    'int main(void) { int x=40; register int *p=&x; *p+=2; return &*p==&x?x:1; }',
    'int pick(int x) { return x; } int main(void) { register int (*p)(int)=pick; return (&*p)(42); }',
    'int main(void) { int a[2]; a[1]=42; register int (*p)[2]=&a; return &(*p)[1]==&a[1]?(*p)[1]:1; }',
    'int main(void) { register int x=40,y=x+2; return y; }',
    'typedef long T; int main(void) { register T T=40,*P=0; P=0; return T+2; }',
    'typedef char T; int main(void) { register int (*T)[sizeof(T)]=0; return sizeof(*T)==sizeof(int)?42:1; }',
    'typedef long T; int main(void) { { T register T=42; if(T!=42) return 1; } T x=42; return x; }',
    'typedef long T; int main(void) { for(register int T=0;T<2;T++) {} T x=42; return x; }',
    'int main(void) { register int x=1; { typedef long x; x y=42; if(y!=42) return 1; } return x+41; }',
    'int main(void) { register int x=40; { int x=2; int *p=&x; *p=3; } return x+2; }',
    'int main(void) { int x=40; { register int x=2; x++; } int *p=&x; return *p+2; }',
    'int main(void) { register int x=40; for(register int i=0,j=2;i<j;i++) x++; return x; }',
    'int main(void) { register const int x=42; return sizeof(x)==sizeof(int)?x:1; }',
    '#define register int\nint main(void) { register x=42; return x; }',
    '#define STORE register\nint main(void) { STORE int x=42; return x; }',
    'int f(void) { return 42; } int main(void) { int (*p)(void)=f; register int f=2; return f==2?p():1; }',
    'int f(int x) { { register int x=2; if(x!=2) return 1; } return x; } int main(void) { return f(42); }',
]
c23_programs = [
    'int main(void) { register int x=40; typeof(x) y=2; int *p=&y; return x+*p; }',
    'int main(void) { const register int x=40; register typeof_unqual(x) y=1; y++; return x+y; }',
    'int main(void) { register bool x=true; return x?42:1; }',
    'int main(void) { register typeof(nullptr) x=0; return x==nullptr?42:1; }',
    'int main(void) { register int x=42; return alignof(typeof(x))==alignof(int)?x:1; }',
]
constraints = [
    ('typedef long T; int main(void) { T register T=40,*P=&T; return 0; }', 'cannot take the address'),
    ('register int x;', 'requires block scope'),
    ('register int f(void);', 'requires block scope'),
    ('int main(void) { register int f(void); return 0; }', 'requires an object type'),
    ('int main(void) { register register int x; return 0; }', 'duplicate register storage-class'),
    ('int main(void) { typedef register int T; return 0; }', 'multiple storage-class'),
    ('int main(void) { register int typedef T; return 0; }', 'multiple storage-class'),
    ('int main(void) { register int x=0; int *p=&x; return 0; }', 'cannot take the address'),
    ('int main(void) { register int x=0; return sizeof(&((x))); }', 'cannot take the address'),
    ('int main(void) { int a[2]; register int *p=a; return sizeof(&p); }', 'cannot take the address'),
    ('int main(void) { register const int x=0; x=1; return 0; }', 'modifiable'),
    ('int main(void) { register int x=0; int x=1; return 0; }', 'redeclaration'),
    ('int main(void) { typedef int T; register int T=1; return 0; }', 'ordinary declaration conflicts'),
    ('int main(void) { return sizeof(register int); }', 'not supported in this context'),
    ('int main(void) { return (register int)42; }', 'not supported in this context'),
]
c23_constraints = [
    ('int main(void) { register int x=0; typeof(&x) p; return 0; }', 'cannot take the address'),
    ('int main(void) { register int x=0; typeof_unqual(&x) p; return 0; }', 'cannot take the address'),
]
subset_errors = [
]
def native_keyword_macro_gap(text, status, diagnostics):
    # C permits keyword-named macros outside the standard-header restrictions.
    # Clang's optional -Wkeyword-macro is promoted by -pedantic-errors here.
    if text != '#define register int\nint main(void) { register x=42; return x; }' or status != 1:
        return False
    records = re.findall(r'(fatal error|error|warning|note): ([^\n]+)', diagnostics)
    return records == [('error', 'keyword is hidden by macro definition [-Werror,-Wkeyword-macro]')]


macro_diagnostic = 'test.c:1:9: error: keyword is hidden by macro definition [-Werror,-Wkeyword-macro]\n'
assert native_keyword_macro_gap(programs[-4], 1, macro_diagnostic)
assert not native_keyword_macro_gap(programs[0], 1, macro_diagnostic)
assert not native_keyword_macro_gap(programs[-4], -11, macro_diagnostic)
assert not native_keyword_macro_gap(programs[-4], 1, macro_diagnostic+'test.c:1:1: note: unrelated\n')


with tempfile.TemporaryDirectory(prefix='kcc register scalars ') as directory:
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
    native_programs = native_constraints = native_macro_gaps = 0
    for text in programs+c23_programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if text in c23_programs and not native_c23:
            continue
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        if native_keyword_macro_gap(text,result.returncode,result.stderr):
            native_macro_gaps += 1
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
    for amount in [256,257]:
        compile_source('int main(void) { register int '+','.join(f'x{i}' for i in range(amount))+'; return 42; }',amount==256,
                       '' if amount==256 else 'local limit (256)')
    for amount in [4094,4095]:
        compile_source('int main(void) { register int x; '+'0;'*amount+' return 42; }',amount==4094,
                       '' if amount==4094 else 'item limit (4096)')
    for extra in ['',',y']:
        compile_source('int f(void) { char a[1048568]; register long x'+extra+'; return 42; }',not extra,
                       '' if not extra else 'storage limit')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = 'int a,int b,int c,int d,int e,int f,int g,int h'
        checks = 'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0;'
        helper = f'{name} pick({params}) {{ {checks} return {expected}; }}'
        definition = f'{name} pick({params}) {{ register {name} x={expected}; {checks} return x; }}'
        driver = f'{name} pick({params}); int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        typed_driver = f'{name} pick({params}); int main(void) {{ register {name} x=pick(1,2,3,4,5,6,7,8); return x=={expected}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(typed_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Register scalars passed: {len(programs)} standard + {len(c23_programs)} C23 originals; '
      f'{native_programs} strict native agreements, {native_macro_gaps} exact keyword-macro diagnostic gaps, {native_constraints} native constraints, {len(subset_errors)} explicit subset rejections; '
      f'256 locals/4096 items/1 MiB storage boundaries; {host}'
      + ('; original C23 keywords' if native_c23 else '; exact legacy keyword absence (not agreements)')
      + ('; QBE/runtime and 24 both-direction mixed-stack ABI arrangements passed' if qbe else ''))
