"""C23 sized-deallocation runtime fallbacks."""
import os
import subprocess
import tempfile
from pathlib import Path
from runtime_link import runtime_link_flags

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
with tempfile.TemporaryDirectory(prefix='kcc-free-sized-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text(r'''
#include <stdlib.h>
int main(void) {
  void *p=malloc(16); void *q=aligned_alloc(16,32);
  if (!p || !q) return 1;
  free_sized(p,16); free_aligned_sized(q,16,32);
  free_sized(nullptr,0); free_aligned_sized(nullptr,0,0);
  return 42;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert 'call $free_sized' in result.stdout and 'call $free_aligned_sized' in result.stdout
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([os.environ.get('HOST_CC', 'cc'), str(asm), str(root / 'build' / 'libkccrt.a'), *runtime_link_flags(),
                        '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
print('sized deallocation checks completed')
