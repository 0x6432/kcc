"""Bounded x86-64 glibc C threads declarations."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
with tempfile.TemporaryDirectory(prefix='kcc-threads-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text(r'''
#include <threads.h>
#include <threads.h>
#include <time.h>
static_assert(sizeof(thrd_t)==8 && sizeof(tss_t)==4);
static_assert(sizeof(once_flag)==4 && sizeof(mtx_t)==40 && alignof(mtx_t)==8);
static_assert(sizeof(cnd_t)==48 && alignof(cnd_t)==8 && TSS_DTOR_ITERATIONS==4);
static once_flag once=ONCE_FLAG_INIT;
static mtx_t lock;
static int total;
void initialize(void) { total=1; }
int worker(void *arg) {
  call_once(&once,initialize);
  if (mtx_lock(&lock)!=thrd_success) return 1;
  total += *(int *)arg;
  if (mtx_unlock(&lock)!=thrd_success) return 2;
  return 7;
}
int main(void) {
  thrd_t thread; int value=41; int result;
  if (mtx_init(&lock,mtx_plain)!=thrd_success) return 1;
  if (thrd_create(&thread,worker,&value)!=thrd_success) return 2;
  if (thrd_join(thread,&result)!=thrd_success) return 3;
  mtx_destroy(&lock);
  return result==7 ? total : 4;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([os.environ.get('HOST_CC', 'cc'), str(asm), '-pthread', '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
print('threads header checks completed')
