"""Source-level bit-precise use must not silently acquire a standard type/ABI."""
import subprocess
import tempfile
from pathlib import Path

compiler = Path(__file__).resolve().parents[1] / 'build' / 'kcc'
with tempfile.TemporaryDirectory(prefix='kcc-bitint-rejection-') as directory:
    source = Path(directory) / 'input.c'
    cases = [
        ('_BitInt(1) value;\n', 'outside the supported range'),
        ('_BitInt(0) value;\n', 'outside the supported range'),
        ('_BitInt(65) value;\n', 'outside the supported range'),
        ('unsigned _BitInt(65) value;\n', 'outside the supported range'),
        ('extern _BitInt(5) x; extern _BitInt(6) x;', 'incompatible'),
        ('extern _BitInt(5) x; extern signed char x;', 'incompatible'),
        ('_Atomic(_BitInt(5)) value;\n', 'unsupported atomic type'),
        ('struct S { unsigned _BitInt(5) x : 2; };', 'bit-field'),
        ('enum E : _BitInt(5) { A };', 'fixed enum underlying type'),
    ]
    # A supported scalar type is not an atomic ABI promise.
    for width in range(1, 65):
        if width in (8, 16, 32, 64):
            continue
        for sign in (['unsigned '] if width == 1 else ['', 'unsigned ']):
            cases.append((f'_Atomic({sign}_BitInt({width})) x;', 'unsupported atomic type'))
    for text, message in cases:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode != 0 and not result.stdout and message in result.stderr, (text, result.stderr)
print('Bit-precise source/ABI rejection passed')
