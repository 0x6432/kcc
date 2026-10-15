"""Explicit include search, direct-header macro boundaries and bounded CLI options."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compiler, oracle = root/'build'/'kcc', root/'build'/'pp_oracle'
host = os.environ.get('HOST_CC', 'cc')
qbe = os.environ.get('QBE')
agreements = 0


def run(tool, arguments, cwd=None):
    return subprocess.run([str(tool), *map(str, arguments)], cwd=cwd,
                          capture_output=True, text=True, timeout=10)


with tempfile.TemporaryDirectory(prefix='kcc include search ') as temporary:
    base = Path(temporary)
    app, first, second = [base/name for name in ('app', 'first headers', 'second')]
    for path in (app, first, second):
        path.mkdir()
    (app/'local.h').write_text('#define VALUE 11\n')
    (first/'local.h').write_text('#define VALUE 42\n')
    (second/'local.h').write_text('#define VALUE 7\n')
    (second/'fallback.h').write_text('#include "nested.h"\n')
    (second/'nested.h').write_text('#define VALUE 42\n')
    (first/'__VA_ARGS__').write_text('#define VALUE 42\n')
    (first/'space name.h').write_text('#define VALUE 42\n')
    (first/'sub').mkdir()
    (first/'sub'/'n-1+.h').write_text('#define VALUE 42\n')
    source, reference = app/'root.c', base/'reference.c'
    cases = [
        ('#include "local.h"', [first, second], 11),
        ('#include <local.h>', [first, second], 42),
        ('#include <local.h>', [second, first], 7),
        ('#include "fallback.h"', [first, second], 42),
        ('#include <fallback.h>', [first, second], 42),
        ('#define local wrong\n#include <local.h>', [first], 42),
        ('#include <__VA_ARGS__>', [first], 42),
        ('#define H <local.h>\n#include H', [first], 42),
        ('#define A(x) <x>\n#include A(local.h)', [first], 42),
        ('#define Q "fallback.h"\n#include Q', [second], 42),
        ('#include "space name.h"', [first], 42),
        ('#include <sub/n-1+.h>', [first], 42),
        (f'#include "{first}/local.h"', [second], 42),
    ]
    for directive, directories, value in cases:
        options = [piece for i, path in enumerate(directories)
                   for piece in (['-I', str(path)] if i % 2 == 0 else ['-I'+str(path)])]
        for ending in ('\n', '\r\n', '\r'):
            source.write_bytes((directive+'\nint main(void) { return VALUE; }\n').replace('\n', ending).encode())
            actual = run(oracle, ['--pp', *options, source])
            assert actual.returncode == 0 and not actual.stderr, (directive, actual.stderr)
            expanded = run(host, ['-std=c2x', '-E', '-P', *options, source])
            assert expanded.returncode == 0, expanded.stderr
            reference.write_text(expanded.stdout)
            expected = run(oracle, ['--pp', reference])
            assert expected.returncode == 0 and expected.stdout == actual.stdout, directive
            result = run(compiler, [*options, source])
            assert result.returncode == 0 and not result.stderr, result.stderr
            assert f'copy {value}' in result.stdout
            assert run(compiler, [source, '--tokens', *options]).returncode == 0
            assert run(compiler, [*options, '--pp-tokens', source]).returncode == 0
            agreements += 1
            if qbe:
                il, assembly, executable = [base/name for name in ('p.ssa', 'p.s', 'p')]
                il.write_text(result.stdout)
                subprocess.run([qbe, '-t', 'amd64_sysv', '-o', str(assembly), str(il)], check=True, timeout=10)
                subprocess.run([host, str(assembly), '-o', str(executable)], check=True, timeout=10)
                assert subprocess.run([str(executable)], timeout=5).returncode == value
                subprocess.run([host, '-std=c2x', *options, str(source), '-o', str(executable)],
                               capture_output=True, check=True, timeout=10)
                assert subprocess.run([str(executable)], timeout=5).returncode == value
    # Absolute angle names work without -I (use a path without spaces).
    with tempfile.TemporaryDirectory(prefix='kcc-angle-') as absolute_directory:
        absolute = Path(absolute_directory)/'absolute.h'
        absolute.write_text('#define VALUE 42\n')
        source.write_text(f'#include <{absolute}>\nint main(void) {{ return VALUE; }}\n')
        assert run(compiler, [source]).returncode == 0
    # Empty directory explicitly means cwd. No implicit cwd search for angles.
    source.write_text('#include <local.h>\nint main(void) { return VALUE; }\n')
    assert run(compiler, ['-I', '', source], app).returncode == 0
    result = run(compiler, [source], app)
    assert result.returncode == 1 and 'cannot load angle include' in result.stderr
    # Exactly 32 configured dirs; a 33rd fails even in raw token mode.
    assert run(compiler, ['-I'+str(first)]*32+[source]).returncode == 0
    for mode in ([], ['--tokens'], ['--pp-tokens']):
        result = run(compiler, [*mode, *(['-I'+str(first)]*33), source])
        assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr
    for args in (['-I'], ['-I', str(first)], [source, source], ['--tokens', '--pp-tokens', source],
                 ['--help', source], ['--version', '-I'+str(first)], ['--bad', source]):
        result = run(compiler, args)
        assert result.returncode == 1 and not result.stdout and 'error:' in result.stderr
    for operand, message in [('<>', 'nonempty'), ('< local.h>', 'whitespace'),
                             ('<local.h >', 'whitespace'), ('<local/**/.h>', 'whitespace'),
                             ('<local.h', "expected '>'"), ('<local.h> extra', 'exactly one'),
                             ('<a@b>', 'unsupported byte'), ('<stdio.h>', 'cannot load angle'),
                             (f'<{first}/local.h>', 'whitespace')]:
        source.write_text(f'#include {operand}\nint main(void) {{ return 0; }}\n')
        result = run(compiler, ['-I'+str(first), source])
        assert result.returncode == 1 and not result.stdout and message in result.stderr, result.stderr
    # Isolated rejection must preserve the next #endif, and child diagnostics retain paths.
    source.write_text('#if 1\n#include <local.h> extra\n#endif\nint\n')
    result = run(compiler, ['--tokens', '-I'+str(first), source])
    assert result.returncode == 1 and result.stderr.count('error:') == 1
    assert ':int\n' in result.stdout and 'unterminated' not in result.stderr
    (first/'bad.h').write_bytes(b'#error search child\\\r\n problem\r\n')
    source.write_text('#include <bad.h>\nint main(void) { return 0; }\n')
    result = run(compiler, ['-I'+str(first), source])
    assert result.returncode == 1 and not result.stdout and 'bad.h:1:2: error:' in result.stderr
    # A too-long candidate stops instead of trying a later directory.
    source.write_text('#include <local.h>\nint main(void) { return VALUE; }\n')
    result = run(compiler, ['-I'+'a'*4095, '-I'+str(first), source])
    assert result.returncode == 1 and 'path limit exceeded' in result.stderr and not result.stdout
print(f'Include search passed ({agreements} host pp agreements; {host})'
      + ('; QBE/runtime passed' if qbe else ''))
