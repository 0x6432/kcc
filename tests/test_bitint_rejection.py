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
        ('struct S { unsigned _BitInt(5) x : 6; };', 'bit-field'),
        ('enum E : _BitInt(5) { A };', 'fixed enum underlying type'),
    ]
    for text, message in cases:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode != 0 and not result.stdout and message in result.stderr, (text, result.stderr)
print('Bit-precise source/ABI rejection passed')
