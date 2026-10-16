"""Fixed target layout, unevaluated constraints and sizeof unsigned-long ABI."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')

def accepts(text):
    return subprocess.run([host, '-std=c2x', '-x', 'c', '-fsyntax-only', '-'],
                          input=text, capture_output=True, text=True, timeout=10).returncode == 0

native_alignment = accepts('_Static_assert(alignof(int)==4,"alignment");')
native_booleans = accepts('_Static_assert(sizeof(true)==1 && sizeof(false)==1,"bool constants"); bool x;')
# Only the host oracle receives these labelled legacy compatibility macros.
prefix = '' if native_alignment else '#define alignof _Alignof\n'
if not native_booleans:
    prefix += '#define bool _Bool\n#define true ((_Bool)1)\n#define false ((_Bool)0)\n'
layouts = [('_Bool', 1), ('char', 1), ('signed char', 1), ('unsigned char', 1),
           ('short', 2), ('unsigned short', 2), ('int', 4), ('unsigned', 4),
           ('long', 8), ('unsigned long', 8), ('long long', 8), ('unsigned long long', 8)]
programs = []
for name, size in layouts:
    programs.append(f'int main(void) {{ const {name} x=0; if(sizeof({name})!={size}UL || '
                    f'sizeof x!={size}UL || alignof(const {name})!={size}UL || _Alignof({name})!={size}UL) return 1; '
                    f'if(sizeof({name}[3][2])!={size*6}UL || alignof({name}[3][2])!={size}UL) return 2; return 42; }}')
programs += [
    'int main(void) { if(sizeof(void *)!=8 || alignof(int *)!=8 || sizeof(int **const)!=8) return 1; return 42; }',
    'int main(void) { if(sizeof(int (*)(int))!=8 || alignof(int (*)(void))!=8 || sizeof(void (*)(void))!=8) return 1; return 42; }',
    'int main(void) { int a[2][3]; if(sizeof a!=24 || sizeof a[0]!=12 || sizeof a[0][0]!=4 || sizeof(a+0)!=8) return 1; return 42; }',
    'int main(void) { int a[3]; int (*p)[]=&a; if(sizeof p!=8 || sizeof *(1?p:&a)!=12) return 1; return 42; }',
    'unsigned long f(int a[3],int g(void)) { return sizeof a+sizeof g; } int id(void) { return 0; } int main(void) { int a[3]; if(f(a,id)!=16) return 1; return 42; }',
    'int main(void) { if(sizeof "abc"!=4 || sizeof("a" "b")!=3 || sizeof "a\\0b"!=4 || sizeof ""!=1) return 1; return 42; }',
    'int main(void) { if(sizeof true!=1 || sizeof false!=1 || sizeof(true?false:true)!=4 || sizeof(bool)!=1) return 1; return 42; }',
    "int main(void) { if(sizeof 'x'!=4 || sizeof((char)'x')!=1 || sizeof((short)1+1)!=4) return 1; return 42; }",
    'int main(void) { if(sizeof(sizeof(int))!=8 || sizeof sizeof true!=8 || sizeof(alignof(int))!=8) return 1; return 42; }',
    'int main(void) { int n=0; if(sizeof(n=42)!=4 || n!=0) return 1; return 42; }',
    'int main(void) { int n=0; if(sizeof(n?((n=1),1L):((n=2),2L))!=8 || n!=0) return 1; return 42; }',
    'int main(void) { int n; if(sizeof(n+1)!=4 || sizeof *&n!=4) return 1; return 42; }',
    'int main(void) { int a[1]; if(sizeof a[999]!=4 || sizeof(a+999)!=8) return 1; return 42; }',
    'int missing(void); int main(void) { if(sizeof missing()!=4) return 1; return 42; }',
    'void missing(void); int main(void) { if(sizeof &missing!=8) return 1; return 42; }',
    'int main(void) { if(sizeof(int[2][3])!=24 || alignof(const int[2][3])!=4) return 1; return 42; }',
    'int main(void) { if(sizeof(int (*)[])!=8 || alignof(int (*)[])!=8) return 1; return 42; }',
    'int main(void) { int a[2]; if(sizeof(a)[0]!=4 || sizeof a*2!=16) return 1; return 42; }',
    'int main(void) { if((sizeof(int)<-1)!=1 || (alignof(int)<-1)!=1) return 1; return 42; }',
    'int main(void) { if(sizeof(int[262144])!=1048576) return 1; return 42; }',
    '#define SIZE sizeof\n#define ALIGN alignof\nint main(void) { if(SIZE(int)!=ALIGN(int)) return 1; return 42; }',
]
constraints = [
    ('int main(void) { return sizeof(void); }', 'complete object'),
    ('int main(void) { return alignof(void); }', 'complete object'),
    ('int f(void); int main(void) { return sizeof f; }', 'complete object'),
    ('int f(void); int main(void) { return sizeof *f; }', 'complete object'),
    ('int main(void) { return sizeof(int (void)); }', 'complete object'),
    ('int main(void) { return _Alignof(int (void)); }', 'complete object'),
    ('int main(void) { return sizeof(int[]); }', 'complete object'),
    ('int main(void) { return alignof(int[]); }', 'complete object'),
    ('int f(int (*p)[]) { return sizeof *p; }', 'complete object'),
    ('int main(void) { return sizeof missing; }', 'undeclared'),
    ('int main(void) { const int x=1; return sizeof(x=2); }', 'modifiable'),
    ('int main(void) { int x=0; return alignof(x); }', 'specifier'),
    ('int main(void) { return alignof 1; }', "expected '('"),
    ('int main(void) { return sizeof(); }', 'expected'),
    ('int main(void) { return sizeof; }', 'expected'),
    ('int main(void) { return sizeof(int; }', "expected ')'"),
    ('int main(void) { return alignof(int; }', "expected ')'"),
    ('int main(void) { return sizeof(int)1; }', 'expected'),
    ('int main(void) { int n=sizeof(int); int a[n]; return 0; }', 'integer constant expression'),
]
with tempfile.TemporaryDirectory(prefix='kcc sizeof ') as directory:
    directory = Path(directory)
    source, other, il, assembly, obj, executable = [directory / name for name in
                                                  ('k.c', 'h.c', 'k.ssa', 'k.s', 'h.o', 'p')]

    def compile_source(text):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
        return result.stdout

    def run(objects):
        subprocess.run([host, *map(str, objects), '-o', str(executable)], capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42

    for text in programs:
        compile_source(text)
        if qbe:
            run([assembly])
        other.write_text(prefix + text)
        result = subprocess.run([host, '-std=c2x', '-fsigned-char', str(other), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (text, result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    for name, size in layouts:
        helper = f'unsigned long measure({name} *p) {{ return sizeof *p+alignof({name}); }}'
        driver = f'unsigned long measure({name} *); int main(void) {{ {name} x=0; '
        driver += f'if(measure(&x)!={size*2}UL) return 1; return 42; }}'
        for kcc_text, host_text in [(helper, driver), (driver, helper)]:
            compile_source(kcc_text)
            if qbe:
                other.write_text(prefix + host_text)
                subprocess.run([host, '-std=c2x', '-c', str(other), '-o', str(obj)],
                               capture_output=True, check=True, timeout=10)
                run([assembly, obj])

    # Native null is never converted by kcc and never dereferenced at runtime.
    compile_source('unsigned long measure(int *p) { return sizeof *p; }')
    if qbe:
        other.write_text('unsigned long measure(int *); int main(void) { if(measure((int *)0)!=4) return 1; return 42; }')
        subprocess.run([host, '-std=c2x', '-c', str(other), '-o', str(obj)],
                       capture_output=True, check=True, timeout=10)
        run([assembly, obj])

    il_text = compile_source('int missing(void); unsigned long only(void) { return sizeof missing(); }')
    assert 'call $missing' not in il_text and '=l copy 4' in il_text, il_text
    for text, message in constraints:
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)

    # n sizeof nodes plus one leaf; type form starts at depth 1 too.
    for count, valid in [(127, True), (128, False)]:
        source.write_text('unsigned long f(void) { return ' + 'sizeof ' * count + '1; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr
    # No root load: sizeof x with 126 unary sizeof layers above it is depth 128.
    for count, valid in [(126, True), (127, False)]:
        source.write_text('unsigned long f(void) { int x; return ' + 'sizeof ' * count + 'sizeof x; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr

print(f'Sizeof/alignment passed: {len(programs)} full-value programs, {len(constraints)} constraints, '
      f'exact unevaluated depths; {host}; '
      + ('native alignof' if native_alignment else 'labelled alignof/_Alignof compatibility oracle')
      + ('; QBE/runtime, 24 unsigned-long ABI arrangements and native-null unevaluated operand passed' if qbe else ''))
