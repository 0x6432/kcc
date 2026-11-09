"""Target libc numeric headers: signatures, ABI and classification dispatch."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

body = r'''
#include <math.h>
#include <float.h>
#include <errno.h>
#include <string.h>
#include <wchar.h>
_Static_assert(sizeof(div_t)==8 && _Alignof(div_t)==4, "div layout");
_Static_assert(sizeof(ldiv_t)==16 && offsetof(ldiv_t,rem)==8, "ldiv layout");
_Static_assert(sizeof(lldiv_t)==16 && offsetof(lldiv_t,rem)==8, "lldiv layout");
_Static_assert(sizeof(imaxdiv_t)==16 && offsetof(imaxdiv_t,rem)==8, "imaxdiv layout");
_Static_assert(_Generic(&div,div_t (*)(int,int):1,default:0), "div signature");
_Static_assert(_Generic(&ldiv,ldiv_t (*)(long,long):1,default:0), "ldiv signature");
_Static_assert(_Generic(&lldiv,lldiv_t (*)(long long,long long):1,default:0), "lldiv signature");
_Static_assert(_Generic(&imaxdiv,imaxdiv_t (*)(intmax_t,intmax_t):1,default:0), "imaxdiv signature");
_Static_assert(_Generic(&atof,double (*)(const char *):1,default:0), "atof signature");
int main(void) {
  div_t (*dptr)(int,int)=div;
  div_t a=dptr(-43,5); div_t b=div(43,-5); div_t c=div(-43,-5);
  if (a.quot!=-8 || a.rem!=-3 || b.quot!=-8 || b.rem!=3 || c.quot!=8 || c.rem!=-3) return 1;
  ldiv_t l=ldiv(-5000000001L,3L);
  lldiv_t ll=lldiv(5000000001LL,-3LL);
  imaxdiv_t im=imaxdiv(-5000000001L,3L);
  if (l.quot!=-1666666667L || l.rem!=0 || ll.quot!=-1666666667LL || ll.rem!=0 || im.quot!=l.quot || im.rem!=l.rem) return 2;
  l=ldiv(-5000000002L,3); ll=lldiv(5000000002LL,-3); im=imaxdiv(-5000000002L,3);
  if (l.quot!=-1666666667L || l.rem!=-1 || ll.quot!=-1666666667LL || ll.rem!=1 || im.rem!=-1) return 3;
  if (atof("-12.5tail")!=-12.5) return 4;
  char *end=0; wchar_t *wend=0;
  if (strtoimax("-987x",&end,10)!=-987 || *end!='x') return 5;
  if (strtoumax("ff!",&end,16)!=255 || *end!='!') return 6;
  if (wcstoimax(L"-123z",&wend,10)!=-123 || *wend!=L'z') return 7;
  if (wcstoumax(L"77z",&wend,8)!=63 || *wend!=L'z') return 8;
  char buf[32];
  if (strfromd(buf,32,"%.1f",12.5)!=4 || strcmp(buf,"12.5")) return 9;
  float f=FLT_TRUE_MIN, z=-0.0f; double g=DBL_TRUE_MIN;
  if (!isfinite(f++) || f!=1.0f || !isfinite(g) || !isfinite(42)) return 10;
  if (!signbit(z) || signbit(0.0f) || !signbit(-0.0) || signbit(0)) return 11;
  if (!isinf(INFINITY) || !isinf((double)INFINITY) || isinf(3)) return 12;
  if (!isnan(NAN) || !isnan((double)NAN) || isnan(3)) return 13;
  return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='kcc-hosted-numeric-') as directory:
    path = Path(directory)
    for i, headers in enumerate(('#include <stdlib.h>\n#include <inttypes.h>\n',
                                  '#include <inttypes.h>\n#include <stdlib.h>\n')):
        source = path / 'test.c'
        source.write_text(headers + body)
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0 and not result.stderr, result.stderr
        for symbol in ('div', 'ldiv', 'lldiv', 'imaxdiv', 'atof', '__finitef', '__finite',
                       '__isinff', '__isinf', '__isnanf', '__isnan', '__signbitf', '__signbit'):
            assert '$' + symbol in result.stdout, symbol
        if qbe:
            il, asm, exe = (path / n for n in ('out.ssa', 'out.s', 'out'))
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True, timeout=30)
            subprocess.run([host, str(asm), '-lm', '-o', str(exe)], check=True, timeout=30)
            result = subprocess.run([str(exe)], timeout=10)
            assert result.returncode == 0, ('runtime', i, result.returncode)
    # Invalid operands must not be silently coerced by the generic default.
    for macro in ('isfinite', 'isinf', 'isnan', 'signbit'):
        source.write_text('#include <math.h>\nint f(void *p) { return ' + macro + '(p); }\n')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=30)
        assert result.returncode != 0, macro
print('hosted numeric headers: signature, dispatch and runtime checks completed')
