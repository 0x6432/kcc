"""C23 constexpr aggregate initialization, named members, storage and constraints."""
import os, subprocess, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
kcc=Path(os.environ.get('KCC',root/'build'/'kcc'))
qbe=os.environ.get('QBE')
host=os.environ.get('HOST_CC','cc')
programs=[
'''constexpr int a[]={40,1,2}; int main(void){return sizeof(a)==12 && a[0]+a[2]==42?42:1;}''',
'''constexpr int a[5]={[2]=42,[4]=7}; int main(void){return a[0]==0 && a[2]==42 && a[4]==7?42:1;}''',
'''constexpr int a[2][3]={{1,2,3},{4,5,42}}; int main(void){return a[1][2];}''',
'''constexpr char s[]="hello"; int main(void){return sizeof(s)==6 && s[0]=='h' && s[5]==0?42:1;}''',
'''struct A{int n; double f; int *p;}; constexpr struct A a={42,2.5,nullptr}; static_assert(a.n==42); static_assert((int)a.f==2); constexpr int *p=a.p; int x[a.n]; int main(void){return sizeof(x)==168 && p==nullptr?42:1;}''',
'''struct A{int a; int b;}; struct B{struct A inner; int c;}; constexpr struct B x={.inner={.a=42}}; static_assert(x.inner.a==42 && x.inner.b==0 && x.c==0); int main(void){return x.inner.a;}''',
'''struct S{int n; double f; int *p;}; int main(void){constexpr struct S a={40,2.0,nullptr}; static constexpr struct S b={a.n+2, a.f, a.p}; static_assert(b.n==42 && (int)b.f==2); return b.p==nullptr?b.n:1;}''',
'''struct S{int n; int a[2];}; constexpr struct S s={.a={40,2}, .n=42}; enum E { ANSWER=s.n }; int main(void){const struct S *p=&s; return p->a[0]+p->a[1]==ANSWER?ANSWER:1;}''',
'''constexpr int a[]={1,2,3}; int main(void){constexpr int b[2]={a[0],2}; return 1;}''',
'''struct S{int n;}; constexpr struct S s={1}; int main(void){switch(42){case s.n+41:return 42;default:return 1;}}''',
'''struct S{unsigned char c; float f; int *p;}; constexpr struct S x={255,1.5f,nullptr}; int main(void){return x.c==255 && x.f==1.5f && x.p==nullptr?42:1;}''',
'''constexpr int a[3]={}; int main(void){static constexpr int b[2]={40,2}; return a[1]==0?b[0]+b[1]:1;}''',
'''int main(void){constexpr int a[]={40,2}; static constexpr int b[]={42}; return sizeof(a)==8 && sizeof(b)==4 && a[0]+a[1]==b[0]?42:1;}''',
'''struct S{int a; int b;}; constexpr struct S s={.a=1,.a=42}; static_assert(s.a==42 && s.b==0); int main(void){return s.a;}''',
'''struct A{int n; int b;}; struct S{struct A a;}; constexpr struct S s={.a={1,2},.a={42}}; static_assert(s.a.n==42 && s.a.b==0); int main(void){return s.a.n;}''',
'''struct S{int n;}; constexpr struct S s={42}; constexpr int x=s.n; int main(void){constexpr int y=s.n; static_assert(y==42); return x;}''',
'''constexpr unsigned char s[]="\\xff"; int main(void){return s[0]==255 && s[1]==0?42:1;}''',
]
# Array indexing is not a C23 named constant: move the deliberately invalid case to refusals.
negative=[programs.pop(8),
'''constexpr int a[2]={1,2}; static_assert(a[0]==1);''',
'''constexpr int a[1]={1}; int main(void){a[0]=2; return 0;}''',
'''struct S{int n;}; constexpr struct S s={42}; int main(void){s.n=1; return 0;}''',
'''constexpr unsigned char a[]={256};''',
'''constexpr _Bool a[]={2};''',
'''constexpr float a[]={0.1};''',
'''int x; constexpr int *a[]={&x};''',
'''int x; constexpr int a[]={x};''',
'''struct S{volatile int n;}; constexpr struct S s={1};''',
'''struct S{int n:3;}; constexpr struct S s={1};''',
'''union U{int n; float f;}; constexpr union U u={1};''',
'''struct S{int n; union U{int x;} u;}; constexpr struct S s={1,{2}};''',
'''struct S{int n; int a[];}; constexpr struct S s={1};''',
'''struct S{int n;}; constexpr struct S s={s.n};''',
'''struct S{int n;}; constexpr struct S s={1}; constexpr struct S t=s;''',
'''constexpr int a[2];''',
'''constexpr int a[1]={1}, b[1]={2};''',
'''constexpr char s[]="\\xff";''',
]
with tempfile.TemporaryDirectory(prefix='kcc constexpr aggregate ') as tmp:
 d=Path(tmp); source=d/'p.c'; il=d/'p.ssa'; asm=d/'p.s'; exe=d/'p'
 def compile_text(text):
  source.write_text(text+'\n')
  return subprocess.run([str(kcc),str(source)],capture_output=True,text=True,timeout=15)
 for text in programs:
  r=compile_text(text)
  assert r.returncode==0 and not r.stderr,(text,r.stderr)
  if qbe:
   il.write_text(r.stdout); subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
   subprocess.run([host,str(asm),'-o',str(exe)],check=True,timeout=15)
   rc=subprocess.run([str(exe)],timeout=5).returncode
   assert rc==42,(text,rc)
 for text in negative:
  r=compile_text(text)
  assert r.returncode==1 and not r.stdout,(text,r.returncode,r.stderr)
 if qbe:
  r=compile_text('''struct S{int n; double f; int *p;}; constexpr struct S a={42, 1.5, nullptr};
    const struct S *get(void){static constexpr struct S b={a.n,a.f,a.p}; return &b;}
    double scalar(void){constexpr double x=1.0/3.0; return x;}
    double inferred(void){constexpr auto x=1.0/3.0; return x;}
    double aggregate(void){constexpr struct S x={1,1.0/3.0,nullptr}; return x.f;}''')
  assert r.returncode==0,r.stderr
  il.write_text(r.stdout);subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
  native=d/'native.c'; native.write_text('''#include <fenv.h>\n#include <stdint.h>\n#include <string.h>\nstruct S{int n; double f; int *p;}; const struct S *get(void); double scalar(void), inferred(void), aggregate(void); int main(void){ const struct S *p=get(); if(p!=get() || p->n!=42 || p->f!=1.5 || p->p) return 1; fesetround(FE_UPWARD); double x[]={scalar(),inferred(),aggregate()}; for(int i=0;i<3;i++){uint64_t u; memcpy(&u,&x[i],8); if(u!=0x3fd5555555555555ULL)return 2;} return 42;}''')
  subprocess.run([host,str(asm),str(native),'-lm','-o',str(exe)],check=True,timeout=15)
  assert subprocess.run([str(exe)],timeout=5).returncode==42
print(f'constexpr aggregates: {len(programs)} runtime cases, {len(negative)} refusals, native ABI and floating rounding')
