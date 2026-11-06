"""C23 explicit-memory-erasure runtime fallback."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
with tempfile.TemporaryDirectory(prefix='kcc-explicit-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text(r'''
#include <string.h>
int main(void) {
  unsigned char data[4]={1,2,3,4};
  if (memset_explicit(data,0x1a5,3)!=data) return 1;
  if (data[0]!=0xa5 || data[1]!=0xa5 || data[2]!=0xa5 || data[3]!=4) return 2;
  if (memset_explicit(data,0,0)!=data || data[0]!=0xa5) return 3;
  return 42;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert 'call $memset_explicit' in result.stdout
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([os.environ.get('HOST_CC', 'cc'), str(asm), str(root / 'build' / 'libkccrt.a'),
                        '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
print('memset_explicit checks completed')
