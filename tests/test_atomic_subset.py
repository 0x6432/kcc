"""M24c bounded atomic types and seq_cst load/store, amd64 SysV + libatomic."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

positive = [
    'int main(void) { int a[4]={0,1,2,42}; _Atomic(int *) p=a; int *x=p++; int *y=++p; p+=1; return x==a && y==a+2 && *p==42 ? 42 : 1; }',
    'int main(void) { int a[4]={42,1,2,3}; _Atomic(int *) p=a+3; int *x=p--; int *y=--p; int *z=(p-=1L); return x==a+3 && y==a+1 && z==a && *p==42 ? 42 : 1; }',
    'int main(void) { int a[3]={0,0,42}; _Atomic(int *) p[2]={a,a}; int i=0; p[i++]+=2; return i==1 && *p[0]==42 ? 42 : 1; }',
    'int main(void) { int x=1,y=42; _Atomic(int *) p=&x; p=&y; int *q=p; return *q; }',
    'int main(void) { int x=42; int * _Atomic p=&x; return *p; }',
    'int main(void) { int x=42; auto _Atomic p=&x; return *p; }',
    '_Atomic int x; int read(void) { return x; } void write(int y) { x=y; }',
    'struct S { _Atomic int *p; };',
    '_Atomic(int) x=41; int main(void) { _Atomic int *p=&x; *p=42; return *p; }',
    'typedef int I; typedef _Atomic(I) A; A x; int main(void) { x=42; return x; }',
    'int main(void) { _Atomic unsigned x=4294967295U; x=42; return x; }',
    'int main(void) { const _Atomic int x=42; return x; }',
    'int main(void) { _Atomic int a[2]={1,2}; a[1]=42; return a[1]; }',
    'int main(void) { _Atomic int x=42; return sizeof(x)==4 && alignof(_Atomic(int))==4 ? x : 1; }',
    'int main(void) { _Atomic int x=1; return sizeof(x=2)==4 && x==1 ? 42 : 1; }',
    'int main(void) { auto _Atomic x=42; return x; }',
    'int main(void) { _Atomic int x=0; int y=(x=42); return x==y ? y : 1; }',
    'int main(void) { _Atomic int x=42; typeof_unqual(x) y=x; return y; }',
    'int main(void) { _Atomic int x=40; int a=x++; int b=++x; return a==40 && b==42 && x==42 ? 42 : 1; }',
    'int main(void) { _Atomic unsigned x=44; int a=x--; int b=--x; return a==44 && b==42 && x==42 ? 42 : 1; }',
    'int main(void) { _Atomic int x=40; int y=(x+=2L); return y==42 && x==42 ? 42 : 1; }',
    'int main(void) { _Atomic int a[2]={0,43}; int i=1; int y=(a[i--]-=1); return i==0 && y==42 && a[1]==42 ? 42 : 1; }',
    'int main(void) { _Atomic unsigned x=63; x &= 42; x |= 1; x ^= 1; return x; }',
]
negative = [
    'int f(void) { _Atomic(void *) p=0; p++; return 0; }',
    'int f(void) { int x[2]; _Atomic(int *) p=x; p&=1; return 0; }',
    'struct S { _Atomic(int *) p; };',
    '_Atomic long x;', '_Atomic _Bool x;',
    '_Atomic void x;', '_Atomic(int[2]) x;',
    '_Atomic(const int) x;', '_Atomic(_Atomic(int)) x;',
    'struct S { _Atomic int x; };', 'struct S { _Atomic int x[2]; };',
    'int main(void) { _Atomic int x=1; x*=2; return x; }',
    'int main(void) { _Atomic int x=1; x<<=2; return x; }',
    'int main(void) { _Atomic int x=1; x+=2.0; return x; }',
    'int main(void) { const _Atomic int x=1; return ++x; }',
    'int main(void) { const _Atomic int x=1; x=2; return x; }',
    'int main(void) { auto _Atomic x=(long)1; return 0; }',
    'typedef int A[2]; _Atomic A x;',
    'int main(void) { return sizeof(' + '_Atomic(' * 65 + 'int' + ')' * 65 + '); }',
]

with tempfile.TemporaryDirectory(prefix='kcc-atomics-') as tmp:
    d = Path(tmp)
    source, il, asm, helper, exe = [d / x for x in ('test.c', 'out.ssa', 'out.s', 'host.c', 'out')]

    def compile_kcc(text, succeeds=True):
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == succeeds, (text, result.stderr)
        if not succeeds:
            assert result.stderr and not result.stdout, (text, result.stderr)
        return result.stdout

    for text in positive:
        output = compile_kcc(text)
        if qbe and 'main(void)' in text:
            il.write_text(output)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True, timeout=10)
            subprocess.run([host, str(asm), '-latomic', '-o', str(exe)], check=True, timeout=10)
            assert subprocess.run([str(exe)], timeout=5).returncode == 42, text
    for text in negative:
        compile_kcc(text, False)

    pointer_output = compile_kcc('int *f(_Atomic(int *) *p) { return *p; } void g(_Atomic(int *) *p,int *q) { *p=q; }')
    assert '$__atomic_load_8' in pointer_output and '$__atomic_store_8' in pointer_output
    pointer_updates = compile_kcc('int *f(_Atomic(int *) *p, int n) { (*p)++; return *p+=n; }')
    assert '$__atomic_fetch_add_8' in pointer_updates and '$__atomic_add_fetch_8' in pointer_updates
    assert 'mul' in pointer_updates and ', 4' in pointer_updates

    # Both translation units access the same atomic objects; synchronize iterations
    # without racing on result slots. The forbidden outcome violates seq_cst.
    output = compile_kcc('void put(_Atomic int *p,int v) { *p=v; } int get(_Atomic int *p) { return *p; }')
    assert '$__atomic_load_4' in output and '$__atomic_store_4' in output
    if qbe:
        il.write_text(output)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True, timeout=10)
        helper.write_text(r'''
#include <stdatomic.h>
#include <pthread.h>
extern void put(_Atomic int *,int);
extern int get(_Atomic int *);
static _Atomic int a, b;
static int r0, r1;
static pthread_barrier_t start, end;
static void *t0(void *x) { (void)x; for (int i=0;i<2000;i++) {
  pthread_barrier_wait(&start); put(&a,1); r0=get(&b); pthread_barrier_wait(&end);
} return 0; }
static void *t1(void *x) { (void)x; for (int i=0;i<2000;i++) {
  pthread_barrier_wait(&start); atomic_store(&b,1); r1=atomic_load(&a); pthread_barrier_wait(&end);
} return 0; }
int main(void) { pthread_t x,y; pthread_barrier_init(&start,0,3); pthread_barrier_init(&end,0,3);
  pthread_create(&x,0,t0,0); pthread_create(&y,0,t1,0);
  for (int i=0;i<2000;i++) { atomic_store(&a,0); put(&b,0); pthread_barrier_wait(&start);
    pthread_barrier_wait(&end); if (!r0 && !r1) return 1; }
  pthread_join(x,0); pthread_join(y,0); return 42; }
''')
        subprocess.run([host, '-std=c11', '-D_XOPEN_SOURCE=700', '-pthread', str(helper), str(asm), '-latomic', '-o', str(exe)], check=True, timeout=10)
        assert subprocess.run([str(exe)], timeout=15).returncode == 42
print('atomic subset compile checks' + (' and QBE/host interoperability' if qbe else ''))
