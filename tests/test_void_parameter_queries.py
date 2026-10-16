"""Written query-derived void markers normalize to zero semantic parameters."""
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
markers = ['typeof(void)','typeof_unqual(const void)','typeof((void)0)',
           'typeof(typeof_unqual(const void))']
programs = [
    'int main(void) { return 42; }',
    'int main() { return 42; }',
    'int f(void) { return 42; } int main(void) { int (*p)(void)=f; return p(); }',
]
for marker in markers:
    programs += [
        f'int main({marker}) {{ return 42; }}',
        f'int f({marker}) {{ return 42; }} int main(void) {{ return f(); }}',
        f'int f(void); int f({marker}) {{ return 42; }} int main(void) {{ return f(); }}',
        f'int f({marker}); int f(void) {{ return 42; }} int main(void) {{ int (*p)({marker})=f; return p(); }}',
        f'int f({marker}) {{ return 42; }} int main(void) {{ typeof(int({marker})) *p=f; return p(); }}',
        f'int f({marker}) {{ return 42; }} int main(void) {{ typeof(f) *p=f; return p(); }}',
        f'int f({marker}) {{ return 42; }} int main(void) {{ int (*p[2])({marker}); p[1]=f; return p[1](); }}',
    ]
programs += [
    'int f(void) { return 2; } int main(void) { int x=40; int (*p)(typeof((void)x++))=f; return x+p(); }',
    'void effect(typeof(void)) { return; } int main(void) { effect(); return 42; }',
    'typeof((void)0) effect(typeof_unqual(const void)) { return; } int main(void) { effect(); return 42; }',
    'int f(typeof(void)) { return 42; } typeof(f) *pick(typeof((void)0)) { return f; } int main(void) { return pick()(); }',
    'int f(typeof(void)) { return 42; } int apply(int (*p)(typeof(void))) { return p(); } int main(void) { return apply(f); }',
    'int f(typeof(void)) { return 42; } int main(void) { _Static_assert(sizeof(typeof(&f))==8,"pointer"); return f(); }',
    '#define EMPTY typeof(void)\nint f(EMPTY) { return 42; } int main(EMPTY) { return f(); }',
]
constraints = [
    ('int f(typeof(void) x);','parameter cannot have void type'),
    ('int f(typeof((void)0) x) { return 0; }','parameter cannot have void type'),
    ('int f(typeof(void),int);','parameter cannot have void type'),
    ('int f(int,typeof(void));','parameter cannot have void type'),
    ('int f(typeof(void),typeof(void));','parameter cannot have void type'),
    ('int f(typeof(const void));','parameter cannot have void type'),
    ('int f(const typeof(void));','parameter cannot have void type'),
    ('int f(void) { int (*p)(typeof(void) named); return 0; }','parameter cannot have void type'),
    ('int f(typeof(void)); int g(void) { return f(1); }','argument count'),
    ('int f(void) { int (*p)(typeof(void))=0; return p(1); }','argument count'),
    ('int f(typeof(void)); int f(int);','incompatible function declaration'),
    ('int f(int); int f(typeof(void));','incompatible function declaration'),
]
syntax_errors = ['int f(typeof(void),);','int f(typeof(void) {}']
subset_errors = [
    ('int main(int x) { return x; }','only zero-parameter main'),
    ('int main(typeof(int) x) { return x; }','only zero-parameter main'),
]
def native_named_void_warning(text, status, diagnostics):
    expected = {
        'int f(typeof(void) x);': "parameter 1 ('x') has void type",
        'int f(void) { int (*p)(typeof(void) named); return 0; }': "parameter 1 ('named') has void type",
    }
    if text not in expected or status != 0:
        return False
    normalized = diagnostics.replace('‘', "'").replace('’', "'")
    messages = re.findall(r'(fatal error|error|warning): ([^\n]+)', normalized)
    return messages == [('warning', expected[text])]


# A required diagnostic need not have error severity. Count these exact GCC
# warnings separately from strict native rejections; kcc acceptance is unchanged.
for original, name in [('int f(typeof(void) x);', 'x'),
                       ('int f(void) { int (*p)(typeof(void) named); return 0; }', 'named')]:
    warning = f"source.c:1:1: warning: parameter 1 ('{name}') has void type\n"
    assert native_named_void_warning(original, 0, warning)
    assert not native_named_void_warning('int other(void);', 0, warning)
    assert not native_named_void_warning(original, 1, warning)
    assert not native_named_void_warning(original, 0, '')
    assert not native_named_void_warning(original, 0, warning+'source.c:1:2: error: unexpected\n')
    assert not native_named_void_warning(original, 0, warning+'source.c:1:2: warning: unrelated\n')


with tempfile.TemporaryDirectory(prefix='kcc void parameter queries ') as directory:
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
    native_void_warnings = 0
    for text in programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if native_supported or 'typeof' not in text:
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
            if native_named_void_warning(text, result.returncode, result.stderr):
                assert not result.stdout
                native_void_warnings += 1
            else:
                assert result.returncode != 0, (text,result.stderr)
                native_constraints += 1
    for text in syntax_errors:
        compile_source(text,False,'error:')
    for text,message in subset_errors:
        compile_source(text,False,message)
    # The sole marker is one written node, never a runtime parameter or spill.
    output = compile_source('int main(typeof(void)) { return 42; }')
    assert '$main()' in output and '%p0' not in output and 'alloc' not in output
    for amount in [128,129]:
        parameters = ','.join(['typeof(int)']*amount)
        compile_source('int f('+parameters+') { return 42; }',amount==128,
                       '' if amount==128 else 'function exceeds parameter limit (128)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        plain_helper = f'{name} pick(void) {{ return {expected}; }}'
        query_helper = f'{name} pick(typeof((void)0)) {{ return {expected}; }}'
        driver = f'int main(void) {{ return pick()=={expected}?42:1; }}'
        plain_prototype = f'{name} pick(void); '
        query_prototype = f'{name} pick(typeof_unqual(const void)); '
        for kcc_text,host_text in [(query_helper,plain_prototype+driver),
                                   (query_prototype+driver,plain_helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)], capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, (host_text,result.stderr)
                link_run([assembly,obj])
print(f'Void parameter queries passed: {len(programs)} original programs, {native_programs} strict native agreements, {len(constraints)} kcc constraints / {native_constraints} strict native rejections / {native_void_warnings} exact native named-void diagnostics; syntax/subset/128-real-parameter limits and no marker ABI slot; {host}'
      + ('; native original C23 keyword support' if native_supported else '; exact legacy keyword absence (no GNU alias oracle)')
      + ('; QBE/runtime and 24 zero-argument primitive-result ABI arrangements passed' if qbe else ''))
