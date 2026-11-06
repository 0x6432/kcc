"""Source-level bit-precise use must not silently acquire a standard type/ABI."""
import subprocess
import tempfile
from pathlib import Path

compiler = Path(__file__).resolve().parents[1] / 'build' / 'kcc'
with tempfile.TemporaryDirectory(prefix='kcc-bitint-rejection-') as directory:
    source = Path(directory) / 'input.c'
    cases = [
        ('_BitInt(5) value;\n', '_BitInt is supported only in direct sizeof and alignof type queries'),
        ('unsigned _BitInt(1) value;\n', '_BitInt is supported only in direct sizeof and alignof type queries'),
        ('_BitInt(65) value;\n', '_BitInt is supported only in direct sizeof and alignof type queries'),
        ('_BitInt(3) f(_BitInt(3) x);\n', '_BitInt is supported only in direct sizeof and alignof type queries'),
        ('struct S { _BitInt(8) x; };\n', '_BitInt is supported only in direct sizeof and alignof type queries'),
        ('int main(void) { return 1wb; }\n', 'bit-precise integer literals are not supported yet'),
        ('int main(void) { return 1UWB; }\n', 'bit-precise integer literals are not supported yet'),
        ('#if 0 && 0wb\n#endif\nint main(void) { return 0; }\n', 'bit-precise integer literals are not supported yet'),
        ('#define T _BitInt\nT(8) value;\n', '_BitInt is supported only in direct sizeof and alignof type queries'),
    ]
    for text, message in cases:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode != 0 and not result.stdout and message in result.stderr, (text, result.stderr)
print('Bit-precise source/ABI rejection passed')
