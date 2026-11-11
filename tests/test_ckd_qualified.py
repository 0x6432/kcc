"""Qualified C23 checked-arithmetic destinations, native model and atomic ABI."""
import os
import subprocess
import tempfile
from pathlib import Path
from runtime_link import runtime_link_flags

root=Path(__file__).resolve().parents[1]
kcc=Path(os.environ.get('KCC',root/'build/kcc'))
qbe=os.environ.get('QBE')
host=os.environ.get('HOST_CC','cc')
runtime=Path(os.environ.get('KCC_RUNTIME',root/'build/libkccrt.a'))
types=[('signed char',8,1),('unsigned char',8,0),('short',16,1),('unsigned short',16,0),
       ('int',32,1),('unsigned int',32,0),('long',64,1),('unsigned long',64,0),
       ('long long',64,1),('unsigned long long',64,0)]
quals=['', 'volatile ', '_Atomic ', 'volatile _Atomic ']
with tempfile.TemporaryDirectory(prefix='kcc ckd qualified ') as tmp:
    d=Path(tmp); objects=[]
    for i,(typ,width,signed) in enumerate(types):
        code=['#include <stdckdint.h>']
        for q,qual in enumerate(quals):
            code.append(f'void ck{i}_{q}(long long a,unsigned long long b,unsigned long long *out) {{ {qual}{typ} r;')
            for j,op in enumerate(('add','sub','mul')):
                code.append(f'out[{2*j}]=ckd_{op}(&r,a,b); out[{2*j+1}]=(unsigned long long)r;')
            code.append('}')
        if i==7:
            code.append('void atomic_write(_Atomic unsigned long *p, unsigned long v) { ckd_add(p,v,0); }')
        src,il,asm,obj=(d/f'u{i}.{ext}' for ext in ('c','ssa','s','o'))
        src.write_text('\n'.join(code)+'\n')
        r=subprocess.run([str(kcc),str(src)],capture_output=True,text=True,timeout=40)
        assert r.returncode==0 and not r.stderr,(i,r.stderr)
        if qbe:
            il.write_text(r.stdout)
            subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=30)
            subprocess.run([host,'-c',str(asm),'-o',str(obj)],check=True,timeout=30)
            objects.append(str(obj))
    for t in ('const int','const volatile int','const _Atomic int','_Bool','char','unsigned _BitInt(8)'):
        src.write_text(f'#include <stdckdint.h>\nint f(void){{{t} x; return ckd_add(&x,1,2);}}\n')
        r=subprocess.run([str(kcc),str(src)],capture_output=True,text=True,timeout=20)
        assert r.returncode!=0 and r.stderr and not r.stdout,(t,r.stderr)
    if qbe:
        # Interpose the helper to verify each qualifier selects the intended
        # runtime store kind, independent of the arithmetic result.
        src.write_text("""#include <stdckdint.h>
int selection(int i) { int a; volatile int b; _Atomic int c; volatile _Atomic int d;
 if(i==0) return ckd_add(&a,1,2); if(i==1) return ckd_add(&b,1,2);
 if(i==2) return ckd_add(&c,1,2); return ckd_add(&d,1,2); }
""")
        r=subprocess.run([str(kcc),str(src)],capture_output=True,text=True,timeout=30)
        assert r.returncode==0 and not r.stderr,r.stderr
        il.write_text(r.stdout)
        subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=30)
        stub=d/'dispatch.c'; dispatch=d/'dispatch'
        stub.write_text("""#include <stdbool.h>
static unsigned actual;
bool __kcc_ckd(void *p,unsigned k,unsigned long a,unsigned sa,unsigned long b,unsigned sb,unsigned op)
{ (void)p;(void)a;(void)sa;(void)b;(void)sb;(void)op;actual=k;return false; }
int selection(int);
int main(void) { unsigned expected[]={288,800,1312,1824};
 for(int i=0;i<4;i++) { selection(i); if(actual!=expected[i])return 1; } return 0; }
""")
        subprocess.run([host,str(asm),str(stub),'-o',str(dispatch)],check=True,timeout=30)
        subprocess.run([str(dispatch)],check=True,timeout=10)
    if qbe:
        declarations='\n'.join(f'void ck{i}_{q}(long long,unsigned long long,unsigned long long *);' for i in range(10) for q in range(4))
        functions=','.join(f'ck{i}_{q}' for i in range(10) for q in range(4))
        widths=','.join(str(w) for _,w,_ in types)
        signs=','.join(str(s) for _,_,s in types)
        harness=d/'harness.c'; exe=d/'test'
        harness.write_text(r'''#include <stdint.h>
#include <stdatomic.h>
#include <pthread.h>
#include <stdio.h>
''' +declarations+r'''
void atomic_write(_Atomic unsigned long *,unsigned long);
static _Atomic unsigned long shared;
static _Atomic int done;
static void *writer(void *unused) { (void)unused; for(int i=0;i<200000;i++) atomic_write(&shared,(i&1)?0xaaaaaaaaaaaaaaaaUL:0x5555555555555555UL); atomic_store(&done,1); return 0; }
int main(void) {
 void (*funcs[])(long long,unsigned long long,unsigned long long*)={'''+functions+r'''};
 const unsigned widths[]={'''+widths+r'''}, signs[]={'''+signs+r'''};
 unsigned long long seed=0xd1b54a32d192ed03ULL;
 for(unsigned i=0;i<10;i++) for(unsigned q=0;q<4;q++) for(unsigned j=0;j<2000;j++) {
  seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;
  long long a=j==0?INT64_MIN:j==1?INT64_MAX:j==2?-1:j==3?0:(long long)seed;
  seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;
  unsigned long long b=j==0?UINT64_MAX:j==1?0:j==2?1:j==3?UINT64_MAX:seed;
  __int128 aa=a, bb=b, vals[]={aa+bb,aa-bb,aa*bb};
  unsigned w=widths[i]; __int128 min=signs[i]?-((__int128)1<<(w-1)):0;
  __int128 max=signs[i]?(((__int128)1<<(w-1))-1):(((__int128)1<<w)-1);
  unsigned long long mask=UINT64_MAX>>(64-w), out[6]; funcs[4*i+q](a,b,out);
  for(int op=0;op<3;op++) if(out[op*2]!=(unsigned)(vals[op]<min||vals[op]>max) || (out[op*2+1]&mask)!=((unsigned long long)vals[op]&mask)) {
   fprintf(stderr,"type %u qualifier %u case %u op %d\n",i,q,j,op);return 1;
  }
 }
 pthread_t t; atomic_store(&shared,0xaaaaaaaaaaaaaaaaUL);
 if(pthread_create(&t,0,writer,0)) return 2;
 while(!atomic_load(&done)) { unsigned long v=atomic_load(&shared); if(v!=0xaaaaaaaaaaaaaaaaUL && v!=0x5555555555555555UL) return 3; }
 if(pthread_join(t,0)) return 4;
 return 0;
}''')
        subprocess.run([host,'-std=c11','-O2','-pthread',str(harness),*objects,str(runtime),*runtime_link_flags(),'-latomic','-o',str(exe)],check=True,timeout=90)
        subprocess.run([str(exe)],check=True,timeout=30)
print('checked arithmetic: ten result types, four qualifier forms, mixed signed/unsigned operations and atomic native interop; '+('QBE/runtime model passed' if qbe else 'runtime not run'))
