"""C23 complete tagged record compatibility and same-scope redefinitions."""
import os, subprocess, tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root/'build'/'kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
programs = [
'''struct S{int x;}; struct S{int x;}; int main(void){struct S x={42}; return x.x;}''',
'''union U{int x; double y;}; union U{int x; double y;}; int main(void){union U u={.x=42}; return u.x;}''',
'''struct N{int x; struct N *next;}; struct N{int x; struct N *next;}; int main(void){struct N n={42,nullptr}; return n.next==nullptr?n.x:1;}''',
'''struct S{unsigned x:6; unsigned :0; int y[2];}; struct S{unsigned x:3+3; unsigned :0; int y[2];}; int main(void){struct S s={42,{1,2}}; return s.x;}''',
'''struct S{_Alignas(8) int x;}; struct S{_Alignas(8) int x;}; int main(void){struct S s={42}; return s.x;}''',
'''struct S; struct S{int x;}; struct S{int x;}; struct S s={42}; int main(void){return s.x;}''',
'''struct S{int x;}; int main(void){struct S{int x;}; struct S{int x;}; struct S a={42}; return a.x;}''',
'''struct S{int x;}; struct S f(struct S x){return x;} int main(void){struct S{int x;}; struct S a={42}; return f(a).x;}''',
'''struct S{int x;}; struct S *f(struct S *x){return x;} int main(void){struct S{int x;}; struct S a={42}; return f(&a)->x;}''',
'''struct N{int x; struct N *next;}; struct N f(struct N n){return n;} int main(void){struct N{int x; struct N *next;}; struct N n={42,nullptr}; return f(n).x;}''',
'''union U{int x; double y;}; union U f(union U x){return x;} int main(void){union U{int x; double y;}; union U a={.x=42}; return f(a).x;}''',
'''struct A{int x;}; struct B{struct A a;}; struct B f(struct B b){return b;} int main(void){struct A{int x;}; struct B{struct A a;}; struct B b={{42}}; return f(b).a.x;}''',
'''struct S{union {int a; double b;};}; struct S f(struct S s){return s;} int main(void){struct S{union {int a; double b;};}; struct S s={.a=42}; return f(s).a;}''',
'''struct S{int x;}; int main(void){struct S a={42}; {struct S{int x;}; struct S b={0}; b=a; return b.x;}}''',
'''struct S{int x;}; int main(void){struct S a={42}; {struct S{int x;}; struct S b=a; return b.x;}}''',
'''struct S{int x;}; int main(void){struct S a={42}; {struct S{int x;}; struct S b={1}; return (1?a:b).x;}}''',
'''struct S{int x;}; int main(void){struct S a={42}; {struct S{int x;}; return _Generic(a, struct S: a.x, default: 1);}}'''
, "struct S{int x;}; int main(void){struct S a={42}; {struct S{int x;}; struct S *p=&a; return p->x;}}"
, "struct S{int x;}; int f(struct S x){return x.x;} int main(void){struct S{int x;}; int (*p)(struct S)=f; struct S x={42}; return p(x);}"
, "struct S{int x;}; struct T{struct S *p;}; int main(void){struct S s={42}; {struct S{int x;}; struct T{struct S *p;}; struct T t={&s}; return t.p->x;}}"
, "struct S{unsigned x:6; unsigned :0; int z;}; struct S f(struct S x){return x;} int main(void){struct S{unsigned x:6; unsigned :0; int z;}; struct S x={42,1}; return f(x).x;}"
, "struct S{int n; int a[];}; struct S{int n; int a[];}; int main(void){struct S s={42}; return s.n;}"
, "struct S{int x[3];}; struct S{int x[1+2];}; int main(void){struct S s={{42}}; return s.x[0];}"
, "struct S{int x;}; typedef struct S T; struct S{int x;}; typedef struct S T; int main(void){T a={42}; return a.x;}"
, "struct S{int x;}; int main(void){struct S a={42}; {struct S{int x;}; struct S *p=&a; struct S *q=0?p:&a; return q->x;}}"

]
negative = [
'''struct S{int x;}; struct S{int y;};''',
'''struct S{int x;}; struct S{long x;};''',
'''struct S{int x; int y;}; struct S{int y; int x;};''',
'''union U{int x; double y;}; union U{double y; int x;};''',
'''struct S{unsigned x:6;}; struct S{unsigned x:5;};''',
'''struct S{_Alignas(8) int x;}; struct S{int x;};''',
'''struct S{int x;}; struct S{const int x;};''',
'''struct S{struct S{int x;} a;};''',
'''struct S{int x;}; int main(void){struct S a={1}; {struct S{long x;}; struct S b=a; return 0;}}''',
'''struct S{int x;}; int main(void){struct S a={1}; {struct S{int y;}; struct S b=a; return 0;}}''',
'''struct S{int x;}; int main(void){struct S a={1}; {struct S{const int x;}; struct S b=a; return 0;}}''',
'''struct S{int x;}; int main(void){struct S a={1}; {struct S{int x; int y;}; struct S b=a; return 0;}}''',
'''struct S{int x;}; int main(void){struct S a={1}; {struct T{int x;}; struct T b=a; return 0;}}''',
'''struct S{int x;}; int main(void){struct S a={1}; {struct {int x;} b=a; return 0;}}''',
'''struct A{int x;}; struct B{struct A a;}; int main(void){struct B b={{1}}; {struct A{long x;}; struct B{struct A a;}; struct B c=b; return 0;}}''',
'''struct N{int x; struct N *next;}; int main(void){struct N a={1,nullptr}; {struct N{long x; struct N *next;}; struct N b=a; return 0;}}''',
'''struct S{struct {int x;} a;}; struct S{struct {int x;} a;};'''
, "struct S{int x;}; struct T{struct S s;}; int main(void){struct T{struct S s;}; struct S{int x;}; struct T{struct S s;}; return 0;}"
, "struct S{int x;}; int main(void){struct S a={1}; {struct S{struct {int x;} a;}; struct S b=a; return 0;}}"
, "struct S{struct {int x;} a;}; int main(void){struct S a={{1}}; {struct S{struct {int x;} a;}; struct S b=a; return 0;}}"
, "struct S{int x;}; struct S{struct S {int x;} a;};"
, "struct S{int x;}; struct S{int x[1];};"

, "struct S{int n; int a[];}; int main(void){struct S x={1}; {struct S{int n; int a[1];}; struct S y=x; return 0;}}"
, "struct S{int n; int a[1];}; int main(void){struct S x={1,{2}}; {struct S{int n; int a[];}; struct S *p=&x; return 0;}}"

]
# Deep chains exercise visited-pair bounds and mismatch propagation without
# relying on the host compiler's C23 redefinition support.
def graph(depth, mismatch=False):
 def declarations(inner):
  forwards=''.join(f'struct R{i};' for i in range(depth))
  definitions=''.join(f'struct R{i}{{' + ('long x;' if inner and mismatch and i==depth-1 else 'int x;') +
      (f'struct R{i+1} *next;' if i+1<depth else 'struct R0 *next;') + '};' for i in range(depth))
  return forwards+definitions
 return (declarations(False)+'int f(struct R0 *x){return x->x;}' +
  'int main(void){'+declarations(True)+'struct R0 x={42,nullptr};return f(&x);}')
