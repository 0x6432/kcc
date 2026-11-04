"""M18 int-range enum execution; originals are also compiled by the host.

Only defined valid programs execute. This is not an exhaustive enum ABI oracle.
"""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build/kcc'))
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')

programs = [
    'enum E { NEG=-2, ZERO=0, N=40, ANSWER=N+2 }; '
    'enum E value=ANSWER; int array[ANSWER]; '
    'int f(enum E x) { switch (x) { case ANSWER: return x; default: return 0; } } '
    'int main(void) { return sizeof(value)==4 && sizeof(array)==168 ? f(value) : 1; }',
    'enum { OUTER=40 }; int main(void) { enum { A=OUTER, B, C=B+1 }; '
    '_Static_assert(C==42,"constant"); enum { VALUE=C } x=VALUE; '
    '{ enum { OUTER=1 }; if(OUTER!=1) return 1; } return x; }',
    'enum E { LOW=-10, HIGH=42 }; int main(void) { enum E x=LOW; '
    'const enum E *p=&x; x=HIGH; return *p; }',
]

with tempfile.TemporaryDirectory(prefix='kcc-enums-') as directory:
    directory = Path(directory)
    source, il, assembly, executable = [directory / name for name in ('test.c', 'test.ssa', 'test.s', 'test')]
    for text in programs:
        source.write_text(text + '\n')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0 and not result.stderr, (text, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
            assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
        subprocess.run([host, '-std=c2x', '-pedantic-errors', str(source), '-o', str(executable)],
                       capture_output=True, text=True, check=True, timeout=10)
        assert subprocess.run([str(executable)], timeout=5).returncode == 42, text
print('ordinary enum runtime fixtures passed')
