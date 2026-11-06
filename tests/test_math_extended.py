"""Extended real math declarations and generic dispatch."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
with tempfile.TemporaryDirectory(prefix='kcc-math-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text(r'''
#include <tgmath.h>
#include <stdlib.h>
#include <float.h>
static_assert(_Generic(fma(1.0f,2.0f,3.0f),float:1,default:0));
static_assert(_Generic(fma(1.0f,2,3.0f),double:1,default:0));
static_assert(_Generic(hypot(1.0f,2.0f),float:1,default:0));
static_assert(_Generic(hypot(1.0f,2.0),double:1,default:0));
int main(void) {
  float x=2.0f;
  float tiny=FLT_TRUE_MIN;
  double double_tiny=DBL_TRUE_MIN;
  if (!issubnormal(double_tiny)) return 6;
  if (fpclassify(tiny)!=FP_SUBNORMAL || !issubnormal(tiny) || !isnormal(x)) return 4;
  if (!iszero(0.0f) || issignaling(x)) return 5;
  if (fma(x++,3.0f,1.0f)!=7.0f || x!=3.0f) return 1;
  if (hypot(3.0,4.0)!=5.0 || exp2(3)!=8.0) return 2;
  if (fmax(1.0f,2.0f)!=2.0f || copysign(3.0,-1.0)!=-3.0) return 3;
  return 42;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    for name in ('fmaf', 'hypot', 'exp2', 'fmaxf', 'copysign'):
        assert 'call $' + name in result.stdout, name
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([os.environ.get('HOST_CC', 'cc'), str(asm), '-lm', '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
print('extended math checks completed')
