"""A scoped typedef hides a function symbol without becoming a runtime value."""
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
    programs.append(f'int item(void) {{ return 42; }} int main(void) {{ typedef {name} item; item x={expected}; return x=={expected}?42:1; }}')
    programs.append(f'int item(void) {{ return 42; }} int main(void) {{ int (*p)(void)=item; {{ typedef {name} item; item x={expected}; if(x!={expected} || p()!=42) return 1; }} return item(); }}')
programs += [
    'int main(void) { typedef int main; main value=42; return value; }',
    'int f(int x) { typedef long f; f y=x; return y; } int main(void) { return f(42); }',
    'int f(void); int main(void) { typedef int f,*P,A[2]; A a; P p=&a[1]; *p=42; return *p; }',
    'int f(void) { return 42; } int main(void) { { typedef void f; f *p=0; if(p!=0) return 1; } return f(); }',
    'int f(void) { return 42; } int main(void) { { typedef int f; f x=1; { typedef long f; f y=2; if(sizeof(f)!=8 || y!=2) return 1; } if(sizeof(f)!=4 || x!=1) return 1; } return f(); }',
    'int f(void) { return 42; } int main(void) { { typedef int f; f x=1; if(x!=1) return 1; } { typedef char f; f x=2; if(x!=2) return 1; } return f(); }',
    'int f(void) { typedef int f; f x=42; return x; } int g(void) { return f(); } int main(void) { return g(); }',
    'int f(void) { return 42; } int main(void) { int (*p)(void)=f; { typedef int f(void); f *q=p; if(q()!=42) return 1; } return f(); }',
    'int f(void) { return 42; } int main(void) { { typedef const int f; f x=42; if(x!=42) return 1; } return f(); }',
    'int f(void) { return 42; } int main(void) { int x=0; while(x<42) { typedef int f; f y=1; x+=y; } return f(); }',
    'int f(void) { return 42; } int main(void) { { typedef int f; goto done; } done: return f(); }',
]
c23_programs = [
    'int f(void); int main(void) { typedef typeof(f) f; f *p=0; return p==0?42:1; }',
    'int f(void) { return 42; } int main(void) { { typedef typeof(nullptr) f; f x=0; if(x!=nullptr) return 1; } return f(); }',
    'int f(void); int main(void) { typedef typeof_unqual(const int) f; f x=40; x+=2; return x; }',
    'int f(void) { return 42; } int main(void) { goto f; f: typedef int f; f x=42; return x; }',
]
constraints = [
    ('int f(void); typedef int f;','typedef name conflicts with prior ordinary declaration'),
    ('typedef int f; int f(void);','function name conflicts with typedef name'),
    ('int f(void); int main(void) { typedef int f; typedef long f; return 0; }','typedef redeclaration has different type'),
    ('int f(void); int main(void) { typedef int f=1; return 0; }','typedef declarations cannot have initializers'),
    ('int f(void); int main(void) { typedef int f; return f(); }','typedef name is not an expression'),
    ('int f(void); int main(void) { typedef int f; return (f)(); }','error:'),
    ('int f(void); int main(void) { typedef int f; return f; }','typedef name is not an expression'),
    ('int f(void); int main(void) { typedef int f; return &f==0?42:1; }','typedef name is not an expression'),
    ('int f(void); int main(void) { typedef int f; int (*p)(void)=f; return 0; }','typedef name is not an expression'),
    ('int f(void); int main(void) { typedef int f; return sizeof f; }','typedef name is not an expression'),
    ('typedef int T; int main(void) { return T(); }','typedef name is not an expression'),
]
subset_errors = [
    ('int main(void) { int T=42; { typedef int T; } return 42; }','block typedef shadowing an object'),
    ('int f(int T) { { typedef long T; } return 42; }','block typedef shadowing an object'),
    ('int f(void); int main(void) { typedef int f; { int f=42; } return 42; }','shadowing a typedef'),
]
with tempfile.TemporaryDirectory(prefix='kcc typedef function shadowing ') as directory:
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
        definition = (f'{name} pick({params}) {{ typedef {name} pick; {aliases} '
                      f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        driver = f'int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        block_driver = f'{name} pick({params}); int main(void) {{ {aliases} signature *p=pick; {{ typedef {name} pick; pick x=p(1,2,3,4,5,6,7,8); return x=={expected}?42:1; }} }}'
        for kcc_text,host_text in [(definition,f'{name} pick({params}); '+driver),(block_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Typedef/function shadowing passed: {len(programs)} standard + {len(c23_programs)} C23 originals, {native_programs} strict native agreements, {native_constraints} native constraints; hidden-name value rejection and object-shadowing limits, 4096 block items, independent external/expanded-depth boundaries and no alias storage; {host}'
      + ('; original C23 support' if native_c23 else '; exact legacy keyword absence (no query aliases)')
      + ('; QBE/runtime and 24 mixed-stack primitive ABI arrangements passed' if qbe else ''))
