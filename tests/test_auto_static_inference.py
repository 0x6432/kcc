"""C23 inferred auto objects with static, file, and thread storage."""
import os, subprocess, tempfile
from pathlib import Path
from runtime_link import runtime_link_flags
root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC',root/'build'/'kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC','cc')
programs = [
'auto x=42; int main(void){int *p=&x; return *p;}',
'extern long x; auto x=42L; int main(void){return x;}',
'static int x; static auto x=42; int main(void){return x;}',
'extern _Thread_local int x; thread_local auto x=42; int main(void){return x;}',
' typedef long T; int main(void){static thread_local auto T=42;return T;}',
' thread_local auto x=42; extern thread_local int x; int main(void){return x;}',
'static auto cell=42; int main(void){return cell;}',
'auto static cell=42; int main(void){return cell;}',
' typedef int T; int main(void){static auto T=42; return T;}',
' thread_local auto x=42; int main(void){return x;}',
' int main(void){static thread_local auto x=42; return x;}',
' volatile auto x=42; int main(void){return x;}',
' _Atomic auto x=42; int main(void){return x;}',
'static auto x=42; int main(void){int *p=&x; return *p;}',
'auto static x=42; int main(void){return x;}',
'extern auto x=42; int main(void){return x;}',
'auto extern x=42; int main(void){return x;}',
'auto x=42L; int main(void){long *p=&x; return sizeof(x)==8?*p:1;}',
'const auto x=42; int main(void){const int *p=&x; return *p;}',
'auto x=1.5; int main(void){double *p=&x; return *p==1.5?42:1;}',
'int n=42; auto p=&n; int main(void){return *p;}',
'auto s="*"; int main(void){return s[0];}',
'int f(void){return 42;} auto p=f; int main(void){return p();}',
'enum E{V=42}; auto x=(enum E)V; int main(void){enum E *p=&x; return *p;}',
'auto x=(unsigned _BitInt(12))42; int main(void){unsigned _BitInt(12) *p=&x; return *p;}',
'constexpr int a=42; auto x=a; int main(void){x++; return x-1;}',
'struct S{int n;}; constexpr struct S s={42}; auto x=s; int main(void){return x.n;}',
'int f(void){static auto x=40; return ++x;} int main(void){return f()+f()==83?42:1;}',
'int f(void){auto static x=40; return ++x;} int main(void){return f()+f()==83?42:1;}',
'int main(void){static auto x=42L; long *p=&x; return *p;}',
'int main(void){static const auto x=42; const int *p=&x; return *p;}',
'int n=42; int main(void){static auto p=&n; return *p;}',
'int f(void){return 42;} int main(void){static auto p=f; return p();}',
'int main(void){static auto s="*"; return s[0];}',
'constexpr int n=42; int main(void){static auto x=n; return x;}',
'struct S{int n;}; constexpr struct S s={42}; int main(void){static auto x=s; return x.n;}',
'auto x=nullptr; int main(void){return x==nullptr?42:1;}',
'int main(void){static auto x=nullptr; return x==nullptr?42:1;}',
'_Alignas(16) auto x=42; int main(void){return x;}',
'int main(void){_Alignas(16) static auto x=42; return x;}',
'constexpr auto c=42; static auto x=c; int main(void){return x;}',
'auto x=(unsigned char)42; int main(void){unsigned char *p=&x; return *p;}',
]
negative = [
'auto x;', 'static auto x;', 'int main(void){thread_local auto x=42;return x;}', 'auto x={42};', 'auto x=(void)42;',
'auto x=1,y=2;', 'auto *x=0;', 'auto x=x;', 'int y; auto x=y;',
'int f(void){return 42;} auto x=f();',
'int main(void){static auto x; return 0;}',
'int main(void){static auto x={1}; return 0;}',
'int f(void){return 42;} int main(void){static auto x=f(); return x;}',
'int n; int main(void){static auto x=n; return x;}',
'int main(void){static auto x=x; return x;}',
'int main(void){extern auto x=42; return x;}',
'int main(void){static auto x=(void)0; return 0;}',
'int main(void){static auto x=1,y=2; return x+y;}',
'const auto x=42; int main(void){x=1; return 0;}',
'restrict auto x=42;', '_Atomic auto x=(struct S{int n;}){42};',
]
with tempfile.TemporaryDirectory(prefix='kcc static auto ') as tmp:
 d=Path(tmp); source=d/'p.c'; il=d/'p.ssa'; asm=d/'p.s'; exe=d/'p'
 def compile_text(text):
  source.write_text(text+'\n')
  return subprocess.run([str(kcc),str(source)],capture_output=True,text=True,timeout=15)
 for text in programs:
  r=compile_text(text)
  assert r.returncode==0 and not r.stderr,(text,r.stderr)
  if qbe:
   il.write_text(r.stdout); subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
   subprocess.run([host,str(asm),str(root/'build'/'libkccrt.a'),*runtime_link_flags(),'-latomic','-o',str(exe)],check=True,timeout=15)
   rc=subprocess.run([str(exe)],timeout=5).returncode
   assert rc==42,(text,rc)
 for text in negative:
  r=compile_text(text)
  assert r.returncode==1 and not r.stdout,(text,r.returncode,r.stderr)
 if qbe:
  r=compile_text('auto global=42L; static auto internal=2; long read_global(void){return global+internal;}')
  assert r.returncode==0 and not r.stderr,r.stderr
  il.write_text(r.stdout);subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
  native=d/'native.c';native.write_text('extern long global; long read_global(void); int main(void){global=40;return read_global();}')
  subprocess.run([host,str(asm),str(native),'-o',str(exe)],check=True,timeout=15)
  assert subprocess.run([str(exe)],timeout=5).returncode==42
 if qbe:
  # Compile KCC TLS definitions and exercise them from a native pthread client.
  r=compile_text('thread_local auto global=42; int *global_address(void){return &global;} int *local_address(void){static thread_local auto local=17;return &local;}')
  assert r.returncode==0 and not r.stderr,r.stderr
  il.write_text(r.stdout); subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
  native=d/'tls_native.c'; native.write_text('''
#include <pthread.h>
extern _Thread_local int global;
int *global_address(void); int *local_address(void);
static void *worker(void *unused) {
  (void)unused; int *g=global_address(), *l=local_address();
  if (g!=&global || *g!=42 || *l!=17) return (void *)1;
  *g=5; *l=7; return 0;
}
int main(void) {
  pthread_t t; void *result;
  if (&global!=global_address() || global!=42 || *local_address()!=17) return 1;
  global=41; *local_address()=19;
  if (pthread_create(&t,0,worker,0) || pthread_join(t,&result) || result) return 2;
  return global==41 && *local_address()==19 ? 42 : 3;
}
''')
  subprocess.run([host,str(asm),str(native),'-pthread','-o',str(exe)],check=True,timeout=15)
  assert subprocess.run([str(exe)],timeout=5).returncode==42
print(f'C23 static/file/TLS auto: {len(programs)} accepted, {len(negative)} refusals; ' + ('QBE runtime and native linkage/pthread passed' if qbe else 'QBE runtime and native linkage not run'))
