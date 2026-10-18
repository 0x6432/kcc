"""Static functions preserve canonical internal linkage and query use provenance.

Only defined curated originals run. Constraints/subsets/boundaries compile only.
"""
# Exact newly supported originals moved to test_storage_promotions.py.
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
    programs += [f'static {name} f({name}); {name} f({name} x) {{ return x; }} int main(void) {{ return f({value})==({name}){value}?42:1; }}',
                 f'typedef {name} F({name}); F static f; static {name} f(register {name} x) {{ return x; }} int main(void) {{ return f({value})==({name}){value}?42:1; }}']
for index in range(5):
    specs = ['unsigned','long','long','const']
    specs.insert(index,'static')
    programs.append(' '.join(specs)+' f(void) { return 18446744073709551615ULL; } int main(void) { return f()==18446744073709551615ULL?42:1; }')
programs += [
    'static int f(int); extern int f(int); int f(int x) { return x; } int main(void) { return f(42); }',
    'static int f(int); int f(int); static int f(int x) { return x; } static int f(int); int main(void) { return f(42); }',
    'static int f(void); extern int f(void); int f(void) { return 42; } int main(void) { return f(); }',
    'static void set(int *); void static set(int *p) { *p=42; } int main(void) { int x=0; set(&x); return x; }',
    'static int f(int x) { if(x) return f(x-1)+1; return 40; } int main(void) { return f(2); }',
    'static int odd(int); static int even(int x) { return x?odd(x-1):1; } int odd(int x) { return x?even(x-1):0; } int main(void) { return even(4)?42:1; }',
    'static int f(int); int f(int x) { return x; } int main(void) { int (*p)(int)=f; return p==&f?p(42):1; }',
    'static int f(int); int f(register int x) { int (*p)(int)=f; { int f=2; if(f!=2) return 1; } return p==&f?x:1; } int main(void) { return f(42); }',
    'typedef long T; static int f(register int T) { return T; } int main(void) { T x=42; return f(x); }',
    'static int f(register int); int f(int x) { int *p=&x; return *p; } int main(void) { return f(42); }',
    'static int f(int); int static f(register int x) { return x; } int main(void) { return f(42); }',
    'static int f(int a[][3]); int f(register int a[][3]) { return a[1][2]; } int main(void) { int a[2][3]; a[1][2]=42; return f(a); }',
    'static int f(int (*a)[]); static int f(int (*a)[3]); int f(int (*a)[3]) { return (*a)[2]; } int main(void) { int a[3]; a[2]=42; return f(&a); }',
    'typedef int F(int); static F f; static F f; int f(int x) { return x; } int main(void) { F *p=f; return p(42); }',
    'int id(int x) { return x; } static int apply(register int g(int),int x) { return g(x); } int main(void) { return apply(id,42); }',
    '#define STORE static\nSTORE int f(void) { return 42; } int main(void) { return f(); }',
    'static int f(void); int f(void) { return 42; } int main(void) { { typedef long f; f x=2; if(x!=2) return 1; } return f(); }',
]
programs += [
    'static int f(void),g(void); int f(void) { return 40; } int g(void) { return 2; } int main(void) { return f()+g(); }',
    'static int f(void); int main(void) { return 42; }',
    'static int f(void); int main(void) { return sizeof(&f)==sizeof(int (*)(void))?42:1; }',
    'static int f(void); int main(void) { return sizeof(sizeof(&f))==sizeof(unsigned long)?42:1; }',
    'static int f(void); int main(void) { return sizeof(int[sizeof(&f)==sizeof(void *)?2:1])==2*sizeof(int)?42:1; }',
    'static int f(void); int main(void) { return _Alignof(int[sizeof(&f)==sizeof(void *)?2:1])==_Alignof(int)?42:1; }',
    'static int f(int x) { return x; } int (*get(void))(int) { return f; } int main(void) { return get()(42); }',
]
c23_programs = [
    'static int f(int x) { return x; } static typeof(f) f; int main(void) { return f(42); }',
    'typedef int F(int); static typeof(F) f; int f(int x) { return x; } int main(void) { return f(42); }',
    'static typeof(int) f(int x) { return x; } int main(void) { return f(42); }',
    'static int f(register int x,typeof(x) y) { int *p=&y; return x+*p; } int main(void) { return f(40,2); }',
    'static int f(register int x) { auto y=x; int *p=&y; return *p; } int main(void) { return f(42); }',
    'static typeof(nullptr) f(void) { return nullptr; } int main(void) { return f()==nullptr?42:1; }',
    'static bool f(bool x) { return x; } int main(void) { return f(true)?42:1; }',
    'static int f(void) { return 42; } int main(void) { auto f=2; return f+40; }',
]
c23_programs += [
    'static int f(void); typeof(f) g; int main(void) { return 42; }',
    'static int f(void); int main(void) { typeof(typeof(f) *) p; return sizeof(p)==sizeof(&f)?42:1; }',
    'static int f(void); int main(void) { return sizeof(typeof(&f))==sizeof(void *)?42:1; }',
    'static int f(void); typeof(int[sizeof(&f)==sizeof(void *)?2:1]) *g(int); int main(void) { return 42; }',
    'static int f(void); int main(void) { auto p=sizeof(&f); return p==sizeof(void *)?42:1; }',
]
constraints = [
    ('static static int f(void);','duplicate static'),
    ('static typedef int F(int);','multiple storage-class'),
    ('typedef static int F(int);','multiple storage-class'),
    ('register static int f(void);','multiple storage-class'),
    ('static register int f(void);','multiple storage-class'),
    ('static extern int f(void);','multiple storage-class'),
    ('extern static int f(void);','multiple storage-class'),
    ('int f(static int x);','static is not permitted'),
    ('int f(int static);','static is not permitted'),
    ('int f(int (*cb)(static int x));','static is not permitted'),
    ('int main(void) { return sizeof(static int); }','static is not permitted'),
    ('int main(void) { return (static int)42; }','static is not permitted'),
    ('static int f(int); long f(int);','incompatible function'),
    ('static int f(void) { return 42; } int f(void) { return 42; }','redefinition'),
    ('int main(void) { return f(); } static int f(void);','call to undeclared function'),
    ('static int f(void); int main(void) { int f=0; return f(); }','called expression'),
    ('static int f(void); int main(void) { int (*p)(long)=f; return 0; }','pointer conversion'),
]
c23_constraints = [
    ('static auto int f(void);','combined auto storage requires an inferred type'),
    ('auto static int f(void);','combined auto storage requires an inferred type'),
    ('typedef int F(int); F auto static f;','combined auto storage requires an inferred type'),
    ('static int f(register int x) { return sizeof(&x); }','cannot take the address'),
    ('static typeof(static int) f(void);','static is not permitted'),
    ('int f(static typeof(missing) x);','static is not permitted'),
]
subset_errors = [
    ('static auto x=42;','file-scope auto declarations'),
    ('auto static x=42;','file-scope auto declarations'),
    ('typedef int F(int); int main(void) { F static f; return 0; }','block-scope static function declaration is not permitted'),
    ('typedef int T; int main(void) { static auto T=42; return 0; }','static or extern auto inference is not supported yet'),
    ('static int main(void) { return 42; }','static main'),
    ('int f(int a[static 3]);','error:'),
    ('static int f(void); int main(void) { return sizeof(int[1?2:f()]); }','array bound must be an integer constant expression'),
]
ub_refusals = [
    'int f(void); static int f(void);',
    'extern int f(void); static int f(void) { return 42; }',
    'int f(void); static int g(void),f(void);',
    'typedef int F(void); F f; static F f;',
    'int f(void); static typeof(f) f;',
]
missing_uses = ['return f();', 'int (*p)(void)=f; return 42;',
                'if(0) return f(); return 42;', 'f; return 42;',
                'return 0 && f();', 'return 1?42:f();',
                'int (*p)(void)=&f; return 42;',
                'sizeof(&f); return f();',
                'sizeof(sizeof(&f)); return f();']
