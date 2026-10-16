"""Typed case/default labels, converted ICEs, fallthrough and nested dispatch."""
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
programs = [
    'int main(void) { switch(5) { case 5: return 42; default: return 1; } }',
    'int main(void) { int x=42; switch(9) { case 1: x=1; } return x; }',
    'int main(void) { switch(9) { case 1: return 1; default: return 42; } }',
    'int main(void) { int x=0; switch(3) { case 3: x=40; case 4: x+=2; break; default: x=1; } return x; }',
    'int main(void) { int x=0; switch(99) { default: x=40; case 1: x+=2; } return x; }',
    'int main(void) { int x=0; switch(1) { case 1: case 2: case 3: x=42; } return x; }',
    'int main(void) { int x=0; switch(2) { case 1: x=1; break; case 2: x=42; break; default: x=0; } return x; }',
    'int main(void) { int x=0; switch(1) { if(0) { case 1: x=42; } else x=1; } return x; }',
    'int main(void) { int x=0; switch(2) { if(1) case 1: x=1; else case 2: x=42; } return x; }',
    'int main(void) { int x=0; switch(1) { while(0) { case 1: x=42; break; } } return x; }',
    'int main(void) { int x=0; switch(2) { for(;;) { case 2: x=42; break; } } return x; }',
    'int main(void) { int x=0; switch(1) { case 1: switch(1) { case 1: x=40; break; default: x=0; } x+=2; break; default: x=1; } return x; }',
    'int main(void) { int x=0; switch(2) { default: switch(3) { default: x=42; } } return x; }',
    'int main(void) { int x=0; for(int i=0;i<6;i++) switch(i) { default: x+=7; continue; } return x; }',
    'int main(void) { int x=0; for(int i=0;i<6;i++) { switch(i) { default: x+=7; break; } } return x; }',
    'int main(void) { int x=0; switch(0) { do { case 0: x+=7; case 1: x+=7; } while(x<42); } return x; }',
    'int main(void) { int x=-7; switch(1) { do { case 0: x+=7; case 1: x+=7; } while(x<42); } return x; }',
    'int main(void) { int x=0; switch(1) { case 1: x=1?40:0; x+=(x==40 && 1)?2:0; break; } return x; }',
    'int main(void) { int x=0; switch((x+=1)?(x+=1):0) { case 2: x+=40; break; } return x; }',
    'int main(void) { int x=0; goto entry; switch(x=1) { case 1: return 1; entry: x=42; break; default: x=0; } return x; }',
    'int main(void) { int x=0; switch(1) { case 1: goto end; default: return 1; end: x=42; } return x; }',
    'int main(void) { int x=0; switch(1) { return 1; case 1: x=42; break; } return x; }',
    'int main(void) { int x=0; switch(1) { if(1) return 1; else return 2; case 1: x=42; } return x; }',
    'int main(void) { int x=42; switch(8) case sizeof(long): break; return x; }',
    'int main(void) { switch(8) { case sizeof(int[2]): return 42; default: return 1; } }',
    'int main(void) { switch(1) { case 1?1:2: return 42; default: return 1; } }',
    'int main(void) { switch(1) { case 1 || (1/0): return 42; default: return 1; } }',
    'int main(void) { switch(0) { case 0 && (1/0): return 42; default: return 1; } }',
    'int main(void) { switch(1) { case (int)1.0: return 42; } return 1; }',
    '#define CHOOSE switch\n#define ARM case\n#define VALUE (40+2)\nint main(void) { CHOOSE(42) { ARM VALUE: return 42; default: return 1; } }',
    'void f(int *p) { switch(*p) { case 0: *p=42; return; default: return; } } int main(void) { int x=0; f(&x); return x; }',
    'int f(void) { switch(1) { case 1: return 40; } return 0; } int main(void) { switch(1) { case 1: return f()+2; } return 1; }',
]
# Floating literals are a separate unsupported milestone, not an ICE oracle.
programs.remove('int main(void) { switch(1) { case (int)1.0: return 42; } return 1; }')
for name in integers:
    for value in [0, 1, 42]:
        effective = 1 if name == '_Bool' and value else value
        programs.append(f'int main(void) {{ {name} x={value}; switch(x) {{ case {effective}: return 42; default: return 1; }} }}')
