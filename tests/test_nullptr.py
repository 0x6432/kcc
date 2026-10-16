"""C23 nullptr: distinct scalar values, constraints, sequencing and pointer ABI."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short', 'unsigned short',
            'int', 'unsigned', 'long', 'unsigned long', 'long long', 'unsigned long long']
programs = []
for name in integers:
    programs.append(f'{name} *zero(void) {{ return nullptr; }} '
                    f'int check({name} *p) {{ return p==nullptr && nullptr==p; }} '
                    f'int main(void) {{ {name} x=0; {name} *p=nullptr; '
                    'if(p || zero() || !check(nullptr)) return 1; p=&x; '
                    'if(p==nullptr || nullptr==p) return 2; p=nullptr; '
                    'if(p!=nullptr || nullptr!=p || (1?p:nullptr) || (0?nullptr:p)) return 3; return 42; }')
# Distinct nullptr equality still accepts all integer-typed zero ICEs.
for name in integers:
    programs.append(f'int main(void) {{ if(nullptr!=({name})0 || ({name})0!=nullptr) return 1; return 42; }}')
programs += [
    'int main(void) { int (*a)[]=nullptr; int (*b)[2]=nullptr; int **c=nullptr; '
    'void **d=nullptr; const int *const e=nullptr; void *v=nullptr; '
    'if(a || b || c || d || e || v) return 1; return 42; }',
    'int id(int x) { return x; } int main(void) { int (*p)(int)=nullptr; '
    'if(p!=nullptr || nullptr!=p) return 1; p=id; '
    'if(p==nullptr || nullptr==p) return 2; '
    'if((1?id:nullptr)(42)!=42 || (0?nullptr:id)(42)!=42) return 3; return 42; }',
    'int main(void) { int x=42; const int *p=&x; '
    'if(sizeof *(1?p:nullptr)!=4 || sizeof *(0?nullptr:p)!=4) return 1; '
    'if(*(1?p:nullptr)!=42 || *(0?nullptr:p)!=42) return 2; return 42; }',
    'int main(void) { if(nullptr!=nullptr || nullptr!=0 || 0!=nullptr) return 1; '
    'if(nullptr!=(void *)0 || (void *)0!=nullptr || nullptr!=(_Bool)0) return 2; '
    'if(!(nullptr==nullptr) || !(nullptr==0) || !(0==nullptr)) return 3; return 42; }',
    'int main(void) { _Bool b=nullptr; if(b || (_Bool)nullptr || !(!nullptr)) return 1; '
    'if(nullptr) return 2; int n=0; if(nullptr && (n=1)) return 3; '
    'if(!(nullptr || (n=2)) || n!=2) return 4; '
    'if(1 || (n=3)) { if(n!=2) return 5; } else return 6; '
    'if(nullptr?1:0) return 7; (void)nullptr; return 42; }',
    'int *once(int *p,int *n) { *n=*n+1; return p; } int main(void) { int x=42,n=0; '
    'if(once(&x,&n)==nullptr || n!=1) return 1; '
    'if(nullptr==once(&x,&n) || n!=2) return 2; '
    'if(*(1?once(&x,&n):nullptr)!=42 || n!=3) return 3; '
    'if(*(0?nullptr:once(&x,&n))!=42 || n!=4) return 4; '
    'int *p=(n=n+1,nullptr); if(p || n!=5) return 5; '
    'p=1?(n=n+1,nullptr):(n=99,nullptr); if(p || n!=6) return 6; '
    'p=0?(n=99,nullptr):(n=n+1,nullptr); if(p || n!=7) return 7; return 42; }',
    '_Static_assert(sizeof(nullptr)==8,"size"); '
    'int main(void) { int a[sizeof nullptr]; '
    'if(sizeof a!=32 || sizeof nullptr!=8 || sizeof(1?nullptr:nullptr)!=8) return 1; '
    'if(sizeof *(int *)nullptr!=4 || sizeof((0,nullptr))!=8) return 2; return 42; }',
    'int main(void) { int nullptr_t=42; return nullptr_t; }',
    'int main(void) { if(nullptr!=false || false!=nullptr) return 1; '
    'if(sizeof *(1?nullptr:(int (*)[2])0)!=8) return 2; return 42; }',
    'int main(void) { int *p=(int *)nullptr; _Bool b=(0,nullptr); '
    'if(p || b || (0,nullptr)!=(1?nullptr:nullptr)) return 1; return 42; }',
    'int main(void) { int n=0; while(nullptr) n=99; '
    'for(;nullptr;) n=98; do n=n+1; while(nullptr); if(n!=1) return 1; return 42; }',
]
# These violate C23 constraints, rather than merely exceeding an implemented
# declaration subset. No constraint source or generated fuzz program is run.
constraints = [
    ('int f(void) { 1?nullptr:0; return 0; }', 'incompatible conditional'),
    ('int f(void) { 1?0:nullptr; return 0; }', 'incompatible conditional'),
    ('int f(int n) { return nullptr==n; }', 'compatible pointers'),
    ('int f(void) { int n=0; return n==nullptr; }', 'compatible pointers'),
    ('int f(void) { nullptr+0; return 0; }', 'pointer'),
    ('int f(void) { 0+nullptr; return 0; }', 'pointer'),
    ('int f(void) { nullptr-nullptr; return 0; }', 'pointer'),
    ('int f(void) { nullptr<<0; return 0; }', 'binary operator'),
    ('int f(void) { return nullptr<0; }', 'compatible pointers'),
    ('int f(void) { return nullptr<nullptr; }', 'compatible pointers'),
    ('int f(void) { +nullptr; return 0; }', 'integer operand'),
    ('int f(void) { -nullptr; return 0; }', 'integer operand'),
    ('int f(void) { ~nullptr; return 0; }', 'integer operand'),
    ('int f(void) { *nullptr; return 0; }', 'pointer'),
    ('int f(void) { nullptr[0]; return 0; }', 'pointer'),
    ('int f(void) { &nullptr; return 0; }', 'address'),
    ('int f(void) { nullptr=0; return 0; }', 'lvalue'),
    ('int f(void) { int n=nullptr; return n; }', 'conversion'),
    ('int f(void) { return (int)nullptr; }', 'conversion'),
    ('int f(void) { return (long)nullptr; }', 'conversion'),
    ('int f(void) { int (*p)(void)=(void *)nullptr; return 0; }', 'pointer conversion'),
    ('int f(void) { int *p=nullptr?0:0; return 0; }', 'pointer conversion'),
    ('int f(void) { int *p=(nullptr,0); return 0; }', 'pointer conversion'),
    ('_Static_assert(!nullptr,"not ICE");', 'integer constant expression'),
    ('_Static_assert((_Bool)nullptr==0,"not ICE");', 'integer constant expression'),
    ('int f(void) { int nullptr=0; return 0; }', 'local name'),
]
pp_programs = [
    '#if nullptr\n#error raw identifier must be zero\n#endif\n'
    'int main(void) { int *p=nullptr; if(p) return 1; return 42; }',
    '#define N nullptr\nint main(void) { int *p=N; if(p) return 1; return 42; }',
    '#define nullptr 42\n#if !defined(nullptr)\n#error macro missing\n#endif\n'
    'int answer(void) { return nullptr; }\n#undef nullptr\n'
    '#if defined(nullptr)\n#error macro survived undef\n#endif\n'
    'int main(void) { int *p=nullptr; if(p) return 1; return answer(); }',
]
with tempfile.TemporaryDirectory(prefix='kcc nullptr ') as directory:
    directory = Path(directory)
    source, native, il, assembly, obj, executable = [directory / n for n in ('k.c','h.c','p.ssa','p.s','h.o','p')]

    def compile_source(text, success=True, message=''):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:1000], result.stderr)
            if qbe:
                il.write_text(result.stdout)
                subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr, (text[:1000], result.stderr)
            assert str(source) + ':' in result.stderr, result.stderr
        return result.stdout

    def run(objects):
        subprocess.run([host, *map(str, objects), '-o', str(executable)], capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42

    # Probe the real keyword; never introduce a macro alias to void * or zero.
    probe = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', '-x', 'c', '-'],
                           input='int *p=nullptr;\n', capture_output=True, text=True, timeout=10)
    native_nullptr = probe.returncode == 0
    if not native_nullptr:
        assert 'nullptr' in probe.stderr and ('undeclared' in probe.stderr or 'undeclared identifier' in probe.stderr), probe.stderr
    native_count = 0
    native_constraint_count = 0
    native_extra_constant_forms = []
    # N3096 6.6p8 excludes nullptr_t operands from integer ICEs. Paragraph
    # 14 permits additional constant forms without making them integer ICEs.
    # Some modern hosts nonetheless fold these exact forms in ICE/null-constant
    # contexts, even under -pedantic-errors. Report this separately: neither
    # accept it in kcc nor call it strict native rejection evidence.
    extra_constant_forms = {
        'int f(void) { int *p=nullptr?0:0; return 0; }',
        '_Static_assert(!nullptr,"not ICE");',
        '_Static_assert((_Bool)nullptr==0,"not ICE");',
    }
    for text in programs:
        compile_source(text)
        if qbe:
            run([assembly])
        if native_nullptr:
            native.write_text(text+'\n')
            result = subprocess.run([host, '-std=c2x', '-pedantic-errors', str(native), '-o', str(executable)],
                                    capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, (text, result.stderr)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42
            native_count += 1
    for text, message in constraints:
        compile_source(text, False, message)
        if native_nullptr:
            native.write_text(text+'\n')
            result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', str(native)],
                                    capture_output=True, text=True, timeout=10)
            if text in extra_constant_forms and result.returncode == 0:
                native_extra_constant_forms.append(text)
            else:
                assert result.returncode != 0, text
                native_constraint_count += 1
    for text in pp_programs:
        compile_source(text)
        if qbe:
            run([assembly])

    # Only the native helper uses traditional zero: this is pointer ABI testing,
    # not a replacement-source oracle for the distinct nullptr expression type.
    for name in integers:
        prototype = f'{name} *relay({name} *,int,int,int,int,int,int,int (*)({name} *),{name} *,{name} *); '
        helper = (f'{name} *relay({name} *p,int a,int b,int c,int d,int e,int f,int (*check)({name} *),{name} *q,{name} *failure) {{ '
                  'if(p || a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || !check(q)) return failure; return 0; } ')
        driver = (f'int check({name} *p) {{ return p==nullptr; }} int main(void) {{ '
                  f'{name} x=0; {name} *p=relay(nullptr,1,2,3,4,5,6,check,(0,nullptr),&x); '
                  'if(p) return 1; return 42; }')
        kcc_helper = helper.replace('return 0;', 'return nullptr;')
        host_driver = (f'int check({name} *p) {{ return p==0; }} int main(void) {{ '
                       f'{name} x=0; {name} *p=relay(0,1,2,3,4,5,6,check,(void *)0,&x); '
                       'if(p) return 1; return 42; }')
        for kcc_text, host_text in [(kcc_helper, prototype+host_driver), (prototype+driver, helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-c', str(native), '-o', str(obj)],
                                        capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, (host_text, result.stderr)
                run([assembly, obj])

    prototype = 'int (*choose(int,int (*)(int)))(int); '
    host_helper = 'int (*choose(int n,int (*p)(int)))(int) { if(n) return p; return 0; }'
    kcc_helper = 'int (*choose(int n,int (*p)(int)))(int) { if(n) return p; return nullptr; }'
    host_driver = ('int id(int x) { return x; } int main(void) { '
                   'if(choose(0,id)!=0 || choose(1,0)!=0) return 1; return choose(1,id)(42); }')
    kcc_driver = ('int id(int x) { return x; } int main(void) { '
                  'if(choose(0,id)!=nullptr || choose(1,nullptr)!=nullptr) return 1; return choose(1,id)(42); }')
    for kcc_text, host_text in [(kcc_helper, prototype+host_driver), (prototype+kcc_driver, host_helper)]:
        compile_source(kcc_text)
        if qbe:
            native.write_text(host_text+'\n')
            result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-c', str(native), '-o', str(obj)],
                                    capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, (host_text, result.stderr)
            run([assembly, obj])

    # A nullptr_t comma result has one leaf plus one level per comma, then
    # assignment-like pointer/bool conversion adds precisely one typed level.
    for target in ['int *', '_Bool']:
        for count, valid in [(126, True), (127, False)]:
            text = target+' f(void) { return '+'('+'0,'*count+'nullptr); }'
            compile_source(text, valid, 'typed expression exceeds depth')
    for count, valid in [(127, True), (128, False)]:
        compile_source('int f(void) { return '+'! '*count+'nullptr; }', valid, 'depth')

print(f'nullptr passed: {len(programs)} original programs, {native_count} strict native agreements, '
      f'{len(constraints)} compile-only constraints, {len(pp_programs)} pp-phase programs, exact typed depths; {host}'
      + (f'; {native_constraint_count} strict native constraint rejections, {len(native_extra_constant_forms)} labelled extra constant forms' if native_nullptr else '')
      + ('; native C23 keyword available' if native_nullptr else '; legacy host lacks C23 nullptr (no alias oracle)')
      + ('; QBE/runtime and 26 stack/callback pointer ABI arrangements passed' if qbe else ''))
