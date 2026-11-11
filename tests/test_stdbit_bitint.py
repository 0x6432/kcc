"""C23 stdbit generic operations across all supported unsigned _BitInt widths."""
import os
import subprocess
import tempfile
from pathlib import Path
from runtime_link import runtime_link_flags

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build/kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')
ops = ('leading_zeros leading_ones trailing_zeros trailing_ones first_leading_zero '
       'first_leading_one first_trailing_zero first_trailing_one count_zeros count_ones '
       'has_single_bit bit_width bit_floor bit_ceil').split()

with tempfile.TemporaryDirectory(prefix='kcc stdbit bitint ') as tmp:
    d = Path(tmp)
    objects = []
    for base in range(1, 65, 4):
        code = ['#include <stdbit.h>']
        for w in range(base, base+4):
            t = f'unsigned _BitInt({w})'
            code.append(f'void bits{w}(unsigned long long raw, unsigned long long *out) {{ {t} x=({t})raw;')
            for i, op in enumerate(ops):
                code.append(f'out[{i}]=stdc_{op}(x++); out[{20+i}]=x==({t})(raw+1ULL); x=({t})raw;')
            code.append(f'out[14]=stdc_count_ones(x++); out[15]=x;')
            code.append(f'out[16]=_Generic(stdc_bit_floor(x), {t}:1, default:0);')
            code.append(f'out[17]=_Generic(stdc_bit_ceil(x), {t}:1, default:0);')
            code.append('out[18]=_Generic(stdc_count_ones(x), unsigned int:1, default:0);')
            code.append('out[19]=_Generic(stdc_has_single_bit(x), bool:1, default:0);')
            code.append('}')
        src, il, asm, obj = (d/f'unit{base}.{ext}' for ext in ('c', 'ssa', 's', 'o'))
        src.write_text('\n'.join(code)+'\n')
        r = subprocess.run([str(kcc), str(src)], capture_output=True, text=True, timeout=90)
        assert r.returncode == 0 and not r.stderr, (base,r.stderr)
        if qbe:
            il.write_text(r.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True, timeout=30)
            subprocess.run([host, '-c', str(asm), '-o', str(obj)], check=True, timeout=30)
            objects.append(str(obj))
    for bad in ('int', 'signed _BitInt(8)', 'bool', 'double', 'void *'):
        src.write_text(f'#include <stdbit.h>\nunsigned int f({bad} x){{return stdc_count_ones(x);}}\n')
        r=subprocess.run([str(kcc),str(src)],capture_output=True,text=True,timeout=30)
        assert r.returncode != 0 and r.stderr and not r.stdout, (bad,r.stderr)
    if qbe:
        harness=d/'harness.c'; exe=d/'test'
        declarations='\n'.join(f'extern void bits{w}(unsigned long long, unsigned long long *);' for w in range(1,65))
        funcs=','.join(f'bits{w}' for w in range(1,65))
        harness.write_text(r'''#include <stdint.h>
#include <stdio.h>
''' + declarations + r'''
int main(void) {
 void (*f[])(unsigned long long,unsigned long long*)={''' + funcs + r'''};
 uint64_t seed=0xd6e8feb86659fd93ULL;
 for (unsigned w=1;w<=64;w++) {
  uint64_t mask=UINT64_MAX >> (64-w);
  for (unsigned j=0;j<600;j++) {
   seed^=seed<<13; seed^=seed>>7; seed^=seed<<17;
   uint64_t x=(j==0?0:j==1?mask:j==2?1:j==3?(1ULL<<(w-1)):j==4?(mask>>1):seed)&mask;
   unsigned long long out[34]; unsigned lz=0,lo=0,tz=0,to=0,ones=0;
   for(unsigned k=0;k<w;k++) { unsigned b=(unsigned)((x>>k)&1); ones+=b; if(k==tz && !b) tz++; if(k==to && b) to++; }
   for(unsigned k=0;k<w;k++) { unsigned b=(unsigned)((x>>(w-1-k))&1); if(k==lz && !b) lz++; if(k==lo && b) lo++; }
   unsigned width=w-lz; uint64_t floor=width?1ULL<<(width-1):0;
   uint64_t ceil=x<=1?1:(x==floor?floor:(width<w?floor<<1:0));
   uint64_t vals[]={lz,lo,tz,to,lo==w?0:lo+1,lz==w?0:lz+1,to==w?0:to+1,tz==w?0:tz+1,w-ones,ones,x && !(x&(x-1)),width,floor,ceil,ones,(x+1)&mask,1,1,1,1};
   f[w-1](x,out);
   for(unsigned k=0;k<34;k++) if(out[k]!=(k<20?vals[k]:1)) {fprintf(stderr,"width %u test %u op %u input %llx got %llu expected %llu\n",w,j,k,(unsigned long long)x,out[k],(unsigned long long)(k<20?vals[k]:1));return 1;}
  }
 }
 return 0;
}
''')
        subprocess.run([host, '-std=c11', '-O2', str(harness), *objects, *runtime_link_flags(), '-o', str(exe)],check=True,timeout=90)
        subprocess.run([str(exe)],check=True,timeout=30)
print('stdbit: all 64 unsigned _BitInt widths, 14 operations, result types, side effects and invalid operands; '+('QBE/native model passed' if qbe else 'runtime not run'))