programs += [
    'int main(void) { unsigned x=4294967295U; switch(x) { case -1: return 42; default: return 1; } }',
    'int main(void) { int x=-1; switch(x) { case 4294967295U: return 42; default: return 1; } }',
    'int main(void) { long x=-1; switch(x) { case 18446744073709551615UL: return 42; default: return 1; } }',
    'int main(void) { unsigned long x=18446744073709551615UL; switch(x) { case -1: return 42; default: return 1; } }',
    'int main(void) { long long x=4294967297LL; switch(x) { case 4294967297LL: return 42; default: return 1; } }',
    'int main(void) { unsigned long long x=9223372036854775808ULL; switch(x) { case 9223372036854775808ULL: return 42; default: return 1; } }',
    'int main(void) { _Bool x=1; switch(x) { case 2: return 1; case 1: return 42; default: return 0; } }',
    'int main(void) { unsigned char x=255; switch(x) { case -1: return 1; case 255: return 42; default: return 0; } }',
]
constraints = [
    ('int f(void) { case 1: return 0; }','case requires an enclosing switch'),
    ('int f(void) { default: return 0; }','default requires an enclosing switch'),
    ('int f(void) { while(0) case 1: break; return 0; }','case requires an enclosing switch'),
    ('int f(void) { return 0; case 1: ; }','case requires an enclosing switch'),
    ('int f(void) { switch(1) { case 1: ; case 1: ; } return 0; }','duplicate case'),
    ('int f(void) { switch(1) { case 1: ; case 1+0: ; } return 0; }','duplicate case'),
    ('int f(void) { switch(1U) { case -1: ; case 4294967295U: ; } return 0; }','duplicate case'),
    ('int f(void) { switch(1) { case 0: ; case 4294967296L: ; } return 0; }','duplicate case'),
    ('int f(void) { switch(1UL) { case -1: ; case 18446744073709551615UL: ; } return 0; }','duplicate case'),
    ('int f(void) { switch(1) { default: ; default: ; } return 0; }','duplicate default'),
    ('int f(void) { switch(1) { if(0) default: ; else default: ; } return 0; }','duplicate default'),
    ('int f(void) { switch(1) { if(0) case 1: ; else case 1: ; } return 0; }','duplicate case'),
    ('int f(int x) { switch(1) { case x: ; } return 0; }','constant'),
    ('int f(void) { const int x=1; switch(1) { case x: ; } return 0; }','constant'),
    ('int g(void); int f(void) { switch(1) { case g(): ; } return 0; }','constant'),
    ('int f(void) { int x=0; switch(1) { case (x=1): ; } return 0; }','constant'),
    ('int f(void) { switch(1) { case (1,2): ; } return 0; }','constant'),
    ('int f(void) { switch(1) { case 1/0: ; } return 0; }','zero'),
    ('int f(void) { switch(1) { case 2147483647+1: ; } return 0; }','overflow'),
    ('int f(void) { switch(1) { case 1<<32: ; } return 0; }','shift'),
    ('int f(void) { int *p=0; switch(1) { case p: ; } return 0; }','case requires an integer'),
    ('int f(void) { switch(1) { case 0: continue; } return 0; }','continue requires an enclosing loop'),
]
# Invalid arithmetic is required to fail kcc's checked ICE query. Hosts may fold
# these with only warnings; do not count them as strict native rejections.
arithmetic_constraints = [entry for entry in constraints if entry[1] in ('zero', 'overflow', 'shift')]
constraints = [entry for entry in constraints if entry[1] not in ('zero', 'overflow', 'shift')]
c23_programs = [
    ('int main(void) { switch(1) { case 1: int x=42; return x; default: return 1; } }','expected expression'),
    ('int main(void) { int x=42; switch(1) { x=0; case 1: } return x; }','label at end of compound statement: expected statement'),
    ('int main(void) { int x=42; switch(2) { x=0; default: } return x; }','label at end of compound statement: expected statement'),
]
syntax_errors = ['int f(void) { switch(1) { case : ; } }','int f(void) { switch(1) { case 1 ; } }',
                 'int f(void) { switch(1) { default 1: ; } }','int f(void) { switch(1) case 1: }',
                 'int f(void) { switch(1) default: }','int f(void) { switch(1) { case 1 ... 2: ; } }']
