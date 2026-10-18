"""C23 expression type queries preserve root types without runtime evaluation."""
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
for name in integers:
    value = '1' if name == '_Bool' else '42'
    programs += [
        f'int main(void) {{ {name} x={value}; typeof(x) y=x; return y=={value}?42:1; }}',
        f'int main(void) {{ const {name} x={value}; typeof_unqual(x) y=0; y=x; return y=={value}?42:1; }}',
    ]
programs += [
    'typeof(1+1) main(void) { return 42; }',
    'int main(void) { int x=40; typeof(x++) y=2; return x+y; }',
    'int main(void) { int x=40; typeof(++x) y=2; return x+y; }',
    'int main(void) { int x=40; typeof(x=0) y=2; return x+y; }',
    'int main(void) { int x=40; typeof(x+=1) y=2; return x+y; }',
    'int effect(int *p) { *p=0; return 1; } int main(void) { int x=40; typeof(effect(&x)) y=2; return x+y; }',
    'int main(void) { int x=40; typeof(x=0,x++) y=2; return x+y; }',
    'int main(void) { int x=40; typeof(x?++x:x++) y=2; return x+y; }',
    'int main(void) { int x=40; typeof(sizeof(typeof(x++))) y=2; return x+y; }',
    'int main(void) { int x=40; _Static_assert(sizeof(typeof(x++))==4,"unevaluated"); return x+2; }',
    'int main(void) { int x=40; int a[sizeof(typeof(x++))]; a[0]=2; return x+a[0]; }',
    'int main(void) { int x=40; return x+_Alignof(typeof((short)x++)); }',
    'int main(void) { int *p=0; typeof(*p) x=42; return x; }',
    'int main(void) { typeof(1/0) x=42; return x; }',
    'int main(void) { int a[2][3]; typeof(a) b; b[1][2]=42; return b[1][2]; }',
    'int main(void) { const int a[2]; typeof_unqual(a) b; b[1]=42; return b[1]; }',
    'int main(void) { int a[2]; typeof(&a) p=&a; (*p)[1]=42; return a[1]; }',
    'int main(void) { typeof("x") a; a[0]=42; return a[0]; }',
    'int main(void) { const int x=40; typeof((0,x)) y=0; y=2; return x+y; }',
    'int main(void) { const int x=40; typeof(x+0) y=0; y=2; return x+y; }',
    'int main(void) { int x=40,y=42; const int *const p=&x; typeof_unqual(p) q=p; q=&y; return *q; }',
    'int add(int x) { return x+2; } int main(void) { typeof(add) *p=add; return p(40); }',
    'int add(int x) { return x+2; } int main(void) { typeof(&add) p=add; typeof(*p) *q=p; return q(40); }',
    'int add(int x) { return x+2; } int apply(typeof(add) f) { return f(40); } int main(void) { return apply(add); }',
    'int f(int x,typeof(x) y) { return x+y; } int main(void) { return f(40,2); }',
    'int f(int a[2],typeof(a) b) { return a[0]+b[1]; } int main(void) { int a[2]; a[0]=40; a[1]=2; return f(a,a); }',
    'int f(const int x,typeof(x) y) { return x+y; } int main(void) { return f(40,2); }',
    'int f(int x,typeof(x) y); int f(int x,int y) { return x+y; } int main(void) { return f(40,2); }',
    'typeof((void)0) effect(int *p) { *p=42; return; } int main(void) { int x=0; effect(&x); return x; }',
    'int main(void) { int x=40; (typeof((void)x++))0; return x+2; }',
    'int main(void) { const int x=42; { typeof_unqual(x) x=40; x+=2; return x; } }',
    'int main(void) { for(int i=0;i<1;i++) { typeof(i) x=42; return x; } return 0; }',
    '#define QUERY typeof\nint main(void) { int x=42; QUERY(x) y=x; return y; }',
    'int main(void) { typeof(nullptr) n=nullptr; n=nullptr; return n==nullptr?42:1; }',
    'int main(void) { typeof(nullptr) n=nullptr; int *p=n; return p==0 && !n?42:1; }',
    'int main(void) { const typeof(nullptr) n=nullptr; typeof_unqual(n) m=n; m=nullptr; return m==nullptr?42:1; }',
    'typeof(nullptr) f(typeof(nullptr) n) { return n; } int main(void) { return f(nullptr)==nullptr?42:1; }',
    'int main(void) { typeof(nullptr) n=nullptr; typeof(&n) p=&n; *p=nullptr; return *p==nullptr?42:1; }',
    'int main(void) { typeof(nullptr) n=(typeof(nullptr))0; return n==nullptr?42:1; }',
    'int main(void) { typeof(nullptr) n=(typeof(nullptr))(2-2); return n==nullptr?42:1; }',
    'int main(void) { typeof(nullptr) n=(typeof(nullptr))(void *)0; return n==nullptr?42:1; }',
]
programs += ['int main(void) { typeof(nullptr) n=0; return n==nullptr?42:1; }', 'int main(void) { typeof(nullptr) n=nullptr; n=0; return n==nullptr?42:1; }', 'typeof(nullptr) f(void) { return 0; } int main(void) { return f()==nullptr?42:1; }', 'int f(typeof(nullptr) n) { return n==nullptr?42:1; } int main(void) { return f(0); }']
constraints = [
    ('int f(void) { const int x=0; typeof(x) y=0; y=1; return 0; }','modifiable'),
    ('int f(void) { const int a[2]; typeof(a) b; b[0]=1; return 0; }','modifiable'),
    ('int f(void) { int x=0; const int *p=&x; typeof_unqual(p) q=p; *q=1; return 0; }','modifiable'),
    ('int f(void) { typeof(missing) x; return 0; }','undeclared'),
    ('int f(void) { typeof(x) x; return 0; }','undeclared'),
    ('int f(void) { const int x=0; typeof(x++) y; return 0; }','modifiable'),
    ('int f(int); int g(void) { typeof(f()) x; return 0; }','argument count'),
    ('int f(void) { typeof(*1) x; return 0; }','pointer'),
    ('int f(void) { typeof((void)0) x; return 0; }','complete'),
    ('int f(void) { int x=0; typeof(nullptr) n=x; return 0; }','conversion'),
    ('int f(void) { int x=0; typeof(nullptr) n=nullptr; n=x; return 0; }','conversion'),
    ('typeof(nullptr) f(void) { int x=0; return x; }','conversion'),
    ('int f(typeof(nullptr)); int g(void) { int x=0; return f(x); }','conversion'),
    ('int f(void) { int x=0; typeof(nullptr) n=(typeof(nullptr))x; return 0; }','cast to nullptr type'),
    ('int f(void) { int *p=0; typeof(nullptr) n=(typeof(nullptr))p; return 0; }','cast to nullptr type'),
    ('int f(void) { typeof(nullptr) n=(typeof(nullptr))1; return 0; }','cast to nullptr type'),
    ('int f(void) { typeof(nullptr) n=nullptr; return n+1; }','integer'),
]
syntax_errors = ['int f(void) { typeof(1+ ) x; }','int f(void) { typeof(1;2) x; }',
                 'int f(void) { typeof(1,) x; }','int f(void) { typeof(1 x; }']
