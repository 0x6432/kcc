"""Inferred identifiers hide outer typedefs without replaying demand tokens.

Only defined curated positives execute. UB/constraints/boundaries compile only.
Native feature absence is probed independently, never counted as agreement.
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
programs = []
for name in integers:
    value = '1' if name == '_Bool' else '42'
    for identifier in ['T', '((T))']:
        programs.append(f'typedef long T; int main(void) {{ auto {identifier}=({name}){value}; typeof(T) copy=T; {name} *p=&copy; return *p=={value} && sizeof(T)==sizeof({name})?42:1; }}')
programs += [
    'typedef long T; int main(void) { auto const T=42; const int *p=&T; return *p; }',
    'typedef long T; int main(void) { auto register const T=42; typeof_unqual(T) copy=T; int *p=&copy; return *p; }',
    'typedef long T; int main(void) { register const auto T=42; typeof_unqual(T) copy=T; int *p=&copy; return *p; }',
    'typedef const long T; int main(void) { auto T=42; int *p=&T; return *p; }',
    'typedef char T; int main(void) { const auto (T)=(long)42; const long *p=&T; return *p; }',
    'typedef long T; int main(void) { register auto T=42; typeof(T) copy=T; int *p=&copy; return *p; }',
    'typedef long T; int main(void) { auto register (T)=42; auto copy=T; int *p=&copy; return *p; }',
    'typedef char T; int main(void) { const register auto ((T))=(long)42; typeof_unqual(T) copy=T; long *p=&copy; return *p; }',
    'typedef int T; int main(void) { int a=42; auto T=&a; int **p=&T; return **p; }',
    'typedef int T; int main(void) { const int a=42; auto (T)=&a; const int **p=&T; return **p; }',
    'typedef int T; int main(void) { int a[2]; a[1]=42; auto T=a; return T[1]; }',
    'typedef int T; int main(void) { int a[2][3]; a[1][2]=42; auto (T)=a; int (*p)[3]=T; return p[1][2]; }',
    'typedef long T; int main(void) { auto ((T))="*"; char **p=&T; return **p; }',
    'typedef long T; int pick(int x) { return x; } int main(void) { auto T=pick; auto pick=2; return T(40)+pick; }',
    'typedef long T; int pick(void) { return 42; } int main(void) { auto (T)=&pick; return T(); }',
    'typedef int T; int main(void) { auto T=nullptr; typeof(nullptr) *p=&T; return *p==nullptr?42:1; }',
    'typedef long T; int step(int *p) { *p+=1; return *p; } int main(void) { int n=40; auto T=step(&n); return n==41?T+1:1; }',
    'typedef long T; int main(void) { int n=40; auto (T)=(n+=1); return n==41?T+1:1; }',
    'typedef long T; int main(void) { T old=40,*p=&old; auto T=2; return *p+T; }',
    'typedef long T; int main(void) { { auto T=2; if(T!=2) return 1; } T x=42; return x; }',
    'typedef long T; int main(void) { for(auto T=0;T<2;T++) {} T x=42; return x; }',
    'typedef long T; int main(void) { for(auto register (T)=0;T<2;T++) {} T x=42; return x; }',
    'typedef long T; int main(void) { auto T=40; for(auto T=0;T<2;T++) {} return T+2; }',
    'typedef int T(int); int main(void) { auto T=42; int *p=&T; return *p; }',
    'typedef int T[2]; int main(void) { auto (T)=42; int *p=&T; return *p; }',
    'typedef long T; int main(void) { auto T=18446744073709551615ULL; return T==18446744073709551615ULL?42:1; }',
    'typedef long T; int main(void) { const int x=40; auto T=x; T+=2; return T; }',
    'typedef long T; int main(void) { auto T=(40,42); return sizeof(T)==4?T:1; }',
    '#define NAME T\ntypedef long T; int main(void) { auto NAME=42; return T; }',
    '#define STORE auto register\ntypedef long T; int main(void) { STORE T=42; return T; }',
]
unavailable = []
for identifier in ['T', '(T)', '((T))']:
    for specifiers in ['auto', 'auto register']:
        for initializer in ['T', 'sizeof(T)', '(typeof(T))0', '0?T:42', '1?42:T', '&T']:
            unavailable.append(f'typedef long T; int main(void) {{ {specifiers} {identifier}={initializer}; return 0; }}')
constraints = [
    ('typedef int T; int main(void) { auto void T=42; return 0; }', 'local object type must be complete'),
    ('typedef long T; int main(void) { const auto T=42; T=1; return 0; }', 'modifiable'),
    ('typedef long T; int main(void) { auto register T=42; return sizeof(&T); }', 'cannot take the address'),
    ('typedef long T; int main(void) { register auto (T)=42; typeof(&T) p; return 0; }', 'cannot take the address'),
    ('typedef char T; int main(void) { auto T=(long)42; int *p=&T; return 0; }', 'pointer'),
    ('typedef long T; int main(void) { const int a=42; auto T=&a; *T=1; return 0; }', 'modifiable'),
    ('typedef int T; int main(void) { register auto T value=42; return 0; }', 'combined auto storage requires an inferred type'),
]
ub_refusals = [
    ('typedef long T; int main(void) { auto T=1,U=2; return 0; }', 'multiple inferred auto declarators'),
    ('typedef long T; int main(void) { auto (T)=1,T=2; return 0; }', 'multiple inferred auto declarators'),
    ('int main(void) { typedef long T; auto T=42; return 0; }', 'ordinary declaration conflicts'),
    ('int main(void) { typedef long T; auto (T)=42; return 0; }', 'ordinary declaration conflicts'),
    ('typedef long T; int main(void) { auto T=1; auto T=2; return 0; }', 'redeclaration'),
]
subset_errors = [
    ('typedef long T; auto T=42;', 'file-scope auto declarations'),
    ('typedef long T; int main(void) { auto (T); return 0; }', 'requires an assignment initializer'),
    ('typedef long T; int main(void) { auto *T=0; return 0; }', 'single identifier declarator'),
    ('typedef long T; int main(void) { auto (T[2])=0; return 0; }', 'single identifier declarator'),
    ('typedef long T; int main(void) { auto (T)(void)=0; return 0; }', 'single identifier declarator'),
    ('typedef long T; int main(void) { auto (T)={42}; return 0; }', 'expected integer literal'),
    ('typedef long T; int main(void) { auto T=(void)42; return 0; }', 'complete scalar or aggregate initializer type'),
    ('typedef long T; int main(void) { register int a[2]; auto T=a; return 0; }', 'register array-to-pointer conversion'),
    ('typedef long T; int main(void) { auto (T=42; return 0; }', "expected ')' after inferred identifier"),
]
native_probe_text = 'typedef int T; int f(void) { auto T=42; return T; }'
expected_alias_errors = [
    ('error', "expected identifier or '(' before '=' token"),
    ('error', "expected expression before 'T'"),
]


def diagnostic_records(text):
    return re.findall(r'(fatal error|error|warning|note): ([^\n]+)',text.replace('‘', "'").replace('’', "'"))


def native_alias_gap(text, status, diagnostics):
    return text == native_probe_text and status == 1 and diagnostic_records(diagnostics) == expected_alias_errors


synthetic_gap = '\n'.join(f'{kind}: {message}' for kind,message in expected_alias_errors)
assert native_alias_gap(native_probe_text,1,synthetic_gap)
for status in [0,-11,127]:
    assert not native_alias_gap(native_probe_text,status,synthetic_gap)
assert not native_alias_gap(native_probe_text+' ',1,synthetic_gap)
for extra in ['\nnote: unrelated', '\nwarning: unexpected', '\nfatal error: failure', '\n'+synthetic_gap]:
    assert not native_alias_gap(native_probe_text,1,synthetic_gap+extra)
with tempfile.TemporaryDirectory(prefix='kcc inferred typedef ') as directory:
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

    native.write_text('int f(void) { auto x=42; return x; }\n')
    probe = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
    native_inference = probe.returncode == 0
    if not native_inference:
        assert probe.returncode == 1 and diagnostic_records(probe.stderr) in [
            [('error', "type defaults to 'int' in declaration of 'x' [-Wimplicit-int]")],
            [('error', 'a type specifier is required for all declarations')],
        ],probe.stderr
    native_alias_inference = False
    if native_inference:
        native.write_text(native_probe_text+'\n')
        probe = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
        native_alias_inference = probe.returncode == 0
        assert native_alias_inference or native_alias_gap(native_probe_text,probe.returncode,probe.stderr),probe.stderr
    native_programs = native_constraints = 0
    for text in programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        if not native_alias_inference:
            continue
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        assert result.returncode == 0,(text,result.stderr)
        assert subprocess.run([str(executable)],timeout=5).returncode == 42,text
        native_programs += 1
    for text in unavailable:
        compile_source(text,False,'inferred name is unavailable in its initializer')
    for text,message in constraints:
        compile_source(text,False,message)
    for text in unavailable+[text for text,_ in constraints]:
        if not native_alias_inference:
            continue
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
        assert result.returncode == 1,(text,result.stderr)
        native_constraints += 1
    for text,message in ub_refusals+subset_errors:
        compile_source(text,False,message)
    for amount in [256,257]:
        compile_source('typedef long T; int f(void) { '+'{ auto T=(char)0; }'*amount+' return 42; }',amount==256,
                       '' if amount==256 else 'local limit (256)')
    for amount in [4094,4095]:
        compile_source('typedef long T; int f(void) { auto T=42; '+'0;'*amount+' return T; }',amount==4094,
                       '' if amount==4094 else 'item limit (4096)')
    for amount in [1048568,1048569]:
        compile_source(f'typedef char T; int f(void) {{ char a[{amount}]; auto T=(long)42; return T; }}',amount==1048568,
                       '' if amount==1048568 else 'storage limit')
    parameters = ','.join(f'long p{i}' for i in range(128))
    for amount in [128,129]:
        compile_source(f'typedef long T; int f({parameters}) {{ '+'{ auto (T)=(char)0; }'*amount+' return 42; }',amount==128,
                       '' if amount==128 else 'local limit (256)')
    for amount in [1047544,1047545]:
        compile_source(f'typedef char T; int f({parameters}) {{ char a[{amount}]; auto (T)=(long)42; return T; }}',amount==1047544,
                       '' if amount==1047544 else 'storage limit')
    for depth in [64,65]:
        compile_source('typedef long T; int f(void) { auto '+'('*depth+'T'+')'*depth+'=42; return T; }',depth==64,
                       '' if depth==64 else 'nesting limit (64)')
    for depth in [62,63]:
        compile_source('typedef int '+'*'*64+' A; typedef A '+'*'*depth+' B[1]; typedef long T; int f(void) { B a; auto T=42; return T; }',depth==62,
                       '' if depth==62 else 'depth limit (128)')
    one_local = compile_source('typedef long T; int f(void) { auto T=42; return T; }')
    assert one_local.count('alloc') == 1 and 'data ' not in one_local
    literal = compile_source('typedef long T; int f(void) { auto (T)="*"; return *T; }')
    assert literal.count('data $') == 1 and literal.count('alloc') == 1
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        params = 'int a,int b,int c,int d,int e,int f,int g,int h'
        checks = 'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0;'
        helper = f'{name} pick({params}) {{ {checks} return {expected}; }}'
        definition = f'typedef long T; {name} pick({params}) {{ auto T=({name}){expected}; typeof(T) copy=T; {name} *p=&copy; {checks} return *p; }}'
        driver = f'{name} pick({params}); int main(void) {{ return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        inferred_driver = f'typedef long T; {name} pick({params}); int main(void) {{ auto (T)=pick(1,2,3,4,5,6,7,8); typeof(T) copy=T; {name} *p=&copy; return *p=={expected}?42:1; }}'
        for kcc_text,host_text in [(definition,driver),(inferred_driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode == 0,(host_text,result.stderr)
                link_run([assembly,obj])
print(f'Inferred typedef shadowing passed: {len(programs)} C23 originals, {native_programs} strict native agreements, '
      f'{native_constraints} native constraints, {len(unavailable)} unavailable-name barriers, '
      f'{len(ub_refusals)} nonexecuted UB refusals, {len(subset_errors)} subset refusals; '
      f'256 locals incl 128 spills/4096 items/1 MiB storage/64 grouping/128 expanded-typedef boundaries; {host}'
      + ('; native alias inference supported' if native_alias_inference else '; exact typedef-inference grammar gap (not agreements)' if native_inference else '; exact legacy inference absence (not agreements)')
      + ('; QBE/runtime and 24 both-direction mixed-stack ABI arrangements passed' if qbe else ''))
