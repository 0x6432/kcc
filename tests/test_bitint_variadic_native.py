"""Clang 15 x86-64 SysV scalar BitInt ellipsis/va_arg differential tests.

Each declared BitInt type is passed and read without integer promotions.
Both cross-object directions exercise GP registers, stack overflow slots, an
independent FP register bank, va_copy, indirect calls and named-argument stack
pressure. Values cover zero, all-one bits and the declared sign boundary.
"""
from pathlib import Path
import subprocess
import shutil
import tempfile
from test_bitint_arbitrary import ROOT, CLANG, compile_clang, compile_kcc, run
from runtime_link import runtime_link_flags


def main():
    types = [(w, u) for w in range(1, 65) for u in (0, 1) if u or w > 1]
    with tempfile.TemporaryDirectory(prefix='bitint-variadic-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        for start in range(0, len(types), 8):
            group = types[start:start+8]
            decl = ['#include <stdarg.h>', 'int printf(const char *, ...);']
            body = []
            tests = []
            for w, u in group:
                tag = f'{"u" if u else "s"}{w}'
                t = f'T{tag}'
                spelling = ('unsigned ' if u else '') + f'_BitInt({w})'
                raw = 1 << (w-1)
                edge = raw if u else ((raw | (((1 << 64)-1) ^ ((1 << w)-1))))
                ones = ((1 << w)-1) if u else ((1 << 64)-1)
                decl.append(f'typedef {spelling} {t}; int r{tag}(int,...); int s{tag}(long,long,long,long,long,long,int,...);')
                body.append(f'''int r{tag}(int tag, ...) {{
 va_list ap, cp; va_start(ap,tag);
 if (sizeof(va_arg(ap,{t})) != sizeof({t})) return 1;
 {t} a=va_arg(ap,{t}); va_copy(cp,ap);
 {t} b=va_arg(ap,{t}); double f=va_arg(ap,double); {t} c=va_arg(ap,{t});
 int n=va_arg(ap,int); {t} d=va_arg(ap,{t}); {t} e=va_arg(ap,{t});
 {t} g=va_arg(ap,{t}); {t} h=va_arg(ap,{t}); double tail=va_arg(ap,double);
 {t} bc=va_arg(cp,{t}); double fc=va_arg(cp,double); {t} cc=va_arg(cp,{t});
 int nc=va_arg(cp,int); {t} dc=va_arg(cp,{t}); {t} ec=va_arg(cp,{t});
 {t} gc=va_arg(cp,{t}); {t} hc=va_arg(cp,{t}); double tc=va_arg(cp,double);
 va_end(ap); va_end(cp);
 if(tag!=7) return 11;
 if((unsigned long)a!={edge}UL) {{ printf("a actual %lu expected {edge}\\n",(unsigned long)a); return 12; }}
 if((unsigned long)b!={ones}UL) {{ printf("b actual %lu expected {ones}\\n",(unsigned long)b); return 13; }}
 if(c!=({t})0) return 14;
 if(n!=42 || f!=1.5 || tail!=2.5 || (unsigned long)d!={edge}UL || (unsigned long)e!={ones}UL) {{ printf("n=%d f=%a tail=%a d=%lu e=%lu\\n",n,f,tail,(unsigned long)d,(unsigned long)e); return 3; }}
 if(g!=({t})0 || (unsigned long)h!={edge}UL) return 4;
 if(bc!=b || fc!=f || cc!=c || nc!=n || dc!=d || ec!=e || gc!=g || hc!=h || tc!=tail) return 5;
 return 0; }}
int s{tag}(long a,long b,long c,long d,long e,long f,int tag,...) {{
 va_list ap; va_start(ap,tag); {t} x=va_arg(ap,{t}); double z=va_arg(ap,double);
 {t} y=va_arg(ap,{t}); int tail=va_arg(ap,int); {t} v=va_arg(ap,{t}); va_end(ap);
 if(a!=1 || b!=2 || c!=3 || d!=4 || e!=5 || f!=6 || tag!=7) return 1;
 if((unsigned long)x!={edge}UL || (unsigned long)y!={ones}UL || v!=({t})0 || z!=3.5 || tail!=99) return 2;
 return 0; }}''')
                tests.append(f'''int check{tag}(void) {{
 {t} edge=({t}){raw}UL, all=({t})-1, zero=({t})0;
 int (*fp)(int,...)=r{tag};
 int rc=fp(7,edge,all,1.5,zero,42,edge,all,zero,edge,2.5);
 if(rc) {{ printf("r{tag}: %d\\n",rc); return 1; }}
 rc=s{tag}(1,2,3,4,5,6,7,edge,3.5,all,99,zero);
 if(rc) {{ printf("s{tag}: %d\\n",rc); return 2; }}
 return 0; }}''')
            shared = '\n'.join(decl)+'\n'
            implementation = shared+'\n'.join(body)+'\n'
            caller = shared+'\n'.join(tests)+'\nint main(void) {\n' + '\n'.join(
                f'if(check{"u" if u else "s"}{w}()) return {i+1};' for i, (w, u) in enumerate(group)) + '\nreturn 0; }\n'
            for side in (0, 1):
                ko = compile_kcc(d, implementation if side == 0 else caller, f'k{side}')
                co = compile_clang(d, caller if side == 0 else implementation, f'c{side}')
                exe = d/f'exe{side}'
                run([CLANG, ko, co, ROOT/'build/libkccrt.a', *runtime_link_flags(), '-o', exe])
                p = subprocess.run([str(exe)], timeout=10)
                if p.returncode:
                    for name in (f'k{side}.ssa', f'k{side}.s', f'c{side}.c', f'c{side}.o'):
                        shutil.copy(d/name, ROOT/'build'/('debug-'+name))
                    raise AssertionError(('group', start, 'side', side, 'type', group[p.returncode-1]))
    print('Clang/KCC variadic BitInt cross-calls passed for all 127 types, registers, stack, FP mixing and va_copy')

if __name__ == '__main__': main()
