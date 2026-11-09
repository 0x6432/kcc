"""Non-native _BitInt atomic operations and width wrapping on x86-64 SysV."""
import os
from pathlib import Path
import subprocess
import tempfile
from runtime_link import runtime_link_flags

ROOT = Path(__file__).resolve().parents[1]
QBE = os.environ.get('QBE', 'qbe')
HOST = os.environ.get('HOST_CC', 'cc')
types = [(w,u) for w in range(1,65) for u in (0,1)
         if (u or w > 1) and w not in (8,16,32,64)]
with tempfile.TemporaryDirectory(prefix='bitint-atomic-', dir=ROOT/'build') as tmp:
    d = Path(tmp)
    def execute(source, name):
        c=d/f'{name}.c'; il=d/f'{name}.ssa'; asm=d/f'{name}.s'; exe=d/name
        c.write_text(source)
        p=subprocess.run([ROOT/'build/kcc',c],capture_output=True,text=True,timeout=45)
        assert p.returncode==0 and not p.stderr, (name,p.stderr)
        il.write_text(p.stdout)
        subprocess.run([QBE,'-t','amd64_sysv','-o',asm,il],check=True)
        subprocess.run([HOST,asm,ROOT/'build/libkccrt.a','-latomic','-pthread',*runtime_link_flags(),'-o',exe],check=True)
        subprocess.run([exe],check=True,timeout=20)
    for start in range(0,len(types),8):
        parts=['#include <stdatomic.h>']; calls=[]
        for width,unsigned in types[start:start+8]:
            tag=f'{"u" if unsigned else "s"}{width}'; T=f'T{tag}'
            expected=(1<<width)-1 if unsigned else (1<<64)-1
            parts.append(f'''typedef {'unsigned ' if unsigned else ''}_BitInt({width}) {T};
_Atomic({T}) x{tag}; int f{tag}(void) {{
 (void)atomic_is_lock_free(&x{tag}); atomic_init(&x{tag},({T})-1);
 if ((unsigned long)atomic_fetch_add_explicit(&x{tag},({T})1,memory_order_acq_rel)!={expected}UL || x{tag}!=0) return 1;
 if (++x{tag}!=1 || atomic_fetch_sub_explicit(&x{tag},({T})1,memory_order_release)!=1 || x{tag}!=0) return 2;
 {T} expected=0; if(!atomic_compare_exchange_strong_explicit(&x{tag},&expected,({T})1,memory_order_acq_rel,memory_order_acquire) || expected!=0 || x{tag}!=1) return 3;
 expected=0; if(atomic_compare_exchange_weak(&x{tag},&expected,({T})0) || expected!=1) return 4;
 if(atomic_exchange_explicit(&x{tag},({T})0,memory_order_relaxed)!=1 || x{tag}!=0) return 5;
 if(atomic_fetch_or_explicit(&x{tag},({T})1,memory_order_acquire)!=0 || atomic_fetch_xor(&x{tag},({T})1)!=1 || x{tag}!=0) return 6;
 x{tag}=({T})-1; if(atomic_fetch_and(&x{tag},({T})0)!=({T})-1 || x{tag}!=0) return 7;
 x{tag}=({T})-1; if((unsigned long)x{tag}++!={expected}UL || x{tag}!=0) return 8;
 x{tag}=({T})0; if((x{tag}+=1)!=1 || (x{tag}-=1)!=0) return 9;
 atomic_store_explicit(&x{tag},({T})-1,memory_order_release);
 if((unsigned long)atomic_load_explicit(&x{tag},memory_order_acquire)!={expected}UL) return 10;
 x{tag}=({T})1; if((x{tag}*=1)!=1 || (x{tag}&=1)!=1 || (x{tag}^=1)!=0 || (x{tag}|=1)!=1 || (x{tag}/=1)!=1 || (x{tag}%=1)!=0) return 11;
 x{tag}=({T})1; if((x{tag}+=0.5)!=1 || (x{tag}>>=1)!=0) return 12;
 return 0; }}''')
            calls.append(f'if(f{tag}()) return 1;')
        execute('\n'.join(parts)+'\nint main(void){'+'\n'.join(calls)+'return 0;}','all')
    execute(r'''#include <stdatomic.h>
typedef unsigned long pthread_t;
int pthread_create(pthread_t *, const void *, void *(*)(void *), void *);
int pthread_join(pthread_t, void **);
_Atomic(unsigned _BitInt(9)) counter; int calls;
_Atomic(unsigned _BitInt(9)) *once(void) { calls++; return &counter; }
int order(void) { calls++; return memory_order_acq_rel; }
void *worker(void *p) { for (int i=0;i<5000;i++) { if (i&1) counter++; else atomic_fetch_add_explicit(&counter,1,memory_order_relaxed); } return p; }
int main(void) { pthread_t a,b,c,d; if(atomic_fetch_add_explicit(once(),1,order())!=0 || calls!=2) return 3; counter=0; if(pthread_create(&a,0,worker,0) || pthread_create(&b,0,worker,0) || pthread_create(&c,0,worker,0) || pthread_create(&d,0,worker,0)) return 1;
 if(pthread_join(a,0) || pthread_join(b,0) || pthread_join(c,0) || pthread_join(d,0)) return 2;
 return counter!=(20000%512); }
''','threads')
print(f'Atomic BitInt: {len(types)} non-native signed/unsigned types, RMW, orders, compare-exchange and pthread contention passed')
