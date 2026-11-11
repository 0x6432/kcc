"""Runtime and SysV interop checks for bytewise volatile aggregate accesses."""
import os
import subprocess
import tempfile
from pathlib import Path
from runtime_link import runtime_link_flags

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
cc = os.environ.get('HOST_CC', 'cc')
cases = [
'''struct S { int x; unsigned a:3; unsigned long b:40; int y; }; volatile struct S g={3,2,7,10}; struct T { int n; volatile int v; volatile unsigned f:4; }; struct T t={1,2,3}; int main(void){ volatile struct S v={4,1,8,9}; struct S x=g; v=x; v.x++; v.a+=2; v.b++; t.v++; t.f++; x=v; g=x; return x.x+x.a+x.b+x.y+t.v+t.f+g.a==37?42:1; }''',
'''struct S { int x; char y; }; volatile struct S a[2]={{1,2},{3,4}}; int main(void){volatile struct S b[2]={{5,6},{7,8}}; b[1]=a[0]; a[0]=b[0]; return b[1].x+b[1].y+a[0].x+a[0].y==14?42:1;}''',
'''union U { int a; double b; }; volatile union U u={.a=40}; union U f(volatile union U p){p.a+=2; return p;} int main(void){union U t=f(u); u=t; return u.a==42?42:1;}''',
'''struct S { volatile int x; int a[3]; }; struct S f(struct S x){x.x++; return x;} int main(void){struct S a={.x=40,.a={1,2,3}}, b=f(a); return b.x+b.a[0]==42?42:1;}''',
'''struct S{int x;}; int main(void){int n=2; volatile struct S a[n]; a[0].x=40; a[1].x=2; return a[0].x+a[1].x;}''',
'''struct S { int x; }; int main(void){volatile struct S s={40}; volatile struct S *p=&s; p->x+=2; return p->x;}''',
'''struct S{volatile unsigned a:3; volatile unsigned b:11; volatile unsigned long c:40;}; int main(void){struct S s={.a=2,.b=36,.c=3}; s.a++; s.b--; s.c+=1; return s.a+s.b+s.c;}''',
'''struct I { volatile int v; }; struct O { struct I in; }; struct O f(void){struct O x={{42}};return x;} int main(void){return f().in.v;}''',
'''struct S { int x; }; typedef struct S A[2]; int main(void){volatile A a={{40},{2}}; return a[0].x+a[1].x;}''',
'''struct S { unsigned x:3; unsigned y:3; }; int main(void){volatile struct S s={1,2}; s.x++; s.y+=1; return 37+s.x+s.y;}''',
]
fields = ''.join(f'volatile unsigned long f{i}:{i};' for i in range(1,65))
ops = ''.join(f's.f{i}=1; s.f{i}^=1; if(s.f{i}!=0)return {i};' for i in range(1,65))
cases.append(f'struct S {{{fields}}}; int main(void){{struct S s={{0}}; {ops} return 42;}}')
fields = ''.join(f'volatile unsigned int u{i}:{i}; volatile int s{i}:{i};' for i in range(1,33))
ops = ''.join(f'x.u{i}=1; x.u{i}^=1; if(x.u{i}!=0)return 1; x.s{i}=-1; if(x.s{i}!=-1)return 2; x.s{i}=0; if(x.s{i}!=0)return 3;' for i in range(1,33))
cases.append(f'struct S {{{fields}}}; int main(void){{struct S x={{0}}; {ops} return 42;}}')
cases += [
  'struct S{volatile int x;}; int main(void){struct S a={42}; a=a; return a.x;}',
  'struct S{int x; int y;}; volatile struct S g={.y=2,.x=40}; int main(void){return g.x+g.y;}',
  'union U{volatile int x; float f;}; struct S{union U u;}; int main(void){struct S a={.u.x=40}; a.u.x+=2;return a.u.x;}',
  'struct S{volatile int x;}; int main(void){return (struct S){.x=42}.x;}',
  'struct S{int x;}; int main(void){int n=2; volatile struct S a[n]; a[0].x=20; a[1].x=22; return a[0].x+a[1].x;}',
  'struct S{float x; double y;}; int main(void){volatile struct S s={20.5,21.5}; return s.x+s.y==42.0?42:1;}',
  'struct S{char a[4]; volatile int x;}; int main(void){struct S s={.a="abc",.x=40}; s.x+=2; return s.a[1]==98 ? s.x : 1;}',
  'struct I{volatile int a; int b;}; struct S{struct I x[2];}; int main(void){struct S s={.x={{40,1},{2,3}}}; s.x[0].a+=s.x[1].a; return s.x[0].a;}',
  'struct S{volatile unsigned x:3; int y;}; int main(void){struct S a={.x=1,.y=40}; struct S b=a; b.x++; return b.x+b.y;}',
]