missing_programs = ['static int f(void); int main(void) { '+use+' }' for use in missing_uses]
c23_missing_programs = [
    'static int f(void); int main(void) { typeof(f) *p; return f(); }',
    'static int f(void); typeof(f) g; int main(void) { return f(); }',
    'static int f(void); int main(void) { typeof(typeof(f) *) p; return f(); }',
    'static int f(void); int main(void) { sizeof(typeof(&f)); return f(); }',
    'static int f(void); int main(void) { _Alignof(typeof(&f)); return f(); }',
]
# Strictly recognize the complete diagnostic records for each unchanged source.
# GCC rejects; Clang's status-zero warning is still a required diagnostic.
def missing_diagnostic(text, result):
    if text not in missing_programs+c23_missing_programs:
        return False
    records = re.findall(r'(fatal error|error|warning|note): ([^\n]+)',
                         result.stderr.replace('‘', "'").replace('’', "'"))
    prefix = [('warning', 'expression result unused [-Wunused-value]')] if text in [missing_programs[i] for i in [3,7,8]]+c23_missing_programs[3:] else []
    return ((result.returncode == 1 and records == [('error', "'f' used but never defined")]) or
            (result.returncode == 0 and records == prefix+[
                ('warning', "function 'f' has internal linkage but is not defined [-Wundefined-internal]"),
                ('note', 'used here')]))

