"""One external specifier base, distinct concrete function declarators and scopes.

Only curated defined originals execute; invalid and generated boundaries compile.
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
    definitions = f'{name} f({name} x) {{ return x; }} {name} g({name} x) {{ return f(x); }} int main(void) {{ return g({value})==({name}){value}?42:1; }}'
    programs += [f'extern {name} f({name}),g({name}); '+definitions,
                 f'typedef {name} F({name}); F extern f,g; '+definitions]
for index in range(5):
    specs = ['unsigned','long','long','const']
    specs.insert(index,'extern')
    programs.append(' '.join(specs)+' f(void),g(void); unsigned long long f(void) { return 18446744073709551615ULL; } '
                    'unsigned long long g(void) { return f(); } int main(void) { return g()==18446744073709551615ULL?42:1; }')
return_qualifier_gap_cases = set(programs[24:29])
programs += [
    'int f(int),g(void); int f(int x) { return x; } int g(void) { return f(42); } int main(void) { return g(); }',
    'int f(int),f(int),f(int); int f(int x) { return x; } int main(void) { return f(42); }',
    'int f(int),*g(int *),(*h(void))(int); int f(int x) { return x; } int *g(int *p) { return p; } int (*h(void))(int) { return f; } int main(void) { int x=42; return h()(*g(&x)); }',
    'void f(int *),g(int *); void f(int *p) { *p=40; } void g(int *p) { f(p); *p+=2; } int main(void) { int x=0; g(&x); return x; }',
    'typedef int I; I f(I),g(I); int f(int x) { return x; } int g(int x) { return f(x); } int main(void) { return g(42); }',
    'typedef long T; int f(int T),g(T x); int f(int x) { return x; } int g(long x) { return x; } int main(void) { return f(40)+g(2); }',
    'typedef long T; int f(register int T),g(T x); int f(int x) { int *p=&x; return *p; } int g(long x) { return x; } int main(void) { return f(40)+g(2); }',
    'typedef long T; int f(int T),g(int a[sizeof(T)]); int f(int x) { return x; } int g(int a[8]) { return a[7]; } int main(void) { int a[8]; a[7]=2; return f(40)+g(a); }',
    'int f(int),g(int a[sizeof(&f)]); int f(int x) { return x; } int g(int a[8]) { return a[7]; } int main(void) { int a[8]; a[7]=2; return f(40)+g(a); }',
    'int f(int (*)[]),f(int (*)[3]),g(int (*)[3]); int f(int (*p)[]) { return (*p)[2]; } int g(int (*p)[3]) { return f(p); } int main(void) { int a[3]; a[2]=42; return g(&a); }',
    'typedef int F(int); extern F f,g; int f(int x) { return x; } int g(int x) { return x; } int main(void) { F *p=f,*q=g; return p(40)+q(2); }',
    'int f(int (*cb)(register int)),g(int (*cb)(int)); int id(int x) { return x; } int f(int (*cb)(int)) { return cb(40); } int g(int (*cb)(int)) { return cb(2); } int main(void) { return f(id)+g(id); }',
    'typedef long T; int f(int (*cb)(char T)),g(T x); int f(int (*cb)(char)) { return cb(2); } int g(long x) { return x; } int id(char x) { return x; } int main(void) { return f(id)+g(40); }',
    '#define STORE extern\nSTORE int f(void),g(void); int f(void) { return 40; } int g(void) { return 2; } int main(void) { return f()+g(); }',
]
c23_programs = [
    'typeof(int(void)) f,g; int f(void) { return 40; } int g(void) { return 2; } int main(void) { return f()+g(); }',
    'int f(int),g(typeof(f) *p); int f(int x) { return x; } int g(int (*p)(int)) { return p(42); } int main(void) { return g(f); }',
    'int f(int x) { return x; } extern typeof(f) g,h; int g(int x) { return f(x); } int h(int x) { return g(x); } int main(void) { return h(42); }',
    'typedef long T; int f(register int T,typeof(T) x),g(T x); int f(int x,int y) { int *p=&x; return *p+y; } int g(long x) { return x; } int main(void) { return f(38,2)+g(2); }',
    'extern typeof(int) f(int),g(int); int f(int x) { return x; } int g(int x) { return f(x); } int main(void) { return g(42); }',
    'extern typeof(nullptr) f(void),g(void); typeof(nullptr) f(void) { return nullptr; } typeof(nullptr) g(void) { return f(); } int main(void) { return g()==nullptr?42:1; }',
    'extern bool f(bool),g(bool); bool f(bool x) { return x; } bool g(bool x) { return f(x); } int main(void) { return g(true)?42:1; }',
    'extern int f(int),g(int); int f(int x) { return x; } int g(int x) { auto f=2; return x+f; } int main(void) { return g(40); }',
]
constraints = [
    ('int f(void),f(int);','incompatible function'),
    ('typedef int F(int); extern F f,F;','function name conflicts with typedef'),
    ('int f(void),g(void) { return 42; }',"expected ',' or ';'"),
    ('int f(void) { return 42; },g(void);','error:'),
    ('int f(int),g(int); int f(int x) { return x; } int main(void) { return f(); }','argument count'),
    ('int f(register int x),g(register int x,int x);','duplicate parameter name'),
    ('int f(void),g(extern int x);','extern is not permitted'),
    ('int f(void),g(auto int x);','auto is not permitted'),
    ('int f(void),g(int x) { return 42; };',"expected ',' or ';'"),
]
c23_constraints = [
    ('int g(typeof(f) *p),f(int);','undeclared'),
    ('int f(register int x,typeof(&x) y),g(void);','cannot take the address'),
    ('typeof(int(void)) f,g; int g(int);','incompatible function'),
]
subset_errors = [
    ('int f(void),x;','file-scope object declarations'),
    ('typeof(int(void)) f,g=0;',"query-derived external declarations require ';'"),
    ('typedef int F(void); extern F f,g { return 42; }',"query-derived external declarations require ';'"),
    ('int main(void) { extern int f(void),g(void); return 0; }','block-scope extern declarations'),
    ('extern auto f=42,g=2;','file-scope auto declarations'),
]
def native_return_qualifier_gap(text, status, diagnostics):
    # N3096 6.7.6.3p4 removes top-level return qualifiers. Keep originals.
    records = re.findall(r'(fatal error|error|warning|note): ([^\n]+)',diagnostics.replace('‘', "'").replace('’', "'"))
    return text in return_qualifier_gap_cases and status == 1 and records == [
        ('error', "conflicting types for 'f'"), ('note', 'previous declaration is here'),
        ('error', "conflicting types for 'g'"), ('note', 'previous declaration is here'),
    ]


gap_text = next(iter(return_qualifier_gap_cases))
gap_diagnostic = "error: conflicting types for 'f'\nnote: previous declaration is here\nerror: conflicting types for 'g'\nnote: previous declaration is here\n"
assert native_return_qualifier_gap(gap_text,1,gap_diagnostic)
assert not native_return_qualifier_gap(programs[0],1,gap_diagnostic)
for status in [0,-11,127]:
    assert not native_return_qualifier_gap(gap_text,status,gap_diagnostic)
for extra in ['warning: unrelated','note: unrelated','fatal error: failure',gap_diagnostic]:
    assert not native_return_qualifier_gap(gap_text,1,gap_diagnostic+extra)


with tempfile.TemporaryDirectory(prefix='kcc function lists ') as directory:
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
    native_programs = native_constraints = native_return_gaps = 0
    for text in programs+c23_programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if text in c23_programs and not native_c23:
            continue
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        if native_return_qualifier_gap(text,result.returncode,result.stderr):
            native_return_gaps += 1
            continue
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
        compile_source('extern int '+','.join(['f(void)']*amount)+';',amount==512,'' if amount==512 else 'declaration limit (512)')
    for amount in [511,512]:
        compile_source('int prior(void); extern int '+','.join(['f(void)']*amount)+';',amount==511,'' if amount==511 else 'declaration limit (512)')
    for amount in [256,257]:
        compile_source('extern int '+','.join(f'f{i}(void)' for i in range(amount))+';',amount==256,'' if amount==256 else 'function limit (256)')
    for amount in [128,129]:
        compile_source('extern int f('+','.join(['register int']*amount)+'),g(void);',amount==128,'' if amount==128 else 'parameter limit (128)')
    params = ','.join(f'register long p{i}' for i in range(128))
    for amount in [128,129]:
        compile_source(f'int f({params}),g(void); int f({params}) {{ char '+','.join(f'x{i}' for i in range(amount))+'; return 42; }',amount==128,'' if amount==128 else 'local limit (256)')
    for amount in [1047552,1047553]:
        compile_source(f'int f({params}),g(void); int f({params}) {{ char a[{amount}]; return 42; }}',amount==1047552,'' if amount==1047552 else 'storage limit')
    for amount in [4095,4096]:
        compile_source('extern int f(void),g(void); int f(void) { '+'0;'*amount+' return 42; }',amount==4095,'' if amount==4095 else 'item limit (4096)')
    for depth in [63,64]:
        compile_source('extern int f('+'register int g('*depth+'register int'+')'*depth+'),g(void);',depth==63,'' if depth==63 else 'nesting limit (64)')
    for depth in [62,63]:
        compile_source('typedef int '+'*'*64+' A; typedef A '+'*'*depth+' B[1]; extern int f(register B a),g(B a);',depth==62,'' if depth==62 else 'depth limit (128)')
    for text in ['extern int f(void),g(int);','typedef int F(int); extern F f,g;','typeof(int(void)) f,g;']:
        assert not compile_source(text).strip()
    single = compile_source('extern int f(void),f(void); int f(void) { return 42; }')
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
        definition = f'extern {name} pick({params}),spare(void); {name} pick({registered}) {{ {checks} return {value}; }}'
        driver = f'{name} pick({params}); int main(void) {{ return pick({args})==({name}){value}?42:1; }}'
        list_driver = f'extern {name} pick({registered}),spare(void); int main(void) {{ return pick({args})==({name}){value}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(list_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
    row_helper = 'int id(int x) { return x; } int pick(int a[][3],int g(int)) { return g(a[1][2]); }'
    row_definition = 'extern int pick(int a[][3],int g(int)),spare(void); int pick(register int a[][3],register int g(int)) { return (&*g)(a[1][2]); }'
    row_driver = 'int id(int x) { return x; } int pick(int a[][3],int g(int)); int main(void) { int a[2][3]; a[1][2]=42; return pick(a,id); }'
    row_call = 'extern int id(int x),pick(register int a[][3],register int g(int)); int main(void) { int a[2][3]; a[1][2]=42; return pick(a,id); }'
    for kcc_text,host_text in [(row_definition,row_driver),(row_call,row_helper)]:
        compile_source(kcc_text)
        if qbe:
            native.write_text(host_text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
            assert result.returncode == 0,(host_text,result.stderr)
            link_run([assembly,obj])
print(f'Function declaration lists passed: {len(programs)} standard + {len(c23_programs)} C23 originals, '
      f'{native_programs} strict native agreements, {native_return_gaps} exact return-qualifier native gaps, {native_constraints} native constraints, {len(subset_errors)} subset refusals; '
      f'512 concrete declarations/256 symbols/128 parameters/256 locals incl spills/4096 items/1 MiB storage/64 nesting/128 expanded-depth boundaries; {host}'
      + ('; original C23 keywords' if native_c23 else '; exact legacy keyword absence (not agreements)')
      + ('; QBE/runtime and 24 both-direction mixed-stack primitive + 2 row/callback ABI arrangements passed' if qbe else ''))
