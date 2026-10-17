"""Written register parameter identity survives adjustment, not function typing.

Only defined curated positives execute; generated boundaries and refusals compile.
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
    programs += [f'int f(register {name} x) {{ return x=={value}?42:1; }} int main(void) {{ return f({value}); }}',
                 f'typedef {name} T; int f(T register x) {{ return x=={value}?42:1; }} int main(void) {{ return f({value}); }}']
for index in range(5):
    specs = ['unsigned', 'long', 'long', 'const']
    specs.insert(index, 'register')
    programs.append('int f('+' '.join(specs)+' x) { return x==18446744073709551615ULL?42:1; } '
                    'int main(void) { return f(18446744073709551615ULL); }')
programs += [
    'int f(register int x) { x+=2; ++x; x--; return x; } int main(void) { return f(40); }',
    'int f(register int); int f(int x) { int *p=&x; *p+=2; return x; } int main(void) { return f(40); }',
    'int f(int); int f(register int x) { x+=2; return x; } int main(void) { return f(40); }',
    'int f(register int) { return 42; } int main(void) { return f(99); }',
    'int f(register int,register int x,register int *) { return x; } int main(void) { return f(0,42,0); }',
    'int step(int *p) { *p+=1; return 0; } int f(register int,register int x) { return x; } int main(void) { int n=0; int x=f(step(&n),42); return n==1?x:1; }',
    'int f(register int *p) { *p+=2; return &*p==p?*p:1; } int main(void) { int x=40; return f(&x); }',
    'int f(register int a[2]) { int *p=&a[1]; *p=42; return sizeof(a)==8?a[1]:1; } int main(void) { int a[2]; a[1]=0; return f(a); }',
    'int f(register int a[][3]) { int *p=&a[1][2]; *p=42; return sizeof(*a)==12?a[1][2]:1; } int main(void) { int a[2][3]; a[1][2]=0; return f(a); }',
    'int id(int x) { return x; } int f(register int g(int)) { return (&*g)(42); } int main(void) { return f(id); }',
    'int id(int x) { return x; } int f(register int (*g)(int)) { return g(42); } int main(void) { return f(id); }',
    'int f(register int x) { { int x=2; int *p=&x; *p=3; } return x; } int main(void) { return f(42); }',
    'int f(register int x) { { typedef char x; x y=2; if(y!=2) return 1; } return x; } int main(void) { return f(42); }',
    'typedef char T; int f(register int T[sizeof(T)]) { return sizeof(T)==8?T[0]:1; } int main(void) { int a[1]; a[0]=42; return f(a); }',
    'typedef long T; int f(register int T,int a[sizeof(T)]) { return a[3]+T; } int main(void) { int a[4]; a[3]=2; return f(40,a); }',
    'typedef long T; int f(int (*cb)(register char T,int a[sizeof(T)]),T x) { return x; } int main(void) { return f(0,42); }',
    'typedef long T; int f(register int T) { for(int T=0;T<2;T++) {} return T; } int main(void) { T x=42; return f(x); }',
    'typedef int F(register int); int f(int x) { int *p=&x; return *p; } int main(void) { F *p=f; return p(42); }',
    'int f(int x) { return x; } int main(void) { int (*p)(register int)=f; return p(42); }',
    'int main(void) { return sizeof(int (*)(register int))+34; }',
    '#define STORE register\nint f(STORE int x) { return x; } int main(void) { return f(42); }',
]
c23_programs = [
    'int f(register int x,typeof(x) y) { int *p=&y; return x+*p; } int main(void) { return f(40,2); }',
    'int f(const register int x,typeof_unqual(x) y) { y+=x; return y; } int main(void) { return f(40,2); }',
    'int f(register typeof(int) x) { typeof(x) y=x; int *p=&y; return *p; } int main(void) { return f(42); }',
    'int f(register int x) { auto y=x; int *p=&y; return *p; } int main(void) { return f(42); }',
    'int f(register int a[2],typeof(a) p) { int **q=&p; return (*q)[1]+a[0]; } int main(void) { int a[2]; a[0]=40; a[1]=2; return f(a,a); }',
    'int id(int x) { return x; } int f(register int g(int),typeof(g) p) { int (**q)(int)=&p; return (*q)(42); } int main(void) { return f(id,id); }',
    'typedef long T; int f(register int T,int (*cb)(register char T,typeof(T) y),typeof(T) x) { return sizeof(x)==4?T+x:1; } int main(void) { return f(40,0,2); }',
    'int f(register int x); int f(int x) { return sizeof(&x)==8?x:1; } int main(void) { return f(42); }',
    'int f(register typeof(nullptr) x) { typeof(x) y=x; typeof(nullptr) *p=&y; return *p==nullptr?42:1; } int main(void) { return f(nullptr); }',
    'int f(register bool x) { return x?42:1; } int main(void) { return f(true); }',
    'int f(register const int x) { typeof(x) copy=x; const int *p=&copy; return *p; } int main(void) { return f(42); }',
    'int f(register int x) { typeof(int (*)(register int)) p=0; return p==0?x:1; } int main(void) { return f(42); }',
]
constraints = [
    ('int f(register register int x);', 'duplicate register'),
    ('int f(register int x,int x);', 'duplicate parameter name'),
    ('int f(register int x) { int x; return 0; }', 'redeclaration'),
    ('int f(register int x) { typedef int x; return 0; }', 'typedef name conflicts'),
    ('int f(register const int x) { x=42; return 0; }', 'modifiable'),
    ('int f(auto int x);', 'auto is not permitted'),
    ('int f(typedef int x);', 'typedef is not permitted'),
    ('int f(register auto x);', 'auto is not permitted'),
    ('int f(auto register int x);', 'auto is not permitted'),
    ('int f(auto typeof(missing) x);', 'auto is not permitted'),
    ('int f(typedef typeof(missing) x);', 'typedef is not permitted'),
    ('int f(register int x) { return sizeof(register int); }', 'not supported in this context'),
    ('int f(register int x) { return (register int)42; }', 'not supported in this context'),
]
for parameter, name in [('register int x','x'),('register int a[2]','a'),('register int g(int)','g')]:
    for expression in [f'&{name}', f'&(({name}))']:
        constraints += [(f'int f({parameter}) {{ return sizeof({expression}); }}', 'cannot take the address')]
c23_constraints = [
    ('int f(register int x,typeof(&x) p);', 'cannot take the address'),
    ('int f(register int a[2],typeof(&a) p);', 'cannot take the address'),
    ('int f(register int g(int),typeof(&g) p);', 'cannot take the address'),
    ('int f(register int x,int (*cb)(typeof(&x) p));', 'cannot take the address'),
    ('int f(int (*cb)(register int x,typeof(&x) p));', 'cannot take the address'),
    ('int f(register typeof(register int) x);', 'not supported in this context'),
    ('int f(register int x) { typeof(&x) p; return 0; }', 'cannot take the address'),
    ('int f(register int x) { typeof_unqual(&x) p; return 0; }', 'cannot take the address'),
]
constraints += [('int f(register int x,int a[sizeof(&x)]);','cannot take the address'),
                ('int f(int x); int f(register int x) { return sizeof(&x); }','cannot take the address')]
subset_errors = [
    ('int f(register void);', 'register void parameters are not supported'),
    ('int f(register void) { return 42; }', 'register void parameters are not supported'),
    ('int f(register typeof(void));', 'register void parameters are not supported'),
    ('typedef void V; int f(V register);', 'register void parameters are not supported'),
    ('int f(int (*cb)(register void));', 'register void parameters are not supported'),
    ('int f(register int n,int a[n]);', 'variable-length arrays'),
    ('int f(register int a[static 2]);', 'error:'),
    ('int f(register int a[const 2]);', 'error:'),
]
with tempfile.TemporaryDirectory(prefix='kcc register parameters ') as directory:
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

    native.write_text('typeof(int) value;\n')
    probe = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
    native_c23 = probe.returncode == 0
    if not native_c23:
        records = re.findall(r'(fatal error|error|warning|note): ([^\n]+)',probe.stderr.replace('‘', "'").replace('’', "'"))
        assert probe.returncode == 1 and records in [
            [('error', "return type defaults to 'int' [-Wimplicit-int]"),('error', "expected declaration specifiers before 'value'"),('error', "expected '{' at end of input")],
            [('error', 'expected function body after function declarator')],
        ],probe.stderr
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
        assert result.returncode == 1,(text,result.stderr)
        native_constraints += 1
    for text,message in subset_errors:
        compile_source(text,False,message)
    for amount in [128,129]:
        compile_source('int f('+','.join(f'register int p{i}' for i in range(amount))+') { return 42; }',amount==128,
                       '' if amount==128 else 'parameter limit (128)')
    params = ','.join(f'register long p{i}' for i in range(128))
    for amount in [128,129]:
        compile_source(f'int f({params}) {{ char '+','.join(f'x{i}' for i in range(amount))+'; return 42; }',amount==128,
                       '' if amount==128 else 'local limit (256)')
    for amount in [1047552,1047553]:
        compile_source(f'int f({params}) {{ char a[{amount}]; return 42; }}',amount==1047552,
                       '' if amount==1047552 else 'storage limit')
    for amount in [4095,4096]:
        compile_source('int f(register int x) { '+'0;'*amount+' return 42; }',amount==4095,
                       '' if amount==4095 else 'item limit (4096)')
    for depth in [63,64]:
        compile_source('int f(register int '+'('*depth+'x'+')'*depth+') { return x; }',depth==63,
                       '' if depth==63 else 'nesting limit (64)')
    for depth in [63,64]:
        compile_source('int f('+'register int g('*depth+'register int'+')'*depth+');',depth==63,
                       '' if depth==63 else 'nesting limit (64)')
    unnamed_params = ','.join(['register int']*128)
    compile_source(f'int f({unnamed_params}) {{ char '+','.join(f'x{i}' for i in range(256))+'; return 42; }')
    for depth in [62,63]:
        compile_source('typedef int '+'*'*64+' A; typedef A '+'*'*depth+' B[1]; int f(register B a) { return 42; }',depth==62,
                       '' if depth==62 else 'depth limit (128)')
    # No runtime storage for prototypes or unnamed ABI members; named spills only.
    assert not compile_source('int f(register int x,typeof(x) y);').strip()
    unnamed = compile_source('int f(register int,register int [],register int (int)) { return 42; }')
    assert 'alloc' not in unnamed and '\tstore' not in unnamed and '%p2' in unnamed
    mixed = compile_source('int f(register int,register int x,register int,register int,register int,register int,register int,register int y) { return x+y; }')
    assert mixed.count('alloc') == 2 and 'storew %p1, %v0' in mixed and 'storew %p7, %v1' in mixed
    # Mixed primitive widths span six argument registers and two stack slots.
    mixed_types = ['char','short','int','long','unsigned','long long','unsigned long long','int']
    mixed_values = ['-7','-1234','-1234567','4294967296L','4294967295U','4611686018427387904LL','18446744073709551615ULL','8']
    result_values = ['1','-7','-7','255','-1234','65535','-1234567','4294967295U','4294967296L','18446744073709551615UL','4611686018427387904LL','18446744073709551615ULL']
    for name,value in zip(integers,result_values):
        names = ['a','b','c','d','e','f','g','h']
        params = ','.join(f'{t} {n}' for t,n in zip(mixed_types,names))
        registered = ','.join(f'register {t} {n}' for t,n in zip(mixed_types,names))
        args = ','.join(mixed_values)
        checks = 'if('+' || '.join(f'{n}!={v}' for n,v in zip(names,mixed_values))+') return 0;'
        helper = f'{name} pick({params}) {{ {checks} return {value}; }}'
        definition = f'{name} pick({registered}) {{ {checks} return {value}; }}'
        driver = f'{name} pick({params}); int main(void) {{ return pick({args})==({name}){value}?42:1; }}'
        registered_driver = f'{name} pick({registered}); int main(void) {{ register {name} x=pick({args}); return x==({name}){value}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(registered_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
    # Separate-object adjusted row and callback parameters in both directions.
    row_helper = 'int id(int x) { return x; } int pick(int a[][3],int g(int)) { return g(a[1][2]); }'
    row_definition = 'int pick(register int a[][3],register int g(int)) { int *p=&a[1][2]; return (&*g)(*p); }'
    row_driver = 'int id(int x) { return x; } int pick(int a[][3],int g(int)); int main(void) { int a[2][3]; a[1][2]=42; return pick(a,id); }'
    row_call = 'int id(int x); int pick(register int a[][3],register int g(int)); int main(void) { int a[2][3]; a[1][2]=42; return pick(a,id); }'
    for kcc_text,host_text in [(row_definition,row_driver),(row_call,row_helper)]:
        compile_source(kcc_text)
        if qbe:
            native.write_text(host_text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
            assert result.returncode == 0,(host_text,result.stderr)
            link_run([assembly,obj])
print(f'Register parameters passed: {len(programs)} standard + {len(c23_programs)} C23 originals, '
      f'{native_programs} strict native agreements, {native_constraints} native constraints, {len(subset_errors)} subset refusals; '
      f'128 parameters/256 locals incl spills/4096 items/1 MiB storage/64 combined declarator nesting/128 expanded-depth boundaries; {host}'
      + ('; original C23 keywords' if native_c23 else '; exact legacy keyword absence (not agreements)')
      + ('; QBE/runtime and 24 both-direction mixed-stack primitive ABI arrangements + 2 row/callback arrangements passed' if qbe else ''))
