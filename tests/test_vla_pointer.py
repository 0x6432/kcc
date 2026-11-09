"""Bounded block-local pointers to runtime-bound arrays, not general VM types."""
import os
import signal
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build/kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
# C11 programs with defined behavior, also used as differential native tests.
programs = [
    'int main(void) { int n=3,a[3]={1,2,42}; int (*p)[n++]=&a; n=9; return sizeof *p==12 && (*p)[2]==42 ? 42:1; }',
    'int main(void) { int n=2,a[2]={20,22}; int (*p)[n++]=&a, (*q)[n++]=0; return n==4 && sizeof *p==8 && sizeof *q==12 && (*p)[0]+(*p)[1]==42 ? 42:1; }',
    'int main(void) { int n=2,a[2][3]={{0,0,0},{0,0,42}}; int (*p)[n++][3]=&a; return n==3 && sizeof *p==24 && (*p)[1][2]==42 ? 42:1; }',
    'int main(void) { int n=2,a[2]={0,42}; int (*p)[n]=0; p=&a; int *q=*p; return q[1]; }',
    'int main(void) { int n=2,a[2]={0,42}; int (*p)[n]=&a; return sizeof p==sizeof(void *) && sizeof **p==sizeof(int) ? (*p)[1]:1; }',
    'int main(void) { int sum=0; for(int n=1;n<=3;n++) { int a[3]={0,0,0}; int (*p)[n]=(void *)a; sum+=sizeof *p; (*p)[n-1]=n; sum+=(*p)[n-1]; } return sum==30 ? 42:1; }',
    'int main(void) { int n=1,total=0,a[2]={20,22}; again:; int (*p)[n]=(void *)a; total+=sizeof *p; if(n++==1) goto again; return total==12 ? 42:1; }',
    'int main(void) { int n=2,a[2]={0,42}; switch(n) { case 2: { int (*p)[n]=&a; switch(n) { case 2: return (*p)[1]; } } } return 1; }',
    'int main(void) { int n=2,a[2]={0,42}; int (*p)[n]=&a; n=9; return (sizeof *p==8 && sizeof *p==8 && n==9) ? (*p)[1]:1; }',
    'int main(void) { int n=2,a[2]={0,42}; int (*const p)[n]=&a; return sizeof *p==8 ? (*p)[1]:1; }',
    'int main(void) { int n=2,a[2]={0,42}; int (*volatile p)[n]=&a; return sizeof *p==8 ? (*p)[1]:1; }',
    'int main(void) { int n=2,a[2]={0,42}; int (*p)[n]=(n++, &a); return n==3 && sizeof *p==8 ? (*p)[1]:1; }',
    'int main(void) { int n=2,a[2]={0,42}; int (*p)[n++]=&a; return sizeof(sizeof *p)==sizeof(unsigned long) && n==3 ? (*p)[1]:1; }',
    'int main(void) { int n=2; int a[n]; int (*p)[n]=&a; (*p)[1]=42; return sizeof a==sizeof *p ? a[1]:1; }',
    'int main(void) { int n=2; int (*p)[n]=0; return p==0 && sizeof *p==8 ? 42:1; }',
    'int main(void) { int n=1048576; char (*p)[n]=0; return sizeof *p==1048576 ? 42:1; }',
    'int main(void) { int n=1048576; for(int i=0;i<1000;i++) { char (*p)[n]=0; if(sizeof *p!=1048576) return 1; } return 42; }',
    'int main(void) { int n=2,a[2]={0,42}; int (*p)[n]=&a; switch(n) { case 2: return sizeof *p==8 ? (*p)[1]:1; default: return 1; } }',
    'int main(void) { int n=2,a[2]={0,42}; int (*p)[n++]=&a; return (1 || sizeof *p) && n==3 ? (*p)[1]:1; }',
    'int main(void) { int n=3, a[2][3]={{0,0,0},{0,0,42}}; int (*p)[n]=a; n=9; return p[1][2]; }',
    'int main(void) { int n=3, a[3][3]={{0},{0},{0,0,42}}; int (*p)[n]=a; int i=0; return (p+(i++,1)+1)[0][2]==42 && i==1 ? 42:1; }',
    'int main(void) { int n=3, a[2][3]={{0,0,42},{0,0,0}}; int (*p)[n]=a+1; return (p-1)[0][2]; }',
    'int main(void) { int n=3, a[2][3]={{0},{0,0,42}}; int (*volatile p)[n]=a; return p[1][2]; }',
    'int main(void) { int n=3, a[2][3]={{0},{0,0,42}}; int (*_Atomic p)[n]=a; return sizeof *p==12 ? p[1][2]:1; }',
    'static int calls; static int row(void) { calls++; return 1; } int main(void) { int n=3, a[2][3]={{0},{0,0,42}}; int (*p)[n]=a; return p[row()][2]==42 && calls==1 ? 42:1; }',
    'int main(void) { int n=2,a[2]={0,42}; int (*p)[n++]={&a}; return n==3 && sizeof *p==8 ? (*p)[1]:1; }',
    'int main(void) { int n=2,a[2]={0,42},r=1; for(int (*p)[n++]=&a; r==1; r=(*p)[1]) {} return n==3 ? r:1; }',
    'int main(void) { int n=3,a[2][3]={{0},{0,0,42}}; int (*p)[n]=a; { int n=2,b[2][2]={{0},{0,7}}; int (*p)[n]=b; if(sizeof *p!=8 || p[1][1]!=7) return 1; } return sizeof *p==12 ? p[1][2]:1; }',
    'int main(void) { int n=2,a[2]={0,42}; register int (*p)[n]=&a; return sizeof *p==8 ? (*p)[1]:1; }',
    'int main(void) { int n=3, a[2][3]={{0},{0,0,42}}; int (*p)[n++]=a; int i=0; return p[i++][2]==0 && p[i][2]==42 && n==4 ? 42:1; }',
]
rejected = [
    ('int f(int n) { goto x; int (*p)[n]=0; x: return 0; }', 'goto enters'),
    ('int f(int n) { { int (*p)[n]=0; x:; } goto x; }', 'goto enters'),
    ('int f(int n) { switch(n) { int (*p)[n]=0; case 1: return 0; } return 0; }', 'switch label enters'),
    ('int f(int n) { switch(n) { case 1:; int (*p)[n]=0; default: return 0; } return 0; }', 'switch label enters'),
    ('int f(int n) { int (*p)[n]=0; p++; return 0; }', 'complete object'),
    ('int f(int n) { int (*p)[n]=0; int (*q)[n]=0; return p-q; }', 'complete object referents'),
    ('int f(int n) { int (*p)[n]=0; int (*q)[2]=0; return ((n?p:q)+1)!=0; }', 'complete object referent'),
    ('int f(int n) { int (*p)[n]=0; int (*q)[2]=0; return ((n?q:p)+1)!=0; }', 'complete object referent'),
    ('int f(int n) { int (*p)[n]=0; int (*q)[2]=0; return sizeof *(n?p:q); }', 'sizeof variable-length'),
    ('int f(int n) { int (*p)[n]=0; return sizeof p[0]; }', 'sizeof variable-length'),
    ('int f(int n) { int (*p)[n]=0; return sizeof *(p+1); }', 'sizeof variable-length'),
    ('int f(int n) { static int (*p)[n]; return 0; }', 'variable-length arrays'),
    ('int f(int n) { extern int (*p)[n]; return 0; }', 'variable-length arrays'),
    ('int f(int n) { int (**p)[n]; return 0; }', 'variable-length arrays'),
    ('int f(int n) { int (*p)[2][n]; return 0; }', 'variable-length arrays'),
    ('int f(int n) { int (*p)[n]; typeof(p) q; return 0; }', 'typeof of variable-length'),
    ('int f(int n) { int a[n]; typeof(&a) q; return 0; }', 'typeof of variable-length'),
    ('int f(int n) { int a[n]; auto q=&a; return 0; }', 'inferred auto with variably modified'),
    ('int f(int n) { int (*p)[n]; static_assert(sizeof *p, "x"); return 0; }', 'constant expression'),
]
traps = [
    'int main(void) { int n=0; int (*p)[n]=0; return 42; }',
    'int main(void) { int n=-1; int (*p)[n]=0; return 42; }',
    'int main(void) { unsigned long n=18446744073709551615UL; char (*p)[n]=0; return 42; }',
    'int main(void) { int n=262145; int (*p)[n]=0; return 42; }',
    'int main(void) { int n=87382; int (*p)[n][3]=0; return 42; }',
]

