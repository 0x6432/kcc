"""Fixed bool enum: bounded range and scalar conversions, optionally execute QBE."""
import hashlib
import os
import re
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
        native = subprocess.run([host, '-std=c2x', '-pedantic-errors', str(source), '-o', str(exe)],
                                capture_output=True, text=True, timeout=10)
        assert native.returncode == 0, (native.stdout, native.stderr)
        execution = subprocess.run([str(exe)], capture_output=True, text=True, timeout=5)
        if execution.returncode != 42:
            # Clang 18.1.8 is observed to truncate integer conversions to
            # this bool-based enum. Accept only this exact fixture, compiler
            # release, diagnostics, and result as a host discrepancy, never
            # as a native runtime agreement. Any other failure remains fatal.
            version = subprocess.run([host, '--version'], capture_output=True, text=True, timeout=10)
            warnings = re.findall(r'warning: ([^\n]+)', native.stderr)
            expected = [
                "implicit conversion from 'int' to 'enum Flag' changes value from 42 to 0 [-Wconstant-conversion]",
                "implicit conversion from 'int' to 'enum Flag' changes value from 2 to 0 [-Wconstant-conversion]",
                "implicit conversion from 'int' to 'enum Flag' changes value from 3 to 1 [-Wconstant-conversion]",
            ]
            assert (hashlib.sha256(source.read_bytes()).hexdigest() ==
                    'dd4f6ae4a8b81f92dfb5a11f403ec2b1c965bd0e2160834e628118dde79aaaa5'
                    and version.returncode == 0 and re.search(r'clang version 18\.1\.\d+\b', version.stdout)
                    and not native.stdout and warnings == expected and 'error:' not in native.stderr
                    and execution.returncode == 1 and not execution.stdout and not execution.stderr), (
                        'unexpected native boolean enum result', version.stdout, native.stderr,
                        execution.returncode, execution.stdout, execution.stderr)
            print('boolean enum: Clang 18.1 host discrepancy (NOT a native runtime agreement)')
        else:
            assert not execution.stdout and not execution.stderr, (execution.stdout, execution.stderr)
            print('boolean enum: native runtime agreement')
    else:
        print('boolean enum: host syntax unavailable (NOT a native runtime agreement)')
print('fixed boolean enum checks complete')