subset_errors = [
    ('int f(void) { int a[2]; typeof(a) b=a; return 0; }','array initializers are not supported yet'),
    ('int f(int n) { int a[n]; typeof(a) b; return 0; }','variable-length'),
]
def native_array_qualification_gap(text, diagnostics):
    expected = 'int main(void) { const int a[2]; typeof_unqual(a) b; b[1]=42; return b[1]; }'
    errors = re.findall(r'error: ([^\n]+)',diagnostics.replace('‘', "'").replace('’', "'"))
    return text == expected and errors in [["assignment of read-only location 'b[1]'"],
                                          ['read-only variable is not assignable']]

# Diagnostic classifier units do not pretend to be native compiler executions.
array_gap_source = 'int main(void) { const int a[2]; typeof_unqual(a) b; b[1]=42; return b[1]; }'
for diagnostic in ["error: assignment of read-only location ‘b[1]’\n",
                   "error: read-only variable is not assignable\n"]:
    assert native_array_qualification_gap(array_gap_source, diagnostic)
    assert not native_array_qualification_gap('int unrelated;', diagnostic)
    assert not native_array_qualification_gap(array_gap_source, diagnostic+'error: unexpected failure\n')
assert not native_array_qualification_gap(array_gap_source, 'error: unsupported operand\n')

