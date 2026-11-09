"""Focused runtime and constant arithmetic cases checked by KCC and Clang."""
from pathlib import Path
from runtime_link import runtime_link_flags
import subprocess
import tempfile
from test_bitint_arbitrary import ROOT, KCC, CLANG, compile_clang, compile_kcc, run

SOURCE = (ROOT/'tests/bitint_arbitrary_values.c').read_text()
REJECT = [
    ('_Static_assert((_BitInt(5))15+(_BitInt(5))1);', 'signed overflow'),
    ('_Static_assert(-(_BitInt(33))-4294967296L);', 'signed overflow'),
    ('_Static_assert((unsigned _BitInt(5))1 << 5);', 'invalid shift'),
]

def main():
    with tempfile.TemporaryDirectory(prefix='bitint-arithmetic-', dir=ROOT/'build') as tmp:
        d = Path(tmp)
        for compiler in (compile_kcc, compile_clang):
            obj = compiler(d, SOURCE, 'arithmetic')
            exe = d/'arithmetic'; run([CLANG, obj, ROOT/'build/libkccrt.a', *runtime_link_flags(), '-o', exe]); run([exe])
        for text, expected in REJECT:
            source = d/'reject.c'; source.write_text(text)
            p = subprocess.run([KCC, source], capture_output=True, text=True, timeout=10)
            assert p.returncode and not p.stdout and expected in p.stderr, (text, p.stderr)
    print('Clang/KCC odd-width arithmetic, static initialization, switch and overflow checks passed')

if __name__ == '__main__': main()