programs.append(graph(64))
negative.append(graph(64, True))
with tempfile.TemporaryDirectory(prefix='kcc record compatibility ') as tmp:
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
 with tempfile.TemporaryDirectory(prefix='kcc tagged records ABI ') as tmp:
  d=Path(tmp); source=d/'kcc.c'; il=d/'kcc.ssa'; asm=d/'kcc.s'; native=d/'native.c'; exe=d/'p'
  source.write_text("""struct S { long a; double b; };
extern struct S native_transform(struct S);
struct S kcc_transform(struct S x) { x.a+=2; x.b+=1.0; return x; }
long kcc_call_native(void) {
 struct S { long a; double b; }; struct S x={39,1.5};
 struct S y=native_transform(x); return y.a==42 && y.b==2.5 ? 42 : 1;
}
""")
  r=subprocess.run([str(kcc),str(source)],capture_output=True,text=True,timeout=15)
  assert r.returncode==0 and not r.stderr, r.stderr
  il.write_text(r.stdout); subprocess.run([qbe,'-t','amd64_sysv','-o',str(asm),str(il)],check=True,timeout=15)
  native.write_text("""struct S { long a; double b; };
struct S native_transform(struct S x) { x.a+=3; x.b+=1.0; return x; }
extern struct S kcc_transform(struct S); extern long kcc_call_native(void);
int main(void) { struct S x={40,1.5}, y=kcc_transform(x);
 return y.a==42 && y.b==2.5 && kcc_call_native()==42 ? 42 : 1; }
""")
  subprocess.run([host,str(asm),str(native),'-o',str(exe)],check=True,timeout=15)
  assert subprocess.run([str(exe)],timeout=5).returncode==42
print(f'C23 tagged records: {len(programs)} programs, {len(negative)} constraints, QBE/runtime and bidirectional native ABI when available')
