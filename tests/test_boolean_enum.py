"""Fixed bool enum: bounded range and scalar conversions, optionally execute QBE."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
kcc = root / 'build/kcc'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
program = '''enum Flag : bool;
enum Flag : _Bool { OFF=0, ON=1 };
_Static_assert(sizeof(ON)==1 && (enum Flag)9==1 && (enum Flag)0==0, "enum conversion");
enum Flag global=42;
enum Flag floating=0.5;
enum Flag identity(enum Flag x) { return x; }
int main(void) {
    enum Flag x=2;
    if (global!=1 || floating!=1 || x!=1) return 1;
    x=0; x++; x++;
    if (x!=1 || identity(3)!=1) return 2;
    x=0.5;
    if (x!=1) return 3;
    x=0;
    return x==0 && ON==1 && OFF==0 ? 42 : 4;
}'''
invalid = [
    'enum Flag : bool { BAD=2 };',
    'enum Flag : bool { BAD=-1 };',
    'enum Flag : bool { ONE=1, OVER };',
]
with tempfile.TemporaryDirectory(prefix='kcc-bool-enum-') as directory:
    directory = Path(directory)
    source, il, asm, exe = [directory / name for name in ('test.c', 'test.ssa', 'test.s', 'test')]
    for text in invalid:
        source.write_text(text + '\n')
        result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 1 and not result.stdout and 'range' in result.stderr, (text, result.stderr)
    source.write_text(program + '\n')
    result = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result.stderr
    if qbe:
        il.write_text(result.stdout)
        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(asm), str(il)], check=True, timeout=10)
        subprocess.run([host, str(asm), '-o', str(exe)], check=True, timeout=10)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
    probe = subprocess.run([host, '-std=c2x', '-pedantic-errors', '-x', 'c', '-fsyntax-only', '-'],
                           input='enum E : _Bool { X=1 };\n', capture_output=True, text=True, timeout=10)
    if probe.returncode == 0:
        subprocess.run([host, '-std=c2x', '-pedantic-errors', str(source), '-o', str(exe)],
                       capture_output=True, text=True, check=True, timeout=10)
        assert subprocess.run([str(exe)], timeout=5).returncode == 42
print('fixed boolean enum checks complete')
