"""Traditional C null constants: typed conversions, selected effects and ABI."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short', 'unsigned short',
            'int', 'unsigned', 'long', 'unsigned long', 'long long', 'unsigned long long']
zero_forms = [f'({name})0' for name in integers] + [
    '0', '0L', '0ULL', "'a'-'a'", '-0', '1-1', '~0U+1U',
    '(unsigned char)256', '4294967295U+1U', '18446744073709551615ULL+1ULL',
    'sizeof(int)-4', '_Alignof(long)-8', '1?0:1/0', '0?(1,2):0',
    '0 && (1/0)', '(void *)0', '(void *)(1-1)', '(void *)(unsigned char)256',
]
programs = []
for zero in zero_forms:
    zero = "(" + zero + ")"
    programs.append(f'int *zero(void) {{ return {zero}; }} '
                    f'int test(int *p) {{ return p=={zero} && {zero}==p; }} '
                    f'int main(void) {{ int *p={zero}; if(p || !test(p) || zero()) return 1; '
                    f'p={zero}; if(p!={zero} || {zero}!=p) return 2; '
                    f'if((1?p:{zero}) || (0?{zero}:p)) return 3; return 42; }}')
boolean_zero_program = programs[0]
programs += [
    'int main(void) { int (*a)[]=0; int (*b)[2]=(void *)0; int **c=0; '
    'void **d=0; const int *const p=0; if(a || b || c || d || p) return 1; return 42; }',
    'int id(int x) { return x; } int main(void) { int (*p)(int)=(void *)0; '
    'int (*q)(int)=(int (*)(int))0; if(p!=0 || (void *)0!=q) return 1; '
    'p=id; if(p==0 || 0==p || p==(void *)0 || (void *)0==p) return 2; '
    'if((1?id:(void *)0)(42)!=42 || (0?(void *)0:id)(42)!=42) return 3; return 42; }',
    'int main(void) { int x=42; const int *p=&x; '
    'if(sizeof *(1?p:(void *)0)!=4 || sizeof *(0?(void *)0:p)!=4) return 1; '
    'if(*(1?p:0)!=42 || *(0?0:p)!=42) return 2; return 42; }',
    'int *once(int *p,int *n) { *n=*n+1; return p; } int main(void) { int x=42,n=0; '
    'if(once(&x,&n)==0 || n!=1) return 1; if(0==once(&x,&n) || n!=2) return 2; '
    'if(*(1?once(&x,&n):0)!=42 || n!=3) return 3; '
    'if(*(0?(void *)0:once(&x,&n))!=42 || n!=4) return 4; '
    'if(0?once(&x,&n):0) return 5; if(n!=4) return 6; return 42; }',
    'int main(void) { int x=42,*p=&x; int *q=(int *)0; '
    'if((1?q:p)!=0 || (0?p:q)!=0) return 1; '
    'if(sizeof *(1?p:(void *)0)!=4) return 2; return 42; }',
    'int main(void) { int *p=0; _Bool b=p; if(b || (_Bool)p) return 1; '
    'if(sizeof *(int *)0!=4 || sizeof((int *)0)!=8) return 2; return 42; }',
    'int main(void) { int a[2]; a[0]=42; int *p=a; '
    'if(p+0!=p || p-0!=p || 0+p!=p) return 1; return *p; }',
]
constraints = [
    ('int f(void) { int *p=1; return 0; }', 'pointer conversion'),
    ('int f(int n) { int *p=n; return 0; }', 'pointer conversion'),
    ('int f(void) { int n=0; int *p=n; return 0; }', 'pointer conversion'),
    ('int f(void) { const int n=0; int *p=n; return 0; }', 'pointer conversion'),
    ('int f(void) { int *p=(0,0); return 0; }', 'pointer conversion'),
    ('int f(void) { int n=0; int *p=(n=0); return 0; }', 'pointer conversion'),
    ('int f(int n) { int *p=1?0:n; return 0; }', 'pointer conversion'),
    ('int missing(void); int f(void) { int *p=1?0:missing(); return 0; }', 'pointer conversion'),
    ('int f(void) { int *p=2147483647+1; return 0; }', 'pointer conversion'),
    ('int f(void) { int *p=1/0; return 0; }', 'pointer conversion'),
    ('int f(int *p) { return p==1; }', 'compatible pointers'),
    ('int f(int *p,int n) { return n==p; }', 'compatible pointers'),
    ('int f(int *p) { return p<0; }', 'compatible pointers'),
    ('int f(int *p) { return 0>=p; }', 'compatible pointers'),
    ('int f(int *p) { 1?p:1; return 0; }', 'incompatible conditional'),
    ('int f(int *p,int n) { 1?n:p; return 0; }', 'incompatible conditional'),
    ('int f(void) { int (*p)(void)=(const void *)0; return 0; }', 'pointer conversion'),
    ('int f(void) { void *p=0; int (*q)(void)=p; return 0; }', 'pointer conversion'),
    ('int f(void) { int (*p)(void)=(void *)(int *)0; return 0; }', 'pointer conversion'),
    ('int f(void) { int (*p)(void)=(int *)0; return 0; }', 'pointer conversion'),
    ('int f(void) { int *p=(long *)0; return 0; }', 'pointer conversion'),
    ('int f(void) { int *p=(int *)1; return 0; }', 'pointer conversion'),
    ('int f(int n) { return (int *)n!=0; }', 'pointer conversion'),
    ('int f(int *p) { return (long)p; }', 'pointer conversion'),
    ('_Static_assert((int *)0==(int *)0,"not an ICE");', 'integer constant expression'),
]
with tempfile.TemporaryDirectory(prefix='kcc null constants ') as directory:
    directory = Path(directory)
    source, native, il, assembly, obj, executable = [directory / n for n in ('k.c','h.c','p.ssa','p.s','h.o','p')]

    def compile_source(text, success=True, message=''):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:1000], result.stderr)
            if qbe:
                il.write_text(result.stdout)
                subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr, (text[:1000], result.stderr)
        return result.stdout

    def run(objects):
        subprocess.run([host, *map(str, objects), '-o', str(executable)], capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42

    native_count = 0
    boolean_zero_gap = False
    for text in programs:
        compile_source(text)
        if qbe:
            run([assembly])
        native.write_text(text + '\n')
        result = subprocess.run([host, '-std=c2x', '-pedantic-errors', str(native), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        # GCC 11 fails to recognize an integer ICE of _Bool type as a null
        # constant in assignment/return contexts. Clang accepts the original.
        # Require this exact diagnosed gap; never rewrite the cast to int.
        if result.returncode != 0 and text == boolean_zero_program:
            assert '_Bool' in result.stderr and result.stderr.count('error:') == 3, result.stderr
            for phrase in ['incompatible types when returning', 'incompatible types when initializing',
                           'incompatible types when assigning']:
                assert phrase in result.stderr, result.stderr
            boolean_zero_gap = True
            continue
        assert result.returncode == 0, (text, result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42
        native_count += 1
    # This uses the original C23 keyword leaf rather than the cast oracle.
    # Legacy hosts do not have these keywords; typed units verify its shape.
    compile_source('int *zero(void) { return false; } int main(void) { bool *p=false; '
                   'if(p || zero() || false!=p || p!=false) return 1; return 42; }')
    if qbe:
        run([assembly])
    for text, message in constraints:
        compile_source(text, False, message)

    # These violate C constraints, unlike our explicitly limited nonzero
    # integer/pointer casts. Keep strict rejection checks separate.
    for index in [0,1,2,3,4,5,10,11,12,13,24]:
        text = constraints[index][0]
        native.write_text(text+'\n')
        result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', str(native)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode != 0, text

    for name in integers:
        prototype = f'{name} *relay({name} *,int,int,int,int,int,int,int (* )({name} *),{name} *,{name} *); '
        helper = (f'{name} *relay({name} *p,int a,int b,int c,int d,int e,int f,int (*check)({name} *),{name} *q,{name} *failure) {{ '
                  'if(p || a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || !check(q)) return failure; return 0; } ')
        # A live failure sentinel makes an ABI mismatch observable without
        # forming invalid addresses or returning a pointer to a dead local.
        driver = (f'int check({name} *p) {{ return p==0; }} int main(void) {{ '
                  f'{name} x=0; {name} *p=relay(0,1,2,3,4,5,6,check,(void *)0,&x); if(p) return 1; return 42; }}')
        # Compile the same sources natively too; only these curated defined
        # programs are executed. No generated fuzz C is run.
        for kcc_text, host_text in [(helper, prototype+driver), (prototype+driver, helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                subprocess.run([host, '-std=c2x', '-pedantic-errors', '-c', str(native), '-o', str(obj)],
                               capture_output=True, check=True, timeout=10)
                run([assembly,obj])

    for count, valid in [(126,True),(127,False)]:
        compile_source('int *f(void) { return '+'+ '*count+'0; }', valid, 'typed expression exceeds depth')
    for count, valid in [(127,True),(128,False)]:
        compile_source('int *f(void) { return '+'(int *)'*count+'0; }', valid, 'depth')

print(f'Null pointer constants passed: {len(programs)} original programs, {native_count} strict native agreements, {len(constraints)} compile-only constraints/limits, '
      f'11 strict native constraint rejections, C23 false-leaf runtime, exact typed depths; {host}' + ('; exact GCC boolean-zero oracle gap' if boolean_zero_gap else '') + ('; QBE/runtime and 24 stack/callback ABI arrangements passed' if qbe else ''))
