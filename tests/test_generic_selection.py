"""Bounded _Generic selection: compile checks and optional QBE execution."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = Path(os.environ.get("KCC", root / "build" / "kcc"))
qbe = os.environ.get("QBE")
host = os.environ.get("HOST_CC", "cc")
valid = [
    'static_assert(_Generic(1, int: 1, default: 0)); int main(void) { return 42; }',
    'int main(void) { int x=40, y=1; _Generic(x++, int: y, default: x)=42; return x==40 ? y : 1; }',
    'int main(void) { const int x=42; return _Generic(x, int: x, default: 1); }',
    'int main(void) { char a[1]; return _Generic(a, char *: 42, default: 1); }',
    'int f(void) { return 42; } int main(void) { return _Generic(f, int (*)(void): f, default: f)(); }',
    'int main(void) { return _Generic(0L, int: 1, long: _Generic(0, int: 42, default: 1)); }',
    'int main(void) { int x=0; (void)_Generic(1, int: (void)(x=42), default: (void)(x=1)); return x; }',
]
invalid = [
    ('int main(void) { return _Generic(0, int: 1, int: 2); }', 'types must be distinct'),
    ('int main(void) { return _Generic(0, default: 1, default: 2); }', 'duplicate generic default'),
    ('int main(void) { return _Generic(0, long: 1); }', 'no matching association'),
    ('int main(void) { return _Generic(0, void: 1, default: 2); }', 'complete object type'),
    ('int main(void) { return _Generic(0, int: 42, default: undeclared); }', 'undeclared identifier'),
]
with tempfile.TemporaryDirectory(prefix="kcc-generic-") as directory:
    path = Path(directory)
    source, il, asm, exe = [path / n for n in ("input.c", "out.ssa", "out.s", "out")]
    for program in valid:
        source.write_text(program + "\n")
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and not result.stderr, (program, result.stderr)
        if qbe:
            il.write_text(result.stdout)
            subprocess.run([qbe, "-t", "amd64_sysv", "-o", str(asm), str(il)], check=True)
            subprocess.run([host, str(asm), "-o", str(exe)], check=True)
            assert subprocess.run([str(exe)], timeout=5).returncode == 42, program
    for program, message in invalid:
        source.write_text(program + "\n")
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and message in result.stderr, (program, result.stderr)
print("generic selection checks completed")