with tempfile.TemporaryDirectory(prefix='kcc vm pointer ') as d:
    d = Path(d)
    src, il, asm, exe = [d / x for x in ('input.c', 'out.ssa', 'out.s', 'out')]
    def compile_kcc(text, error=None):
        src.write_text(text+'\n')
        r = subprocess.run([str(kcc),str(src)], capture_output=True, text=True, timeout=10)
        if error:
            assert r.returncode == 1 and not r.stdout and error in r.stderr, (text,r.stderr)
        else:
            assert r.returncode == 0 and not r.stderr, (text,r.stderr)
        return r.stdout
    def run_kcc(output, extra=()):
        il.write_text(output)
        subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)], check=True, timeout=10)
        subprocess.run([host,str(asm),*map(str,extra),str(root/'build/libkccrt.a'),'-latomic','-o',str(exe)], check=True, timeout=10)
        return subprocess.run([str(exe)], capture_output=True, timeout=5).returncode
    for text in programs:
        out = compile_kcc(text)
        if qbe:
            assert run_kcc(out) == 42, text
        src.write_text(text+'\n')
        r = subprocess.run([host,'-std=c11','-pedantic-errors',str(src),'-o',str(exe)], capture_output=True, text=True, timeout=10)
        assert r.returncode == 0, (text,r.stderr)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42, text
    for text,error in rejected:
        compile_kcc(text,error)
    for text in traps:
        out = compile_kcc(text)
        if qbe:
            assert run_kcc(out) == -signal.SIGABRT, text
    # sizeof of the supported direct indirection evaluates the volatile pointer
    # exactly once, but sizeof(sizeof *p) leaves it unevaluated.
    out = compile_kcc('int main(void) { int n=2; int (*volatile p)[n]=0; return sizeof *p==8 ? 42:1; }')
    assert out.count('call $__kcc_volatile_load_8') == 1, out
    out = compile_kcc('int main(void) { int n=2; int (*volatile p)[n]=0; return sizeof(sizeof *p)==8 ? 42:1; }')
    assert out.count('call $__kcc_volatile_load_8') == 0, out
    # Both directions: a VM pointer crosses the boundary as an ordinary pointer;
    # no VM parameter ABI is claimed or required.
    pairs = [
        ('int h(int (*)[3]); int main(void) { int a[3]={0,0,42},n=3; int (*p)[n]=&a; return h(p); }',
         'int h(int (*p)[3]) { return (*p)[2]; }'),
        ('int f(int *a,int n) { int (*p)[n]=(void *)a; return sizeof *p==12 ? (*p)[2]:1; }',
         'int f(int *,int); int main(void) { int a[3]={0,0,42}; return f(a,3); }'),
    ]
    for ktext,htext in pairs:
        out = compile_kcc(ktext)
        if qbe:
            other = d / 'host.c'; obj = d / 'host.o'
            other.write_text(htext+'\n')
            subprocess.run([host,'-std=c11','-pedantic-errors','-c',str(other),'-o',str(obj)], check=True, timeout=10)
            assert run_kcc(out,[obj]) == 42, ktext
print('VM pointer checks: compile, native differential' + (', QBE runtime and mixed ABI' if qbe else ''))