with tempfile.TemporaryDirectory(prefix='kcc static functions ') as directory:
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
    native_missing_rejections = native_missing_warnings = 0
    for text in missing_programs+c23_missing_programs:
        compile_source(text,False,'referenced internal function requires a definition')
        if text in c23_missing_programs and not native_c23:
            continue
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
        assert missing_diagnostic(text,result),(text,result.returncode,result.stderr)
        native_missing_rejections += result.returncode == 1
        native_missing_warnings += result.returncode == 0
        assert not missing_diagnostic('int different;',result)
        for status in [-11,2]:
            assert not missing_diagnostic(text,subprocess.CompletedProcess([],status,'',result.stderr))
        for extra in ['warning: extra','note: extra','fatal error: extra','error: extra']:
            assert not missing_diagnostic(text,subprocess.CompletedProcess([],result.returncode,'',result.stderr+'\n'+extra+'\n'))
    for text in ub_refusals:
        compile_source(text,False,'static declaration after external linkage')
    for text,message in subset_errors:
        compile_source(text,False,message)
    for amount in [512,513]:
        compile_source('static int f(void);'*amount,amount==512,'' if amount==512 else 'declaration limit (512)')
    for amount in [512,513]:
        compile_source('static int '+','.join(['f(void)']*amount)+';',amount==512,
                       '' if amount==512 else 'declaration limit (512)')
    for amount in [511,512]:
        compile_source('int prior(void); static int '+','.join(['f(void)']*amount)+';',amount==511,
                       '' if amount==511 else 'declaration limit (512)')
    for amount in [256,257]:
        compile_source('static int '+','.join(f'f{i}(void)' for i in range(amount))+';',amount==256,
                       '' if amount==256 else 'function limit (256)')
    for amount in [128,129]:
        compile_source('static int f('+','.join(['register int']*amount)+');',amount==128,
                       '' if amount==128 else 'parameter limit (128)')
    params = ','.join(f'register long p{i}' for i in range(128))
    for amount in [128,129]:
        compile_source(f'static int f({params}) {{ char '+','.join(f'x{i}' for i in range(amount))+'; return 42; }',amount==128,
                       '' if amount==128 else 'local limit (256)')
    for amount in [1047552,1047553]:
        compile_source(f'static int f({params}) {{ char a[{amount}]; return 42; }}',amount==1047552,
                       '' if amount==1047552 else 'storage limit')
    for amount in [4095,4096]:
        compile_source('static int f(void) { '+'0;'*amount+' return 42; }',amount==4095,
                       '' if amount==4095 else 'item limit (4096)')
    for depth in [63,64]:
        compile_source('static int f('+'register int g('*depth+'register int'+')'*depth+');',depth==63,
                       '' if depth==63 else 'nesting limit (64)')
    for depth in [62,63]:
        compile_source('typedef int '+'*'*64+' A; typedef A '+'*'*depth+' B[1]; static int f(register B a);',depth==62,
                       '' if depth==62 else 'depth limit (128)')
    assert not compile_source('typedef int F(void); static F f; static F f;').strip()
    assert not compile_source('static int f(void),g(void); typeof(f) h;').strip()
    # Queries remain constrained even when their operands are not evaluated.
    compile_source('static int f(void); int main(void) { return sizeof(f); }',False,'sizeof requires a complete object type')
    single = compile_source('static int f(void); static int f(void) { return 42; } static int f(void);')
    assert single.count('export function') == 0 and single.count('function ') == 1 and 'alloc' not in single and 'data ' not in single
    mixed_types = ['char','short','int','long','unsigned','long long','unsigned long long','int']
    mixed_values = ['-7','-1234','-1234567','4294967296L','4294967295U','4611686018427387904LL','18446744073709551615ULL','8']
    for name,value in zip(integers,values):
        names = ['a','b','c','d','e','f','g','h']
        params = ','.join(f'{t} {n}' for t,n in zip(mixed_types,names))
        registered = ','.join(f'register {t} {n}' for t,n in zip(mixed_types,names))
        args = ','.join(mixed_values)
        checks = 'if('+' || '.join(f'{n}!={v}' for n,v in zip(names,mixed_values))+') return 0;'
        helper = f'{name} pick({params}) {{ {checks} return {value}; }}'
        definition = f'static {name} private_pick({registered}) {{ {checks} return {value}; }} {name} pick({params}) {{ return private_pick(a,b,c,d,e,f,g,h); }}'
        driver = f'{name} pick({params}); int main(void) {{ return pick({args})==({name}){value}?42:1; }}'
        static_driver = f'{name} pick({registered}); int main(void) {{ return pick({args})==({name}){value}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(static_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
    row_helper = 'int id(int x) { return x; } int pick(int a[][3],int g(int)) { return g(a[1][2]); }'
    row_definition = 'static int private_pick(register int a[][3],register int g(int)) { return (&*g)(a[1][2]); } int pick(int a[][3],int g(int)) { return private_pick(a,g); }'
    row_driver = 'int id(int x) { return x; } int pick(int a[][3],int g(int)); int main(void) { int a[2][3]; a[1][2]=42; return pick(a,id); }'
    row_call = 'int id(int x); int pick(register int a[][3],register int g(int)); int main(void) { int a[2][3]; a[1][2]=42; return pick(a,id); }'
    for kcc_text,host_text in [(row_definition,row_driver),(row_call,row_helper)]:
        compile_source(kcc_text)
        if qbe:
            native.write_text(host_text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
            assert result.returncode == 0,(host_text,result.stderr)
            link_run([assembly,obj])
    if qbe:
        compile_source('static int private_helper(void) { return 40; } int exported(void) { return private_helper(); } int other(void); int relay(void) { return other(); }')
        subprocess.run([host,'-c',str(assembly),'-o',str(obj)],check=True,capture_output=True,timeout=10)
        symbols = subprocess.run(['nm',str(obj)],capture_output=True,text=True,check=True,timeout=10).stdout
        assert re.search(r' t private_helper$',symbols,re.M) and re.search(r' T exported$',symbols,re.M) and re.search(r' T relay$',symbols,re.M) and re.search(r' U other$',symbols,re.M),symbols
        private_objects = []
        for name,value in [('left',40),('right',2)]:
            compile_source(f'static int helper(void) {{ return {value}; }} int {name}(void) {{ return helper(); }}')
            target = directory/(name+'.o')
            subprocess.run([host,'-c',str(assembly),'-o',str(target)],check=True,capture_output=True,timeout=10)
            private_objects.append(target)
        native.write_text('int left(void); int right(void); int main(void) { return left()+right(); }\n')
        link_run([*private_objects,native])
        compile_source('static int helper(void) { return 40; } int left(void) { return helper(); }')
        native.write_text('int helper(void) { return 2; } int left(void); int main(void) { return left()+helper(); }\n')
        link_run([assembly,native])

print(f'Static functions passed: {len(programs)} standard + {len(c23_programs)} C23 originals, '
      f'{native_programs} strict native agreements, {native_constraints} native constraints, missing definitions: {native_missing_rejections} native rejections/{native_missing_warnings} native warning diagnostics; {len(ub_refusals)} UB/{len(subset_errors)} subset refusals; '
      f'512 declarations/256 functions/128 parameters/256 locals incl spills/4096 items/1 MiB storage/64 nesting/128 expanded-depth boundaries; {host}'
      + ('; original C23 keywords' if native_c23 else '; exact legacy keyword absence (not agreements)')
      + ('; QBE/runtime, 24 both-direction mixed-stack primitive + 2 row/callback ABI arrangements and nm exports passed' if qbe else ''))
