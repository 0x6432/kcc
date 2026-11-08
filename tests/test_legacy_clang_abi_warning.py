"""Opt-in legacy Clang ABI warnings do not change generated code."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
kcc = Path(os.environ.get('KCC', root / 'build/kcc'))
flag = '--warn-legacy-clang-abi'
warning = 'warning: aggregate with unnamed bit-field may be incompatible with legacy Clang x86-64 ABI'
fixtures = [
    ('direct', 'struct A { float x; unsigned :1; }; struct A f(struct A a) { return a; }\n', True),
    ('nested', 'struct A { float x; unsigned :1; }; struct B { struct A a[2]; }; '
     'struct B f(struct B b) { return b; }\n', True),
    ('union', 'struct A { float x; unsigned :1; }; union B { struct A a; long n; }; '
     'union B f(union B b) { return b; }\n', True),
    ('call', 'struct A { float x; unsigned :1; }; struct A f(struct A); '
     'int g(struct A *p) { struct A a=f(*p); return (int)a.x; }\n', True),
    ('zero-width-integer', 'struct A { int x; unsigned :0; }; struct A f(struct A a) { return a; }\n', False),
    ('named-only', 'struct A { float x; unsigned n:1; }; struct A f(struct A a) { return a; }\n', False),
    ('pointer-only', 'struct A { float x; unsigned :1; }; int f(struct A *p) { return (int)p->x; }\n', False),
    ('unused-prototype', 'struct A { float x; unsigned :1; }; struct A f(struct A); int g(void) { return 0; }\n', False),
    ('execution', 'struct A { float x; unsigned :1; }; struct A f(struct A a) { return a; } '
     'int main(void) { struct A a={42.0f}; return (int)f(a).x; }\n', True),
]

with tempfile.TemporaryDirectory(prefix='kcc-abi-warning-') as tmp:
    d = Path(tmp)
    for name, text, expect_warning in fixtures:
        source = d / f'{name}.c'
        source.write_text(text)
        default = subprocess.run([str(kcc), str(source)], capture_output=True, text=True, timeout=15)
        warned = subprocess.run([str(kcc), flag, str(source)], capture_output=True, text=True, timeout=15)
        assert default.returncode == 0 and not default.stderr, (name, default.stderr)
        assert warned.returncode == 0 and warned.stdout == default.stdout, (name, warned.stderr)
        lines = warned.stderr.splitlines()
        assert all(warning in line for line in lines), (name, lines)
        assert bool(lines) == expect_warning, (name, lines)
        if name == 'execution' and os.environ.get('QBE'):
            il, assembly, exe = d/'test.ssa', d/'test.s', d/'test'
            il.write_text(warned.stdout)
            subprocess.run([os.environ['QBE'], '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
            subprocess.run([os.environ.get('HOST_CC', 'cc'), str(assembly), '-o', str(exe)], check=True, timeout=10)
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=5)
            assert (run.returncode, run.stdout, run.stderr) == (42, '', ''), run
    result = subprocess.run([str(kcc), flag, '--tokens', str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr
    result = subprocess.run([str(kcc), flag, '--pp-tokens', str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr
    source.write_text('struct A { float x; unsigned :0; float y; }; struct A f(struct A a) { return a; }\n')
    result = subprocess.run([str(kcc), flag, str(source)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and not result.stdout and 'aggregate ABI unsupported' in result.stderr
print('legacy Clang ABI warning: direct, nested, union, calls, pointer/prototype controls and unchanged code passed')
