"""Computed quoted names resolve at the include site, not macro spelling sites."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler, oracle = root/'build'/'kcc', root/'build'/'pp_oracle'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
with tempfile.TemporaryDirectory(prefix='kcc computed includes ') as directory:
    directory = Path(directory)
    app, definitions = directory/'app', directory/'defs'
    app.mkdir()
    definitions.mkdir()
    (app/'sub').mkdir()
    (app/'local.h').write_text('#define ANSWER 42\n')
    (app/'sub'/'name.h').write_text('#define ANSWER 42\n')
    (definitions/'local.h').write_text('#define ANSWER 7\n')  # Wrong anchor must not succeed silently.
    (definitions/'macros.h').write_text(
        '#define TARGET "local.h"\n#define ALIAS TARGET\n#define S(x) #x\n'
        '#define C(a,b) a##b\n#define PASS(x) x\n#define E\n'
        '#define V(...) __VA_OPT__("local.h")\n#define R R\n')
    source, reference = app/'root.c', directory/'reference.c'
    operands = ['TARGET', 'ALIAS', 'S(local.h)', 'S(sub/name.h)', 'C(TAR,GET)',
                'PASS(TARGET)', 'V(1)', '"local.h" E']
    for operand in operands:
        for ending in ('\n', '\r\n', '\r'):
            text = '#include "../defs/macros.h"\n'+f'#include {operand}\nint main(void) {{ return ANSWER; }}\n'
            source.write_bytes(text.replace('\n', ending).encode())
            actual = subprocess.run([str(oracle), '--pp', str(source)], capture_output=True, text=True, timeout=5)
            assert actual.returncode == 0 and not actual.stderr, (operand, actual.stderr)
            expanded = subprocess.run([host, '-std=c2x', '-E', '-P', str(source)], capture_output=True, text=True, timeout=10)
            assert expanded.returncode == 0, expanded.stderr
            reference.write_text(expanded.stdout)
            expected = subprocess.run([str(oracle), '--pp', str(reference)], capture_output=True, text=True, timeout=5)
            assert expected.returncode == 0 and expected.stdout == actual.stdout, operand
            result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
            assert result.returncode == 0 and not result.stderr, result.stderr
            assert 'copy 42' in result.stdout and 'copy 7' not in result.stdout
            if qbe:
                il, assembly, executable = [directory/name for name in ('p.ssa', 'p.s', 'p')]
                il.write_text(result.stdout)
                subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
                subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
                assert subprocess.run([str(executable)], timeout=5).returncode == 42
                subprocess.run([host, '-std=c2x', str(source), '-o', str(executable)], capture_output=True, check=True, timeout=10)
                assert subprocess.run([str(executable)], timeout=5).returncode == 42
    for operand, message in [('E', 'quoted name'), ('V()', 'quoted name'), ('R', 'quoted name'),
                             ('TARGET TARGET', 'exactly one'), ('S(missing.h)', 'root.c:2:10: error: cannot load')]:
        source.write_text('#include "../defs/macros.h"\n'+f'#include {operand}\nint main(void) {{ return 0; }}\n')
        result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    source.write_text('#define BAD(x) ((x)/0)\n#if BAD(1)\n#endif\nint main(void) { return 0; }\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and not result.stdout
    assert 'root.c:2:5: error: division by zero' in result.stderr, result.stderr
print(f'Computed includes passed ({len(operands)*3} host pp agreements; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
