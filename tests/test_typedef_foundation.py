"""Unshadowed file-scope typedefs retain syntax and immutable type identity."""
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
    programs.append(f'typedef {name} T; typedef T U; U same(T x) {{ return x; }} int main(void) {{ U x={value}; return same(x)=={value}?42:1; }}')
programs += [
    'typedef int T; int main(void) { T const x=42; return x; }',
    'typedef const int T; int main(void) { T x=42; return x; }',
    'typedef int *P; int main(void) { int x=42; const P p=&x; *p=42; return *p; }',
    'typedef const int *P; int main(void) { const int x=42; P p=&x; return *p; }',
    'typedef int A[2]; int main(void) { A a; a[0]=40; a[1]=2; return a[0]+a[1]; }',
    'typedef int A[2]; typedef A B[2]; int main(void) { B a; a[1][1]=42; return a[1][1]; }',
    'typedef int A[]; int same(A p) { return p[1]; } int main(void) { int a[2]; a[1]=42; return same(a); }',
    'typedef int A[2]; int same(A p) { return p[1]; } int main(void) { A a; a[1]=42; return same(a); }',
    'typedef int F(int); F same; int same(int x) { return x; } int main(void) { return same(42); }',
    'typedef int F(int); int same(int x) { return x; } int apply(F p) { return p(42); } int main(void) { return apply(same); }',
    'typedef int (*P)(int); int same(int x) { return x; } int main(void) { P p=same; return p(42); }',
    'typedef int F(int); typedef F *P; int same(int x) { return x; } int main(void) { P p=same; return p(42); }',
    'typedef int T; T main(void) { T x=(T)42L; return x; }',
    'typedef void V; int f(V) { return 42; } int main(void) { return f(); }',
    'typedef void V; V set(int *p) { *p=42; } int main(void) { int x=0; set(&x); return x; }',
    'typedef int T; int main(void) { T sum=0; for(T i=0;i<7;i++) sum+=i; return sum*2; }',
    'typedef int T; int main(void) { T a=40,b=2; return a+b; }',
    'typedef int T; int main(void) { goto T; T:; T x=42; return x; }',
    'typedef int T; int main(void) { if(1) goto T; return 1; T: return (T)42; }',
    'typedef int T; int main(void) { T const x=40; const T y=2; return x+y; }',
    'typedef int T; int main(void) { return sizeof(T)==4 && _Alignof(T)==4?42:1; }',
    'typedef int A[2]; int main(void) { A a; return sizeof(A)==sizeof(a)?42:1; }',
    '#define DECL typedef\nDECL int T; int main(void) { T x=42; return x; }',
    '#define typedef int\nint main(void) { typedef x=42; return x; }',
    'int f(void) { int T=42; return T; } typedef int T; int main(void) { T x=f(); return x; }',
    'typedef int T; typedef T U; typedef U V; int main(void) { V x=42; return x; }',
    'typedef int T; int main(void) { T (*p)[2]; T a[2]; p=&a; (*p)[1]=42; return a[1]; }',
    'typedef int F(int); F f; int f(int x) { if(x==0) return 42; return f(x-1); } int main(void) { return f(3); }',
    'typedef int T; int main(void) { int a[sizeof(T)]; a[3]=42; return a[3]; }',
    'typedef int T; int main(void) { int T_label=42; return T_label; }',
]
c23_programs = [
    'typedef typeof(nullptr) N; N same(N n) { return n; } int main(void) { N n=0; return same(n)==nullptr?42:1; }',
    'typedef int T; typedef typeof(T) U; int main(void) { U x=42; return x; }',
    'typedef const int T; int main(void) { typeof_unqual(T) x=40; x+=2; return x; }',
    'typedef int T; int main(void) { T x=42; typeof(x) y=x; return y; }',
    'typedef typeof(int(int)) F; F f; int f(int x) { return x; } int main(void) { return f(42); }',
    'typedef typeof(void) V; int f(V) { return 42; } int main(void) { return f(); }',
    'typedef int T; int main(void) { return alignof(T)==4?42:1; }',
    'typedef bool B; int main(void) { B b=true; return b?42:1; }',
    'typedef int T; static_assert(sizeof(T)==4); int main(void) { return 42; }',
    'typedef int T; int f(T x,typeof(x) y) { return x+y; } int main(void) { return f(40,2); }',
]
constraints = [
    ('int T(void); typedef int T;','typedef name conflicts'),
    ('typedef int T; int T(void);','function name conflicts'),
    ('typedef int T; long T(void) { return 42; }','function name conflicts'),
    ('typedef const int T; int main(void) { T x=0; x=42; return x; }','modifiable'),
    ('typedef int *P; int main(void) { int x=0,y=42; const P p=&x; p=&y; return *p; }','modifiable'),
    ('typedef const int *P; int main(void) { int x=42; P p=&x; *p=42; return x; }','modifiable'),
    ('typedef int T; typedef T unsigned U;','typedef name cannot combine'),
    ('typedef int F(void); F f; long f(void);','incompatible function declaration'),
    ('typedef int A[]; int main(void) { A a; return 42; }','complete'),
    ('typedef void A[2];','array element type must be complete'),
    ('typedef int F(void); typedef F A[2];','array element type must be complete'),
    ('typedef int T; int main(void) { return T; }','undeclared'),
    ('typedef int T; int main(void) { return missing; }','undeclared'),
]
subset_errors = [
    ('typedef int T,U;','single name'),
    ('typedef int T=42;','single name'),
    ('int main(void) { typedef int T; return 42; }','block-scope typedef'),
    ('int main(void) { for(typedef int T;;) return 42; }','block-scope typedef'),
    ('typedef int T; int main(void) { int T=42; return T; }','shadowing a typedef'),
    ('typedef int T; int main(void) { T T=42; return T; }','shadowing a typedef'),
    ('typedef int T; int f(int T) { return T; }','shadowing a typedef'),
    ('typedef int T; T x;','file-scope object declarations'),
    ('typedef int F(void); F f { return 42; }',"query-derived external declarations require ';'"),
    ('typedef int F(void); int main(void) { F f; return 42; }','block-scope function declarations'),
    ('typedef int F(void); const F f;','function type cannot be qualified'),
]
with tempfile.TemporaryDirectory(prefix='kcc typedef foundation ') as directory:
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

    native_programs = 0
    native_constraints = 0
    keyword_macro_warning = False
    native.write_text('typeof(int) value;\n')
    probe = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)], capture_output=True, text=True, timeout=10)
    native_c23 = probe.returncode == 0
    if not native_c23:
        errors = re.findall(r'error: ([^\n]+)',probe.stderr.replace('‘', "'").replace('’', "'"))
        assert errors in [["return type defaults to 'int' [-Wimplicit-int]", "expected declaration specifiers before 'value'", "expected '{' at end of input"], ['expected function body after function declarator']],probe.stderr
    for text in programs+c23_programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if text in programs or native_c23:
            native.write_text(text+'\n')
            result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)], capture_output=True, text=True, timeout=10)
            if result.returncode and text == '#define typedef int\nint main(void) { typedef x=42; return x; }':
                errors = re.findall(r'error: ([^\n]+)',result.stderr)
                assert errors == ['keyword is hidden by macro definition [-Werror,-Wkeyword-macro]'], result.stderr
                keyword_macro_warning = True
                # Clang's keyword-macro style warning is not a C constraint.
                # Keep the original program and pedantic errors, disabling only it.
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-Wno-keyword-macro',str(native),'-o',str(executable)], capture_output=True, text=True, timeout=10)
            assert result.returncode == 0,(text,result.stderr)
            assert subprocess.run([str(executable)],timeout=5).returncode == 42,text
            native_programs += 1
    for text,message in constraints:
        compile_source(text,False,message)
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
        assert result.returncode != 0,text
        native_constraints += 1
    for text,message in subset_errors:
        compile_source(text,False,message)
    assert 'function' not in compile_source('typedef int T; typedef T A[2]; typedef int F(T);')
    for amount in [512,513]:
        compile_source(''.join(f'typedef int T{i};' for i in range(amount)),amount==512,
                       '' if amount==512 else 'translation unit exceeds declaration limit (512)')
    for amount in [256,257]:
        compile_source('typedef int F(void);'+''.join(f'F f{i};' for i in range(amount)),amount==256,
                       '' if amount==256 else 'translation unit exceeds function limit (256)')
    # A long valid alias chain reuses types; it is bounded by external items.
    compile_source('typedef int T0;'+''.join(f'typedef T{i-1} T{i};' for i in range(1,511))+'int main(void) { T510 x=42; return x; }')
    if qbe:
        link_run([assembly])
    # Alias-shaped labels still consume one item, independent of type lookup.
    for items in [4096,4097]:
        compile_source('typedef int T; int main(void) { T:'+ ';'*(items-2)+'return 42; }',items==4096,
                       '' if items==4096 else 'function body exceeds item limit (4096)')
    for stars in [63,64]:
        compile_source('typedef int '+ '*'*64+' A; typedef A '+ '*'*stars+' B;',stars==63,
                       '' if stars==63 else 'typedef type exceeds expanded depth limit (128)')
    # 32*127 + 30 + function/return nodes = 4096; one extra pointer is 4097.
    for stars in [29,30]:
        prefix = 'typedef int '+ '*'*64+' Base; typedef Base '+ '*'*62+' A; typedef int '+ '*'*stars+' B;'
        compile_source(prefix+'typedef int F('+ ','.join(['A']*32+['B'])+');',stars==29,
                       '' if stars==29 else 'typedef type exceeds expanded node limit (4096)')
    branching = 'typedef int T0;'+''.join(f'typedef T{i-1} *T{i}(T{i-1} *,T{i-1} *);' for i in range(1,8))
    compile_source(branching,False,'typedef type exceeds expanded node limit (4096)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = 'int a,int b,int c,int d,int e,int f,int g,int h'
        aliases = f'typedef {name} result; typedef result signature({params}); signature pick; '
        helper = (f'{name} pick({params}) {{ '
                  f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        definition = (f'result pick({params}) {{ '
                      f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; return {expected}; }}')
        driver = f'int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        for kcc_text,host_text in [(aliases+definition,f'{name} pick({params}); '+driver),(aliases+driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Typedef foundation passed: {len(programs)} standard + {len(c23_programs)} C23 originals, {native_programs} strict native agreements, {native_constraints} native constraints; explicit subset, 512 declarations/256 functions, alias chain, expanded DAG/depth/item boundaries and declaration-only IL; {host}'
      + ('; original C23 support' if native_c23 else '; exact legacy keyword absence (no query aliases)')
      + ('; exact original keyword-macro style warning disabled' if keyword_macro_warning else '')
      + ('; QBE/runtime and 24 mixed-stack primitive ABI arrangements passed' if qbe else ''))
