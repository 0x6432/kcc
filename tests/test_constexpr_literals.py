"""C23 constexpr compound literals: initialization, storage and constraints."""
import os, subprocess, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
kcc=Path(os.environ.get('KCC',root/'build'/'kcc')); qbe=os.environ.get('QBE'); host=os.environ.get('HOST_CC','cc')
programs=[
'''int main(void){return (constexpr int){42};}''',
'''const int *p=&(constexpr int){42}; int main(void){return *p;}''',
'''int main(void){const int *p=&(constexpr int){42};return *p;}''',
'''int main(void){return (static constexpr int){42};}''',
'''int main(void){return (constexpr static int){42};}''',
'''int main(void){return (constexpr register int){42};}''',
'''int main(void){return sizeof((constexpr int[]){1,2,3})==12 && (constexpr int[]){40,2}[0]==40?42:1;}''',
'''struct S{int x; unsigned y:6; double z;}; int main(void){const struct S *s=&(constexpr struct S){40,42,1.5}; return s->x==40 && s->y==42 && s->z==1.5?42:1;}''',
'''struct S{int x;}; const struct S *p=&(constexpr struct S){.x=42}; int main(void){return p->x;}''',
'''int main(void){return (constexpr int *){nullptr}==nullptr?42:1;}''',
'''int main(void){return (constexpr int){}==0?42:1;}''',
'''constexpr int n=42; int main(void){return (constexpr int){n};}''',
'''static_assert((constexpr int){42}==42); constexpr int x=(constexpr int){40}+2; int a[(constexpr int){42}]; int main(void){return x==42 && sizeof(a)==168?42:1;}''',
'''struct S{int x; unsigned y:6;}; static_assert((constexpr struct S){40,42}.y==42); int main(void){return (constexpr struct S){40,42}.y;}''',
'''union U{int a; int b;}; static_assert((constexpr union U){.b=42}.b==42); int main(void){return (constexpr union U){.b=42}.b;}''',
'''static_assert((int)(constexpr double){42.0}==42); constexpr double x=(constexpr double){21.0}*2.0; int main(void){return x==42.0?42:1;}''',
'''constexpr int *p=(constexpr int *){nullptr}; int main(void){return p==nullptr?42:1;}''',
'''int main(void){return sizeof((constexpr char[]){"abc"})==4?42:1;}''',
'''int main(void){const int *a=0; int ok=1; for(int i=0;i<2;i++){const int *b=&(static constexpr int){42}; if(i && a!=b)ok=0; a=b;} return ok && *a==42?42:1;}''',
]
negative=[
'''union U{int a; int b;}; static_assert((constexpr union U){.a=42}.b==42);''',
'''int main(void){(constexpr int){42}=0;return 0;}''',
'''int main(void){int x=42; return (constexpr int){x};}''',
'''int main(void){return (constexpr unsigned char){256};}''',
'''int main(void){return (constexpr float){0.1}>0;}''',
'''int main(void){int x; return (constexpr int *){&x}!=0;}''',
'''int main(void){return (constexpr volatile int){1};}''',
'''int main(void){return (constexpr _Atomic int){1};}''',
'''int main(void){return (constexpr constexpr int){1};}''',
'''int main(void){return (constexpr thread_local int){1};}''',
'''int main(void){return (constexpr int)1;}''',
'''int main(void){return sizeof((constexpr int){1/0});}''',
'''struct S{unsigned x:3;}; int main(void){return (constexpr struct S){8}.x;}''',
'''int main(void){int *p=&(constexpr register int){42};return *p;}''',
]
with tempfile.TemporaryDirectory(prefix='kcc constexpr literal ') as tmp:
 d=Path(tmp); source=d/'p.c'; il=d/'p.ssa'; asm=d/'p.s'; exe=d/'p'
 def compile_text(text):
  source.write_text(text+'\n');return subprocess.run([str(kcc),str(source)],capture_output=True,text=True,timeout=15)
 for text in programs:
  r=compile_text(text); assert r.returncode==0 and not r.stderr,(text,r.stderr)
  if qbe:
   il.write_text(r.stdout);subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
   subprocess.run([host,str(asm),'-o',str(exe)],check=True,timeout=15)
   rc=subprocess.run([str(exe)],timeout=5).returncode;assert rc==42,(text,rc)
 for text in negative:
  r=compile_text(text);assert r.returncode==1 and not r.stdout,(text,r.returncode,r.stderr)
 if qbe:
  r=compile_text('double get(void){return (constexpr double){1.0/3.0};}');assert r.returncode==0,r.stderr
  il.write_text(r.stdout);subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True)
  native=d/'native.c';native.write_text('#include <fenv.h>\n#include <stdint.h>\n#include <string.h>\ndouble get(void); int main(void){fesetround(FE_UPWARD);double x=get();uint64_t u;memcpy(&u,&x,8);return u==0x3fd5555555555555ULL?42:1;}')
  subprocess.run([host,str(asm),str(native),'-lm','-o',str(exe)],check=True);assert subprocess.run([str(exe)]).returncode==42
print(f'constexpr compound literals: {len(programs)} runtime cases, {len(negative)} refusals and rounding independence')
