"""Case-free switches, integer control, goto entry and nested jump contexts."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root/'build'/'kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
integers = ['_Bool', 'char', 'signed char', 'unsigned char', 'short', 'unsigned short',
            'int', 'unsigned', 'long', 'unsigned long', 'long long', 'unsigned long long']
programs = [
    'int main(void) { switch(42) {} return 42; }',
    'int main(void) { switch(0) ; return 42; }',
    'int main(void) { switch(1) return 1; return 42; }',
    'int main(void) { switch(1) break; return 42; }',
    'int main(void) { int x=40; switch(x+=2) { x=1; } return x; }',
    'int main(void) { int x=0; switch(x++?1:(x=42)) { x=1; } return x; }',
    'int main(void) { int x=40; switch((x+=1,x+=1)) {} return x; }',
    'int main(void) { int x=40; switch((x+=1) && (x+=1)) {} return x; }',
    'int main(void) { int x=0; goto inside; switch(x=1) { inside: x=42; } return x; }',
    'int main(void) { int x=40; goto inside; switch(x=1) inside: { x+=2; break; x=0; } return x; }',
    'int main(void) { int x=0; goto inside; switch(0) { if(0) inside: { x=42; break; } x=1; } return x; }',
    'int main(void) { int x=0; goto inner; switch(1) { switch(2) { inner: x=40; break; } x+=2; break; } return x; }',
    'int main(void) { int x=0; for(int i=0;i<6;i++) { goto inside; switch(1) { inside: x+=7; break; } } return x; }',
    'int main(void) { int x=0; for(int i=0;i<6;i++) { goto inside; switch(1) { inside: x+=7; continue; } x=0; } return x; }',
    'int main(void) { int x=0; while(x<42) { goto inside; switch(1) { inside: x+=7; continue; } x=0; } return x; }',
    'int main(void) { int x=0; do { goto inside; switch(1) { inside: x+=7; continue; } x=0; } while(x<42); return x; }',
    'int main(void) { int x=0; goto entry; switch(1) { entry: while(1) { x=40; break; } x+=2; break; } return x; }',
    'int main(void) { int x=0; for(int i=0;i<6;i++) { goto entry; switch(1) { switch(2) { entry: x+=7; continue; } } x=0; } return x; }',
    'int main(void) { int x=0; goto entry; switch(1) { entry: for(int i=0;i<6;i++) { x+=7; continue; } break; } return x; }',
    'int main(void) { int x=42; switch(1) { int x=0; } return x; }',
    'int f(int *p) { *p+=2; return 1; } int main(void) { int x=40; switch(f(&x)) {} return x; }',
    '#define SELECT switch\nint main(void) { int x=40; SELECT(x+=2) { x=0; } return x; }',
    'int main(void) { int x=0; if(1) switch(1) if(0) x=1; else x=2; return x+42; }',
    'void f(int *p) { goto entry; switch(1) { entry: *p=42; return; } } int main(void) { int x=0; f(&x); return x; }',
]
for name in integers:
    programs.append(f'int main(void) {{ {name} x=1; int y=40; switch(x) {{ y=0; }} switch((y+=2,x)) {{ y=1; }} return y; }}')
constraints = [
    ('int f(void) { int *p=0; switch(p) {} return 0; }', 'switch control requires an integer'),
    ('int f(void) { int a[1]; switch(a) {} return 0; }', 'switch control requires an integer'),
    ('int g(void); int f(void) { switch(g) {} return 0; }', 'switch control requires an integer'),
    ('void g(void); int f(void) { switch(g()) {} return 0; }', 'switch control requires an integer'),
    ('int f(void) { switch(1) { continue; } return 0; }', 'continue requires an enclosing loop'),
    ('int f(void) { switch(1) { switch(2) continue; } return 0; }', 'continue requires an enclosing loop'),
    ('int f(void) { switch(1) { missing=1; } return 0; }', 'undeclared'),
    ('int f(void) { switch(1) { goto missing; } return 0; }', 'goto target is not defined'),
    ('int f(void) { switch(1) { const int x=0; x=1; } return 0; }', 'modifiable'),
    ('int f(void) { switch(1) { int x=0; } return x; }', 'undeclared'),
    ('int f(void) { switch(1) {} break; return 0; }', 'break requires an enclosing'),
    ('int f(void) { switch(1) { static_assert(0); } return 0; }', 'static assertion failed'),
]
syntax_errors = ['int f(void) { switch 1; }', 'int f(void) { switch() {} }',
                 'int f(void) { switch(1 {} }', 'int f(void) { switch(1) }',
                 'int f(void) { switch(1) int x; }']
unsupported = ['int f(void) { switch(1) { case 1: return 0; } return 0; }',
               'int f(void) { switch(1) { default: return 0; } }',
               'int f(void) { switch(nullptr) {} return 0; }']
with tempfile.TemporaryDirectory(prefix='kcc switch ') as directory:
    directory = Path(directory)
    source, native, il, assembly, obj, executable = [directory/n for n in ('k.c','h.c','p.ssa','p.s','h.o','p')]

    def compile_source(text, success=True, message=''):
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:1500], result.stderr)
            if qbe:
                il.write_text(result.stdout)
                subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr, (text[:1500], result.stderr)
        return result.stdout

    def link_run(objects):
        result = subprocess.run([host, *map(str, objects), '-o', str(executable)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert subprocess.run([str(executable)], timeout=5).returncode == 42

    for text in programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        native.write_text(text+'\n')
        result = subprocess.run([host, '-std=c2x', '-pedantic-errors', str(native), '-o', str(executable)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (text, result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42
    for text, message in constraints:
        compile_source(text, False, message)
        native.write_text(text+'\n')
        result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-fsyntax-only', str(native)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0, text
    for text in syntax_errors + unsupported:
        compile_source(text, False, 'error:')
    # Existing 128-level statement guard includes the function's outer compound.
    compile_source('int f(void) { '+'switch(1) '*127+'; return 0; }')
    compile_source('int f(void) { '+'switch(1) '*128+'; return 0; }', False, 'nesting')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        prototype = f'{name} pick(int,int,int,int,int,int,int,int); '
        helper = (f'{name} pick(int a,int b,int c,int d,int e,int f,int g,int h) {{ '
                  f'goto entry; switch(a=0) {{ entry: if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) return 0; break; }} return {expected}; }}')
        driver = f'int main(void) {{ switch(0) {{ return 0; }} return pick(1,2,3,4,5,6,7,8)=={expected}?42:1; }}'
        for kcc_text, host_text in [(helper, prototype+driver), (prototype+driver, helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-c', str(native), '-o', str(obj)], capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, (host_text, result.stderr)
                link_run([assembly, obj])
print(f'Switch foundation passed: {len(programs)} strict native original programs, {len(constraints)} native constraint rejections; syntax/nesting and case/default subset rejection; {host}'
      + ('; QBE/runtime and 24 mixed-stack primitive-result ABI arrangements passed' if qbe else ''))
