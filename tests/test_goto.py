"""Direct goto resolution, nested target traversal and defined CFG execution."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
compiler=Path(os.environ.get('KCC',root/'build'/'kcc'))
host=os.environ.get('HOST_CC','cc')
qbe=os.environ.get('QBE')
integers=['_Bool','char','signed char','unsigned char','short','unsigned short',
          'int','unsigned','long','unsigned long','long long','unsigned long long']
programs=[
    'int main(void) { goto done; return 1; done: return 42; }',
    'int main(void) { int x=0; again: x+=7; if(x<42) goto again; return x; }',
    'int main(void) { goto entry; if(0) entry: return 42; return 1; }',
    'int main(void) { int x=0; goto entry; while(0) { entry: x=42; break; } return x; }',
    'int main(void) { int x=0; goto entry; do { entry: x+=7; } while(x<42); return x; }',
    'int main(void) { int x=0; goto entry; for(;x<42;) { entry: x+=7; } return x; }',
    'int main(void) { int x=0; goto inner; { int y=1; { inner: x=42; } } return x; }',
    'int main(void) { if(1) goto entry; else return 1; return 2; entry: return 42; }',
    'int main(void) { goto entry; if(0) return 1; else return 2; entry: return 42; }',
    'int main(void) { int x=0; goto entry; if(0) { entry: x=42; } else x=1; return x; }',
    'int main(void) { goto entry; { if(1) return 1; else return 2; entry: return 42; } }',
    'int main(void) { int x=0; goto a; if(0) { a: x=40; goto b; } else { b: x+=2; } return x; }',
    'int main(void) { int x=0; goto inner; while(0) { for(;;) { inner: x=42; break; } break; } return x; }',
    'int main(void) { int i=0,sum=0; goto body; for(;i<6;i++) { body: sum+=7; continue; } return sum; }',
    'int main(void) { int x=42; { goto end; x=1; end: ; } return x; }',
    'int main(void) { int x=0; goto entry; if(0) { entry: x=(1?(x=40):(x=2)); x+=(x==40 && 1)?2:4; } return x; }',
    'int main(void) { int x=0; goto first; a: return x; first: x=1?40:0; x+=0?1:2; goto a; }',
    'int f(int x) { goto x; return 0; x: return x; } int main(void) { return f(42); }',
    'int a(void) { goto same; same: return 42; } int main(void) { goto same; same: return a(); }',
    '#define JUMP goto\n#define TARGET done\nint main(void) { JUMP TARGET; return 1; TARGET: return 42; }',
    'int main(void) { int x=42; goto a; a: b: c: return x; }',
    'void f(int *p) { goto done; *p=1; done: *p=42; return; } int main(void) { int x=0; f(&x); return x; }',
]
c23_programs=[
    ('int main(void) { int x=42; { goto end; x=1; end: } return x; }','expected statement'),
    ('int main(void) { int x=0; goto decl; return 1; decl: int y=(x=42); return x; }','expected expression'),
]
constraints=[
    'int f(void) { goto missing; return 0; }',
    'int f(void) { return 0; goto missing; }',
    'int f(void) { if(0) goto missing; return 0; }',
    'int f(void) { int target=0; goto target; return 0; }',
    'int target(void); int f(void) { goto target; return 0; }',
    'int a(void) { elsewhere: return 0; } int f(void) { goto elsewhere; return 0; }',
]
syntax_errors=['int f(void) { goto; }','int f(void) { goto 1; }',
               'int f(void) { goto *p; }','int f(void) { goto label }',
               'int f(void) { goto if; }']
with tempfile.TemporaryDirectory(prefix='kcc goto ') as directory:
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
    for text in constraints:
        compile_source(text,False,'goto target is not defined in this function')
        native.write_text(text+'\n')
        result=subprocess.run([host,'-std=c2x','-pedantic-errors','-fsyntax-only',str(native)],capture_output=True,text=True,timeout=10)
        assert result.returncode!=0,text
    for text in syntax_errors:
        compile_source(text,False,'error:')
    # Resource bound is independent of 4096 block items: each if holds two gotos.
    for count,valid in [(4096,True),(4097,False)]:
        pairs='if(0) goto end; else goto end; '*(count//2)
        odd='goto end; ' if count%2 else ''
        compile_source('int f(void) { '+pairs+odd+'end: return 0; }',valid,'goto limit')
    for name in integers:
        expected='1' if name=='_Bool' else '42'
        prototype=f'{name} pick(int,int,int,int,int,int,int,int); '
        helper=(f'{name} pick(int a,int b,int c,int d,int e,int f,int g,int h) {{ '
                f'if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || g!=7 || h!=8) goto fail; '
                f'goto done; fail: return 0; done: return {expected}; }}')
        driver=f'int main(void) {{ if(pick(1,2,3,4,5,6,7,8)!={expected}) goto fail; goto done; fail: return 1; done: return 42; }}'
        for kcc_text,host_text in [(helper,prototype+driver),(prototype+driver,helper)]:
            compile_source(kcc_text)
            if qbe:
                native.write_text(host_text+'\n')
                result=subprocess.run([host,'-std=c2x','-pedantic-errors','-c',str(native),'-o',str(obj)],capture_output=True,text=True,timeout=10)
                assert result.returncode==0,(host_text,result.stderr)
                run([assembly,obj])

print(f'Goto passed: {len(programs)} strict native original programs, {c23_agreements} original C23 placement agreements, '
      f'{grammar_gaps} exact legacy grammar gaps, {len(constraints)} native target-constraint rejections, syntax/4096-reference limits; {host}'
      + ('; QBE/runtime and 24 mixed-stack primitive-result ABI arrangements passed' if qbe else ''))
