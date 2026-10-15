"""Raw diagnostic directives: severity, driver modes and QBE execution."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler = root / 'build' / 'kcc'
qbe = os.environ.get('QBE')
host = os.environ.get('HOST_CC', 'cc')

with tempfile.TemporaryDirectory(prefix='kcc-diagnostics-') as directory:
    directory = Path(directory)
    source = directory / 'input.c'
    for ending in ('\n', '\r\n', '\r'):
        for marker in ('#', '%:'):
            for body in ('', ' X+12u /**/ .5 "raw"', ' ++++++++', ' hello\\\nworld'):
                for directive in ('warning', 'error'):
                    text = (f'#define X expanded\n{marker}{directive}{body}\n'
                            'int main(void) { return 42; }\n')
                    source.write_bytes(text.replace('\n', ending).encode())
                    expected = '#'+directive+':'
                    for mode in ([], ['--tokens'], ['--pp-tokens']):
                        result = subprocess.run([str(compiler), *mode, str(source)],
                                                capture_output=True, text=True, timeout=5)
                        if mode == ['--pp-tokens']:
                            assert result.returncode == 0 and not result.stderr, result.stderr
                            continue  # Raw lexer mode does not execute directives.
                        assert result.returncode == (directive == 'error'), result.stderr
                        assert result.stderr.count(f': {directive}: ') == 1, result.stderr
                        assert expected in result.stderr
                        assert 'expanded' not in result.stderr
                        if body.startswith(' X'):
                            assert 'X+12u .5 "raw"' in result.stderr, result.stderr
                        if not mode and directive == 'error':
                            assert not result.stdout
                    reference = subprocess.run([host, '-std=c2x', '-E', str(source)],
                                               capture_output=True, text=True, timeout=10)
                    assert (reference.returncode != 0) == (directive == 'error'), reference.stderr
                    if directive == 'warning' and qbe:
                        result = subprocess.run([str(compiler), str(source)],
                                                capture_output=True, text=True, timeout=5)
                        il = directory / 'program.ssa'
                        assembly = directory / 'program.s'
                        executable = directory / 'program'
                        il.write_text(result.stdout)
                        subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)],
                                       check=True, timeout=10)
                        subprocess.run([host, str(assembly), '-o', str(executable)],
                                       check=True, timeout=10)
                        assert subprocess.run([str(executable)], timeout=5).returncode == 42
    source.write_text('#warning first\n#error second\nint main(void) { return 0; }\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and not result.stdout
    assert result.stderr.count(': warning:') == 1 and ': error: #error: second' in result.stderr
    # Many adjoining tokens must not overflow the temporary diagnostic buffer.
    source.write_text('#warning ' + '+' * 10000 + '\nint main(void) { return 0; }\n')
    result = subprocess.run([str(compiler), str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and ': warning:' in result.stderr
print('Diagnostic directives passed in all driver modes' + ('; QBE/runtime passed' if qbe else ''))