def native_nullptr_cast_gap(text, diagnostics):
    expected = {
        'int main(void) { typeof(nullptr) n=(typeof(nullptr))0; return n==nullptr?42:1; }': "cannot cast an object of type 'int' to 'nullptr_t'",
        'int main(void) { typeof(nullptr) n=(typeof(nullptr))(2-2); return n==nullptr?42:1; }': "cannot cast an object of type 'int' to 'nullptr_t'",
        'int main(void) { typeof(nullptr) n=(typeof(nullptr))(void *)0; return n==nullptr?42:1; }': "cannot cast an object of type 'void *' to 'nullptr_t'",
    }
    errors = re.findall(r'error: ([^\n]+)',diagnostics.replace('‘', "'").replace('’', "'"))
    return text in expected and errors == [expected[text]]

# Exact local Clang 18 diagnostics; future accepting hosts count as agreements.
for operand,kind in [('0','int'),('(2-2)','int'),('(void *)0','void *')]:
    text = f'int main(void) {{ typeof(nullptr) n=(typeof(nullptr)){operand}; return n==nullptr?42:1; }}'
    diagnostic = f"error: cannot cast an object of type '{kind}' to 'nullptr_t'\n"
    assert native_nullptr_cast_gap(text, diagnostic)
    assert not native_nullptr_cast_gap('int unrelated;', diagnostic)
    assert not native_nullptr_cast_gap(text, diagnostic+'error: unexpected failure\n')
    assert not native_nullptr_cast_gap(text, 'error: unsupported operand\n')

with tempfile.TemporaryDirectory(prefix='kcc typeof expressions ') as directory:
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
    native_array_gaps = 0
    native_cast_gaps = 0
    native_constraints = 0
    for text in programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if native_supported:
            native.write_text(text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)], capture_output=True, text=True, timeout=10)
            if result.returncode:
                # Distinct, exact observed gaps, never broad native failures.
                if native_array_qualification_gap(text, result.stderr):
                    native_array_gaps += 1
                else:
                    assert native_nullptr_cast_gap(text, result.stderr), (text,result.stderr)
                    native_cast_gaps += 1
            else:
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
    # Interleave expression/type-name queries to exercise the shared guard.
    for depth in [64,65]:
        query = 'typeof(0)'
        for level in range(depth-1):
            query = f'typeof(sizeof({query}))'
        compile_source('int f(void) { '+query+' x=0; return x; }',depth==64,
                       '' if depth==64 else 'type query nesting exceeds limit (64)')
    # No side-effecting query subtree appears in emitted executable instructions.
    output = compile_source('int effect(int *p) { *p=0; return 1; } int main(void) { int x=40; typeof(effect(&x)) y=2; return x+y; }')
    assert 'call $effect' not in output
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        prototype = f'{name} pick(int,int,int,int,int,int,int,int); '
        plain_helper = (f'{name} pick(int a,int b,int c,int d,int e,int f,int g,int h) {{ '
                        f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        query_helper = plain_helper.replace(f'{name} pick(',f'typeof(({name})0) pick(',1)
        driver = f'int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        query_driver = driver.replace('return pick(','typeof(pick(1,2,3,4,5,6,7,8)) x=pick(',1).replace(f')=={expected}?42:1;',f'); return x=={expected}?42:1;',1)
        for kcc_text,host_text in [(query_helper,prototype+driver),(prototype+query_driver,plain_helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)], capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, (host_text,result.stderr)
                link_run([assembly,obj])
print(f'Typeof expressions passed: {len(programs)} original programs, {native_programs} strict native agreements / {native_array_gaps} exact native array-qualification gaps / {native_cast_gaps} exact native nullptr-cast gaps, {len(constraints)} kcc constraints / {native_constraints} strict native rejections; syntax/subset/mixed 64-query limits and operand non-evaluation; {host}'
      + ('; native original C23 keyword support' if native_supported else '; exact legacy keyword absence (no GNU alias oracle)')
      + ('; QBE/runtime and 24 mixed-stack primitive-result ABI arrangements passed' if qbe else ''))
