"""File-scope typedef lists retain source order and one shared specifier base."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root/'build'/'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool','char','signed char','unsigned char','short','unsigned short',
            'int','unsigned','long','unsigned long','long long','unsigned long long']
programs = []
for name in integers:
    expected = '1' if name == '_Bool' else '42'
    programs.append(f'typedef {name} T,*P,A[2],F(T); F f; T f(T x) {{ return x; }} int main(void) {{ A a; P p=&a[1]; *p={expected}; return f(*p)=={expected}?42:1; }}')
    programs.append(f'typedef {name} T,T,*P; int main(void) {{ T x={expected}; P p=&x; return *p=={expected}?42:1; }}')
programs += [
    'typedef int T,A[sizeof(T)],(*P)[sizeof(T)]; int main(void) { A a; P p=&a; (*p)[3]=42; return a[3]; }',
    'typedef void V,F(V),*P; F f; V f(V) { return; } int main(void) { P p=0; f(); return p==0?42:1; }',
    'typedef int T,(*P)(T),F(T); F f; int f(int x) { return x; } int main(void) { P p=f; return p(42); }',
    'typedef int T,A[2][3],(*P)[3]; int main(void) { A a; P p=a; p[1][2]=42; return a[1][2]; }',
    'typedef int T,*const P; int main(void) { T x=42; P p=&x; return *p; }',
    'typedef const int C,*P,A[2]; int main(void) { C x=42; P p=&x; return *p; }',
    'typedef int A[],F(A); F f; int f(int *p) { return p[1]; } int main(void) { int a[2]; a[1]=42; return f(a); }',
    'typedef int T; typedef T A[2],B[sizeof(A)],*P; int main(void) { B b; P p=&b[7]; *p=42; return b[7]; }',
    'typedef int T,A[2],A[2]; int main(void) { A a; a[1]=42; return a[1]; }',
    'typedef int T,F(const int),F(int); F f; int f(int x) { return x; } int main(void) { return f(42); }',
    'typedef int T; int main(void) { goto T; T: return 42; }',
    '#define GROUP T,*P,A[2]\ntypedef int GROUP; int main(void) { A a; P p=&a[1]; *p=42; return a[1]; }',
]
c23_programs = [
    'typedef int T,F(typeof(T)); F f; int f(int x) { return x; } int main(void) { return f(42); }',
    'typedef typeof(nullptr) N,N,*P; int main(void) { N n=0; P p=&n; return *p==nullptr?42:1; }',
    'typedef typeof_unqual(const int) T,A[sizeof(typeof(T))]; int main(void) { A a; a[3]=42; return a[3]; }',
    'typedef void V,F(typeof(V)); F f; void f(void) { return; } int main(void) { f(); return 42; }',
]
constraints = [
    ('typedef int T,T[2];','typedef redeclaration has different type'),
    ('typedef int A[],A[2];','typedef redeclaration has different type'),
    ('typedef int A[2],A[];','typedef redeclaration has different type'),
    ('typedef int A[2],A[3];','typedef redeclaration has different type'),
    ('typedef int *P,(*P)[2];','typedef redeclaration has different type'),
    ('typedef int F(int),F(long);','typedef redeclaration has different type'),
    ('typedef int T=1;','typedef declarations cannot have initializers'),
    ('typedef int T,*P=0;','typedef declarations cannot have initializers'),
    ('typedef int T; int T(void);','function name conflicts with typedef name'),
    ('int T(void); typedef int A,T;','typedef name conflicts with prior ordinary declaration'),
]
subset_errors = [
    ('typedef int T; int main(void) { typedef int A,B; return 42; }','block-scope typedef'),
    ('typedef int T,*P; int main(void) { int T=42; return T; }','shadowing a typedef'),
]
with tempfile.TemporaryDirectory(prefix='kcc typedef lists ') as directory:
    directory = Path(directory)
    source,native,il,assembly,obj,executable = [directory/n for n in ('k.c','h.c','p.ssa','p.s','h.o','p')]

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
        assert subprocess.run([str(executable)], timeout=5).returncode == 42

    native_programs = 0
    native_constraints = 0
    native.write_text('typeof(int) value;\n')
    probe = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)], capture_output=True, text=True, timeout=10)
    native_c23 = probe.returncode == 0
    if not native_c23:
        errors = re.findall(r'error: ([^\n]+)',probe.stderr.replace('‘', "'").replace('’', "'"))
        assert errors in [["return type defaults to 'int' [-Wimplicit-int]", "expected declaration specifiers before 'value'", "expected '{' at end of input"], ['expected function body after function declarator']],probe.stderr
    for text in programs+c23_programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if text in programs or native_c23:
            native.write_text(text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)], capture_output=True, text=True, timeout=10)
            assert result.returncode == 0,(text,result.stderr)
            assert subprocess.run([str(executable)],timeout=5).returncode == 42,text
            native_programs += 1
    for text,message in constraints:
        compile_source(text,False,message)
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
        assert result.returncode != 0,text
        native_constraints += 1
    for text,message in subset_errors:
        compile_source(text,False,message)
    for text in ['typedef int T,;', 'typedef int ,T;', 'typedef int T,*;', 'typedef int T', 'typedef int T P;']:
        compile_source(text, False, 'error:')
    # A later name is not visible to an earlier declarator.
    compile_source('typedef int F(U),U;', False, 'error:')
    assert 'function' not in compile_source('typedef int T,*P,A[2],F(T);')
    for prefix,available in [('',512),('int f(void);',511),('static_assert(1); int f(void);',510)]:
        for amount in [available,available+1]:
            compile_source(prefix+'typedef int '+','.join(f'T{i}' for i in range(amount))+';', amount==available,
                           '' if amount==available else 'translation unit exceeds declaration limit (512)')
            compile_source(prefix+'typedef int '+','.join(['T']*amount)+';',amount==available,
                           '' if amount==available else 'translation unit exceeds declaration limit (512)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = 'int a,int b,int c,int d,int e,int f,int g,int h'
        aliases = f'typedef {name} result,result,signature({params}),signature({params}); signature pick; '
        helper = (f'{name} pick({params}) {{ '
                  f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        definition = (f'result pick({params}) {{ '
                      f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        driver = f'int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        for kcc_text,host_text in [(aliases+definition,f'{name} pick({params}); '+driver),(aliases+driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Typedef declaration lists passed: {len(programs)} standard + {len(c23_programs)} C23 originals, {native_programs} strict native agreements, {native_constraints} native constraints; explicit scope limits, 512/513 unique/repeated/mixed external boundaries and declaration-only IL; {host}'
      + ('; original C23 support' if native_c23 else '; exact legacy keyword absence (no query aliases)')
      + ('; QBE/runtime and 24 mixed-stack primitive ABI arrangements passed' if qbe else ''))
