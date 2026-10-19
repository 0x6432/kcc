"""Inferred auto and register are independent specifiers, not copied type flags.

Only defined curated positives execute; constraints, UB and boundaries compile only.
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
programs = []
for name in integers:
    value = '1' if name == '_Bool' else '42'
    for specifiers in ['auto register', 'register auto']:
        programs.append(f'int main(void) {{ {specifiers} x=({name}){value}; typeof(x) copy=x; {name} *p=&copy; return *p=={value} && sizeof(x)==sizeof({name})?42:1; }}')
programs += [
    'int main(void) { const register auto x=42; return x; }',
    'int main(void) { register const auto x=42; return x; }',
    'int main(void) { register auto const x=42; return x; }',
    'int main(void) { const auto register x=42; return x; }',
    'int main(void) { auto const register x=42; return x; }',
    'int main(void) { auto register const x=42; return x; }',
    'int main(void) { register auto x=18446744073709551615ULL; return x==18446744073709551615ULL?42:1; }',
    'int main(void) { auto register x=9223372036854775807L; return x==9223372036854775807L?42:1; }',
    'int main(void) { const int x=40; auto register y=x; y+=2; auto z=y; int *p=&z; return *p; }',
    'int main(void) { const register auto x=40; typeof_unqual(x) y=x+2; int *p=&y; return *p; }',
    'int main(void) { int a=42; auto register p=&a; return *p; }',
    'int main(void) { int a=42; register auto p=&a; auto q=&*p; return *q; }',
    'int main(void) { const int a=42; auto register p=&a; const int *q=p; return *q; }',
    'int main(void) { int a[2]; a[1]=42; register auto p=a; return p[1]; }',
    'int main(void) { int a[2][3]; a[1][2]=42; auto register p=a; return p[1][2]; }',
    'int main(void) { register auto s="*"; auto p=s; char **q=&p; return **q; }',
    'int pick(int x) { return x; } int main(void) { auto register f=pick; return f(42); }',
    'int pick(void) { return 42; } int main(void) { register auto f=&pick; return f(); }',
    'int step(int *p) { *p+=1; return *p; } int main(void) { int n=40; auto register x=step(&n); return n==41?x+1:1; }',
    'int main(void) { int n=40; register auto x=(n+=1); return n==41?x+1:1; }',
    'int main(void) { auto register x=(40,42); return x; }',
    'int main(void) { register auto (x)=42; return x; }',
    'int main(void) { int x=40; { auto register x=2; if(x!=2) return 1; } return x+2; }',
    'int main(void) { int i=40; for(register auto i=0;i<2;i++) {} return i+2; }',
    'int main(void) { int x=40; for(auto register i=0;i<2;i++) x++; return x; }',
    'int x(void) { return 40; } int main(void) { auto p=x; { auto register x=2; if(x!=2) return 1; } return p()+2; }',
    'int main(void) { register auto p=nullptr; auto q=p; typeof(nullptr) *r=&q; return *r==nullptr?42:1; }',
    '#define STORE auto register\nint main(void) { STORE x=42; return x; }',
]
unavailable = []
for specifiers in ['auto register', 'register auto']:
    for initializer in ['x', 'sizeof(x)', '(typeof(x))0', '0?x:42', '1?42:x', 'x()']:
        unavailable.append(f'int x(void) {{ return 42; }} int main(void) {{ {specifiers} x={initializer}; return 0; }}')
constraints = [
    ('int f(register auto x);', 'auto is not permitted'),
    ('int main(void) { register x=42; return 0; }', 'expected type specifier with qualifier'),
    ('int main(void) { register const x=42; return 0; }', 'expected type specifier with qualifier'),
    ('int main(void) { auto register x=42; return sizeof(&x); }', 'cannot take the address'),
    ('int main(void) { register auto x=42; typeof(&x) p; return 0; }', 'cannot take the address'),
    ('int main(void) { int a=42; auto register p=&a; return sizeof(&p); }', 'cannot take the address'),
    ('int main(void) { const register auto x=42; x=1; return 0; }', 'modifiable'),
    ('int main(void) { auto register int x=42; return 0; }', 'combined auto storage requires an inferred type'),
    ('int main(void) { register auto long x=42; return 0; }', 'combined auto storage requires an inferred type'),
    ('typedef int T; int main(void) { T auto register x=42; return 0; }', 'combined auto storage requires an inferred type'),
    ('typedef int T; int main(void) { register auto T x=42; return 0; }', 'combined auto storage requires an inferred type'),
    ('int main(void) { auto register typeof(int) x=42; return 0; }', 'combined auto storage requires an inferred type'),
    ('int main(void) { auto register void x; return 0; }', 'combined auto storage requires an inferred type'),
    ('int main(void) { auto register auto x=42; return 0; }', 'duplicate auto'),
    ('int main(void) { register auto register x=42; return 0; }', 'duplicate register'),
    ('int main(void) { auto typedef int T; return 0; }', 'multiple storage-class'),
    ('int main(void) { typedef auto int T; return 0; }', 'multiple storage-class'),
    ('int main(void) { register typedef int T; return 0; }', 'multiple storage-class'),
    ('int main(void) { typedef register int T; return 0; }', 'multiple storage-class'),
    ('int main(void) { auto register typedef int T; return 0; }', 'multiple storage-class'),
    ('int main(void) { typedef auto register int T; return 0; }', 'multiple storage-class'),
    ('int main(void) { auto register x=42; typeof(x) y=0; long *p=&y; return 0; }', 'pointer'),
    ('int main(void) { const int a=42; auto register p=&a; *p=1; return 0; }', 'modifiable'),
]
# N3096 6.7p12 UB, not required native constraint diagnostics. Never execute.
ub_refusals = [
    ('int main(void) { auto register x=40,y=x+2; return y; }', 'multiple inferred auto declarators'),
    ('int main(void) { register auto x=1,x=2; return x; }', 'multiple inferred auto declarators'),
    ('int main(void) { int x=1; auto register x=42; return x; }', 'redeclaration'),
]
subset_errors = [
    ('auto register x=42;', 'register storage class requires block scope'),
    ('int main(void) { auto register x; return 0; }', 'requires an assignment initializer'),
    ('int main(void) { register auto *x=0; return 0; }', 'single identifier declarator'),
    ('int main(void) { auto register x[2]=0; return 0; }', 'single identifier declarator'),
    ('int main(void) { register auto x(void)=0; return 0; }', 'single identifier declarator'),
    ('int main(void) { auto register x={42}; return 0; }', 'inferred auto requires an assignment initializer'),
    ('int main(void) { register auto x=(void)42; return 0; }', 'complete scalar or aggregate initializer type'),
    ('int main(void) { register int a[2]; auto register p=a; return 0; }', 'register array-to-pointer conversion'),
]
with tempfile.TemporaryDirectory(prefix='kcc register auto ') as directory:
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
            assert result.returncode == 1 and not result.stdout and message in result.stderr,(text[:1800],message,result.stderr)
        return result.stdout

    def link_run(objects):
        result = subprocess.run([host,*map(str,objects),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        assert result.returncode == 0,result.stderr
        assert subprocess.run([str(executable)],timeout=5).returncode == 42

    native.write_text('int f(void) { auto x=42; return x; }\n')
    probe = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
    native_inference = probe.returncode == 0
    if not native_inference:
        records = re.findall(r'(error|warning|note): ([^\n]+)',probe.stderr.replace('‘', "'").replace('’', "'"))
        assert probe.returncode == 1 and records in [
            [('error', "type defaults to 'int' in declaration of 'x' [-Wimplicit-int]")],
            [('error', 'a type specifier is required for all declarations')],
        ],probe.stderr
    native_programs = native_constraints = 0
    for text in programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if not native_inference:
            continue
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        assert result.returncode == 0,(text,result.stderr)
        assert subprocess.run([str(executable)],timeout=5).returncode == 42,text
        native_programs += 1
    for text in unavailable:
        compile_source(text,False,'inferred name is unavailable in its initializer')
    for text,message in constraints:
        compile_source(text,False,message)
    for text in unavailable+[text for text,_ in constraints]:
        if not native_inference:
            continue
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
        assert result.returncode == 1,(text,result.stderr)
        native_constraints += 1
    for text,message in ub_refusals+subset_errors:
        compile_source(text,False,message)
    for amount in [256,257]:
        compile_source('int f(void) { '+''.join(f'register auto a{i}=(char)0;' for i in range(amount))+' return 42; }',amount==256,
                       '' if amount==256 else 'local limit (256)')
    for amount in [4094,4095]:
        compile_source('int f(void) { register auto x=42; '+'0;'*amount+' return x; }',amount==4094,
                       '' if amount==4094 else 'item limit (4096)')
    for amount in [1048568,1048569]:
        compile_source(f'int f(void) {{ char a[{amount}]; register auto x=(long)42; return x; }}',amount==1048568,
                       '' if amount==1048568 else 'storage limit')
    parameters = ','.join(f'long p{i}' for i in range(128))
    for amount in [128,129]:
        compile_source(f'int f({parameters}) {{ '+''.join(f'register auto a{i}=(char)0;' for i in range(amount))+' return 42; }',amount==128,
                       '' if amount==128 else 'local limit (256)')
    for amount in [1047544,1047545]:
        compile_source(f'int f({parameters}) {{ char a[{amount}]; register auto x=(long)42; return x; }}',amount==1047544,
                       '' if amount==1047544 else 'storage limit')
    for depth in [64,65]:
        compile_source('int f(void) { register auto '+'('*depth+'x'+')'*depth+'=42; return x; }',depth==64,
                       '' if depth==64 else 'nesting limit (64)')
    for depth in [62,63]:
        compile_source('typedef int '+'*'*64+' A; typedef A '+'*'*depth+' B[1]; int f(void) { B a; register auto x=42; return x; }',depth==62,
                       '' if depth==62 else 'depth limit (128)')
    one_local = compile_source('int f(void) { register auto x=42; return x; }')
    assert one_local.count('alloc') == 1 and 'data ' not in one_local
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = 'int a,int b,int c,int d,int e,int f,int g,int h'
        checks = 'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0;'
        helper = f'{name} pick({params}) {{ {checks} return {expected}; }}'
        definition = f'{name} pick({params}) {{ register auto value=({name}){expected}; auto copy=value; {name} *p=&copy; {checks} return *p; }}'
        driver = f'{name} pick({params}); int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        inferred_driver = f'{name} pick({params}); int main(void) {{ register auto value=pick(1,2,3,4,5,6,7,8); auto copy=value; {name} *p=&copy; return *p=={expected}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(inferred_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Register auto inference passed: {len(programs)} C23 originals, {native_programs} strict native agreements, '
      f'{native_constraints} native constraints, {len(unavailable)} unavailable-name barriers, '
      f'{len(ub_refusals)} nonexecuted UB refusals, {len(subset_errors)} subset refusals; '
      f'256 locals incl 128 spills/4096 items/1 MiB storage/64 parenthesis/128 expanded-typedef boundaries; {host}'
      + ('; native inference independently supported' if native_inference else '; exact legacy inference absence (not agreements)')
      + ('; QBE/runtime and 24 both-direction mixed-stack ABI arrangements passed' if qbe else ''))
