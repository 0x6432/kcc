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
'''struct S{unsigned a:6; signed b:5; unsigned c:3;}; constexpr struct S s={42,-3,7}; static_assert(s.a==42 && s.b==-3 && s.c==7); int main(void){return s.a;}''',
'''struct S{unsigned a:4; unsigned b:6; unsigned c:4;}; constexpr struct S s={.a=2,.b=42,.c=3,.a=1}; static_assert(s.a==1 && s.b==42 && s.c==3); int main(void){return s.b;}''',
'''struct S{signed long a:40; unsigned long b:40;}; constexpr struct S s={-12345678901L,42}; static_assert(s.a==-12345678901L && s.b==42); int main(void){return s.b;}''',
'''struct S{unsigned _BitInt(8) a:6; signed _BitInt(8) b:6;}; int main(void){constexpr struct S s={42,-3}; static_assert(s.a==42 && s.b==-3); return s.a;}''',
'''struct S{unsigned a:3; unsigned :0; unsigned b:6;}; constexpr struct S s={.b=42}; static_assert(s.a==0 && s.b==42); int main(void){return s.b;}''',
'''struct S{_Bool a:1; unsigned b:6;}; constexpr struct S s={1,42}; static_assert(s.a==1 && s.b==42); int main(void){return s.b;}''',
'''enum E : unsigned int { A=1 }; struct S{enum E x:6;}; constexpr struct S s={42}; static_assert(s.x==42); int main(void){return s.x;}''',
'''struct S{signed long x:64; unsigned long y:64;}; constexpr struct S s={-9223372036854775807L-1,18446744073709551615UL}; static_assert(s.x<0 && s.y==~0UL); int main(void){return s.x<0 && s.y==~0UL?42:1;}''',
'''struct S{signed x:3; unsigned y:6;}; int main(void){static constexpr struct S s={-4,42}; static_assert(s.x==-4 && s.y==42); return s.y;}''',
'''struct S{int n;}; constexpr struct S s={42}; constexpr struct S t=s; static_assert(t.n==42); int main(void){return t.n;}''',
'''struct S{int n; double f; int *p; char a[4]; unsigned bit:6;}; constexpr struct S s={42,1.5,nullptr,"abc",42}; constexpr struct S t=s; int main(void){return t.n==42 && t.f==1.5 && t.p==nullptr && t.a[2]=='c' && t.bit==42?42:1;}''',
'''struct A{int n; int m;}; struct B{int z; struct A a;}; constexpr struct B b={1,{42,2}}; constexpr struct A a=b.a; static_assert(a.n==42 && a.m==2); int main(void){return a.n;}''',
'''struct A{int n; int m;}; struct B{struct A a; int z;}; constexpr struct A a={42,2}; constexpr struct B b={a,3}; static_assert(b.a.n==42 && b.a.m==2); int main(void){return b.a.n;}''',
'''struct S{int n;}; constexpr struct S s=(constexpr struct S){42}; static_assert(s.n==42); int main(void){return s.n;}''',
'''struct S{int n;}; constexpr struct S source={42}; struct S a=source; static struct S b=(constexpr struct S){42}; int main(void){return a.n==42 && b.n==42?42:1;}''',
'''struct S{int n;}; constexpr struct S source={42}; constexpr auto a=source; static_assert(a.n==42); int main(void){return a.n;}''',
'''union U{int a; int b;}; constexpr union U u={.a=42}; static_assert(u.a==42); int main(void){return u.a;}''',
'''union U{int a; int b;}; constexpr union U u={.b=42}; static_assert(u.b==42); int main(void){return u.b;}''',
'''struct S{int n;}; union U{int n; struct S s;}; constexpr union U u={.s={42}}; constexpr struct S s=u.s; static_assert(s.n==42); int main(void){return s.n;}''',
'''union U{int a; int b;}; constexpr union U u={}; static_assert(u.a==0); int main(void){return u.a==0?42:1;}''',
'''union U{double f; int n;}; constexpr union U u={.f=42.0}; static_assert((int)u.f==42); int main(void){return u.f==42.0?42:1;}''',
'''union U{int *p; int n;}; constexpr union U u={.p=nullptr}; constexpr int *q=u.p; int main(void){return q==nullptr?42:1;}''',
'''union U{int a; int b;}; struct S{int v; union U u;}; constexpr struct S s={1,{.b=42}}; static_assert(s.u.b==42); int main(void){return s.u.b;}''',
'''struct S{int a; int b;}; union U{struct S s; int n;}; constexpr union U u={.s={40,42}}; static_assert(u.s.a==40 && u.s.b==42); int main(void){return u.s.b;}''',
'''union U{unsigned a:6; signed b:6;}; constexpr union U u={.a=42}; static_assert(u.a==42); int main(void){return u.a;}''',
'''union U{int a; int b;}; constexpr union U u={.a=1,.b=42}; static_assert(u.b==42); int main(void){return u.b;}''',
'''union U{int a; int b;}; int main(void){constexpr union U u={.b=42}; static_assert(u.b==42); return u.b;}''',
'''union U{int a; int b;}; int main(void){static constexpr union U u={.b=42}; static_assert(u.b==42); return u.b;}''',
'''union U{int a; int b;}; struct S{union U x; union U y;}; constexpr struct S s={.x={.a=1},.y={.b=42}}; static_assert(s.x.a==1 && s.y.b==42); int main(void){return s.y.b;}''',
'''union U{int a; int b;}; struct S{union U u; int z;}; constexpr struct S s={}; static_assert(s.u.a==0 && s.z==0); int main(void){return s.z==0?42:1;}''',
'''union U{int a; double d;}; constexpr union U u={.d=42.0}; constexpr double f=u.d; int main(void){return f==42.0?42:1;}''',
'''union U{int a; int *p;}; constexpr union U u={.p=nullptr}; int main(void){static constexpr int *p=u.p; return p==nullptr?42:1;}''',
'''union U{int a; double b;}; constexpr union U a[2]={{.a=42},{.b=1.5}}; int main(void){return a[0].a==42 && a[1].b==1.5?42:1;}''',
'''struct S{int n;}; constexpr auto a=(constexpr struct S){42}; static_assert(a.n==42); int main(void){return a.n;}''',
'''struct S{int n;}; constexpr struct S source={42}; int main(void){constexpr auto a=source; static_assert(a.n==42); return a.n;}''',
'''struct S{int n;}; constexpr struct S source={42}; int main(void){constexpr register auto a=source; static_assert(a.n==42); return a.n;}''',
'''struct S{int n;}; constexpr struct S source={42}; int main(void){constexpr const auto a=source; const struct S *p=&a; return p->n;}''',
'''struct S{int n;}; constexpr struct S source={42}; int main(void){static constexpr auto a=source; static_assert(a.n==42); return a.n;}''',
'''struct A{int n;}; struct B{struct A a;}; constexpr struct B b={{42}}; constexpr auto a=b.a; static_assert(a.n==42); int main(void){return a.n;}''',
'''struct S{unsigned n:6; double f; int *p;}; constexpr auto a=(constexpr struct S){42,1.5,nullptr}; int main(void){constexpr auto b=a; static_assert(b.n==42); return b.f==1.5 && b.p==nullptr?b.n:1;}''',
'''struct S{int n;}; struct B{struct S s;}; constexpr struct S source={42}; static struct B b={source}; int main(void){return b.s.n;}''',
'''struct S{int n; int m;}; int main(void){constexpr struct S a={42,0}; constexpr struct S b=a; static_assert(b.n==42 && b.m==0); return b.n;}''',
'''struct A{int n; int z;}; struct B{struct A a;}; constexpr struct A a={1,2}; constexpr struct B b={.a=a,.a.n=42}; static_assert(b.a.n==42 && b.a.z==2); int main(void){return b.a.n;}''',
]
# Array indexing is not a C23 named constant: move the deliberately invalid case to refusals.
negative=[programs.pop(8),
'''struct S{int n;}; union U{int n; struct S s;}; constexpr union U u={.n=42}; constexpr struct S s=u.s;''',
'''struct S{int n;}; union U{int n; struct S s;}; constexpr union U u={.n=42}; constexpr auto s=u.s;''',
'''union U{int a; int b;}; struct S{union U x; union U y;}; constexpr struct S s={.x={.a=1},.y={.b=42}}; static_assert(s.y.a==42);''',
'''union U{int a; int b;}; constexpr union U u={}; static_assert(u.b==0);''',
'''union U{unsigned a:3; int b;}; constexpr union U u={.a=8};''',
'''union U{int a; int b;}; constexpr union U u={.a=42}; static_assert(u.b==42);''',
'''union U{int a; int b;}; constexpr union U u={}; static_assert(u.b==0);''',
'''union U{int a; int b;}; constexpr union U u={.a=1,.b=42}; static_assert(u.a==42);''',
'''union U{int a; int b;}; struct S{union U u;}; constexpr struct S s={{.b=42}}; static_assert(s.u.a==42);''',
'''union U{int a; int b;}; constexpr union U a={42}; constexpr union U b=a;''',
'''struct S{union {int a; int b;};}; constexpr struct S s={.a=42};''',
'''struct S{int n;}; constexpr struct S s={1}; int main(void){constexpr auto a=s; a.n=2; return 0;}''',
'''struct S{int n;}; struct S s={1}; constexpr auto a=s;''',
'''struct S{int n;}; int main(void){struct S s={1}; constexpr auto a=s; return 0;}''',
'''struct S{volatile int n;}; constexpr auto a=(struct S){1};''',
'''struct S{int n;}; constexpr auto a=a;''',
'''struct S{int n;}; struct S s={1}; constexpr struct S t=s;''',
'''struct S{int n;}; constexpr struct S s={1}; constexpr struct S t=*(&s);''',
'''struct S{unsigned x:3;}; constexpr struct S s={8};''',
'''struct S{_Bool x:1;}; constexpr struct S s={2};''',
'''struct S{signed x:3;}; constexpr struct S s={4};''',
'''struct S{signed x:3;}; constexpr struct S s={-5};''',
'''struct S{unsigned x:3;}; constexpr struct S s={-1};''',
'''struct S{unsigned x:3;}; int f(void){constexpr struct S s={8}; return 0;}''',
'''constexpr int a[2]={1,2}; static_assert(a[0]==1);''',
'''constexpr int a[1]={1}; int main(void){a[0]=2; return 0;}''',
'''struct S{int n;}; constexpr struct S s={42}; int main(void){s.n=1; return 0;}''',
'''constexpr unsigned char a[]={256};''',
'''constexpr _Bool a[]={2};''',
'''constexpr float a[]={0.1};''',
'''int x; constexpr int *a[]={&x};''',
'''int x; constexpr int a[]={x};''',
'''struct S{volatile int n;}; constexpr struct S s={1};''',
'''struct S{int n; int a[];}; constexpr struct S s={1};''',
'''struct S{int n;}; constexpr struct S s={s.n};''',
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
    double aggregate(void){constexpr struct S x={1,1.0/3.0,nullptr}; return x.f;}
    double copy(void){constexpr struct S x={1,1.0/3.0,nullptr}; constexpr struct S y=x; return y.f;}''')
  assert r.returncode==0,r.stderr
  il.write_text(r.stdout);subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
  native=d/'native.c'; native.write_text('''#include <fenv.h>\n#include <stdint.h>\n#include <string.h>\nstruct S{int n; double f; int *p;}; const struct S *get(void); double scalar(void), inferred(void), aggregate(void), copy(void); int main(void){ const struct S *p=get(); if(p!=get() || p->n!=42 || p->f!=1.5 || p->p) return 1; fesetround(FE_UPWARD); double x[]={scalar(),inferred(),aggregate(),copy()}; for(int i=0;i<4;i++){uint64_t u; memcpy(&u,&x[i],8); if(u!=0x3fd5555555555555ULL)return 2;} return 42;}''')
  subprocess.run([host,str(asm),str(native),'-lm','-o',str(exe)],check=True,timeout=15)
  assert subprocess.run([str(exe)],timeout=5).returncode==42
if qbe:
 with tempfile.TemporaryDirectory(prefix='kcc constexpr bitfield abi ') as tmp:
  d=Path(tmp); source=d/'p.c'; il=d/'p.ssa'; asm=d/'p.s'; exe=d/'p'; native=d/'native.c'
  source.write_text('struct S{signed a:5; unsigned b:6;}; const struct S *get(void){static constexpr struct S s={-3,42}; return &s;}')
  r=subprocess.run([str(kcc),str(source)],capture_output=True,text=True,timeout=15); assert r.returncode==0,r.stderr
  il.write_text(r.stdout); subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True)
  native.write_text('struct S{signed a:5; unsigned b:6;}; const struct S *get(void); int main(void){const struct S *s=get();return s->a==-3 && s->b==42?42:1;}')
  subprocess.run([host,str(asm),str(native),'-o',str(exe)],check=True); assert subprocess.run([str(exe)]).returncode==42
print(f'constexpr aggregates: {len(programs)} runtime cases, {len(negative)} refusals, native ABI and floating rounding')
