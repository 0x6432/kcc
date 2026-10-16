"""Original C23 typeof type-name queries, immutable qualifiers and fixed ABI."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root/'build'/'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool','char','signed char','unsigned char','short','unsigned short',
            'int','unsigned','long','unsigned long','long long','unsigned long long']
programs = []
for name in integers:
    value = '1' if name == '_Bool' else '42'
    programs += [
        f'int main(void) {{ typeof({name}) x={value}; return x=={value}?42:1; }}',
        f'int main(void) {{ typeof_unqual(const {name}) x=0; x={value}; return x=={value}?42:1; }}',
    ]
programs += [
    'typeof(int) f(typeof(unsigned char) x) { return x; } int main(void) { return f(42); }',
    'typeof(void) f(int *p) { *p=42; return; } int main(void) { int x=0; f(&x); return x; }',
    'int main(void) { int x=40; typeof(int *) p=&x; *p+=2; return x; }',
    'int main(void) { typeof(int[2]) a; a[0]=40; a[1]=2; return a[0]+a[1]; }',
    'int main(void) { typeof_unqual(const int[2][3]) a; a[1][2]=42; return a[1][2]; }',
    'int main(void) { int x=40,y=42; typeof_unqual(const int * const) p=&x; p=&y; return *p; }',
    'int main(void) { int x=42; typeof(int * const) p=&x; *p=40; *p+=2; return x; }',
    'int main(void) { typeof(typeof_unqual(const int)) x=42; return x; }',
    'int main(void) { typeof_unqual(typeof(const int)) x=0; x=42; return x; }',
    'int main(void) { const typeof_unqual(const int) x=42; return x; }',
    'int main(void) { typeof_unqual(const int) const x=42; return x; }',
    'int main(void) { return (typeof(unsigned char))298; }',
    'int main(void) { int x=40; (typeof(void))(x+=2); return x; }',
    'int main(void) { return sizeof(typeof(int[2]))==8?42:1; }',
    'int main(void) { return _Alignof(typeof_unqual(const long))==8?42:1; }',
    'int main(void) { _Static_assert(sizeof(typeof(int))==4,"layout"); return 42; }',
    'int main(void) { typeof(int[sizeof(typeof(short))]) a; a[1]=42; return a[1]; }',
    'int add(int x) { return x+2; } int main(void) { typeof(int (*)(int)) p=add; return p(40); }',
    'int add(int x) { return x+2; } int main(void) { typeof_unqual(int (* const)(int)) p=0; p=add; return p(40); }',
    'int f(typeof(int[2]) a) { return a[1]; } int main(void) { int a[2]; a[1]=42; return f(a); }',
    'int f(int *a); typeof(int) f(typeof(int[]) a) { return a[0]; } int main(void) { int a[1]; a[0]=42; return f(a); }',
    'int main(void) { for(typeof(int) i=0;i<1;i++) { typeof(int) x=42; return x; } return 0; }',
    'int main(void) { typeof(int) x=0; switch(1) { case sizeof(typeof(char)): x=42; break; } return x; }',
    '#define QUERY typeof\n#define PLAIN typeof_unqual\nint main(void) { QUERY(PLAIN(const int)) x=42; return x; }',
]
constraints = [
    ('int f(void) { typeof(const int) x=0; x=1; return 0; }','modifiable'),
    ('int f(void) { const typeof_unqual(const int) x=0; x=1; return 0; }','modifiable'),
    ('int f(void) { int x=0; typeof_unqual(const int *) p=&x; *p=1; return 0; }','modifiable'),
    ('int f(void) { int x=0; typeof(int * const) p=&x; p=0; return 0; }','modifiable'),
    ('int f(void) { typeof(const int[2]) a; a[0]=1; return 0; }','modifiable'),
    ('int f(void) { typeof(int[]) a; return 0; }','complete'),
    ('int f(void) { typeof(void) x; return 0; }','complete'),
    ('int f(void) { return sizeof(typeof(int(void))); }','complete'),
    ('int f(void) { const typeof(int(void)) *p; return 0; }','function type cannot be qualified'),
    ('int f(void) { typeof(int[0]) a; return 0; }','positive'),
]
syntax_errors = ['int f(void) { typeof int x; }','int f(void) { typeof() x; }',
                 'int f(void) { typeof(int x; }','int f(void) { typeof(int named) x; }',
                 'int f(void) { int typeof(int) x; }','int f(void) { typeof(int) unsigned x; }',
                 'int f(void) { typeof(int) typeof(int) x; }']
subset_errors = [
    ('int f(int n) { typeof(int[n]) a; return 0; }','variable-length'),
    ('int f(void) { int x=0; typeof(x) y; return 0; }','typeof expression operands are not supported yet'),
    ('typeof(int(void)) f;','file-scope object declarations are not supported yet'),
    ('int f(typeof(void));','parameter cannot have void type'),
]
with tempfile.TemporaryDirectory(prefix='kcc typeof types ') as directory:
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
    for text,message in constraints:
        compile_source(text,False,message)
        if native_supported:
            native.write_text(text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)], capture_output=True, text=True, timeout=10)
            # Function qualification is outside the supported subset; do not
            # pretend hosts' extension policy is a strict constraint oracle.
            if message != 'function type cannot be qualified':
                assert result.returncode != 0, text
                native_constraints += 1
    for text in syntax_errors:
        compile_source(text,False,'error:')
    for text,message in subset_errors:
        compile_source(text,False,message)
    compile_source('int f(void) { '+'typeof('*64+'int'+')'*64+' x=0; return x; }')
    compile_source('int f(void) { '+'typeof('*65+'int'+')'*65+' x=0; return x; }',False,'type query nesting exceeds limit (64)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        prototype = f'{name} pick(int,int,int,int,int,int,int,int); '
        plain_helper = (f'{name} pick(int a,int b,int c,int d,int e,int f,int g,int h) {{ '
                        f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        query_helper = plain_helper.replace(f'{name} pick(',f'typeof({name}) pick(',1)
        driver = f'int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        query_driver = driver.replace('return pick(',f'typeof_unqual(const {name}) x=pick(',1).replace(f')=={expected}?42:1;',f'); return x=={expected}?42:1;',1)
        for kcc_text,host_text in [(query_helper,prototype+driver),(prototype+query_driver,plain_helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)], capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, (host_text,result.stderr)
                link_run([assembly,obj])
print(f'Typeof type names passed: {len(programs)} original programs, {native_programs} strict native agreements, {len(constraints)} kcc constraints / {native_constraints} strict native rejections; syntax/subset/64-query limits; {host}'
      + ('; native original C23 keyword support' if native_supported else '; exact legacy keyword absence (no GNU alias oracle)')
      + ('; QBE/runtime and 24 mixed-stack primitive-result ABI arrangements passed' if qbe else ''))
