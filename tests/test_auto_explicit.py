"""Explicit auto storage uses ordinary object semantics, separately from C23 inference."""
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
expected_gaps = {}
for name in integers:
    value = '1' if name == '_Bool' else '42'
    programs += [f'int main(void) {{ auto {name} x={value}; return x=={value}?42:1; }}']
    text = f'typedef {name} T; int main(void) {{ T auto x={value}; T *p=&x; return *p=={value}?42:1; }}'
    programs.append(text)
    expected_gaps[text] = ["cannot combine with previous 'type-name' declaration specifier"]
programs += [
    'int main(void) { int auto x=42; return x; }',
    'int main(void) { const auto int x=42; return x; }',
    'int main(void) { auto const long x=42; return x; }',
    'int main(void) { unsigned long auto long const x=42; return x; }',
    'int main(void) { auto int x=40,*p=&x; *p+=2; return x; }',
    'int main(void) { auto int a[2],*p=a; p[1]=42; return a[1]; }',
    'int pick(int x) { return x; } int main(void) { auto int (*p)(int)=pick; return p(42); }',
    'typedef char T; int main(void) { auto int (*T)[sizeof(T)]=0; return sizeof(*T)==4?42:1; }',
    'typedef long T; int main(void) { { T auto T=40,*P=&T; *P+=2; if(T!=42) return 1; } T x=42; return x; }',
    'typedef long T; int main(void) { for(auto int T=0;T<2;T++) {} T x=42; return x; }',
    'int main(void) { auto int x=40; { register int x=2; x++; } return x+2; }',
    'int main(void) { register int x=40; { auto int x=2; int *p=&x; *p=3; } return x+2; }',
    'int main(void) { auto int x=40; for(auto int i=0,j=2;i<j;i++) x++; return x; }',
    '#define STORE auto\nint main(void) { STORE int x=42; return x; }',
    '#define auto int\nint main(void) { auto x=42; return x; }',
    'typedef long T; int main(void) { auto T x=42; return x; }',
]
expected_gaps[programs[26]] = ["'long auto' is invalid"]
expected_gaps[programs[24]] = ["cannot combine with previous 'int' declaration specifier"]
expected_gaps[programs[32]] = ["cannot combine with previous 'type-name' declaration specifier"]
keyword_macro = programs[-2]
expected_gaps[keyword_macro] = ['keyword is hidden by macro definition [-Werror,-Wkeyword-macro]']
expected_gaps[programs[-1]] = ["declaration of variable 'T' with deduced type 'auto' requires an initializer", "expected ';' at end of declaration", "use of undeclared identifier 'x'"]
c23_programs = [
    'int main(void) { auto typeof(int) x=42; return x; }',
    'int main(void) { typeof(int) auto x=42; return x; }',
    'int main(void) { const int x=40; auto typeof_unqual(x) y=1; y++; return x+y; }',
    'int main(void) { auto bool x=true; return x?42:1; }',
    'int main(void) { auto typeof(nullptr) x=0; return x==nullptr?42:1; }',
    'int main(void) { register int a[2]; auto typeof(a) b; b[1]=42; return b[1]; }',
]
for index in [0,2]:
    expected_gaps[c23_programs[index]] = ["cannot combine with previous 'auto' declaration specifier"]
expected_gaps[c23_programs[5]] = ["cannot combine with previous 'auto' declaration specifier", "declaration of variable 'b' with deduced type 'auto' requires an initializer"]
expected_gaps[c23_programs[1]] = ["cannot combine with previous 'typeof' declaration specifier"]
expected_gaps[c23_programs[4]] = ["cannot combine with previous 'auto' declaration specifier", "invalid operands to binary expression ('int' and 'nullptr_t')"]
constraints = [
    ('auto int value;', 'file-scope auto declarations'),
    ('auto int f(void);', 'file-scope auto declarations'),
    ('int main(void) { auto int f(void); return 0; }', 'auto storage requires an object type'),
    ('typedef int F(void); int main(void) { auto F f; return 0; }', 'block-scope function declarations'),
    ('int main(void) { auto auto int x; return 0; }', 'duplicate auto storage-class'),
    ('int main(void) { auto typedef int T; return 0; }', 'multiple storage-class'),
    ('int main(void) { typedef int auto T; return 0; }', 'multiple storage-class'),
    ('int f(auto int x);', 'auto is not permitted'),
    ('int main(void) { return sizeof(auto int); }', 'auto is not permitted'),
    ('int main(void) { return (auto int)42; }', 'auto is not permitted'),
    ('int main(void) { auto const int x=0; x=1; return 0; }', 'modifiable'),
    ('int main(void) { auto int x=0; int x=1; return 0; }', 'redeclaration'),
    ('int main(void) { typedef int T; auto int T=1; return 0; }', 'ordinary declaration conflicts'),
]
c23_constraints = []
subset_errors = [
    ('auto x=42;', 'file-scope auto declarations are not supported yet'),
    ('int main(void) { auto register x=42; return x; }', 'combined auto storage classes are not supported'),
    ('int main(void) { register auto x=42; return x; }', 'combined auto storage classes are not supported'),
    ('int f(int n) { auto int a[n]; return 0; }', 'variable-length arrays'),
    ('int main(void) { auto int a[2]=0; return 0; }', 'array initializers are not supported'),
]


