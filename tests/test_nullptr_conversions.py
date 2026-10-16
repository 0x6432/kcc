"""Assignment-like C23 nullptr conversions use checked null constant forms."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root/'build'/'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
forms = ['0','2-2','0L','0ULL','(void *)0']
programs = []
for value in forms:
    programs += [
        f'int main(void) {{ typeof(nullptr) n={value}; return n==nullptr?42:1; }}',
        f'int main(void) {{ typeof(nullptr) n=nullptr; n={value}; return n==nullptr?42:1; }}',
        f'typeof(nullptr) pick(void) {{ return {value}; }} int main(void) {{ return pick()==nullptr?42:1; }}',
        f'int accept(typeof(nullptr) n) {{ return n==nullptr?42:1; }} int main(void) {{ return accept({value}); }}',
    ]
programs += [
    'int main(void) { int x=40; typeof(nullptr) n=(x++,nullptr); n=(x++,nullptr); return x; }',
    'typeof(nullptr) pick(typeof(nullptr) n) { return n; } int main(void) { int x=40; return pick((x++,nullptr))==nullptr?x+1:1; }',
    'int main(void) { int x=40; typeof((x++,nullptr)) n=0; return n==nullptr?x+2:1; }',
    'int main(void) { typeof(nullptr) a[2]; a[0]=0; a[1]=nullptr; return a[0]==a[1]?42:1; }',
    'int main(void) { typeof(nullptr) n=0; typeof(&n) p=&n; *p=0; return n==nullptr?42:1; }',
]
constraints = []
for declaration,value in [('int x=0;','x'),('long x=0;','x'),('int *x=0;','x'),('void *x=0;','x'),('','1')]:
    constraints += [
        f'int f(void) {{ {declaration} typeof(nullptr) n={value}; return 0; }}',
        f'int f(void) {{ {declaration} typeof(nullptr) n=nullptr; n={value}; return 0; }}',
        f'typeof(nullptr) f(void) {{ {declaration} return {value}; }}',
        f'int f(typeof(nullptr)); int g(void) {{ {declaration} return f({value}); }}',
    ]
# Non-ICE zero is checked without using host constant folding as a C oracle.
nonconstant_zero = [
    'int f(void) { typeof(nullptr) n=(0,0); return 0; }',
    'int f(void) { typeof(nullptr) n=nullptr; n=(0,0); return 0; }',
    'typeof(nullptr) f(void) { return (0,0); }',
    'int f(typeof(nullptr)); int g(void) { return f((0,0)); }',
]
with tempfile.TemporaryDirectory(prefix='kcc nullptr conversions ') as directory:
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

    support = []
    for operator in ['typeof','typeof_unqual']:
        native.write_text(f'{operator}(int) value;\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)], capture_output=True, text=True, timeout=10)
        support.append(result.returncode == 0)
        if result.returncode:
            errors = re.findall(r'error: ([^\n]+)',result.stderr.replace('‘', "'").replace('’', "'"))
            assert errors in [["return type defaults to 'int' [-Wimplicit-int]", "expected declaration specifiers before 'value'", "expected '{' at end of input"],
                              ['expected function body after function declarator']], result.stderr
    native_supported = all(support)
    native_programs = 0
    native_constraints = 0
    native_abi = 0
    for text in programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if native_supported:
            native.write_text(text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)], capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, (text,result.stderr)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42
            native_programs += 1
    for text in constraints:
        compile_source(text,False,'conversion')
        if native_supported:
            native.write_text(text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)], capture_output=True, text=True, timeout=10)
            assert result.returncode != 0, text
            native_constraints += 1
    for text in nonconstant_zero:
        compile_source(text,False,'conversion')
    compile_source('int f(void) { const typeof(nullptr) n=0; n=0; return 0; }',False,'modifiable')
    # Both TUs agree on actual C23 nullptr_t, not a void-pointer stand-in.
    if native_supported and qbe:
        arguments = '1,2,3,4,5,6,7,8,0'
        signature = 'int a,int b,int c,int d,int e,int f,int g,int h,typeof(nullptr) n'
        prototype = 'int accept('+signature+'); '
        helper = ('int accept('+signature+') { '
                  'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8 || n!=nullptr) return 1; return 42; }')
        driver = 'int main(void) { return accept('+arguments+'); }'
        return_prototype = 'typeof(nullptr) pick(void); '
        return_helper = 'typeof(nullptr) pick(void) { return 0; }'
        return_driver = 'int main(void) { return pick()==nullptr?42:1; }'
        for kcc_text,host_text in [(helper,prototype+driver), (prototype+driver,helper),
                                   (return_helper,return_prototype+return_driver),
                                   (return_prototype+return_driver,return_helper)]:
            compile_source(kcc_text)
            native.write_text(host_text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)], capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, (host_text,result.stderr)
            link_run([assembly,obj])
            native_abi += 1
print(f'Nullptr assignment conversions passed: {len(programs)} original programs, {native_programs} strict native agreements, {len(constraints)} strict constraint cases / {native_constraints} native rejections; {len(nonconstant_zero)} compile-only non-ICE zero forms, const write and typed conversion contexts; {host}'
      + ('; native original C23 keyword support' if native_supported else '; exact legacy keyword absence (no alias oracle)')
      + (f'; QBE/runtime and {native_abi} actual-C23 both-direction nullptr ABI arrangements' if qbe else ''))
