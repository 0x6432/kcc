"""A typedef may hide an outer object, but cannot redeclare a same-scope one."""
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
    programs.append(f'int main(void) {{ int T=40; int *p=&T; {{ typedef {name} T,T; T x={expected}; if(x!={expected}) return 1; *p+=2; }} return T; }}')
    programs.append(f'int f(int T) {{ int *p=&T; {{ typedef {name} T; T x={expected}; if(x!={expected}) return 1; *p+=2; }} return T; }} int main(void) {{ return f(40); }}')
programs += [
    'int main(void) { int T=40; { typedef long T; T x=2; { typedef char T; T y=1; if(sizeof(T)!=1 || y!=1) return 1; } if(sizeof(T)!=8 || x!=2) return 1; } T+=2; return T; }',
    'int f(int T) { { typedef int T; T x=2; if(x!=2) return 1; } T+=2; return T; } int main(void) { return f(40); }',
    'int main(void) { int T[2]; T[1]=42; { typedef long T[3]; T x; x[2]=1; if(sizeof(T)!=24 || x[2]!=1) return 1; } return sizeof(T)==8?T[1]:1; }',
    'int f(int x) { return x; } int main(void) { int (*T)(int)=f; { typedef long T; T x=2; if(x!=2) return 1; } return T(42); }',
    'int main(void) { int T=40; int *p=&T; { typedef void T; T *q=p; int *r=q; *r+=2; } return T; }',
    'int f(int T) { { typedef long T; T x=2; if(x!=2) return 1; } { typedef char T; T y=1; if(y!=1) return 1; } return T; } int main(void) { return f(42); }',
    'int main(void) { int T=42; { typedef int T; goto done; } done: return T; }',
    'int main(void) { int T=40; int *p=&T; while(*p<42) { typedef long T; T y=1; *p+=y; } return T; }',
    'int main(void) { int T=40; int *p=&T; for(int i=0;i<2;i++) { typedef int T; T x=1; *p+=x; } return T; }',
]
c23_programs = [
    'int main(void) { int T=40; { typedef typeof(T) T; T x=2; if(sizeof(T)!=4 || x!=2) return 1; } return T+2; }',
    'int f(const int T) { { typedef typeof_unqual(T) T; T x=40; x+=2; if(x!=42) return 1; } return T; } int main(void) { return f(42); }',
    'int main(void) { int T=42; { typedef typeof(nullptr) T; T x=0; if(x!=nullptr) return 1; } return T; }',
    'int main(void) { int T=42; { goto T; T: typedef int T; T x=1; if(x!=1) return 1; } return T; }',
]
constraints = [
    ('int main(void) { int T=1; typedef int T; return 0; }','typedef name conflicts with prior ordinary declaration'),
    ('int f(int T) { typedef int T; return 0; }','typedef name conflicts with prior ordinary declaration'),
    ('int f(int T) { { typedef int T; typedef long T; } return 0; }','typedef redeclaration has different type'),
    ('int main(void) { int T=1; { typedef int T=1; } return 0; }','typedef declarations cannot have initializers'),
    ('int main(void) { int T=1; { typedef int T; return T; } }','typedef name is not an expression'),
    ('int main(void) { int T=1; { typedef int T; return &T==0; } }','typedef name is not an expression'),
    ('int main(void) { int T=1; { typedef int T; return sizeof T; } }','typedef name is not an expression'),
    ('int f(int x) { return x; } int main(void) { int (*T)(int)=f; { typedef int T; return T(42); } }','typedef name is not an expression'),
]
subset_errors = [
]
with tempfile.TemporaryDirectory(prefix='kcc typedef object shadowing ') as directory:
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
        definition = (f'{name} pick({params}) {{ {{ typedef {name} a; a value={expected}; if(value!={expected}) return 0; }} {aliases} '
                      f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        driver = f'int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        block_driver = f'{name} pick({params}); int main(void) {{ int result=1; {{ {aliases} signature *p=pick; if(p(1,2,3,4,5,6,7,8)!={expected}) return 1; }} return result==1?42:1; }}'
        for kcc_text,host_text in [(definition,f'{name} pick({params}); '+driver),(block_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Typedef/object shadowing passed: {len(programs)} standard + {len(c23_programs)} C23 originals, {native_programs} strict native agreements, {native_constraints} native constraints; same-scope conflicts and hidden-value checks, 4096 block items, independent external/expanded-depth boundaries and no alias storage; {host}'
      + ('; original C23 support' if native_c23 else '; exact legacy keyword absence (no query aliases)')
      + ('; QBE/runtime and 24 mixed-stack primitive ABI arrangements passed' if qbe else ''))
