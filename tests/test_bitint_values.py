"""Bounded source-level bit-precise values, and explicit unsupported boundaries."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build/kcc'
qbe = os.environ.get('QBE', 'qbe')
host = os.environ.get('HOST_CC', 'cc')
with tempfile.TemporaryDirectory(prefix='bitint-values-', dir=root / 'build') as directory:
    path = Path(directory)
    source, il, asm, exe = [path / n for n in ('input.c', 'out.ssa', 'out.s', 'out')]
    result = subprocess.run([str(compiler), str(root / 'tests/bitint_values.c')], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and not result.stderr, result.stderr
    il.write_text(result.stdout)
    subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True)
    subprocess.run([host, str(asm), str(root / 'build/libkccrt.a'), '-o', str(exe)], check=True)
    result = subprocess.run([str(exe)], timeout=5)
    assert result.returncode == 0, result.returncode
    cases = [
        ('_BitInt(31) x;', 'only widths 32 and 64'),
        ('unsigned _BitInt(33) x;', 'only widths 32 and 64'),
        ('_BitInt(65) x;', 'outside the supported range'),
        ('_BitInt(32) f(void);', 'function return ABI'),
        ('void f(_BitInt(64) x);', 'parameter ABI'),
        ('typedef _BitInt(32) T; void f(T x);', 'parameter ABI'),
        ('void f(int x, ...); int g(void) { f(1, (_BitInt(32))2); return 0; }', 'variadic ABI'),
        ('_Atomic(_BitInt(32)) x;', 'unsupported atomic type'),
        ('typedef _BitInt(32) T; enum E : T { A };', 'fixed enum underlying type'),
        ('#include <stdarg.h>\nint f(int n, ...) { va_list a; va_start(a); return va_arg(a, _BitInt(32)); }', 'va_arg supports'),
        ('struct S { _BitInt(32) x : 3; };', 'bit-field'),
        ('struct S { _BitInt(32) x; }; struct S f(struct S x) { return x; }', 'aggregate ABI unsupported'),
        ('struct S { _BitInt(64) x[3]; }; struct S f(struct S x) { return x; }', 'aggregate ABI unsupported'),
        ('static_assert((_BitInt(32))2147483647 + (_BitInt(32))1);', 'signed overflow'),
        ('extern _BitInt(32) x; extern int x;', 'incompatible'),
        ('extern _BitInt(32) x; extern unsigned _BitInt(32) x;', 'incompatible'),
        ('int f(void) { return _Generic(1, _BitInt(32): 1, _BitInt(32): 2, default: 0); }', 'distinct'),
    ]
    for text, message in cases:
        source.write_text(text + '\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode != 0 and not result.stdout and message in result.stderr, (text, result.stderr)
print('BitInt 32/64 value execution and rejection checks passed')
