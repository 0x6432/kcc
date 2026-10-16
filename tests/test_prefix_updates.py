"""Prefix updates preserve stored types and evaluate the operand address once."""
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
programs = []
for name in integers[1:]:
    programs.append(f'int main(void) {{ {name} x=40; '
                    'if(++x!=41 || x!=41 || ++x!=42 || x!=42) return 1; '
                    'if(--x!=41 || x!=41 || --x!=40 || x!=40) return 2; '
                    'if(sizeof(++x)!=sizeof x || sizeof(--x)!=sizeof x || x!=40) return 3; return ++x+1; }')
for name, maximum in [('unsigned char','255U'), ('unsigned short','65535U'), ('unsigned','4294967295U'),
                      ('unsigned long','18446744073709551615UL'), ('unsigned long long','18446744073709551615ULL')]:
    programs.append(f'int main(void) {{ {name} x=0; '
                    f'if(--x!={maximum} || x!={maximum}) return 1; '
                    'if(++x!=0 || x!=0) return 2; return 42; }')
for name in integers:
    programs.append(f'int main(void) {{ {name} a[3]; {name} *p=a; '
                    'if(++p!=a+1 || p!=a+1 || --p!=a || p!=a) return 1; '
                    '++p; ++p; if(++p!=a+3) return 2; if(--p!=a+2) return 3; '
                    'if(sizeof(++p)!=8 || p!=a+2) return 4; return 42; }')
