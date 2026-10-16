"""Block typedefs have syntax and semantic lifetimes without runtime storage."""
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
    programs.append(f'int main(void) {{ typedef {name} T,T,*P,A[2]; A a; P p=&a[1]; *p={expected}; return *p=={expected}?42:1; }}')
    programs.append(f'int main(void) {{ typedef {name} T; {{ T x={expected}; if(x!={expected}) return 1; }} return 42; }}')
programs += [
    'int main(void) { { typedef int T; T x=42; if(x!=42) return 1; } { typedef long T; T x=42; if(sizeof(T)!=8) return 1; if(x!=42) return 1; } return 42; }',
    'int f(void) { typedef int T; T x=40; return x; } typedef long T; int main(void) { T x=2; return f()+x; }',
    'int f(void) { typedef int T; return sizeof(T); } int main(void) { typedef long T; return f()==4 && sizeof(T)==8?42:1; }',
    'typedef int T; int main(void) { typedef T U,*P,A[2]; A a; P p=&a[1]; *p=42; U x=*p; return x; }',
    'int f(int x) { return x; } int main(void) { typedef int T,F(T),(*P)(T); P p=f; return p(42); }',
    'void f(void) { return; } int main(void) { typedef void V,F(V),*P; F *p=f; P q=0; p(); return q==0?42:1; }',
    'int main(void) { typedef int T; T x=40; { typedef T U; U y=2; x+=y; } return x; }',
    'int main(void) { typedef int T; int x=0; for(T i=0;i<6;i++) { typedef int U; U j=7; x+=j; } return x; }',
    'int main(void) { typedef int T; T x=0; while(x<42) { typedef int U; U y=1; x+=y; } return x; }',
    'int main(void) { typedef int T,A[2],A[2]; A a; a[1]=42; return a[1]; }',
    'int main(void) { typedef int T; { typedef long U; U x=42; if(x!=42) return 1; } typedef long U; U x=42; return x; }',
    'int main(void) { typedef int T; T x=(T)42; return sizeof(T)==4 && _Alignof(T)==4?x:1; }',
]
c23_programs = [
    'int main(void) { typedef typeof(nullptr) N,N,*P; N n=0; P p=&n; return *p==nullptr?42:1; }',
    'int main(void) { typedef const int C; typedef typeof_unqual(C) T; T x=40; x+=2; return x; }',
    'int main(void) { typedef int T; goto T; T: typedef long U; U x=42; return x; }',
    'int main(void) { typedef int T; { typedef typeof(T) U; U x=42; if(x!=42) return 1; } return 42; }',
]
constraints = [
    ('int main(void) { typedef int T; typedef long T; return 0; }','typedef redeclaration has different type'),
    ('int main(void) { typedef int A[],A[2]; return 0; }','typedef redeclaration has different type'),
    ('int main(void) { typedef int F(int),F(long); return 0; }','typedef redeclaration has different type'),
    ('int main(void) { typedef int T=1; return 0; }','typedef declarations cannot have initializers'),
    ('int main(void) { int T=1; typedef int T; return 0; }','typedef name conflicts with prior ordinary declaration'),
    ('int f(int T) { typedef int T; return 0; }','typedef name conflicts with prior ordinary declaration'),
]
subset_errors = [
]
with tempfile.TemporaryDirectory(prefix='kcc block typedefs ') as directory:
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
        definition = (f'{name} pick({params}) {{ {aliases} '
                      f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        driver = f'int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        block_driver = f'{name} pick({params}); int main(void) {{ {aliases} signature *p=pick; return p(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        for kcc_text,host_text in [(definition,f'{name} pick({params}); '+driver),(block_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Block typedefs passed: {len(programs)} standard + {len(c23_programs)} C23 originals, {native_programs} strict native agreements, {native_constraints} native constraints; explicit shadowing limits, 4096 block items, independent external/expanded-depth boundaries and no alias storage; {host}'
      + ('; original C23 support' if native_c23 else '; exact legacy keyword absence (no query aliases)')
      + ('; QBE/runtime and 24 mixed-stack primitive ABI arrangements passed' if qbe else ''))
