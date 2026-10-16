"""Nearest ordinary-name classification and object/alias point of declaration."""
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
    programs.append(f'typedef {name} T; int main(void) {{ T T={expected}; return T=={expected}?42:1; }}')
    programs.append(f'int main(void) {{ typedef {name} T; {{ T T={expected}; if(T!={expected}) return 1; }} T x={expected}; return x=={expected}?42:1; }}')
programs += [
    'typedef int T; int main(void) { int T=42; return T; }',
    'typedef int T,*P; int main(void) { int T=42; P p=&T; return *p; }',
    'typedef long T; int main(void) { int T=sizeof(T); return T==4?42:1; }',
    'typedef char T; int main(void) { long T[sizeof(T)]; T[0]=42; return sizeof(T)==8?T[0]:1; }',
    'typedef long T; int main(void) { T T=40,*P=&T; return *P+2; }',
    'typedef int T; int main(void) { int T=6; T*T; return (T)+36; }',
    'typedef long T; int main(void) { int T=2; int a[sizeof(T)]; a[3]=40; return a[3]+T; }',
    'typedef int T; int main(void) { { int T=40; { typedef long T; T x=2; if(x!=2) return 1; } T+=2; if(T!=42) return 1; } T x=42; return x; }',
    'int main(void) { int T=42; { typedef int T; { int T=1; if(T!=1) return 1; } T x=2; if(x!=2) return 1; } return T; }',
    'typedef int T; int main(void) { typedef long T; { int T=42; if(T!=42) return 1; } T x=42; return x; }',
    'int f(void); int main(void) { typedef int f; { int f=42; if(f!=42) return 1; } f x=42; return x; }',
    'typedef long T; int main(void) { for(int T=0;T<2;T++) {} T x=42; return sizeof(T)==8?x:1; }',
    'typedef long T; int main(void) { int x=40; for(T T=2;T;T--) x++; T y=x; return y; }',
    'typedef int T; int main(void) { int T=40,U=T+2; return U; }',
    'typedef int T; int main(void) { { int T=1; } { T T=42; return T; } }',
    'typedef int T; int main(void) { int T=40; goto T; T: T+=2; return T; }',
    'typedef int T; int f(void) { int T=1; return T; } T main(void) { return f()+41; }',
    'typedef int T; int f(int x) { return x; } int main(void) { int (*T)(int)=f; return T(42); }',
    'typedef int T; int main(void) { int x=42; int *T=&x; return *T; }',
    'typedef const int T; int main(void) { { int T=40; T+=2; if(T!=42) return 1; } T x=42; return x; }',
]
c23_programs = [
    'typedef long T; int main(void) { int T=40; typeof(T) x=T+2; return sizeof(x)==4?x:1; }',
    'typedef int T; int main(void) { const long T=40; typeof_unqual(T) x=T; x+=2; return sizeof(x)==8?x:1; }',
    'typedef long T; int main(void) { typeof(T) T=42; return sizeof(T)==8?T:1; }',
    'typedef long T; int main(void) { typeof(nullptr) T=0; return T==nullptr?42:1; }',
    'typedef int T; int main(void) { goto T; T: int T=42; return T; }',
]
constraints = [
    ('int main(void) { typedef int T; int T=42; return 0; }','ordinary declaration conflicts with typedef name'),
    ('int main(void) { typedef int T; T T=42; return 0; }','ordinary declaration conflicts with typedef name'),
    ('int main(void) { int T=1; typedef int T; return 0; }','typedef name conflicts with prior ordinary declaration'),
    ('typedef int T; int main(void) { int T=1; int T=2; return 0; }','redeclaration of local in this scope'),
    ('typedef int T; int main(void) { int T=1; T x=42; return 0; }','error:'),
    ('typedef int T; int main(void) { int T=1; return (T)42; }','error:'),
    ('typedef int T; int main(void) { int T=1; return sizeof(T *); }','error:'),
    ('typedef int T; int main(void) { int T=1; { typedef long T; return T; } }','typedef name is not an expression'),
]
subset_errors = [
]
with tempfile.TemporaryDirectory(prefix='kcc object typedef shadowing ') as directory:
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
    for text in ['int f(void) { typedef int T; return 42; } T x;',
                 'int main(void) { { typedef int T; } T x; return 42; }',
                 'int main(void) { typedef int F(U),U; return 42; }']:
        compile_source(text,False,'error:')
    il_only = compile_source('int f(void) { typedef int T,*P,A[2],F(T); return 42; }')
    assert 'alloc' not in il_only and 'data ' not in il_only
    for amount in [4095,4096]:
        compile_source('int main(void) { typedef int '+','.join(f'T{i}' for i in range(amount))+'; return 42; }',amount==4095,
                       '' if amount==4095 else 'function body exceeds item limit (4096)')
        compile_source('int main(void) { typedef int '+','.join(['T']*amount)+'; return 42; }',amount==4095,
                       '' if amount==4095 else 'function body exceeds item limit (4096)')
    for amount in [510,511]:
        compile_source('int f(void);'*amount+'int main(void) { typedef int T,*P,A[2]; return 42; }')
    for stars in [63,64]:
        compile_source('int main(void) { typedef int '+'*'*64+' A; typedef A '+'*'*stars+' B; return 42; }',stars==63,
                       '' if stars==63 else 'typedef type exceeds expanded depth limit (128)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = 'int a,int b,int c,int d,int e,int f,int g,int h'
        aliases = f'typedef {name} result,result,signature({params}),signature({params});'
        helper = (f'{name} pick({params}) {{ '
                  f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        definition = (f'typedef {name} value; {name} pick({params}) {{ value value={expected}; if(value!={expected}) return 0; {aliases} '
                      f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        driver = f'int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        block_driver = f'{name} pick({params}); typedef {name} result; int main(void) {{ result result=pick(1,2,3,4,5,6,7,8); return result=={expected}?42:1; }}'
        for kcc_text,host_text in [(definition,f'{name} pick({params}); '+driver),(block_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Object/typedef shadowing passed: {len(programs)} standard + {len(c23_programs)} C23 originals, {native_programs} strict native agreements, {native_constraints} native constraints; point-of-declaration, ordinary-name masks and same-scope conflicts, 4096 block items, independent external/expanded-depth boundaries and no alias storage; {host}'
      + ('; original C23 support' if native_c23 else '; exact legacy keyword absence (no query aliases)')
      + ('; QBE/runtime and 24 mixed-stack primitive ABI arrangements passed' if qbe else ''))
