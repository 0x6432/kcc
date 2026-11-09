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
        ('struct S { _BitInt(5) x; }; struct S f(struct S x) { return x; }', 'aggregate'),
        ('struct S { unsigned _BitInt(5) x : 2; };', 'bit-field'),
        ('void f(int, ...); void g(void) { f(0, (_BitInt(5))1); }', 'variadic arguments'),
        ('#include <stdarg.h>\nint f(int x, ...) { va_list ap; va_start(ap,x); return va_arg(ap,_BitInt(5)); }', 'va_arg'),
        ('enum E : _BitInt(5) { A };', 'fixed enum underlying type'),
    ]
    # A supported scalar type is not an atomic or aggregate ABI promise.
    for width in range(1, 65):
        if width in (8, 16, 32, 64):
            continue
        for sign in (['unsigned '] if width == 1 else ['', 'unsigned ']):
            cases.append((f'_Atomic({sign}_BitInt({width})) x;', 'unsupported atomic type'))
    cases += [
        ('struct A { unsigned _BitInt(33) x[3]; }; struct B { struct A a; }; struct B f(struct B x){return x;}', 'aggregate'),
        ('struct A { _BitInt(17) x; }; struct A f(struct A); int g(void) { struct A a={1}; f(a); return 0; }', 'aggregate'),
        ('void f(int, ...); void g(void) { f(0, (unsigned _BitInt(63))1); }', 'variadic arguments'),
    ]
    for text, message in cases:
        source.write_text(text)
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode != 0 and not result.stdout and message in result.stderr, (text, result.stderr)
print('Bit-precise source/ABI rejection passed')
