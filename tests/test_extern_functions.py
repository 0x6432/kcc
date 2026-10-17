"""Explicit extern functions reuse canonical external linkage and source caches.

Only defined curated originals run. Constraints/subsets/boundaries compile only.
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
values = ['1','-7','-7','255','-1234','65535','-1234567','4294967295U','4294967296L','18446744073709551615UL','4611686018427387904LL','18446744073709551615ULL']
programs = []
for name,value in zip(integers,values):
    programs += [f'extern {name} f({name}); {name} f({name} x) {{ return x; }} int main(void) {{ return f({value})==({name}){value}?42:1; }}',
                 f'typedef {name} F({name}); F extern f; extern {name} f(register {name} x) {{ return x; }} int main(void) {{ return f({value})==({name}){value}?42:1; }}']
for index in range(5):
    specs = ['unsigned','long','long','const']
    specs.insert(index,'extern')
    programs.append(' '.join(specs)+' f(void) { return 18446744073709551615ULL; } int main(void) { return f()==18446744073709551615ULL?42:1; }')
programs += [
    'int f(int); extern int f(int x) { return x; } int main(void) { return f(42); }',
    'extern int f(int); int f(int); extern int f(int x) { return x; } extern int f(int); int main(void) { return f(42); }',
    'extern int main(void) { return 42; }',
    'extern void set(int *); void extern set(int *p) { *p=42; } int main(void) { int x=0; set(&x); return x; }',
    'extern int f(int x) { if(x) return f(x-1)+1; return 40; } int main(void) { return f(2); }',
    'extern int odd(int); extern int even(int x) { return x?odd(x-1):1; } int odd(int x) { return x?even(x-1):0; } int main(void) { return even(4)?42:1; }',
    'extern int f(int); int f(int x) { return x; } int main(void) { int (*p)(int)=f; return p==&f?p(42):1; }',
    'extern int f(int); int f(register int x) { int (*p)(int)=f; { int f=2; if(f!=2) return 1; } return p==&f?x:1; } int main(void) { return f(42); }',
    'typedef long T; extern int f(register int T) { return T; } int main(void) { T x=42; return f(x); }',
    'extern int f(register int); int f(int x) { int *p=&x; return *p; } int main(void) { return f(42); }',
    'extern int f(int); int extern f(register int x) { return x; } int main(void) { return f(42); }',
    'extern int f(int a[][3]); int f(register int a[][3]) { return a[1][2]; } int main(void) { int a[2][3]; a[1][2]=42; return f(a); }',
    'extern int f(int (*a)[]); extern int f(int (*a)[3]); int f(int (*a)[3]) { return (*a)[2]; } int main(void) { int a[3]; a[2]=42; return f(&a); }',
    'typedef int F(int); extern F f; extern F f; int f(int x) { return x; } int main(void) { F *p=f; return p(42); }',
    'int id(int x) { return x; } extern int apply(register int g(int),int x) { return g(x); } int main(void) { return apply(id,42); }',
    '#define STORE extern\nSTORE int f(void) { return 42; } int main(void) { return f(); }',
    'extern int f(void); int f(void) { return 42; } int main(void) { { typedef long f; f x=2; if(x!=2) return 1; } return f(); }',
]
c23_programs = [
    'int f(int x) { return x; } extern typeof(f) f; int main(void) { return f(42); }',
    'typedef int F(int); extern typeof(F) f; int f(int x) { return x; } int main(void) { return f(42); }',
    'extern typeof(int) f(int x) { return x; } int main(void) { return f(42); }',
    'extern int f(register int x,typeof(x) y) { int *p=&y; return x+*p; } int main(void) { return f(40,2); }',
    'extern int f(register int x) { auto y=x; int *p=&y; return *p; } int main(void) { return f(42); }',
    'extern typeof(nullptr) f(void) { return nullptr; } int main(void) { return f()==nullptr?42:1; }',
    'extern bool f(bool x) { return x; } int main(void) { return f(true)?42:1; }',
    'extern int f(void) { return 42; } int main(void) { auto f=2; return f+40; }',
]
constraints = [
    ('extern extern int f(void);','duplicate extern'),
    ('extern typedef int F(int);','multiple storage-class'),
    ('typedef extern int F(int);','multiple storage-class'),
    ('register extern int f(void);','multiple storage-class'),
    ('extern register int f(void);','multiple storage-class'),
    ('int f(extern int x);','extern is not permitted'),
    ('int f(int extern);','extern is not permitted'),
    ('int f(int (*cb)(extern int x));','extern is not permitted'),
    ('int main(void) { return sizeof(extern int); }','extern is not permitted'),
    ('int main(void) { return (extern int)42; }','extern is not permitted'),
    ('extern int f(int); long f(int);','incompatible function'),
    ('extern int f(void) { return 42; } int f(void) { return 42; }','redefinition'),
    ('int main(void) { return f(); } extern int f(void);','call to undeclared function'),
    ('extern int f(void); int main(void) { int f=0; return f(); }','called expression'),
    ('extern int f(void); int main(void) { int (*p)(long)=f; return 0; }','pointer conversion'),
]
c23_constraints = [
    ('extern auto int f(void);','combined auto storage requires an inferred type'),
    ('auto extern int f(void);','combined auto storage requires an inferred type'),
    ('typedef int F(int); F auto extern f;','combined auto storage requires an inferred type'),
    ('extern int f(register int x) { return sizeof(&x); }','cannot take the address'),
    ('extern typeof(extern int) f(void);','extern is not permitted'),
    ('int f(extern typeof(missing) x);','extern is not permitted'),
]
subset_errors = [
    ('extern int x;','file-scope object declarations'),
    ('extern int x=42;','file-scope object declarations'),
    ('extern int (*p)(int);','file-scope object declarations'),
    ('typedef int T; T extern x;','file-scope object declarations'),
    ('extern auto x=42;','file-scope auto declarations'),
    ('auto extern x=42;','file-scope auto declarations'),
    ('int main(void) { extern int f(void); return 0; }','block-scope extern declarations'),
    ('typedef int F(int); int main(void) { F extern f; return 0; }','block-scope extern declarations'),
    ('typedef int T; int main(void) { extern auto T=42; return 0; }','block-scope extern declarations'),
    ('static int f(void) { return 42; }','error:'),
    ('extern inline int f(void) { return 42; }','error:'),
]
with tempfile.TemporaryDirectory(prefix='kcc extern functions ') as directory:
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
    for amount in [512,513]:
        compile_source('extern int f(void);'*amount,amount==512,'' if amount==512 else 'declaration limit (512)')
    for amount in [256,257]:
        compile_source(''.join(f'extern int f{i}(void);' for i in range(amount)),amount==256,
                       '' if amount==256 else 'function limit (256)')
    for amount in [128,129]:
        compile_source('extern int f('+','.join(['register int']*amount)+');',amount==128,
                       '' if amount==128 else 'parameter limit (128)')
    params = ','.join(f'register long p{i}' for i in range(128))
    for amount in [128,129]:
        compile_source(f'extern int f({params}) {{ char '+','.join(f'x{i}' for i in range(amount))+'; return 42; }',amount==128,
                       '' if amount==128 else 'local limit (256)')
    for amount in [1047552,1047553]:
        compile_source(f'extern int f({params}) {{ char a[{amount}]; return 42; }}',amount==1047552,
                       '' if amount==1047552 else 'storage limit')
    for amount in [4095,4096]:
        compile_source('extern int f(void) { '+'0;'*amount+' return 42; }',amount==4095,
                       '' if amount==4095 else 'item limit (4096)')
    for depth in [63,64]:
        compile_source('extern int f('+'register int g('*depth+'register int'+')'*depth+');',depth==63,
                       '' if depth==63 else 'nesting limit (64)')
    for depth in [62,63]:
        compile_source('typedef int '+'*'*64+' A; typedef A '+'*'*depth+' B[1]; extern int f(register B a);',depth==62,
                       '' if depth==62 else 'depth limit (128)')
    assert not compile_source('typedef int F(void); extern F f; extern F f;').strip()
    single = compile_source('extern int f(void); extern int f(void) { return 42; } extern int f(void);')
    assert single.count('export function') == 1 and 'alloc' not in single and 'data ' not in single
    mixed_types = ['char','short','int','long','unsigned','long long','unsigned long long','int']
    mixed_values = ['-7','-1234','-1234567','4294967296L','4294967295U','4611686018427387904LL','18446744073709551615ULL','8']
    for name,value in zip(integers,values):
        names = ['a','b','c','d','e','f','g','h']
        params = ','.join(f'{t} {n}' for t,n in zip(mixed_types,names))
        registered = ','.join(f'register {t} {n}' for t,n in zip(mixed_types,names))
        args = ','.join(mixed_values)
        checks = 'if('+' || '.join(f'{n}!={v}' for n,v in zip(names,mixed_values))+') return 0;'
        helper = f'{name} pick({params}) {{ {checks} return {value}; }}'
        definition = f'extern {name} pick({registered}) {{ {checks} return {value}; }}'
        driver = f'{name} pick({params}); int main(void) {{ return pick({args})==({name}){value}?42:1; }}'
        extern_driver = f'extern {name} pick({registered}); int main(void) {{ return pick({args})==({name}){value}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(extern_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
    row_helper = 'int id(int x) { return x; } int pick(int a[][3],int g(int)) { return g(a[1][2]); }'
    row_definition = 'extern int pick(register int a[][3],register int g(int)) { return (&*g)(a[1][2]); }'
    row_driver = 'int id(int x) { return x; } int pick(int a[][3],int g(int)); int main(void) { int a[2][3]; a[1][2]=42; return pick(a,id); }'
    row_call = 'extern int id(int x); extern int pick(register int a[][3],register int g(int)); int main(void) { int a[2][3]; a[1][2]=42; return pick(a,id); }'
    for kcc_text,host_text in [(row_definition,row_driver),(row_call,row_helper)]:
        compile_source(kcc_text)
        if qbe:
            native.write_text(host_text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
            assert result.returncode == 0,(host_text,result.stderr)
            link_run([assembly,obj])
    if qbe:
        compile_source('extern int exported(void) { return 42; } extern int other(void); extern int relay(void) { return other(); }')
        subprocess.run([host,'-c',str(assembly),'-o',str(obj)],check=True,capture_output=True,timeout=10)
        symbols = subprocess.run(['nm','-g',str(obj)],capture_output=True,text=True,check=True,timeout=10).stdout
        assert re.search(r' T exported$',symbols,re.M) and re.search(r' T relay$',symbols,re.M) and re.search(r' U other$',symbols,re.M),symbols
print(f'Extern functions passed: {len(programs)} standard + {len(c23_programs)} C23 originals, '
      f'{native_programs} strict native agreements, {native_constraints} native constraints, {len(subset_errors)} subset refusals; '
      f'512 declarations/256 functions/128 parameters/256 locals incl spills/4096 items/1 MiB storage/64 nesting/128 expanded-depth boundaries; {host}'
      + ('; original C23 keywords' if native_c23 else '; exact legacy keyword absence (not agreements)')
      + ('; QBE/runtime, 24 both-direction mixed-stack primitive + 2 row/callback ABI arrangements and nm exports passed' if qbe else ''))
