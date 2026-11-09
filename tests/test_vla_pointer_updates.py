"""Tracked VM pointer updates/differences; compare only defined C11 programs."""
import os
import subprocess
import tempfile
from pathlib import Path
from runtime_link import runtime_link_flags

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root/'build/kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
programs = [
    # Prefix and postfix results, both directions, after changing the bound.
    'int main(void) { int n=3,a[4][3]={{1},{2},{3},{42}}; int (*p)[n++]=a; n=9; if((*p++)[0]!=1 || (*++p)[0]!=3 || (*p--)[0]!=3 || (*--p)[0]!=1) return 1; return n==9 ? 42:1; }',
    'int main(void) { int n=3,a[3][3]={{0},{0,0,42},{0}}; int (*p)[n]=a; return (p++)[0][0]==0 && (++p)[-1][2]==42 ? 42:1; }',
    'int main(void) { int n=3,a[4][3]={{0},{0},{0,0,42},{0}}; int (*p)[n]=a; if((p+=2)[0][2]!=42) return 1; return (p-=1)[1][2]; }',
    'int main(void) { int n=3,a[4][3]={{0},{0,0,42},{0},{0}}; int (*p)[n]=a+2; int i=-1; p+=i; p-=i; return (p-i)[-2][2]; }',
    # Different fixed-inner shape and a one-byte stride.
    'int main(void) { int n=2,a[3][2][3]={{{0}},{{0}},{{0,0,42}}}; int (*p)[n][3]=a; p+=2; return (*p)[0][2]; }',
    'int main(void) { int n=1; char a[3][1]={{0},{42},{0}}; char (*p)[n]=a; return (*++p)[0]; }',
    # Distinct captured bounds have the same value; never rely on UB for unequal VLA types.
    'int main(void) { int n=3,m=3,a[4][3]={{0}}; int (*p)[n++]=a+3; int (*q)[m++]=a; n=9; m=8; return p-q==3 && q-p==-3 && (p-1)-(q+1)==1 ? 42:1; }',
    'int main(void) { int n=3,a[4][3]={{0}}; int (*p)[n]=a+3; int (*q)[3]=a; return p-q==3 && q-p==-3 ? 42:1; }',
    'int main(void) { int n=3,a[4][3]={{0}}; int (*p)[n]=a; int (*q)[n]=a+3; return (p++)-q==-3 && p-q==-2 && (q-=1)-p==1 ? 42:1; }',
    'static int calls; static int step(void) { calls++; return 2; } int main(void) { int n=3,a[4][3]={{0},{0},{0,0,42},{0}}; int (*p)[n++]=a; p+=step(); return calls==1 && n==4 && (*p)[2]==42 ? 42:1; }',
    # Qualifiers, actual atomic/volatile runtime helpers, and compound result values.
    'int main(void) { int n=3,a[3][3]={{0},{0,0,42},{0}}; int (*volatile p)[n]=a; if((*p++)[0]!=0) return 1; return (*p)[2]; }',
    'int main(void) { int n=3,a[4][3]={{0},{0},{0,0,42},{0}}; int (*volatile p)[n]=a; p+=2; return (*p)[2]; }',
    'int main(void) { int n=3,a[3][3]={{0},{0,0,42},{0}}; int (*_Atomic p)[n]=a; if((*p++)[0]!=0) return 1; return (*p)[2]; }',
    'int main(void) { int n=3,a[4][3]={{0},{0},{0,0,42},{0}}; int (*_Atomic p)[n]=a; p+=2; return (*p)[2]; }',
    'int main(void) { int n=3,a[3][3]={{0},{0,0,42},{0}}; int (*_Atomic p)[n]=a+2; p--; return (*p)[2]; }',
    'int main(void) { int n=3,a[4][3]={{0},{0,0,42},{0},{0}}; int (*_Atomic p)[n]=a+3; p-=2; return (*p)[2]; }',
    'int main(void) { int n=3,a[4][3]={{0},{0},{0,0,42},{0}}; int (*_Atomic p)[n]=a; return (p+=2)[0][2]; }',
    'int main(void) { int n=3,a[3][3]={{0},{0,0,42},{0}}; int (*_Atomic p)[n]=a+2; int i=-1; p+=i; return (*p)[2]; }',
    'int main(void) { int n=3; const int a[2][3]={{0},{0,0,42}}; const int (*p)[n]=a; p++; return (*p)[2]; }',
    'int main(void) { int n=3,a[3][3]={{0},{0,0,42},{0}}; register int (*p)[n]=a; return (*++p)[2]; }',
    # Re-evaluation and saved size for each entry; short-circuit leaves updates unexecuted.
    'int main(void) { int a[3][3]={{0},{0,0,42},{0}},r=0; for(int n=1;n<=3;n++) { int (*p)[n]=(void *)a; if(n==3) { p++; r=(*p)[2]; } } return r; }',
    'int main(void) { int n=3,a[2][3]={{42},{0}}; int (*p)[n]=a; if(0 && (*p++)[0]) return 1; return (*p)[0]; }',
    'int main(void) { int n=3,a[4][3]={{0},{0},{0},{0}}; int (*p)[n]=a; int (*q)[n]=a+2; long d=(++p)-(q--); return d==-1 && p==q ? 42:1; }',
    'int main(void) { char a[2][524272]; int n=524272; char (*p)[n]=a; p++; return p-a==1 ? 42:1; }',
    'int main(void) { int a[3][3]={{0},{0,0,42},{0}},n=3,i=0; again:; int (*p)[n]=(void *)a; p++; if(++i==1) goto again; return (*p)[2]; }',
]
rejected = [
    ('int f(int n) { int (*const p)[n]=0; p++; return 0; }', 'modifiable'),
    ('int f(int n) { int (*p)[n]=0; (*(&p))++; return 0; }', 'complete object'),
    ('int f(int n) { int (*p)[n]=0; (*(&p))+=1; return 0; }', 'complete object'),
    ('int f(int n) { int a[n]; return &a-&a; }', 'complete object referents'),
    ('int f(int n) { int (*p)[n]=0; int (*q)[2]=0; return (n?p:q)-p; }', 'complete object referents'),
    ('int f(int n) { int (*p)[n]=0; p*=2; return 0; }', 'only additive'),
    ('int f(int n) { int (*p)[n]=0; p+=1.0; return 0; }', 'integer right operand'),
    ('int f(int n) { goto x; int (*p)[n]=0; x: p++; return 0; }', 'goto enters'),
    ('int f(int n) { switch(n) { int (*p)[n]=0; case 1: p++; } return 0; }', 'switch label enters'),
    ('int f(int n) { int a[2][n]; return 0; }', 'variable-length arrays'),
]
tmp_base = root/'build'/'tmp'
tmp_base.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='vm-updates-', dir=tmp_base) as d:
    d=Path(d); src, il, asm, exe = [d/x for x in ('input.c','out.ssa','out.s','out')]
    def compile_kcc(text, error=None):
        src.write_text(text+'\n')
        r=subprocess.run([str(kcc),str(src)],capture_output=True,text=True,timeout=10)
        if error:
            assert r.returncode==1 and not r.stdout and error in r.stderr,(text,r.stderr)
        else:
            assert r.returncode==0 and not r.stderr,(text,r.stderr)
        return r.stdout
    def run_kcc(out, extra=()):
        il.write_text(out)
        subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=10)
        subprocess.run([host,str(asm),*map(str,extra),str(root/'build/libkccrt.a'),'-latomic',*runtime_link_flags(),'-o',str(exe)],check=True,timeout=10)
        return subprocess.run([str(exe)],capture_output=True,timeout=5).returncode
    native_gaps=0
    for text in programs:
        out=compile_kcc(text)
        if qbe:
            assert run_kcc(out)==42,text
        src.write_text(text+'\n')
        r=subprocess.run([host,'-std=c11','-pedantic-errors',str(src),'-o',str(exe)],capture_output=True,text=True,timeout=10)
        # Clang 15 rejects atomic pointer += even though GCC and kcc accept it;
        # keep this one exact oracle gap separate, never mask another diagnostic.
        if ('int (*_Atomic p)[n]' in text and ('p+=2' in text or 'p-=2' in text or 'p+=i' in text) and
            r.returncode==1 and r.stderr.count('error:')==1 and
            "error: invalid operands to binary expression ('_Atomic(int (*)[n])' and 'int')" in r.stderr):
            native_gaps += 1
            continue
        assert r.returncode==0,(text,r.stderr)
        assert subprocess.run([str(exe)],timeout=5).returncode==42,text
    for text,error in rejected:
        compile_kcc(text,error)
    # Verify volatile accesses and atomic update mechanics in emitted IL.
    out=compile_kcc('int main(void) { int n=3,a[2][3]={{0}}; int (*volatile p)[n]=a; p++; return 42; }')
    assert out.count('call $__kcc_volatile_load_8')==1 and out.count('call $__kcc_volatile_store_8')==2,out
    out=compile_kcc('int main(void) { int n=3,a[2][3]={{0}}; int (*_Atomic p)[n]=a; p++; return 42; }')
    assert 'call $__atomic_fetch_add_8' in out and ', l %z' in out,out
    out=compile_kcc('int main(void) { int n=3,a[2][3]={{0}}; int (*_Atomic p)[n]=a; p+=1; return 42; }')
    assert 'call $__atomic_add_fetch_8' in out and '=l mul ' in out,out
    pairs = [
        ('int helper(int (*)[3]); int main(void) { int n=3,a[3][3]={{0},{0,0,42},{0}}; int (*p)[n]=a; return helper(++p); }',
         'int helper(int (*p)[3]) { return (*p)[2]; }'),
        ('int worker(int *a,int n) { int (*p)[n]=(void *)a; p+=1; return (*p)[2]; }',
         'int worker(int *,int); int main(void) { int a[2][3]={{0},{0,0,42}}; return worker(&a[0][0],3); }'),
    ]
    for ktext,htext in pairs:
        out=compile_kcc(ktext)
        if qbe:
            h=d/'host.c'; obj=d/'host.o'; h.write_text(htext+'\n')
            subprocess.run([host,'-std=c11','-pedantic-errors','-c',str(h),'-o',str(obj)],check=True,timeout=10)
            assert run_kcc(out,[obj])==42,ktext
print('VM pointer updates: compile and native differential' + (', QBE runtime and mixed ABI' if qbe else '') + f'; exact native oracle gaps: {native_gaps}')
