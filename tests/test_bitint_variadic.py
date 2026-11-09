"""Exercise non-native bit-precise ellipsis and va_arg without a C23 host."""
import os
from pathlib import Path
import subprocess
import tempfile
from runtime_link import runtime_link_flags

root = Path(__file__).resolve().parents[1]
compiler = root / 'build/kcc'
qbe = os.environ.get('QBE', 'qbe')
host = os.environ.get('HOST_CC', 'cc')
types = [(w, u) for w in (2, 7, 9, 15, 17, 31, 33, 63) for u in (0, 1)]
parts = ['#include <stdarg.h>']
calls = []
for w, u in types:
    tag = ('u' if u else 's') + str(w)
    t = ('unsigned ' if u else '') + f'_BitInt({w})'
    edge = (1 << (w-1)) if u else ((1 << 64) - (1 << (w-1)))
    ones = (1 << w)-1 if u else (1 << 64)-1
    parts.append(f'''typedef {t} T{tag};
int f{tag}(int n, ...) {{
 va_list ap, cp; va_start(ap,n);
 T{tag} a=va_arg(ap,T{tag}); double x=va_arg(ap,double);
 va_copy(cp,ap); T{tag} b=va_arg(ap,T{tag});
 T{tag} c=va_arg(ap,T{tag}), d=va_arg(ap,T{tag}), e=va_arg(ap,T{tag});
 T{tag} f=va_arg(ap,T{tag}), g=va_arg(ap,T{tag});
 T{tag} b2=va_arg(cp,T{tag}); va_end(cp); va_end(ap);
 return n!=7 || x!=1.5 || (unsigned long)a!={edge}UL ||
 (unsigned long)b!={ones}UL || b2!=b || c!=0 ||
 (unsigned long)d!={edge}UL || (unsigned long)e!={ones}UL ||
 f!=0 || (unsigned long)g!={edge}UL;
}}''')
    calls.append(f'''{{ T{tag} edge=(T{tag}){1 << (w-1)}UL, all=(T{tag})-1, zero=0;
 if(f{tag}(7,edge,1.5,all,zero,edge,all,zero,edge)) return 1; }}''')
parts.append('int main(void) {\n' + '\n'.join(calls) + '\n return 0; }')
with tempfile.TemporaryDirectory(prefix='bitint-variadic-', dir=root/'build') as d:
    d = Path(d)
    source, ssa, asm, exe = [d / n for n in ('input.c', 'out.ssa', 'out.s', 'out')]
    source.write_text('\n'.join(parts))
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0 and not result.stderr, result.stderr
    ssa.write_text(result.stdout)
    subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(ssa)], check=True)
    subprocess.run([host, str(asm), str(root/'build/libkccrt.a'), *runtime_link_flags(), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)
print('BitInt variadic runtime: 16 signed/unsigned width samples, registers, stack and va_copy passed')
