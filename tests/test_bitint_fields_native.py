"""Clang/KCC bit-precise field layout and cross-object behavior."""
from pathlib import Path
import subprocess
import tempfile
from test_bitint_arbitrary import ROOT, CLANG, compile_clang, compile_kcc, run
from runtime_link import runtime_link_flags

types = [(w,u) for w in range(1,65) for u in (0,1) if u or w>1]
with tempfile.TemporaryDirectory(prefix='bitint-fields-',dir=ROOT/'build') as temp:
 d=Path(temp)
 for start in range(0,len(types),8):
  group=types[start:start+8];decl=[];owner=[];caller=[]
  for w,u in group:
   n=f'{"u" if u else "s"}{w}'; t=f'T{n}'
   decl.append(f'typedef {"unsigned " if u else ""}_BitInt({w}) {t};')
   for k in sorted({1,(w+1)//2,w}):
    f=f'{n}_{k}'; original=(1<<k)-1 if u else (1<<64)-1
    initial=f'({t}){(1<<k)-1}UL' if u else f'({t})-1'
    decl.append(f'struct S{f} {{ unsigned p:3; {t} a:{k}; unsigned q:2; char c; }}; extern struct S{f} g{f}; struct S{f} transform{f}(struct S{f}); int size{f}(void);')
    owner.append(f'''struct S{f} g{f}={{5,{initial},2,77}};
int size{f}(void) {{ return sizeof(struct S{f}); }}
struct S{f} transform{f}(struct S{f} x) {{ if((unsigned long)x.a!={original}UL || x.p!=5 || x.q!=2 || x.c!=77) x.c=0; else {{ x.a++; x.c=78; }} return x; }}''')
    caller.append(f'''{{ struct S{f} z=transform{f}(g{f});
if(sizeof(struct S{f})!=size{f}() || (unsigned long)g{f}.a!={original}UL || z.a!=0 || z.p!=5 || z.q!=2 || z.c!=78 || !_Generic((0,g{f}.a), {t}:1,default:0)) return 1; }}''')
  shared='\n'.join(decl)+'\n'; implementation=shared+'\n'.join(owner); main=shared+'int main(void) {\n'+'\n'.join(caller)+'\nreturn 0;}'
  for side in (0,1):
   ko=compile_kcc(d,implementation if side==0 else main,'k'+str(side)); co=compile_clang(d,main if side==0 else implementation,'c'+str(side)); exe=d/'run'
   run([CLANG,ko,co,ROOT/'build/libkccrt.a',*runtime_link_flags(),'-o',exe]);p=subprocess.run([exe])
   if p.returncode:raise AssertionError(('group',start,'side',side,'types',group))
print('BitInt bit-field cross-object matrix passed for 127 types and three field widths')
