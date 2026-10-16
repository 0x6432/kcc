"""Fixed register arrays permit direct queries, never implicit address computation."""
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
    programs += [f'int main(void) {{ register {name} a[2]; return sizeof(a)==2*sizeof({name})?42:1; }}',
                 f'typedef {name} A[2][3]; int main(void) {{ A register a,b; return sizeof(a)==6*sizeof({name}) && sizeof(b)==sizeof(a)?42:1; }}']
programs += [
    'int main(void) { register const int a[2][3]; return sizeof(a)==24?42:1; }',
    'int main(void) { register int a[2],x=42,b[3]; return sizeof(a)==8 && sizeof(b)==12?x:1; }',
    'int main(void) { int a[2]; a[1]=42; { register long a[3]; if(sizeof(a)!=24) return 1; } return a[1]; }',
    'int main(void) { register int a[2]; { int a[2]; a[1]=42; if(a[1]!=42) return 1; } return sizeof(a)==8?42:1; }',
    'int main(void) { register int a[2]; { typedef long a; a x=42; if(x!=42) return 1; } return sizeof(a)==8?42:1; }',
    'typedef char T; int main(void) { register T T[sizeof(T)]; return sizeof(T)==1?42:1; }',
    'typedef long T; int main(void) { T register T[sizeof(T)],P[sizeof(T)]; return sizeof(T)==64 && sizeof(P)==512?42:1; }',
    'int main(void) { for(register int a[2],x=42;x;x=0) return sizeof(a)==8?x:1; return 1; }',
    'typedef long A; int main(void) { for(register int A[2];sizeof(A)==8;) break; A x=42; return x; }',
    'int main(void) { register int *a[2]; return sizeof(a)==16?42:1; }',
    'int main(void) { register int (*a[2])(int); return sizeof(a)==16?42:1; }',
    '#define STORE register\nint main(void) { STORE int a[2]; return sizeof(a)==8?42:1; }',
    'int main(void) { int a[2][3]; a[1][2]=42; register int (*p)[3]=a; return p[1][2]; }',
]
c23_programs = [
    'int main(void) { register int a[2][3]; typeof(a) copy; copy[1][2]=42; return sizeof(copy)==sizeof(a)?copy[1][2]:1; }',
    'int main(void) { register int a[2]; typeof_unqual(a) copy; int *p=copy; p[1]=42; return sizeof(a)==8?copy[1]:1; }',
    'int main(void) { register const int a[2]; typeof(a) copy; return sizeof(copy)==sizeof(a)?42:1; }',
    'int main(void) { register int a[2]; typeof(a) register b; return sizeof(b)==sizeof(a)?42:1; }',
    'int main(void) { register typeof(nullptr) a[2]; typeof(a) b; b[1]=0; return sizeof(a)==16 && b[1]==nullptr?42:1; }',
    'int main(void) { register int a[2]; return alignof(typeof(a))==alignof(int)?42:1; }',
]
constraints = [
    ('int main(void) { register int a[2]; return sizeof(&a); }', 'cannot take the address'),
    ('int main(void) { register int a[2]; int (*p)[2]=&((a)); return 0; }', 'cannot take the address'),
    ('int main(void) { register int a[2]; a=0; return 0; }', 'modifiable lvalue'),
    ('int main(void) { register int a[2]; a++; return 0; }', 'modifiable'),
]
c23_constraints = [
    ('int main(void) { register int a[2]; typeof(&a) p; return 0; }', 'cannot take the address'),
]
# These are not executed and are NOT claimed to be native constraint violations.
decay_refusals = [
    'int main(void) { register int a[2]; int *p=a; return 0; }',
    'int main(void) { register int a[2]; return a[0]; }',
    'int main(void) { register int a[2]; int *p=&a[0]; return 0; }',
    'int main(void) { register int a[2]; return a==0; }',
    'int main(void) { register int a[2]; a; return 0; }',
    'int f(int *p); int main(void) { register int a[2]; return f(a); }',
    'int main(void) { register int a[2][3]; return a[0][0]; }',
    'int main(void) { register int a[2]; int *p=1?a:0; return 0; }',
]
subset_errors = [
    ('int main(void) { register int a[2]; return sizeof(a[0]); }', 'register array-to-pointer conversion'),
    ('int main(void) { register int a[2]; typeof(a+0) p; return 0; }', 'register array-to-pointer conversion'),
    ('int f(int n) { register int a[n]; return 0; }', 'variable-length arrays'),
    ('int main(void) { register int a[]; return 0; }', 'must be complete'),
    ('int main(void) { register int a[2]=0; return 0; }', 'array initializers are not supported'),
    ('int f(register int a[2]);', 'register storage is not supported in this context'),
]
with tempfile.TemporaryDirectory(prefix='kcc register arrays ') as directory:
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
    for text in decay_refusals:
        compile_source(text,False,'register array-to-pointer conversion')
    for amount in [256,257]:
        compile_source('int main(void) { register char '+','.join(f'a{i}[1]' for i in range(amount))+'; return 42; }',amount==256,
                       '' if amount==256 else 'local limit (256)')
    for amount in [4094,4095]:
        compile_source('int main(void) { register int a[2]; '+'0;'*amount+' return 42; }',amount==4094,
                       '' if amount==4094 else 'item limit (4096)')
    for amount in [1048576,1048577]:
        compile_source(f'int f(void) {{ register char a[{amount}]; return 42; }}',amount==1048576,
                       '' if amount==1048576 else 'storage limit')
    for depth in [62,63]:
        compile_source('typedef int '+'*'*64+' A; typedef A '+'*'*depth+' B[1]; int f(void) { register B a; return 42; }',depth==62,
                       '' if depth==62 else 'depth limit (128)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = 'int a,int b,int c,int d,int e,int f,int g,int h'
        checks = 'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0;'
        helper = f'{name} pick({params}) {{ {checks} return {expected}; }}'
        definition = f'{name} pick({params}) {{ register {name} scratch[2]; {checks} return sizeof(scratch)==2*sizeof({name})?{expected}:0; }}'
        driver = f'{name} pick({params}); int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        typed_driver = f'{name} pick({params}); int main(void) {{ register {name} a[2]; return sizeof(a)==2*sizeof({name}) && pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(typed_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Register arrays passed: {len(programs)} standard + {len(c23_programs)} C23 originals; '
      f'{native_programs} strict native agreements, {native_constraints} native constraints; '
      f'{len(decay_refusals)} nonexecuted decay refusals, {len(subset_errors)} explicit subset rejections; '
      f'256 locals/4096 items/1 MiB storage/128 depth boundaries; {host}'
      + ('; original C23 keywords' if native_c23 else '; exact legacy keyword absence (not agreements)')
      + ('; QBE/runtime and 24 both-direction mixed-stack ABI arrangements passed' if qbe else ''))
