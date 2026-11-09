"""Baseline bit-precise values and explicit unsupported boundaries."""
import os
import subprocess
import tempfile
from pathlib import Path
from runtime_link import runtime_link_flags

root = Path(__file__).resolve().parents[1]
compiler = root / 'build/kcc'
qbe = os.environ.get('QBE', 'qbe')
host = os.environ.get('HOST_CC', 'cc')
with tempfile.TemporaryDirectory(prefix='bitint-values-', dir=root / 'build') as directory:
    path = Path(directory)
    source, il, asm, exe = [path / n for n in ('input.c', 'out.ssa', 'out.s', 'out')]
    for test in ('bitint_values.c', 'bitint_narrow.c', 'bitint_arbitrary_values.c'):
        result = subprocess.run([str(compiler), str(root / 'tests' / test)], capture_output=True, text=True, timeout=20)
        assert result.returncode == 0 and not result.stderr, (test, result.stderr)
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
        subprocess.run([host, str(asm), str(root / 'build/libkccrt.a'), *runtime_link_flags(), '-o', str(exe)], check=True)
        result = subprocess.run([str(exe)], timeout=5)
        assert result.returncode == 0, (test, result.returncode)
    cases = [
        ('_BitInt(65) x;', 'outside the supported range'),
        ('struct S { unsigned _BitInt(16) x : 2; };', 'bit-field'),
        ('static_assert((_BitInt(8))127 + (_BitInt(8))1);', 'signed overflow'),
        ('static_assert(-(_BitInt(16))-32768);', 'signed overflow'),
        ('static_assert((unsigned _BitInt(8))1 << 8);', 'invalid shift'),
        ('extern _BitInt(8) x; extern signed char x;', 'incompatible'),
        ('extern _BitInt(8) x; extern _BitInt(16) x;', 'incompatible'),
        ('enum E : _BitInt(16) { A };', 'fixed enum underlying type'),
        ('static_assert((_BitInt(8))-128 / (_BitInt(8))-1);', 'signed overflow'),
        ('static_assert((_BitInt(8))1 << 7);', 'signed overflow'),
        ('typedef _BitInt(32) T; enum E : T { A };', 'fixed enum underlying type'),
        ('struct S { _BitInt(32) x : 3; };', 'bit-field'),
        ('static_assert((_BitInt(32))2147483647 + (_BitInt(32))1);', 'signed overflow'),
        ('extern _BitInt(32) x; extern int x;', 'incompatible'),
        ('extern _BitInt(32) x; extern unsigned _BitInt(32) x;', 'incompatible'),
        ('int f(void) { return _Generic(1, _BitInt(32): 1, _BitInt(32): 2, default: 0); }', 'distinct'),
    ]
    # The driver offers no alternate target: do not silently accept one.
    source.write_text('int main(void) { return 0; }\n')
    target = subprocess.run([str(compiler), '--target=aarch64', str(source)], capture_output=True, text=True, timeout=5)
    assert target.returncode != 0 and not target.stdout, target.stderr
    for text, message in cases:
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode != 0 and not result.stdout and message in result.stderr, (text, result.stderr)
print('BitInt value execution and rejection checks passed')
