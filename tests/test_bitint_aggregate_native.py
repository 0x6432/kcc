"""Clang/KCC x86-64 by-value BitInt aggregate interoperability matrix."""
from pathlib import Path
from test_bitint_arbitrary import ROOT, CLANG, compile_clang, compile_kcc, run
from runtime_link import runtime_link_flags
import tempfile, subprocess

types = [(w,u) for w in range(1,65) for u in (0,1) if u or w > 1]
with tempfile.TemporaryDirectory(prefix='bitint-aggr-', dir=ROOT/'build') as td:
 d=Path(td)
 for start in range(0,len(types),8):
  group=types[start:start+8]; decl=['#include <stdarg.h>', 'int printf(const char *,...);']; body=[]; test=[]
  for w,u in group:
   n=f'{"u" if u else "s"}{w}'; t=f'T{n}'; raw=1<<(w-1); edge=raw if u else (1<<64)-raw; ones=(1<<w)-1 if u else (1<<64)-1
   decl.append(f'''typedef {'unsigned ' if u else ''}_BitInt({w}) {t};
struct A{n} {{ {t} x; char z; }}; struct B{n} {{ double f; {t} x; }}; struct C{n} {{ {t} x[4]; double d; }};
union U{n} {{ {t} x; unsigned long raw; }}; struct D{n} {{ _Alignas(16) {t} x; unsigned long tail; }}; union U{n} un{n}(union U{n}); struct D{n} aligned{n}(struct D{n}); extern struct A{n} g{n}; struct A{n} mutate{n}(void);
struct A{n} a{n}(struct A{n}); struct B{n} b{n}(long,long,long,long,long,long,struct B{n}); struct C{n} c{n}(struct C{n}); int v{n}(int,...);''')
   body.append(f'''struct A{n} g{n}={{({t}){raw}UL,17}};
union U{n} un{n}(union U{n} u) {{ if((unsigned long)u.x!={edge}UL) u.x=0; else u.x=({t})-1; return u; }}
struct D{n} aligned{n}(struct D{n} x) {{ if((unsigned long)x.x!={edge}UL || x.tail!=23) x.x=0; else x.x=({t})-1; return x; }}
struct A{n} mutate{n}(void) {{ g{n}.x=({t})-1; g{n}.x++; g{n}.x-=({t})1; return g{n}; }}
struct A{n} a{n}(struct A{n} a) {{ if((unsigned long)a.x!={edge}UL || a.z!=17) a.z=0; else {{a.x=({t})-1; a.z=18;}} return a; }}
struct B{n} b{n}(long a,long b,long c,long d,long e,long f,struct B{n} z) {{ if((unsigned long)z.x!={edge}UL || z.f!=1.5 || a+b+c+d+e+f!=21) z.f=0; else {{z.x=({t})-1; z.f=2.5;}} return z; }}
struct C{n} c{n}(struct C{n} z) {{ if((unsigned long)z.x[0]!={edge}UL || (unsigned long)z.x[2]!={ones}UL || z.d!=3.5) z.d=0; else {{z.x[3]=({t})-1; z.d=4.5;}} return z; }}
int v{n}(int tag,...) {{ va_list ap,cp; va_start(ap,tag); va_copy(cp,ap); struct A{n} copy=va_arg(cp,struct A{n}); va_end(cp); struct A{n} a=va_arg(ap,struct A{n}); struct B{n} b=va_arg(ap,struct B{n}); struct C{n} c=va_arg(ap,struct C{n}); va_end(ap); return tag!=7 || (unsigned long)copy.x!={edge}UL || copy.z!=17 || (unsigned long)a.x!={edge}UL || a.z!=17 || b.f!=1.5 || (unsigned long)b.x!={edge}UL || (unsigned long)c.x[2]!={ones}UL || c.d!=3.5; }}''')
   test.append(f'''int check{n}(void) {{ {t} edge=({t}){raw}UL, ones=({t})-1; struct A{n} a={{edge,17}}, r=a{n}(a); struct B{n} b={{1.5,edge}}, s=b{n}(1,2,3,4,5,6,b); struct C{n} c={{{{edge,0,ones,0}},3.5}}, v=c{n}(c); struct A{n} global=g{n}, changed=mutate{n}(); union U{n} u={{.x=edge}}, ur=un{n}(u); struct D{n} dd={{edge,23}}, dr=aligned{n}(dd); if((unsigned long)ur.x!={ones}UL || (unsigned long)dr.x!={ones}UL || (unsigned long)global.x!={edge}UL || global.z!=17 || (unsigned long)changed.x!={ones}UL || (unsigned long)u.x!={edge}UL || (unsigned long)r.x!={ones}UL || r.z!=18 || s.f!=2.5 || (unsigned long)s.x!={ones}UL || v.d!=4.5 || (unsigned long)v.x[3]!={ones}UL || v{n}(7,a,b,c)) {{printf("failed {n}: r=%lu z=%d sf=%a sx=%lu vd=%a vx=%lu va=%d\\n", (unsigned long)r.x, r.z, s.f,(unsigned long)s.x,v.d,(unsigned long)v.x[3],v{n}(7,a,b,c)); return 1;}} return 0; }}''')
  shared='\n'.join(decl)+'\n'; impl=shared+'\n'.join(body); caller=shared+'\n'.join(test)+'\nint main(void){\n'+'\n'.join(f'if(check{"u" if u else "s"}{w}()) return {i+1};' for i,(w,u) in enumerate(group))+'return 0;}'
  for side in (0,1):
   ko=compile_kcc(d,impl if side==0 else caller,'k'+str(side));co=compile_clang(d,caller if side==0 else impl,'c'+str(side));exe=d/'test'
   run([CLANG,ko,co,ROOT/'build/libkccrt.a',*runtime_link_flags(),'-o',exe]); p=subprocess.run([str(exe)],timeout=10)
   if p.returncode:raise AssertionError(('group',start,'side',side,'type',group[p.returncode-1]))
print('Clang/KCC aggregate ABI passed all 127 BitInt types, unions, aligned and memory records, stack pressure and va_copy')