programs += [
    'int main(void) { _Bool b=0; if(--b!=1 || b!=1 || ++b!=1 || b!=1) return 1; '
    'if(--b!=0 || b!=0 || ++b!=1 || b!=1) return 2; '
    'if(sizeof(++b)!=1 || sizeof(--b)!=1 || b!=1) return 3; return 42; }',
    'int main(void) { signed char c=127; short s=32767; '
    'if(++c!=-128 || c!=-128 || ++s!=-32768 || s!=-32768) return 1; '
    'if(--c!=127 || --s!=32767) return 2; return 42; }',
    'int main(void) { int a[2][3]; int (*p)[3]=a; if(++p!=a+1 || --p!=a) return 1; '
    'int x=42; int *v[2]; v[1]=&x; int **q=v; if(++q!=v+1 || **q!=42) return 2; '
    'const int *r=a[0]; if(++r!=a[0]+1 || --r!=a[0]) return 3; return 42; }',
    'int *locate(int *p,int *n) { *n=*n+1; return p; } '
    'int next(int *n) { *n=*n+1; return 0; } int main(void) { int x=40,n=0; '
    'if(++*locate(&x,&n)!=41 || n!=1 || x!=41) return 1; '
    'if(--*locate(&x,&n)!=40 || n!=2 || x!=40) return 2; '
    'int a[1]; a[0]=41; if(++a[next(&n)]!=42 || a[0]!=42 || n!=3) return 3; '
    'if(sizeof(++*locate(&x,&n))!=4 || n!=3 || x!=40) return 4; return 42; }',
    'int **locate(int **p,int *n) { *n=*n+1; return p; } '
    'int main(void) { int a[2]; int *p=a; int n=0; '
    'if(++*locate(&p,&n)!=a+1 || n!=1 || p!=a+1) return 1; '
    'if(--*locate(&p,&n)!=a || n!=2 || p!=a) return 2; return 42; }',
    'int main(void) { int x=40; if(0 && ++x) return 1; if(x!=40) return 2; '
    'if(!(1 || --x) || x!=40) return 3; if((1?++x:--x)!=41 || x!=41) return 4; '
    'if((0?--x:++x)!=42 || x!=42) return 5; if((--x,++x)!=42) return 6; return 42; }',
    '#define UP ++\n#define JOIN(a,b) a##b\nint main(void) { int x=40; '
    'UP x; return JOIN(+,+)x; }',
    'int main(void) { int x=40; if(+ +x!=40 || - -x!=40 || x!=40) return 1; return ++x+1; }',
]
constraints = [
    ('int f(void) { return ++1; }', 'modifiable'),
    ('int f(void) { return --1; }', 'modifiable'),
    ('int f(void) { int x=0; return ++(x=1); }', 'modifiable'),
    ('int f(void) { int x=0; return ++ ++x; }', 'modifiable'),
    ('int f(void) { const int x=0; return ++x; }', 'modifiable'),
    ('int f(void) { int *const p=0; ++p; return 0; }', 'modifiable'),
    ('int f(void) { int a[2]; ++a; return 0; }', 'modifiable'),
    ('int id(void); int f(void) { ++id; return 0; }', 'modifiable'),
    ('void v(void); int f(void) { ++v(); return 0; }', 'modifiable'),
    ('int f(void) { int x=0; return ++(int)x; }', 'modifiable'),
    ('int f(void) { void *p=0; ++p; return 0; }', 'complete object'),
    ('int f(void) { int (*p)(void)=0; --p; return 0; }', 'complete object'),
    ('int f(void) { int (*p)[]=0; ++p; return 0; }', 'complete object'),
    ('int f(void) { const int x=0; return sizeof(++x); }', 'modifiable'),
    ('int f(void) { int x=0; _Static_assert(++x,"not ICE"); return 0; }', 'integer constant expression'),
]
with tempfile.TemporaryDirectory(prefix='kcc prefix updates ') as directory:
    directory = Path(directory)
    source, native, il, assembly, obj, executable = [directory/n for n in ('k.c','h.c','p.ssa','p.s','h.o','p')]

    def compile_source(text, success=True, message=''):
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler),str(source)], capture_output=True,text=True,timeout=10)
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:1200],result.stderr)
            if qbe:
                il.write_text(result.stdout)
                subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=10)
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr, (text[:1200],result.stderr)
        return result.stdout

    def run(objects):
        result = subprocess.run([host,*map(str,objects),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        assert result.returncode == 0, result.stderr
        assert subprocess.run([str(executable)],timeout=5).returncode == 42

    for text in programs:
        compile_source(text)
        if qbe:
            run([assembly])
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],
                                capture_output=True,text=True,timeout=10)
        assert result.returncode == 0, (text,result.stderr)
        assert subprocess.run([str(executable)],timeout=5).returncode == 42
    for text,message in constraints:
        compile_source(text,False,message)
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],
                                capture_output=True,text=True,timeout=10)
        assert result.returncode != 0, text
    # VLA syntax is valid C23, but runtime bounds remain an implementation
    # limit. Do not mislabel this as a native constraint rejection.
    compile_source('int f(void) { int x=1; int a[++x]; return 0; }',False,'integer constant expression')
    # nullptr is not a real or pointer type, even though it is scalar. Legacy
    # native hosts lack the keyword, so this is not native constraint evidence.
    compile_source('int f(void) { ++nullptr; return 0; }',False,'modifiable')
    # A null pointer object's update is constraint-valid, but executing it is
    # undefined. Compile only; never run this or generated fuzz C.
    compile_source('int *f(void) { int *p=0; return ++p; }')

    for name in integers:
        initial, expected = ('0','1') if name == '_Bool' else ('41','42')
        prototype = f'{name} update({name} *,int,int,int,int,int,int,int); '
        helper = (f'{name} update({name} *p,int a,int b,int c,int d,int e,int f,int g) {{ '
                  'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7) return 0; return ++*p; }')
        driver = (f'int main(void) {{ {name} x={initial}; '
                  f'if(update(&x,1,2,3,4,5,6,7)!={expected} || x!={expected}) return 1; return 42; }}')
        for kcc_text,host_text in [(helper,prototype+driver),(prototype+driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],
                                        capture_output=True,text=True,timeout=10)
                assert result.returncode == 0, (host_text,result.stderr)
                run([assembly,obj])
    for count,valid in [(63,True),(64,False)]:
        compile_source('int f(void) { int x=0; return ++'+'* &'*count+'x; }',valid,'depth')

print(f'Prefix updates passed: {len(programs)} strict native original programs, {len(constraints)} native constraint rejections, '
      f'nullptr constraint, VLA subset limit, compile-only null update, exact depth, once-only addresses; {host}'
      + ('; QBE/runtime and 24 mixed-stack narrow-return ABI arrangements passed' if qbe else ''))
