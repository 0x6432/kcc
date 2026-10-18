"""Query-derived file-scope function declarations preserve written syntax."""
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
integers = ['_Bool','char','signed char','unsigned char','short','unsigned short',
            'int','unsigned','long','unsigned long','long long','unsigned long long']
programs = []
for operator in ['typeof','typeof_unqual']:
    programs += [
        f'{operator}(int(void)) f; int f(void) {{ return 42; }} int main(void) {{ return f(); }}',
        f'{operator}(int(int)) f; int f(int x) {{ return x+2; }} int main(void) {{ return f(40); }}',
        f'int f(int); {operator}(f) g; int g(int x) {{ return x+2; }} int main(void) {{ return g(40); }}',
        f'int f(int x) {{ return x+2; }} {operator}(f) f; int main(void) {{ return f(40); }}',
        f'{operator}(int(typeof(void))) f; int f(void) {{ return 42; }} int main(void) {{ return f(); }}',
        f'{operator}(int(int[2])) sum; int sum(int *p) {{ return p[0]+p[1]; }} int main(void) {{ int a[2]; a[0]=40; a[1]=2; return sum(a); }}',
        f'{operator}(int(int(int))) apply; int apply(int (*p)(int)) {{ return p(40); }} int add(int x) {{ return x+2; }} int main(void) {{ return apply(add); }}',
        f'{operator}(int *(int *)) same; int *same(int *p) {{ return p; }} int main(void) {{ int x=42; return *same(&x); }}',
        f'{operator}(int(const int)) f; int f(int x) {{ return x+2; }} int main(void) {{ return f(40); }}',
        f'{operator}(int(int x,typeof(x))) f; int f(int x,int y) {{ return x+y; }} int main(void) {{ return f(40,2); }}',
        f'{operator}(int(void)) main; int main(void) {{ return 42; }}',
        f'{operator}(int(void)) (f); int f(void) {{ return 42; }} int main(void) {{ return f(); }}',
    ]
programs += [
    'typeof(typeof(int(void))) f; int f(void) { return 42; } int main(void) { return f(); }',
    'int base(int x) { return x; } typeof(base) other; int other(int x) { return x+2; } int main(void) { return base(40)==40?other(40):1; }',
    'typeof(int(int)) f; int main(void) { int (*p)(int)=f; return p(40); } int f(int x) { return x+2; }',
    'typeof(int(int)) f; int f(int x) { if(x==0) return 42; return f(x-1); } int main(void) { return f(3); }',
    'int add(int x) { return x+2; } int (*pick(void))(int); typeof(pick) pick; int (*pick(void))(int) { return add; } int main(void) { return pick()(40); }',
    'typeof(void(int *)) effect; void effect(int *p) { *p=42; } int main(void) { int x=0; effect(&x); return x; }',
    'typeof(typeof(nullptr)(typeof(nullptr))) same; typeof(nullptr) same(typeof(nullptr) n) { return n; } int main(void) { return same(0)==nullptr?42:1; }',
    'int f(int (*)[2]); typeof(f) f; int f(int (*p)[2]) { return (*p)[1]; } int main(void) { int a[2]; a[1]=42; return f(&a); }',
    'int f(int (*)[]); typeof(f) f; int f(int (*)[2]); typeof(f) f; int f(int (*p)[]) { return (*p)[1]; } int main(void) { int a[2]; a[1]=42; return f(&a); }',
    '#define SIGNATURE typeof(int(int))\nSIGNATURE f; int f(int x) { return x+2; } int main(void) { return f(40); }',
]
constraints = [
    ('typeof(int(void)) f; long f(void);','incompatible function declaration'),
    ('long f(void); typeof(int(void)) f;','incompatible function declaration'),
    ('typeof(int(int)) f; int f(void);','incompatible function declaration'),
    ('typeof(int(int *)) f; int f(long *);','incompatible function declaration'),
    ('typeof(int(int)) f; int g(void) { return f(); }','argument count'),
    ('typeof(int(void)) f; int g(void) { return f(1); }','argument count'),
    ('typeof(missing) f;','undeclared'),
    ('typeof(f) f;','undeclared'),
    ('typeof(later) f; int later(void);','undeclared'),
    ('int f(int (*)[]); typeof(f) f; int f(int (*)[2]); typeof(f) f; int f(int (*)[3]);','incompatible function declaration'),
    ('typeof(int(int n,typeof(n))) f; int main(void) { return n; }','undeclared'),
    ('typeof(int(void)) f; int f(void) { return 42; } int f(void) { return 42; }','redefinition'),
]
subset_errors = [
    ('typeof(void) x;','file-scope declaration requires a scalar, array or record object type'),
    ('typeof(int(void)) f { return 42; }',"query-derived external declarations require ';'"),
    ('typeof(int(void)) f=0;',"query-derived external declarations require ';'"),
    ('const typeof(int(void)) f;','function type cannot be qualified'),
    ('typeof(int(int)) main;','only zero-parameter main'),
    ('typeof(long(void)) main;','main must return int'),
]
with tempfile.TemporaryDirectory(prefix='kcc queried function declarations ') as directory:
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
            assert result.returncode != 0, text
            native_constraints += 1
    for text,message in subset_errors:
        compile_source(text,False,message)
    output = compile_source('typeof(int(int)) f;')
    assert 'function' not in output and '$f' not in output
    for amount in [256,257]:
        compile_source(''.join(f'typeof(int(void)) f{i};' for i in range(amount)),amount==256,
                       '' if amount==256 else 'translation unit exceeds function limit (256)')
    for amount in [512,513]:
        compile_source('typeof(int(void)) f;'*amount,amount==512,
                       '' if amount==512 else 'translation unit exceeds declaration limit (512)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        parameters = 'int a,int b,int c,int d,int e,int f,int g,int h'
        prototype = f'{name} pick({parameters}); '
        query_prototype = f'typeof({name}({parameters})) pick; '
        helper = (f'{name} pick({parameters}) {{ '
                  f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        driver = f'int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        for kcc_text,host_text in [(query_prototype+helper,prototype+driver),
                                   (query_prototype+driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)], capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, (host_text,result.stderr)
                link_run([assembly,obj])
print(f'Queried function declarations passed: {len(programs)} original programs, {native_programs} strict native agreements, {len(constraints)} kcc constraints / {native_constraints} native rejections; subset/symbol/composite and 256-function/512-declaration limits, declaration-only IL; {host}'
      + ('; native original C23 keyword support' if native_supported else '; exact legacy keyword absence (no alias oracle)')
      + ('; QBE/runtime and 24 mixed-stack primitive-result ABI arrangements passed' if qbe else ''))
