"""Typed conditional arithmetic, composite pointers and selected QBE control flow."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
# Every case is defined whichever arm it selects. Potentially invalid operations
# occur only in explicitly unselected arms, testing non-eager lowering.
qualified_incomplete_array_case = 'int main(void) { int a[3]; a[2]=42; const int (*p)[]=&a; return (*(0?&a:p))[2]; }'
qualified_row_array_case = 'int main(void) { int a[2][3]; a[1][2]=42; const int (*p)[3]=a; return (0?a:p)[1][2]; }'
programs = [
    'int main(void) { return 1?42:7; }',
    'int main(void) { return 0?7:42; }',
    'int main(void) { int n=0; return (n=n+1)?(n=n+41):(n=1); }',
    'int main(void) { int n=0; int x=1?n=20,n=n+22:7; if(n!=42) return 1; return x; }',
    'int main(void) { int n=1; return 0?7:(n=42); }',
    'int main(void) { return 0?1:0?2:42; }',
    'int main(void) { return 1?0?7:42:8; }',
    'int main(void) { return 0||1?42:7; }',
    'int main(void) { int n=0; n=1?42:7; return n; }',
    'int main(void) { int n=0; int x=0?7:42,y=0; y=n?1:x; return y; }',
    'int main(void) { return (1?7:8,42); }',
    'int main(void) { return (1?42:7)+0; }',
    'int main(void) { if((1L<<40)?0:1) return 1; return 42; }',
    'int main(void) { int x=42; return (&x)?x:7; }',
    'int main(void) { if((0?1ULL<<63:1ULL<<62)!=(1ULL<<62)) return 1; return 42; }',
    'int main(void) { int n=0; int x=1?(n=1,42):(n=2,7); if(n!=1) return 1; return x; }',
    'int main(void) { int n=0; int x=0?(n=1,7):(n=2,42); if(n!=2) return 1; return x; }',
    'int main(void) { int n=0; 1?(n=42):(n=7); return n; }',
    'int main(void) { int n=0; int z=0; return 1?42:1/z; }',
    'int main(void) { int a[1]; a[0]=42; return *(1?a:a+10); }',
    'int main(void) { int x=42; const int *p=&x; return *(0?&x:p); }',
    'int main(void) { int x=42; const void *p=&x; const int *q=1?&x:p; return *q; }',
    'int main(void) { int x=42; void *p=&x; const int *q=&x; const void *v=0?q:p; return *(const int *)v; }',
    'int main(void) { int a[3]; a[2]=42; int (*p)[]=&a; return (*(1?p:&a))[2]; }',
    qualified_incomplete_array_case,
    qualified_row_array_case,
    'int id(int x) { return x; } int bad(int x) { return x+1; } int main(void) { return (1?id:bad)(42); }',
    'int id(int x) { return x; } int bad(int x) { return x+1; } int main(void) { int (*p)(int)=id; return (0?bad:p)(42); }',
    'void set(int *p,int x) { *p=x; } int main(void) { int n=0; 1?set(&n,42):set(&n,7); return n; }',
    'void set(int *p,int x) { *p=x; } int main(void) { int n=0; 0?set(&n,7):set(&n,42); return n; }',
    'void set(int *p,int x) { *p=x; } int main(void) { int n=0; (1?set(&n,20):set(&n,1)),(0?(void)(n=1):(void)(n=n+22)); return n; }',
    'int main(void) { int n=0; (1?0:1)?(void)(n=7):(0?(void)(n=8):(void)(n=42)); return n; }',
    'int main(void) { int n=0; return 1?((n=1)&&1?42:7):((n=2)||1?8:9); }',
    'int main(void) { int n=0; return 0?((n=1)&&1?7:8):((n=2)||0?42:9); }',
    'int main(void) { int n=0; int x=(0?1:1)?(0?7:42):(1?8:9); if(n) return 1; return x; }',
    '#define PICK(c,a,b) ((c)?(a):(b))\nint main(void) { return PICK(1,42,7); }',
    'int main(void) { return *(0?"x":"*"); }',
    'int main(void) { _Bool a=1,b=0; if((a?a:b)+1!=2) return 1; return 42; }',
]
# Clang 15 predates C23 matching array/element qualification (6.7.3p10).
# These exact original programs still execute under kcc/QBE; count a narrow
# native diagnostic gap instead of rewriting the source to claim agreement.
array_qualification_gap_cases = {qualified_incomplete_array_case, qualified_row_array_case}
legacy_host_gaps = 0
# Pairwise integer ranks/signs; selected negative values expose signedness and
# wide zero-extension, not merely matching process-exit low bytes.
types = [('_Bool', 8, True, 0), ('char', 8, False, 1), ('signed char', 8, False, 1),
         ('unsigned char', 8, True, 1), ('short', 16, False, 2), ('unsigned short', 16, True, 2),
         ('int', 32, False, 3), ('unsigned', 32, True, 3), ('long', 64, False, 4),
         ('unsigned long', 64, True, 4), ('long long', 64, False, 5), ('unsigned long long', 64, True, 5)]

def promote(t):
    return ('int', 32, False, 3) if t[1] < 32 else t


def common_unsigned(a, b):
    a, b = promote(a), promote(b)
    if a[2] == b[2]:
        return a[2]
    u, s = (a, b) if a[2] else (b, a)
    return u[3] >= s[3] or s[1] <= u[1]

checks = []
for a in types:
    for b in types:
        # Only signed operands can supply -1 as a negative value after casting.
        negative = not a[2] and not common_unsigned(a, b)
        checks.append(f'if(((1?({a[0]})-1:({b[0]})0)<0)!={int(negative)}) return 1;')
        negative = not b[2] and not common_unsigned(a, b)
        checks.append(f'if(((0?({a[0]})0:({b[0]})-1)<0)!={int(negative)}) return 2;')
programs += ['int main(void) {' + ''.join(checks[i:i+24]) + 'return 42; }'
             for i in range(0, len(checks), 24)]
constraints = [
    ('int main(void) { return 1?:42; }', 'expected'),
    ('int main(void) { return 1?42; }', "expected ':'"),
    ('int main(void) { return 1?42:; }', 'expected'),
    ('int main(void) { return 1?42:7:8; }', 'expected'),
    ('int main(void) { int n=0; (1?n:n)=42; return n; }', 'modifiable'),
    ('int main(void) { int n=0; return 1?42:n=7; }', 'modifiable'),
    ('int main(void) { int n=0; int *p=&(1?n:n); return 0; }', 'lvalue'),
    ('int main(void) { return 1?42:missing; }', 'undeclared'),
    ('int main(void) { const int n=7; return 1?42:(n=0); }', 'modifiable'),
    ('void done(void) { return; } int main(void) { return done()?42:7; }', 'scalar condition'),
    ('void done(void) { return; } int main(void) { 1?done():7; return 0; }', 'incompatible conditional'),
    ('int main(void) { int x=0; return 1?&x:1; }', 'incompatible conditional'),
    ('int main(void) { int x=0; const int *p=&x; *(1?&x:p)=7; return 0; }', 'modifiable'),
    ('int main(void) { int x=0; long y=0; 1?&x:&y; return 0; }', 'incompatible conditional'),
    ('int main(void) { int x=0,*p=&x; const int *q=p; 1?&p:&q; return 0; }', 'incompatible conditional'),
    ('int f(int x) { return x; } int main(void) { int x=0; 1?f:&x; return 0; }', 'incompatible conditional'),
    ('int f(int x) { return x; } int main(void) { int x=0; void *p=&x; 1?f:p; return 0; }', 'incompatible conditional'),
]
with tempfile.TemporaryDirectory(prefix='kcc conditionals ') as directory:
    directory = Path(directory)
    source, other, il, assembly, obj, executable, dirty = [directory / name for name in
                                                         ('k.c', 'h.c', 'k.ssa', 'k.s', 'h.o', 'p', 'dirty.s')]

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
        result = subprocess.run([host, '-std=c2x', '-fsigned-char', str(source), '-o', str(executable)],
                                capture_output=True, text=True, timeout=10)
        if result.returncode:
            assert text in array_qualification_gap_cases and 'pointer type mismatch' in result.stderr and \
                'subscripted value is not an array' in result.stderr, (text, result.stderr)
            legacy_host_gaps += 1
            continue
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    values = ['1', '-1', '-1', '255', '-32768', '65535', '-2147483647', '4294967295U',
              '-4611686018427387904L', '9223372036854775808UL', '-4611686018427387904LL',
              '18446744073709551615ULL']
    for (name, _, _, _), value in zip(types, values):
        helper = f'{name} select(long c,{name} a,{name} b) {{ return c?a:b; }}'
        driver = f'{name} select(long,{name},{name}); int main(void) {{ '
        driver += f'if(select(1L<<40,({name})({value}),0)!=({name})({value}) || '
        driver += f'select(0,0,({name})({value}))!=({name})({value})) return 1; return 42; }}'
        for kcc_text, host_text in [(helper, driver), (driver, helper)]:
            compile_source(kcc_text)
            if qbe:
                other.write_text(host_text)
                subprocess.run([host, '-std=c2x', '-fsigned-char', '-c', str(other), '-o', str(obj)],
                               capture_output=True, check=True, timeout=10)
                run([assembly, obj])

    helper = 'const int *choose(void *c,const int *a,int *b) { return c?a:b; }'
    driver = 'const int *choose(void *,const int *,int *); int main(void) { int a=7,b=42; ' \
             'if(choose((void *)0,&a,&b)!=&b || choose(&a,&b,&a)!=&b) return 1; return *choose((void *)0,&a,&b); }'
    # Only the host driver uses its implemented integer null-constant support.
    compile_source(helper)
    if qbe:
        other.write_text(driver)
        subprocess.run([host, '-std=c2x', '-c', str(other), '-o', str(obj)],
                       capture_output=True, check=True, timeout=10)
        run([assembly, obj])

    # Composite bound is reflected in pointer arithmetic of the result, not
    # guessed from one arm. This must remain valid with either selected arm.
    compile_source('int main(void) { int a[3]; int (*p)[]=&a; if((1?p:&a)+1-&a!=1 || (0?p:&a)+1-&a!=1) return 1; return 42; }')
    if qbe:
        run([assembly])
    # A valid narrow low-byte representation with unspecified upper bits stays
    # canonical through nested merges; unselected calls cannot leak their value.
    compile_source('unsigned char one(void); unsigned char zero(void); int main(void) { '
                   'if((1?one():zero())!=1 || (0?one():zero())!=0) return 1; return 42; }')
    if qbe:
        dirty.write_text('.text\n.globl one\none:\n movl $0x12340001, %eax\n ret\n'
                         '.globl zero\nzero:\n movl $0x12340000, %eax\n ret\n'
                         '.section .note.GNU-stack,"",@progbits\n')
        run([assembly, dirty])

    for text, message in constraints:
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)

    # Right-nested integer arms: n conditional nodes plus one literal leaf.
    for count, valid in [(127, True), (128, False)]:
        source.write_text('int main(void) { return ' + '0?1:' * count + '42; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr
    # Typed depth also counts implicit promotion below the final ternary node.
    for count, valid in [(125, True), (126, False)]:
        source.write_text('int main(void) { return 1?' + '+ ' * count + 'true:42; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr

print(f'Conditional expressions passed: {len(programs)} host programs, 288 pairwise sign/rank checks, '
      f'{len(constraints)} constraints, exact syntax/typed depths; {len(programs)-legacy_host_gaps} native runtime agreements, '
      f'{legacy_host_gaps} exact C23 array-qualification host gaps; {host}'
      + ('; QBE/runtime, composite bounds, 24 primitive cross-object ABI arrangements, native-null pointer ABI and dirty returns passed' if qbe else ''))
