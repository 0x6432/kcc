"""Function-scoped identifier labels, including C23 standalone block labels."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root/'build'/'kcc'))
host = os.environ.get('HOST_CC','cc')
qbe = os.environ.get('QBE')
integers = ['_Bool','char','signed char','unsigned char','short','unsigned short',
            'int','unsigned','long','unsigned long','long long','unsigned long long']
programs = [
    'int main(void) { start: return 42; }',
    'int main(void) { a: b: c: return 42; }',
    'int main(void) { int x=40; one: x+=1; two: x+=1; return x; }',
    'int main(void) { int x=0; if(1) yes: x=42; else no: x=1; return x; }',
    'int main(void) { int x=0; outer: if(1) inner: x=42; else other: x=1; return x; }',
    'int main(void) { int x=0; for(int i=0;i<6;i++) body: x+=7; return x; }',
    'int main(void) { int x=0; while(1) stop: { x=42; quit: break; } return x; }',
    'int main(void) { int x=0; do again: { x+=7; if(x<42) skip: continue; } while(x<42); return x; }',
    'int f(int x) { x: return x; } int main(void) { int f=42; f: return f; }',
    'int a(void) { same: return 42; } int b(void) { same: return a(); } int main(void) { same: return b(); }',
    'int main(void) { int x=40; { inside: x+=2; } outside: return x; }',
    'int main(void) { if(1) { a: return 42; } else b: return 1; return 2; }',
    '#define LABEL tag\n#define COLON :\nint main(void) { LABEL COLON return 42; }',
    'int f(int x) { return x; } int main(void) { int x=40; int a[1]; a[0]=x; '
    'f(x); x+=a[0]-39; if(1) x+=1; x?x:0; return x; }',
    'int main(void) { int x=42; if(0) dead: x=0; return x; after: return 0; }',
]
# These original programs are also the narrow host feature probes. Do not
# rewrite them to older C and then count that as source-language agreement.
c23_programs = [
    ('int main(void) { before: int x; return 42; }','expected expression'),
    ('int main(void) { return 42; end: }','expected statement'),
]
constraints = [
    ('int f(void) { a: ; a: return 0; }','duplicate label'),
    ('int f(void) { { a: ; } { a: ; } return 0; }','duplicate label'),
    ('int f(void) { if(1) a: return 0; else a: return 1; }','duplicate label'),
    ('int f(void) { return 0; a: ; a: return 1; }','duplicate label'),
    ('int f(void) { if(0) a: ; a: return 0; }','duplicate label'),
]
syntax_errors = [
    'int f(void) { if(1) label: }',
    'int f(void) { if(1) label: int x=0; return 0; }',
    'int f(void) { while(0) label: }',
    'int f(void) { : return 0; }',
    'int f(void) { label return 0; }',
]
with tempfile.TemporaryDirectory(prefix='kcc labels ') as directory:
    directory=Path(directory)
    source,native,il,assembly,obj,executable=[directory/n for n in ('k.c','h.c','p.ssa','p.s','h.o','p')]

    def compile_source(text,success=True,message=''):
        source.write_text(text+'\n')
        result=subprocess.run([str(compiler),str(source)],capture_output=True,text=True,timeout=10)
        if success:
            assert result.returncode==0 and not result.stderr,(text[:1500],result.stderr)
            if qbe:
                il.write_text(result.stdout)
                subprocess.run([qbe,'-t','amd64_sysv','-o',str(assembly),str(il)],check=True,timeout=10)
        else:
            assert result.returncode==1 and not result.stdout and message in result.stderr,(text[:1500],result.stderr)
        return result.stdout

    def run(objects):
        result=subprocess.run([host,*map(str,objects),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        assert result.returncode==0,result.stderr
        assert subprocess.run([str(executable)],timeout=5).returncode==42

    for text in programs:
        compile_source(text)
        if qbe:
            run([assembly])
        native.write_text(text+'\n')
        result=subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        assert result.returncode==0,(text,result.stderr)
        assert subprocess.run([str(executable)],timeout=5).returncode==42
    c23_agreements=0
    grammar_gaps=0
    for text,diagnostic in c23_programs:
        compile_source(text)
        if qbe:
            run([assembly])
        native.write_text(text+'\n')
        result=subprocess.run([host,'-std=c2x','-pedantic-errors',str(native),'-o',str(executable)],capture_output=True,text=True,timeout=10)
        if result.returncode==0:
            assert subprocess.run([str(executable)],timeout=5).returncode==42
            c23_agreements+=1
        else:
            errors=re.findall(r'error: ([^\n]+)',result.stderr)
            assert errors==[diagnostic],(text,result.stderr)
            grammar_gaps+=1
    for text,message in constraints:
        compile_source(text,False,message)
        native.write_text(text+'\n')
        result=subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
        assert result.returncode!=0,text
    for text in syntax_errors:
        compile_source(text,False,'error:')
    for count,valid in [(512,True),(513,False)]:
        compile_source('int f(void) { '+''.join(f'label_{i}: ; ' for i in range(count))+'return 0; }',valid,'label limit')
    # Function compound + if + each secondary label consumes one nesting frame.
    for count,valid in [(126,True),(127,False)]:
        compile_source('int f(void) { if(1) '+''.join(f'l{i}: ' for i in range(count))+'return 0; return 1; }',valid,'nesting')
    for name in integers:
        value='1' if name=='_Bool' else '42'
        prototype=f'{name} pick(int,int,int,int,int,int,int,int); '
        helper=f'{name} pick(int a,int b,int c,int d,int e,int f,int g,int h) {{ start: if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) fail: return 0; end: return {value}; }}'
        driver=f'int main(void) {{ call: if(pick(1,2,3,4,5,6,7,8)!={value}) fail: return 1; done: return 42; }}'
        for kcc_text,host_text in [(helper,prototype+driver),(prototype+driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result=subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode==0,(host_text,result.stderr)
                run([assembly,obj])
    # No object/static allocation is attributable to a label alone.
    output=compile_source('int f(void) { first: second: return 42; }')
    assert 'alloc' not in output and 'data ' not in output

print(f'Named labels passed: {len(programs)} strict native original programs, {c23_agreements} original C23 placement agreements, '
      f'{grammar_gaps} exact legacy grammar gaps, {len(constraints)} native duplicate-label rejections, syntax/nesting/512-label limits; {host}'
      + ('; QBE/runtime and 24 mixed-stack primitive-result ABI arrangements passed' if qbe else ''))