def native_auto_gap(text, status, diagnostics):
    if text not in expected_gaps or status != 1:
        return False
    records = re.findall(r'(fatal error|error|warning|note): ([^\n]+)', diagnostics.replace('‘', "'").replace('’', "'"))
    return records == [('error', message) for message in expected_gaps[text]]


for original,messages in expected_gaps.items():
    diagnostic = ''.join('test.c:1:1: error: '+message+'\n' for message in messages)
    assert native_auto_gap(original,1,diagnostic)
    assert not native_auto_gap(programs[0],1,diagnostic)
    for status in [0,-11,127]:
        assert not native_auto_gap(original,status,diagnostic)
    assert not native_auto_gap(original,1,diagnostic+'test.c:1:1: note: unrelated\n')
    assert not native_auto_gap(original,1,diagnostic+diagnostic)


with tempfile.TemporaryDirectory(prefix='kcc explicit auto ') as directory:
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
            assert result.returncode == 1 and not result.stdout and message in result.stderr,(text[:1800],result.stderr)
        return result.stdout

    def link_run(objects):
        result = subprocess.run([host,*map(str,objects),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        assert result.returncode == 0,result.stderr
        assert subprocess.run([str(executable)],timeout=5).returncode == 42

    native.write_text('typeof(int) value;\n')
    probe = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
    native_c23 = probe.returncode == 0
    if not native_c23:
        errors = re.findall(r'error: ([^\n]+)',probe.stderr.replace('‘', "'").replace('’', "'"))
        assert errors in [["return type defaults to 'int' [-Wimplicit-int]", "expected declaration specifiers before 'value'", "expected '{' at end of input"], ['expected function body after function declarator']],probe.stderr
    native_programs = native_constraints = native_gaps = c11_corroborations = 0
    for text in programs+c23_programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if text in c23_programs and not native_c23:
            continue
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        if native_auto_gap(text,result.returncode,result.stderr):
            native_gaps += 1
            if text in programs and text != keyword_macro:
                # Same original source; independent traditional-C corroboration,
                # deliberately not a C23 agreement or source-rewriting workaround.
                older = subprocess.run([host,'-std=c11','-pedantic-errors',str(native),'-o',str(executable)],capture_output=True,text=True,timeout=10)
                assert older.returncode == 0,(text,older.stderr)
                assert subprocess.run([str(executable)],timeout=5).returncode == 42,text
                c11_corroborations += 1
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
        assert result.returncode != 0,(text,result.stderr)
        native_constraints += 1
    for text,message in subset_errors:
        compile_source(text,False,message)
    for amount in [256,257]:
        compile_source('int main(void) { auto char '+','.join(f'a{i}[1]' for i in range(amount))+'; return 42; }',amount==256,
                       '' if amount==256 else 'local limit (256)')
    for amount in [4094,4095]:
        compile_source('int main(void) { auto int a[2]; '+'0;'*amount+' return 42; }',amount==4094,
                       '' if amount==4094 else 'item limit (4096)')
    for amount in [1048576,1048577]:
        compile_source(f'int f(void) {{ auto char a[{amount}]; return 42; }}',amount==1048576,
                       '' if amount==1048576 else 'storage limit')
    for depth in [62,63]:
        compile_source('typedef int '+'*'*64+' A; typedef A '+'*'*depth+' B[1]; int f(void) { auto B a; return 42; }',depth==62,
                       '' if depth==62 else 'depth limit (128)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = 'int a,int b,int c,int d,int e,int f,int g,int h'
        checks = 'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0;'
        helper = f'{name} pick({params}) {{ {checks} return {expected}; }}'
        definition = f'{name} pick({params}) {{ auto {name} value={expected}; {checks} return value; }}'
        driver = f'{name} pick({params}); int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        typed_driver = f'{name} pick({params}); int main(void) {{ auto {name} value=pick(1,2,3,4,5,6,7,8); return value=={expected}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(typed_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Explicit auto passed: {len(programs)} standard + {len(c23_programs)} C23 originals; '
      f'{native_programs} strict C23 native agreements, {native_gaps} exact native diagnostic gaps, {c11_corroborations} unchanged-source C11 corroborations (not C23 agreements); '
      f'{native_constraints} native constraints, {len(subset_errors)} subset refusals; '
      f'256 locals/4096 items/1 MiB storage/128 expanded-typedef depth boundaries; {host}'
      + ('; original C23 keywords' if native_c23 else '; exact legacy keyword absence (not agreements)')
      + ('; QBE/runtime and 24 both-direction mixed-stack ABI arrangements passed' if qbe else ''))
