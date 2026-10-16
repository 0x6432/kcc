"""C23 keyword types/constants, raw preprocessing, promotions and bool ABI."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
# This is only an explicitly labelled runtime oracle for pre-C23 hosts. The
# original kcc source is never rewritten; semantic units verify its real types.
compatibility_prefix = '#define bool _Bool\n#define true ((_Bool)1)\n#define false ((_Bool)0)\n'
probe = '_Static_assert(_Generic(true,_Bool:1,default:0),"true type");\n' \
        '_Static_assert(_Generic(false,_Bool:1,default:0),"false type");\nbool flag;\n'
result = subprocess.run([host, '-std=c2x', '-x', 'c', '-fsyntax-only', '-'], input=probe,
                        capture_output=True, text=True, timeout=10)
native = result.returncode == 0
prefix = '' if native else compatibility_prefix
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short', 'unsigned short',
            'int', 'unsigned', 'long', 'unsigned long', 'long long', 'unsigned long long']
values = ['1', '-1', '-1', '255', '-32768', '65535', '-2147483647', '4294967295U',
          '-4611686018427387904L', '9223372036854775808UL', '-4611686018427387904LL',
          '18446744073709551615ULL']
programs = [f'int main(void) {{ {name} x=true,y=false; bool a=({name})({value}),b=y; '
            'if(x!=1 || y!=0 || a!=true || b!=false) return 1; return 42; }'
            for name, value in zip(integers, values)]
programs += [
    'int main(void) { if(true+true!=2 || ~false!=-1 || -true!=-1 || (true<<3)!=8) return 1; return 42; }',
    'int main(void) { if(!true || !!false || true==false || !(false<true) || (true^false)!=1) return 1; return 42; }',
    'bool id(_Bool); _Bool id(bool x) { return x; } int main(void) { return id(true)+41; }',
    'bool id(const bool x) { return x; } int main(void) { bool (*const p)(_Bool)=id; return p(true)+41; }',
    'bool id(bool x) { return x; } bool apply(_Bool (*p)(bool),bool x) { return p(x); } int main(void) { return apply(id,true)+41; }',
    'int main(void) { const bool x=true; bool const *p=&x; return *p+41; }',
    'int main(void) { bool a[2]; a[0]=false; a[1]=true; bool *p=a; if(*p || !p[1]) return 1; return 42; }',
    'bool read(const bool a[][2]) { return a[1][1]; } int main(void) { bool a[2][2]; a[1][1]=true; return read(a)+41; }',
    'int main(void) { int x=42; bool a=&x; bool b=(bool)&x; if(!a || !b) return 1; return x; }',
    'bool flag(void) { return true; } int main(void) { bool b=flag; if(!b || !flag()) return 1; return 42; }',
    'int main(void) { int n=0; false && (n=1); true || (n=2); if(n) return 1; return (false,true)+41; }',
    'int main(void) { int n=0; bool b=(n=41,true); if(!b) return 1; return (n=n+1,false,n); }',
    'void done(void) { return; } int main(void) { (false,done()); (void)true; return 42; }',
    'int main(void) { bool x=false; if((x=256)!=true) return 1; x=0; if(x!=false) return 1; return 42; }',
    'int main(void) { bool x=(bool)(1ULL<<63); if(!x || (bool)(unsigned char)256) return 1; return 42; }',
    'int main(void) { for(bool b=true;b;b=false) return 42; return 1; }',
    '#define FLAG bool\n#define YES true\n#define CAT(a,b) a##b\nint main(void) { FLAG x=YES; return (x!=CAT(fal,se))+41; }',
]
# Compatibility macros would alter defined/undef semantics. Only native hosts
# are an oracle here; every original program still runs through kcc and QBE.
preprocessing_programs = [
    '#if defined(true) || defined(false) || defined(bool)\n#error keywords are not macros\n'
    '#elif false || bool\n#error not selected\n#elif true\nint main(void) { return true+41; }\n#endif\n',
    '#define true 0\n#define false 1\n#if true\n#error expanded true\n#elif false\n'
    'int selected(void) { return 41; }\n#endif\n#undef true\n#undef false\n'
    'int main(void) { return selected()+true+false; }',
    '#define bool int\n#define true 42\nint selected(void) { bool x=true; return x; }\n'
    '#undef bool\n#undef true\nint main(void) { bool x=true; if(!x) return 1; return selected(); }',
]
constraints = [
    ('bool bool f(void);', 'duplicate _Bool'),
    ('bool _Bool f(void);', 'duplicate _Bool'),
    ('_Bool bool f(void);', 'duplicate _Bool'),
    *[(f'{name} bool f(void);', 'cannot combine') for name in
      ['int', 'signed', 'unsigned', 'char', 'short', 'long', 'long long', 'void']],
    ('bool main(void) { return true; }', 'main must return int'),
    ('int f(bool); int f(unsigned char);', 'incompatible function'),
    ('int main(void) { const bool x=true; x=false; return 0; }', 'modifiable'),
    ('int main(void) { true=false; return 0; }', 'modifiable'),
    ('int main(void) { bool *p=&true; return 0; }', 'lvalue'),
    ('int main(void) { bool *p=false; return 0; }', 'pointer conversion'),
    ('int main(void) { bool n=true; bool a[n]; return 0; }', 'integer constant expression'),
    ('int main(void) { bool x=; return 0; }', 'expected'),
    ('int main(void) { int true; return 0; }', 'expected'),
    ('int main(void) { int false; return 0; }', 'expected'),
    ('int main(void) { int bool; return 0; }', 'cannot combine'),
]
with tempfile.TemporaryDirectory(prefix='kcc C23 booleans ') as directory:
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

    for text in programs + preprocessing_programs:
        compile_source(text)
        if qbe:
            run([assembly])
        if text in preprocessing_programs and not native:
            continue
        other.write_text(prefix + text + '\n')
        subprocess.run([host, '-std=c2x', '-fsigned-char', str(other), '-o', str(executable)],
                       capture_output=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text

    # Conversion in both directions at each primitive boundary, with distinct
    # full-width source values. Calls/returns use true bool, never int substitutes.
    for name, value in zip(integers, values):
        helper = f'bool nonzero({name} x) {{ return x; }} {name} widen(bool x) {{ return x; }}'
        driver = f'bool nonzero({name}); {name} widen(bool); int main(void) {{ '
        driver += f'if(nonzero(({name})({value}))!=true || nonzero(0)!=false) return 1; '
        driver += 'if(widen(true)!=1 || widen(false)!=0) return 2; return 42; }'
        for kcc_text, host_text in [(helper, driver), (driver, helper)]:
            compile_source(kcc_text)
            if qbe:
                other.write_text(prefix + host_text)
                subprocess.run([host, '-std=c2x', '-fsigned-char', '-c', str(other), '-o', str(obj)],
                               capture_output=True, check=True, timeout=10)
                run([assembly, obj])

    # Eight arguments exercise register and stack slots; callbacks mix spelling
    # and top-level const. Both object ownership arrangements are tested.
    helper = 'bool id(const _Bool x) { return x; } bool apply(bool (*p)(_Bool),bool x) { return p(x); }\n' \
             'int mixed(bool a,int b,bool c,long d,bool e,short f,bool g,bool h) { return a+b+c+d+e+f+g+h; }'
    driver = '_Bool id(bool); _Bool apply(_Bool (*p)(bool),_Bool); int mixed(_Bool,int,_Bool,long,_Bool,short,_Bool,_Bool);\n' \
             'int main(void) { if(apply(id,true)!=true || apply(id,false)!=false) return 1; ' \
             'return mixed(true,20,false,18L,true,0,false,true)+1; }'
    for kcc_text, host_text in [(helper, driver), (driver, helper)]:
        compile_source(kcc_text)
        if qbe:
            other.write_text(prefix + host_text)
            subprocess.run([host, '-std=c2x', '-c', str(other), '-o', str(obj)],
                           capture_output=True, check=True, timeout=10)
            run([assembly, obj])

    compile_source('bool one(void); bool zero(void); int main(void) { const bool a=one(),b=zero(); '
                   'if(a!=true || b!=false || +one()!=1 || +zero()!=0) return 1; return 42; }')
    if qbe:
        dirty.write_text('.text\n.globl one\none:\n movl $0x12340001, %eax\n ret\n'
                         '.globl zero\nzero:\n movl $0x12340000, %eax\n ret\n'
                         '.section .note.GNU-stack,"",@progbits\n')
        run([assembly, dirty])

    for text, message in constraints:
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, (text, result.stderr)

    # Leaf depth 1, one explicit bool->int promotion, and n unary operators.
    for count, valid in [(126, True), (127, False)]:
        source.write_text('int main(void) { return ' + '+ ' * count + 'true; }\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == valid and bool(result.stdout) == valid, result.stderr
        if not valid:
            assert 'depth' in result.stderr, result.stderr

n = len(programs) + len(preprocessing_programs)
print(f'C23 booleans passed: {n} original programs, {len(constraints)} constraints, exact promotion depth; {host}; '
      + ('native C23 oracle' if native else f'labelled compatibility oracle; {len(preprocessing_programs)} native preprocessing gaps')
      + ('; QBE/runtime, 26 cross-object ABI arrangements and dirty returns passed' if qbe else '; runtime requires QBE'))
