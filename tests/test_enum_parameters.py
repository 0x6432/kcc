"""Bounded enum definitions in outer function parameter specifiers."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
kcc = root / 'build/kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
program = '''typedef int VALUE;
int f(enum E { VALUE=40, NEXT=VALUE+1 } x, enum E y) {
    enum E local=x;
    return VALUE+NEXT-local-y;
}
typedef int X;
int g(typeof(enum Tag { X=1 }) x) { return X+x; }
typedef int Y;
int nested(int (*p)(enum Callback { Y } v)) { return sizeof(Y); }
int main(void) { return f(19,20)==42 && g(1)==2 && nested(0)==4 ? 42 : 1; }
'''
invalid = [
    'int f(enum E { A } A);',
    'int f(int x, enum E { x=1 } y);',
    'int f(enum E { A } x); int y=A;',
    'int f(int (*p)(enum E { A } x)); int outside=A;',
]
with tempfile.TemporaryDirectory(prefix='kcc-enum-params-') as directory:
    directory = Path(directory)
    source, il, asm, exe = [directory / name for name in ('test.c', 'test.ssa', 'test.s', 'test')]
    for text in invalid:
        source.write_text(text + '\n')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 1 and not result.stdout and result.stderr, (text, result.stderr)
    source.write_text(program)
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True, timeout=10)
        subprocess.run([host, str(asm), '-o', str(exe)], check=True, timeout=10)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
print('bounded parameter enum checks complete')
