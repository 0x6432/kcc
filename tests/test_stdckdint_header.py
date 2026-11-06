"""Bounded checked integer macros and runtime helper."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
with tempfile.TemporaryDirectory(prefix='kcc-checked-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text(r'''
#include <stdckdint.h>
#include <stdckdint.h>
#include <stdint.h>
static_assert(_Generic(ckd_add((int *)0,1,2), bool:1, default:0));
int main(void) {
  signed char c; unsigned int u; long long s; unsigned long long z;
  int i=1; int j=0; int vals[2];
  if (!ckd_add(&c,127,1) || c!=-128) return 1;
  if (!ckd_sub(&u,0u,1u) || u!=4294967295u) return 2;
  if (ckd_mul(&s,-3,7u) || s!=-21) return 3;
  if (!ckd_mul(&z,UINT64_MAX,UINT64_MAX) || z!=1) return 4;
  if (ckd_add(&vals[j++],i++,2) || i!=2 || j!=1 || vals[0]!=3) return 5;
  return 42;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert '__kcc_ckd' in result.stdout
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([os.environ.get('HOST_CC', 'cc'), str(asm), str(root / 'build' / 'libkccrt.a'),
                        '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
    for text in ('int f(void){char x; return ckd_add(&x,1,2);}',
                 'int f(void){int x; return ckd_add(&x,1.0,2);}',
                 'int f(void){volatile int x; return ckd_add(&x,1,2);}',
                 'int f(void){_Bool x; return ckd_add(&x,1,2);}'):
        source.write_text('#include <stdckdint.h>\n' + text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and result.stderr, text
print('checked arithmetic header checks completed')