with tempfile.TemporaryDirectory(prefix='kcc switch cases ') as directory:
    directory = Path(directory)
    source,native,il,assembly,obj,executable = [directory/n for n in ('k.c','h.c','p.ssa','p.s','h.o','p')]

    def compile_source(text, success=True, message=''):
        source.write_text(text+'\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=20)
        if success:
            assert result.returncode == 0 and not result.stderr, (text[:1800], result.stderr)
            if qbe:
                il.write_text(result.stdout)
                subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)], check=True, timeout=30)
        else:
            assert result.returncode == 1 and not result.stdout and message in result.stderr, (text[:1800], result.stderr)
        return result.stdout

    def link_run(objects):
        result = subprocess.run([host,*map(str,objects),'-o',str(executable)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert subprocess.run([str(executable)], timeout=5).returncode == 42

    for text in programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (text,result.stderr)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42
    agreements = 0
    grammar_gaps = 0
    for text, diagnostic in c23_programs:
        compile_source(text)
        if qbe:
            link_run([assembly])
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            assert subprocess.run([str(executable)], timeout=5).returncode == 42
            agreements += 1
        else:
            errors = re.findall(r'error: ([^\n]+)', result.stderr)
            # Declaration rejection can have a follow-on unknown-local diagnostic.
            if diagnostic == 'expected expression':
                assert errors == ['expected expression', "use of undeclared identifier 'x'"], result.stderr
            else:
                assert errors == [diagnostic], result.stderr
            grammar_gaps += 1
    for text, message in constraints:
        compile_source(text, False, message)
        native.write_text(text+'\n')
        result = subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0, text
    for text, message in arithmetic_constraints:
        compile_source(text, False, message)
    for text in syntax_errors + ['int f(void) { switch(1) { case nullptr: ; } return 0; }']:
        compile_source(text, False, 'error:')
    # Compile-only resource boundaries: these sources are not runtime tests.
    pairs = ''.join(f'if(0) case {i}: ; else case {i+1}: ;' for i in range(0,1024,2))
    compile_source('int f(void) { switch(0) {'+pairs+'} return 0; }')
    compile_source('int f(void) { switch(0) {'+pairs+'default: ;} return 0; }', False, 'switch exceeds label limit (1024)')
    body = 'switch(0) {'+pairs+'}'
    compile_source('int f(void) {'+body*4+'return 0; }')
    compile_source('int f(void) {'+body*4+'switch(0) { default: ; } return 0; }', False, 'function exceeds switch-label limit (4096)')
    for name in integers:
        expected = '1' if name == '_Bool' else '42'
        prototype = f'{name} pick(int,int,int,int,int,int,int,int); '
        helper = (f'{name} pick(int a,int b,int c,int d,int e,int f,int g,int h) {{ '
                  f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7) return 0; '
                  f'switch(h) {{ case 8: return {expected}; default: return 0; }} }}')
        driver = f'int main(void) {{ switch(pick(1,2,3,4,5,6,7,8)) {{ case {expected}: return 42; default: return 1; }} }}'
        for kcc_text,host_text in [(helper,prototype+driver),(prototype+driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result = subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)], capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, (host_text,result.stderr)
                link_run([assembly,obj])
print(f'Switch cases passed: {len(programs)} strict native original programs, {agreements} original C23 placement agreements, '
      f'{grammar_gaps} exact legacy grammar gaps, {len(constraints)} native constraint rejections, {len(arithmetic_constraints)} compile-only invalid ICE arithmetic cases; syntax/1024-switch/4096-function limits; {host}'
      + ('; QBE/runtime and 24 mixed-stack primitive-result ABI arrangements passed' if qbe else ''))