def run(command, **kw):
    return subprocess.run(command, capture_output=True, text=True, timeout=60, **kw)

with tempfile.TemporaryDirectory(prefix='kcc-volatile-records-') as directory:
    path = Path(directory)
    def compile_kcc(text, stem):
        source, il, asm, obj = [path / (stem + x) for x in ('.c', '.ssa', '.s', '.o')]
        source.write_text(text)
        result = run([str(compiler), str(source)])
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        il.write_text(result.stdout)
        if qbe:
            result = run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)])
            assert result.returncode == 0, result.stderr
            result = run([cc, '-c', str(asm), '-o', str(obj)])
            assert result.returncode == 0, result.stderr
        return obj, il.read_text()
    for i, text in enumerate(cases):
        obj, il = compile_kcc(text, 'k'+str(i))
        assert '__kcc_volatile_' in il, (i, 'missing volatile operation')
        native = path / ('native'+str(i)); src = path / ('native'+str(i)+'.c'); src.write_text(text)
        result = run([cc, '-std=c11', str(src), '-o', str(native)])
        assert result.returncode == 0, (i, result.stderr)
        assert subprocess.run([str(native)], timeout=5).returncode == 42, i
        if qbe:
            exe = path / ('run'+str(i))
            result = run([cc, str(obj), str(root/'build/libkccrt.a'), *runtime_link_flags(), '-o', str(exe)])
            assert result.returncode == 0, (i,result.stderr)
            assert subprocess.run([str(exe)], timeout=5).returncode == 42, i
    # Previously unsupported declarations remain as exact compile-only cases.
    for i, text in enumerate([
        'struct S { volatile int member; };',
        'struct S { volatile int x:32; };',
        'struct S { int x; }; typedef struct S A[2]; volatile A a;',
        'struct S { volatile unsigned long x:33; }; struct S s;',
        'struct R { volatile unsigned long x:33; }; struct R cell;',
        'struct S { volatile unsigned long x:33; }; int f(void) { return (struct S){.x=2}.x; }',
    ]):
        compile_kcc(text, 'former_refusal'+str(i))
    # C23-only inferred volatile records and empty VLA initialization.
    for i, text in enumerate([
        'struct S{int x;}; int main(void){struct S a={42}; volatile auto b=a; return b.x;}',
        'struct S{volatile int x;}; int main(void){int n=2; struct S a[n]={}; a[1].x=42; return a[1].x;}',
        'struct S{volatile unsigned _BitInt(17) x:17; volatile _BitInt(9) y:9;}; int main(void){struct S s={40,-1}; s.x+=3; return s.x+s.y;}',
    ]):
        obj, il = compile_kcc(text, 'c23_'+str(i))
        assert '__kcc_volatile_' in il
        if qbe:
            exe=path/('c23run'+str(i))
            result=run([cc, str(obj), str(root/'build/libkccrt.a'), *runtime_link_flags(), '-o', str(exe)])
            assert result.returncode==0, result.stderr
            assert subprocess.run([str(exe)], timeout=5).returncode==42
    if qbe:
        # Interpose helper symbols to verify the emitted accesses, not just values.
        probe = r"""
struct S { int x; unsigned b:3; }; volatile struct S g={40,2};
struct V { volatile int x; }; struct V vg={1};
extern int copy_read, copy_write, reads4, writes4, reads1, writes1;
int bound(int a[(vg,2)]) { return a[0]; }
int main(void){
  int a[2]={0}; bound(a); if(copy_read!=1) return 6; copy_read=0;
  int z=sizeof(g); if(copy_read||copy_write||reads4||writes4||reads1||writes1) return 1;
  (void)g; if(copy_read!=1||copy_write) return 2;
  g.x+=2; if(reads4!=1||writes4!=1) return 3;
  g.b++; if(reads1<2||writes1!=1) return 4;
  struct S tmp=g; g=tmp;
  if(copy_read!=2||copy_write!=1 || g.x!=42 || g.b!=3 || z<4) return 5;
  return 42;
}
"""
        helpers = r"""
int copy_read,copy_write,reads4,writes4,reads1,writes1;
unsigned int __kcc_volatile_load_1(const volatile void *p){reads1++;return *(const volatile unsigned char*)p;}
unsigned int __kcc_volatile_load_4(const volatile void *p){reads4++;return *(const volatile unsigned int*)p;}
void __kcc_volatile_store_1(volatile void *p,unsigned int v){writes1++;*(volatile unsigned char*)p=v;}
void __kcc_volatile_store_4(volatile void *p,unsigned int v){writes4++;*(volatile unsigned int*)p=v;}
void __kcc_volatile_copy(void *d,const void *s,unsigned long n,unsigned int flags){
  if(flags&1) copy_read++; if(flags&2) copy_write++;
  for(unsigned long i=0;i<n;i++){
    unsigned char x=flags&1?((const volatile unsigned char*)s)[i]:((const unsigned char*)s)[i];
    if(flags&2)((volatile unsigned char*)d)[i]=x; else ((unsigned char*)d)[i]=x;
  }
}
"""
        obj, _ = compile_kcc(probe, 'access_probe')
        hs = path/'helpers.c'; hs.write_text(helpers); exe = path/'probe'
        result = run([cc, '-std=c11', '-fno-strict-aliasing', str(obj), str(hs), '-o', str(exe)])
        assert result.returncode == 0, result.stderr
        result = subprocess.run([str(exe)], timeout=5)
        assert result.returncode == 42, ('access probe', result.returncode)
    interop = [
        ('struct S { volatile int x; unsigned long b:40; int z; }; ',
         'struct S x={30,7,4}; struct S y=f(x); return y.x+y.b+y.z==43?42:1;',
         'struct S f(struct S x){ x.x++; x.b++; return x; }'),
        ('struct S { volatile double x; double y; }; ',
         'struct S x={20.0,21.0}; struct S y=f(x); return y.x+y.y==42.0?42:1;',
         'struct S f(struct S x){ x.x+=1.0; return x; }'),
        ('struct S { volatile long x; long y; long z; }; ',
         'struct S x={10,11,20}; struct S y=f(x); return y.x+y.y+y.z==42?42:1;',
         'struct S f(struct S x){ x.x++; return x; }'),
        ('union U { volatile long x; double y; }; ',
         'union U x={.x=41}; union U y=f(x); return y.x==42?42:1;',
         'union U f(union U x){ x.x++; return x; }'),
    ]
    if qbe:
        for number, (common, body, callee) in enumerate(interop):
            typename = 'union U' if number == 3 else 'struct S'
            caller = common + typename + ' f(' + typename + '); int main(void){' + body + '}'
            callee = common + callee
            for kcc_caller in (True, False):
                ko, _ = compile_kcc(caller if kcc_caller else callee, f'interop_k{number}_{kcc_caller}')
                hs = path/'host.c'; ho = path/'host.o'; hs.write_text(callee if kcc_caller else caller)
                result = run([cc, '-std=c11', '-c', str(hs), '-o', str(ho)])
                assert result.returncode == 0, result.stderr
                exe = path/'interop'
                result = run([cc, str(ko), str(ho), str(root/'build/libkccrt.a'), *runtime_link_flags(), '-o', str(exe)])
                assert result.returncode == 0, result.stderr
                assert subprocess.run([str(exe)], timeout=5).returncode == 42, (number,kcc_caller)
print(f'Volatile aggregates: {len(cases)} native comparisons'+(', QBE/runtime and both-direction ABI passed' if qbe else '; QBE not configured'))
