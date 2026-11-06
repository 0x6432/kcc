"""Bounded x86-64 glibc floating-environment declarations."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
with tempfile.TemporaryDirectory(prefix='kcc-fenv-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text(r'''
#include <fenv.h>
#include <fenv.h>
static_assert(sizeof(fenv_t)==32 && alignof(fenv_t)==4);
static_assert(sizeof(fexcept_t)==2 && alignof(fexcept_t)==2);
static_assert(sizeof(femode_t)==8 && alignof(femode_t)==4);
static_assert(FE_ALL_EXCEPT==61 && FE_TOWARDZERO==3072);
const fenv_t *default_environment=FE_DFL_ENV;
const femode_t *default_mode=FE_DFL_MODE;
int main(void) {
  fenv_t env; fexcept_t flag; femode_t mode;
  if (fegetenv(&env) || fegetmode(&mode)) return 1;
  if (feclearexcept(FE_ALL_EXCEPT) || feraiseexcept(FE_INVALID)) return 2;
  if (!(fetestexcept(FE_INVALID))) return 3;
  if (fegetexceptflag(&flag,FE_ALL_EXCEPT) || !(fetestexceptflag(&flag,FE_INVALID))) return 4;
  if (fesetmode(&mode) || fesetenv(&env)) return 5;
  return 42;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([os.environ.get('HOST_CC', 'cc'), str(asm), '-lm', '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
print('floating environment header checks completed')
