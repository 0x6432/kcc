"""Local name reservation, storage completion and initialization preserve one-pass order."""
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
    programs += [f'int main(void) {{ {name} x=sizeof(x); return x==sizeof({name})?42:1; }}',
                 f'int main(void) {{ auto {name} x={value}; register {name} y=x; {name} *p=&x; return *p=={value} && y=={value}?42:1; }}']
programs += [
    'typedef char T; int main(void) { long T[sizeof(T)]; T[0]=42; return sizeof(T)==8?T[0]:1; }',
    'typedef char T; int main(void) { long T=sizeof(T); return T==8?42:1; }',
    'typedef long T; int main(void) { T T=40,*P=&T; *P+=2; return T; }',
    'int id(int x) { return x; } int main(void) { char *s="*"; int (*p)(int)=id; return p(*s); }',
    'int main(void) { int a[2],*p=a; p[0]=40; p[1]=2; return a[0]+a[1]; }',
    'int main(void) { register int x=sizeof(x); return x+38; }',
    'int pick(int a[2]) { int *p=a; return p[1]; } int main(void) { int a[2]; a[1]=42; return pick(a); }',
    'int id(int x) { return x; } int apply(int f(int),int x) { return f(x); } int main(void) { return apply(id,42); }',
    'int main(void) { auto int x=40; for(register int i=0;i<2;i++) x++; return x; }',
    'typedef long T; int main(void) { for(auto int T=0;T<2;T++) {} T x=42; return x; }',
    'int f(void) { return 42; } int main(void) { int (*p)(void)=f; register int f=2; return f==2?p():1; }',
    'int main(void) { int x=40; { int x=sizeof(x); if(x!=4) return 1; } return x+2; }',
]
c23_programs = [
    'int step(int *p) { *p+=1; return *p; } int main(void) { int n=40; typeof(step(&n)) value=n+2; return n==40?value:1; }',
    'int main(void) { typeof("x") a; return sizeof(a)==2?42:1; }',
    'int main(void) { const int x=42; typeof_unqual(x) y=x; int *p=&y; return *p; }',
    'int main(void) { register int x=40; typeof(x) y=x+2; int *p=&y; return *p; }',
    'int main(void) { register int a[2]; typeof(a) b; b[1]=42; return b[1]; }',
    'int main(void) { typeof(nullptr) x=0; typeof(x) y=x; return y==nullptr?42:1; }',
]
constraints = [
    ('int main(void) { int x=0; int x=1; return 0; }', 'redeclaration'),
    ('int main(void) { typedef int T; int T=1; return 0; }', 'ordinary declaration conflicts'),
    ('int main(void) { register int x=0; int *p=&x; return 0; }', 'cannot take the address'),
    ('int main(void) { const int x=0; x=1; return 0; }', 'modifiable'),
    ('int main(void) { int x=0; int *p=x; return 0; }', 'unsupported pointer conversion'),
    ('int main(void) { int a[2]; a=0; return 0; }', 'modifiable'),
    ('int main(void) { int *p=1; return 0; }', 'unsupported pointer conversion'),
]
c23_constraints = [
    ('int main(void) { register int x=0; typeof(&x) p; return 0; }', 'cannot take the address'),
]
subset_errors = [
    ('int f(int n) { int a[n]; return 0; }', 'variable-length arrays'),
    ('int main(void) { int a[2]=0; return 0; }', 'array initializers are not supported'),
]
with tempfile.TemporaryDirectory(prefix='kcc binding phases ') as directory:
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
    native_programs = native_constraints = 0
    for text in programs+c23_programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if text in c23_programs and not native_c23:
            continue
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],capture_output=True,text=True,timeout=10)
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
        compile_source('int main(void) { auto char '+','.join(f'a{i}[1]' for i in range(amount))+'; return 42; }',amount==256,
                       '' if amount==256 else 'local limit (256)')
    for amount in [4094,4095]:
        compile_source('int main(void) { auto int a[2]; '+'0;'*amount+' return 42; }',amount==4094,
                       '' if amount==4094 else 'item limit (4096)')
    for amount in [1048576,1048577]:
        compile_source(f'int f(void) {{ auto char a[{amount}]; return 42; }}',amount==1048576,
                       '' if amount==1048576 else 'storage limit')
    for depth in [62,63]:
        compile_source('typedef int '+'*'*64+' A; typedef A '+'*'*depth+' B[1]; int f(void) { B a; return 42; }',depth==62,
                       '' if depth==62 else 'depth limit (128)')
    parameters = ','.join(f'long p{i}' for i in range(128))
    for amount in [128,129]:
        compile_source('int f('+parameters+') { int '+','.join(f'x{i}' for i in range(amount))+'; return 42; }',amount==128,
                       '' if amount==128 else 'local limit (256)')
    for amount in [1047552,1047553]:
        compile_source(f'int f({parameters}) {{ char a[{amount}]; return 42; }}',amount==1047552,
                       '' if amount==1047552 else 'storage limit')
    one_local = compile_source('typedef int T; int f(void) { T x=42; return x; }')
    assert one_local.count('alloc') == 1 and 'data ' not in one_local
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = 'int a,int b,int c,int d,int e,int f,int g,int h'
        checks = 'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0;'
        helper = f'{name} pick({params}) {{ {checks} return {expected}; }}'
        definition = f'{name} pick({params}) {{ {name} value={expected}; register {name} copy=value; {name} *p=&value; {checks} return copy==*p?copy:0; }}'
        driver = f'{name} pick({params}); int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        typed_driver = f'{name} pick({params}); int main(void) {{ auto {name} value=pick(1,2,3,4,5,6,7,8); {name} *p=&value; return *p=={expected}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(typed_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Local binding phases passed: {len(programs)} standard + {len(c23_programs)} C23 originals; '
      f'{native_programs} strict native agreements, {native_constraints} native constraints, {len(subset_errors)} subset refusals; '
      f'self-size/ordinary initializer visibility, one-pass decay/storage, 256 locals incl 128 spills/4096 items/1 MiB storage/128 expanded-typedef depth boundaries; {host}'
      + ('; original C23 keywords' if native_c23 else '; exact legacy keyword absence (not agreements)')
      + ('; QBE/runtime and 24 both-direction mixed-stack ABI arrangements passed' if qbe else ''))
