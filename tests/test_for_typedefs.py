"""C23 loop typedefs are scoped through clause-1, condition, step and body."""
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
    programs.append(f'int main(void) {{ int done=0; int result=0; for(typedef {name} T,T,*P,A[2];!done;done=1) {{ A a; P p=&a[1]; *p={expected}; result=*p=={expected}?42:1; }} return result; }}')
    programs.append(f'int main(void) {{ int done=0; int result=0; for(typedef {name} T;(T)done<1;done+=(T)1) {{ T x={expected}; result=x=={expected}?42:1; }} return result; }}')
programs += [
    'int main(void) { int done=0; int result=0; for(typedef int T;!done;done=1) { T x=40; for(typedef T U;x<42;x+=(U)1) { U y=1; if(y!=1) return 1; } result=x; } return result; }',
    'int main(void) { int done=0; for(typedef int T;!done;done=1) { T x=1; if(sizeof(T)!=4 || x!=1) return 1; } done=0; for(typedef long T;!done;done=1) { T x=42; if(sizeof(T)!=8 || x!=42) return 1; } return 42; }',
    'int main(void) { int done=0; for(typedef int T;!done;done=1) { T x=1; if(x!=1) return 1; } typedef long T; T x=42; return sizeof(T)==8?x:1; }',
    'int f(void) { for(typedef int T;;) { T x=42; return x; } } typedef long T; int main(void) { T x=0; return f()+x; }',
    'int f(int x) { return x; } int main(void) { for(typedef int T,F(T),(*P)(T);;) { P p=f; F *q=p; return q(42); } }',
    'void f(void) { return; } int main(void) { for(typedef void V,F(V),*P;;) { F *p=f; P q=0; p(); return q==0?42:1; } }',
    'int main(void) { for(typedef int T,A[sizeof(T)],(*P)[sizeof(T)];;) { A a; P p=&a; (*p)[3]=42; return a[3]; } }',
    'int main(void) { int x=0; for(typedef int T;x<42;x+=(T)1) { if(x<41) continue; break; } return x+1; }',
    'int main(void) { for(typedef int T;;) { goto done; } done: return 42; }',
    'int main(void) { int x=0; for(typedef int T;sizeof(T)==4;) { x=42; break; } return x; }',
]
programs += [
    'typedef long T; int main(void) { int x=0; for(typedef int T;x<42;x+=(T)1) { if(sizeof(T)!=4) return 1; } return sizeof(T)==8?x:1; }',
    'int main(void) { typedef int T; for(typedef long T;;) { T x=42; return sizeof(T)==8?x:1; } }',
    'typedef long T; int main(void) { int x=40; for(typedef int T;x<42;x+=(T)1) { typedef char T; T y=1; if(sizeof(T)!=1 || y!=1) return 1; } return sizeof(T)==8?x:1; }',
    'typedef long T; int main(void) { for(typedef int T;;) { for(typedef char T;;) { T x=42; if(sizeof(T)!=1 || x!=42) return 1; break; } if(sizeof(T)!=4) return 1; break; } return sizeof(T)==8?42:1; }',
    'typedef int T; int main(void) { T x=42; for(typedef T *T,*P;;) { P p=&x; if(*p!=42) return 1; break; } return sizeof(T)==4?x:1; }',
]
programs += [
    'int f(void) { return 42; } int main(void) { int done=0; for(typedef int f;!done;done=(f)1) { f x=42; if(x!=42) return 1; } return f(); }',
    'int f(void) { return 42; } int main(void) { int (*p)(void)=f; for(typedef int f(void);;) { f *q=p; if(q()!=42) return 1; break; } return f(); }',
]
programs += [
    'int main(void) { int T=40; int *p=&T; for(typedef int T;*p<42;*p+=(T)1) { T x=1; if(x!=1) return 1; } return T; }',
    'int f(int T) { int *p=&T; for(typedef long T;*p<42;*p+=(T)1) { T x=2; if(sizeof(T)!=8 || x!=2) return 1; } return T; } int main(void) { return f(40); }',
]
c23_programs = [
    'int main(void) { for(typedef typeof(nullptr) N,N,*P;;) { N n=0; P p=&n; return *p==nullptr?42:1; } }',
    'int main(void) { for(typedef typeof_unqual(const int) T;;) { T x=40; x+=2; return x; } }',
    'int f(int x) { return x; } int main(void) { for(typedef int T,F(typeof(T));;) { F *p=f; return p(42); } }',
    'int main(void) { int done=0; for(typedef int T;!done;done=(typeof(T))1) { T x=42; if(x!=42) return 1; } return 42; }',
]
constraints = [
    ('int main(void) { for(typedef int T,T[2];;) return 0; }','typedef redeclaration has different type'),
    ('int main(void) { for(typedef int A[],A[2];;) return 0; }','typedef redeclaration has different type'),
    ('int main(void) { for(typedef int F(int),F(long);;) return 0; }','typedef redeclaration has different type'),
    ('int main(void) { for(typedef int T=1;;) return 0; }','typedef declarations cannot have initializers'),
]
subset_errors = [
    ('int main(void) { for(typedef int T;;) { int T=42; } }','shadowing a typedef'),
]
with tempfile.TemporaryDirectory(prefix='kcc for typedefs ') as directory:
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
    native.write_text('int main(void) { for(typedef int T;;) return 42; }\n')
    probe = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
    native_for_typedef = probe.returncode == 0
    if not native_for_typedef:
        errors = re.findall(r'error: ([^\n]+)',probe.stderr.replace('‘', "'").replace('’', "'"))
        assert errors in [["declaration of non-variable 'T' in 'for' loop initial declaration"],
                          ["non-variable declaration in 'for' loop"]],probe.stderr
    for text in programs+c23_programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if native_for_typedef and (text in programs or native_c23):
            native.write_text(text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)], capture_output=True, text=True, timeout=10)
            assert result.returncode == 0,(text,result.stderr)
            assert subprocess.run([str(executable)],timeout=5).returncode == 42,text
            native_programs += 1
    for text,message in constraints:
        compile_source(text,False,message)
        if native_for_typedef:
            native.write_text(text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
            assert result.returncode != 0,text
            native_constraints += 1
    for text,message in subset_errors:
        compile_source(text,False,message)
    for text in ['int main(void) { for(typedef int T;0;) ; T x; return 42; }',
                 'int main(void) { for(typedef int T;0;) ; for(T x=0;0;) ; return 42; }',
                 'int main(void) { for(typedef int F(U),U;;) return 42; }']:
        compile_source(text,False,'error:')
    il_only = compile_source('int f(void) { for(typedef int T,*P,A[2],F(T);;) return 42; }')
    assert 'alloc' not in il_only and 'data ' not in il_only
    # Each alias and the containing for block item consume one item.
    # A bare return body is a statement, not a second block item.
    for amount in [4095,4096]:
        compile_source('int main(void) { for(typedef int '+','.join(f'T{i}' for i in range(amount))+';;) return 42; }',amount==4095,
                       '' if amount==4095 else 'function body exceeds item limit (4096)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = 'int a,int b,int c,int d,int e,int f,int g,int h'
        aliases = f'typedef {name} result,result,signature({params}),signature({params});'
        helper = (f'{name} pick({params}) {{ '
                  f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        definition = (f'{name} pick({params}) {{ for({aliases} ;) {{ '
                      f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }} }}')
        driver = f'int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        block_driver = f'{name} pick({params}); int main(void) {{ for({aliases} ;) {{ signature *p=pick; return p(1,2,3,4,5,6,7,8)=={expected}?42:1; }} }}'
        for kcc_text,host_text in [(definition,f'{name} pick({params}); '+driver),(block_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'For typedefs passed: {len(programs)} base-type + {len(c23_programs)} C23 originals, {native_programs} strict native agreements, {native_constraints} native constraints; explicit shadowing limits, 4096 items, loop lifetime and no alias storage; {host}'
      + ('; original C23 for-typedef support' if native_for_typedef else '; exact native for-typedef grammar gap (not an agreement)')
      + ('; QBE/runtime and 24 mixed-stack primitive ABI arrangements passed' if qbe else ''))
