"""LP64 explicit integer-pointer representation conversions."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
with tempfile.TemporaryDirectory(prefix='kcc-int-pointer-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text(r'''
#include <stdint.h>
void *absolute=(void *)(signed char)-1;
void *values[]={(void *)1,(void *)(short)-2,0};
void *from_signed(int n) { return (void *)n; }
void *from_unsigned(unsigned int n) { return (void *)n; }
unsigned char low(void *p) { return (unsigned char)p; }
int main(void) {
  int x=42; uintptr_t raw=(uintptr_t)&x;
  int *p=(int *)raw;
  if (p!=&x || *p!=42) return 1;
  if ((uintptr_t)from_signed(-1)!=~(uintptr_t)0) return 2;
  if ((uintptr_t)from_unsigned(0xffffffffU)!=0xffffffffUL) return 3;
  if (low((void *)0x1234UL)!=0x34) return 4;
  if ((uintptr_t)absolute != ~(uintptr_t)0 || (uintptr_t)values[0]!=1 ||
      (uintptr_t)values[1] != ~(uintptr_t)1 || values[2]) return 5;
  return 42;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([os.environ.get('HOST_CC', 'cc'), str(asm), '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
    for text in ('int f(void){ int *p=1; return 0; }',
                 'double f(void *p){return (double)p;}'):
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and result.stderr, text
print('integer-pointer cast checks completed')
