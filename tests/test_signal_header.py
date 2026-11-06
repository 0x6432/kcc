"""Bounded signal.h for the Linux x86-64 target."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get('KCC', root / 'build' / 'kcc'))
qbe = os.environ.get('QBE')
with tempfile.TemporaryDirectory(prefix='kcc-signal-') as directory:
    path = Path(directory)
    source = path / 'test.c'
    source.write_text(r'''
#include <signal.h>
#include <signal.h>
#include <stdint.h>
static_assert(sizeof(sig_atomic_t)==4 && SIG_ATOMIC_MIN == (-2147483647-1));
static_assert(SIG_ATOMIC_MAX == 2147483647);
void (*initial_ignore)(int) = SIG_IGN;
void (*initial_error)(int) = SIG_ERR;
volatile sig_atomic_t received;
void handler(int signum) { received=signum; }
int main(void) {
  __kcc_sighandler_t previous=signal(SIGINT,initial_ignore);
  if (initial_error!=SIG_ERR) return 4;
  if (previous==SIG_ERR) return 1;
  if (raise(SIGINT)!=0) return 2;
  if (signal(SIGINT,handler)==SIG_ERR || raise(SIGINT)!=0 || received!=SIGINT) return 3;
  if (signal(SIGINT,previous)==SIG_ERR) return 5;
  return 42;
}
''')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il, asm, exe = (path / n for n in ('test.ssa', 'test.s', 'test'))
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([os.environ.get('HOST_CC', 'cc'), str(asm), str(root / 'build' / 'libkccrt.a'),
                        '-o', str(exe)], check=True)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
print('signal header checks completed')
